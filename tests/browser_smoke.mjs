#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const cli = path.join(root, "skills", "xiumi-native-clipboard", "scripts", "xiumi_clipboard.py");
const documentPath = path.resolve(process.argv[2] || path.join(root, "examples", "demo.xiumi.json"));
const COMPS_MIME = "application/xiumi-comps; category=paper.comp";
const LABEL_MIME = "application/xiumi-label; origin=studio";

function fail(message) { throw new Error(message); }
function onceLine(stream, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => reject(new Error("timed out waiting for process output")), timeoutMs);
    stream.setEncoding("utf8");
    stream.on("data", chunk => {
      buffer += chunk;
      const newline = buffer.indexOf("\n");
      if (newline >= 0) { clearTimeout(timer); resolve(buffer.slice(0, newline).trim()); }
    });
    stream.once("error", error => { clearTimeout(timer); reject(error); });
  });
}
function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(error => error ? reject(error) : resolve(port));
    });
  });
}
function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "/opt/google/chrome/chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  for (const candidate of candidates) if (existsSync(candidate)) return candidate;
  for (const name of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    const result = spawnSync("which", [name], { encoding: "utf8" });
    if (result.status === 0 && result.stdout.trim()) return result.stdout.trim();
  }
  fail("Chrome/Chromium executable was not found; set CHROME_PATH");
}
function countDocument(document) {
  const format = document.clipboard.formats.find(entry => entry.mime === COMPS_MIME);
  if (!format) fail(`missing ${COMPS_MIME}`);
  let components = 0;
  let images = 0;
  const visit = value => {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!value || typeof value !== "object") return;
    if (value._comp) components += 1;
    if (value.type === "image") images += 1;
    Object.values(value).forEach(visit);
  };
  visit(format.data.slices);
  return { title: document.meta.title, slices: format.data.slices.length, components, images };
}
async function devtoolsPage(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let lastTargets = [];
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      lastTargets = targets;
      const page = targets.find(target => target.type === "page");
      if (page) return page;
    } catch (_) {}
    await delay(100);
  }
  fail(`Chrome DevTools page target did not become ready; targets=${JSON.stringify(lastTargets)}`);
}
function connectCDP(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let nextId = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const task = pending.get(message.id);
    pending.delete(message.id);
    message.error ? task.reject(new Error(JSON.stringify(message.error))) : task.resolve(message.result);
  };
  const ready = new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = event => reject(new Error(event.message || "WebSocket connection failed"));
  });
  return {
    ready,
    send(method, params = {}) {
      const id = ++nextId;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    },
    close() { socket.close(); },
  };
}
async function stop(child) {
  if (!child || child.exitCode !== null) return;
  child.kill("SIGTERM");
  await Promise.race([new Promise(resolve => child.once("exit", resolve)), delay(3000)]);
  if (child.exitCode === null) child.kill("SIGKILL");
}

const document = JSON.parse(await readFile(documentPath, "utf8"));
const expected = countDocument(document);
const server = spawn("python3", [cli, "serve", documentPath], { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
let chrome;
let profile;
let cdp;
let chromeStderr = "";
try {
  const url = await onceLine(server.stdout);
  if (!url.startsWith("http://127.0.0.1:")) fail(`unexpected preview URL: ${url}`);
  const port = await freePort();
  profile = await mkdtemp(path.join(os.tmpdir(), "xiumi-browser-"));
  const headed = process.env.BROWSER_SMOKE_HEADED === "1";
  chrome = spawn(findChrome(), [
    headed ? "--ozone-platform=x11" : "--headless=new",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-gpu",
    "--window-position=-2000,-2000",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    url,
  ], { stdio: ["ignore", "ignore", "pipe"] });
  chrome.stderr.setEncoding("utf8");
  chrome.stderr.on("data", chunk => { chromeStderr = (chromeStderr + chunk).slice(-8000); });
  let page;
  try {
    page = await devtoolsPage(port);
  } catch (error) {
    fail(`${error.message}\nChrome stderr:\n${chromeStderr}`);
  }
  cdp = connectCDP(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send("Runtime.enable");
  await cdp.send("Page.enable");
  await cdp.send("Page.navigate", { url });
  await delay(300);
  await cdp.send("Page.bringToFront");
  await cdp.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  const expectedJSON = JSON.stringify(expected);
  await cdp.send("Runtime.evaluate", {
    userGesture: true,
    awaitPromise: true,
    returnByValue: true,
    expression: `(async()=>{
      const expected=${expectedJSON};
      for(let i=0;i<600 && (!document.getElementById("sliceCount")||document.getElementById("sliceCount").textContent!==String(expected.slices));i++) await new Promise(r=>setTimeout(r,50));
      const images=[...document.querySelectorAll("#paper img")];
      await Promise.all(images.map(image=>image.complete?Promise.resolve():new Promise(resolve=>{image.addEventListener("load",resolve,{once:true});image.addEventListener("error",resolve,{once:true});})));
      window.__copyProbe=null;
      window.__smokeStats={
        title:document.getElementById("documentTitle").textContent,
        slices:Number(document.getElementById("sliceCount").textContent),
        components:Number(document.getElementById("componentCount").textContent),
        imageStat:Number(document.getElementById("imageCount").textContent),
        imageDom:images.length,
        imageDecoded:images.filter(image=>image.complete&&image.naturalWidth>0).length
      };
      document.addEventListener("copy",event=>{window.__copyProbe={trusted:event.isTrusted,types:[...event.clipboardData.types]}},{once:true});
      document.body.tabIndex=-1;
      document.body.focus();
      const range=document.createRange();
      range.selectNodeContents(document.getElementById("documentTitle"));
      const selection=getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      return window.__smokeStats;
    })()`,
  });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await cdp.send("Page.bringToFront");
    await cdp.send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Control", code: "ControlLeft", windowsVirtualKeyCode: 17, nativeVirtualKeyCode: 37, modifiers: 2 });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "c", code: "KeyC", windowsVirtualKeyCode: 67, nativeVirtualKeyCode: 54, modifiers: 2, commands: ["Copy"] });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "c", code: "KeyC", windowsVirtualKeyCode: 67, nativeVirtualKeyCode: 54, modifiers: 2 });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Control", code: "ControlLeft", windowsVirtualKeyCode: 17, nativeVirtualKeyCode: 37, modifiers: 0 });
    await delay(120);
    const probe = await cdp.send("Runtime.evaluate", { returnByValue: true, expression: "window.__copyProbe" });
    if (probe.result.value) break;
  }
  const evaluation = await cdp.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `({copyProbe:window.__copyProbe,status:document.getElementById("status").textContent,...window.__smokeStats})`,
  });
  const actual = evaluation.result.value;
  if (!actual.copyProbe?.trusted) fail(`expected a trusted copy event, got ${JSON.stringify(actual.copyProbe)}`);
  for (const mime of [COMPS_MIME, LABEL_MIME, "text/plain"]) if (!actual.copyProbe.types.includes(mime)) fail(`copy event is missing ${mime}`);
  for (const key of ["title", "slices", "components"]) if (actual[key] !== expected[key]) fail(`${key}: expected ${expected[key]}, got ${actual[key]}`);
  for (const key of ["imageStat", "imageDom", "imageDecoded"]) if (actual[key] !== expected.images) fail(`${key}: expected ${expected.images}, got ${actual[key]}`);
  if (!actual.status.includes("已写入 Chromium 原生剪切板")) fail(`unexpected status: ${actual.status}`);
  console.log(JSON.stringify({ ok: true, url, expected, actual }, null, 2));
} finally {
  if (cdp) cdp.close();
  await stop(chrome);
  await stop(server);
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 8, retryDelay: 150 });
}
