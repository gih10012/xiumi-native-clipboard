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
  let embedded = 0;
  let remote = 0;
  const visit = value => {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!value || typeof value !== "object") return;
    if (value._comp) components += 1;
    if (value.type === "image") {
      images += 1;
      if (typeof value.src === "string" && value.src.startsWith("data:image/")) {
        embedded += 1;
      } else if (typeof value.src === "string" && /^(?:https?:)?\/\//.test(value.src)) remote += 1;
    }
    Object.values(value).forEach(visit);
  };
  visit(format.data.slices);
  return { title: document.meta.title, slices: format.data.slices.length, components, images, embedded, remote };
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
async function trustedCopy(cdp) {
  await cdp.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(()=>{
      window.__copyProbe=null;
      document.addEventListener("copy",event=>{
        const html=event.clipboardData.getData("text/html");
        const template=document.createElement("template");
        template.innerHTML=html;
        const topBlocks=[...template.content.children];
        window.__copyProbe={
          trusted:event.isTrusted,
          types:[...event.clipboardData.types],
          htmlLength:html.length,
          htmlImages:template.content.querySelectorAll("img[src]").length,
          htmlTopBlocks:topBlocks.length,
          htmlMixedBlocks:topBlocks.filter(block=>block.querySelector("img[src]")&&block.textContent.trim()).length,
          htmlSpacers:topBlocks.filter(block=>block.hasAttribute("data-xiumi-skip-spacer")&&block.querySelector("br")&&!block.querySelector("img[src]")).length,
          htmlText:template.content.textContent.replace(/\u200b/g,"").trim()
        };
      },{once:true});
      document.body.tabIndex=-1;
      document.body.focus();
      const range=document.createRange();
      range.selectNodeContents(document.getElementById("documentTitle"));
      const selection=getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
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
    if (probe.result.value) return probe.result.value;
  }
  return null;
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
  const initialEvaluation = await cdp.send("Runtime.evaluate", {
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
        embeddedStat:Number(document.getElementById("embeddedCount").textContent),
        remoteStat:Number(document.getElementById("remoteCount").textContent),
        imageDom:images.length,
        imageDecoded:images.filter(image=>image.complete&&image.naturalWidth>0).length,
        copyDisabled:document.getElementById("copyButton").disabled,
        uploadHidden:document.getElementById("uploadButton").hidden
      };
      return window.__smokeStats;
    })()`,
  });
  const initial = initialEvaluation.result.value;
  for (const key of ["title", "slices", "components"]) if (initial[key] !== expected[key]) fail(`${key}: expected ${expected[key]}, got ${initial[key]}`);
  if (initial.imageStat !== expected.images || initial.imageDom !== expected.images) fail(`initial image count mismatch: ${JSON.stringify(initial)}`);
  if (initial.embeddedStat !== expected.embedded || initial.remoteStat !== expected.remote) fail(`initial image persistence mismatch: ${JSON.stringify(initial)}`);
  if (initial.uploadHidden !== (expected.embedded === 0)) fail(`step 1 image action visibility is wrong: ${JSON.stringify(initial)}`);
  if (expected.embedded && !initial.copyDisabled) fail(`step 2 should be locked before image return: ${JSON.stringify(initial)}`);
  if (!expected.embedded && initial.copyDisabled) fail(`save-ready document copy is disabled: ${JSON.stringify(initial)}`);

  let uploadProbe = null;
  if (expected.embedded) {
    await cdp.send("Runtime.evaluate", { userGesture: true, expression: 'document.getElementById("uploadButton").click()' });
    uploadProbe = await trustedCopy(cdp);
    if (!uploadProbe?.trusted) fail(`expected a trusted image-sheet copy, got ${JSON.stringify(uploadProbe)}`);
    for (const mime of ["text/html", "text/plain"]) if (!uploadProbe.types.includes(mime)) fail(`image sheet is missing ${mime}`);
    if (uploadProbe.types.includes(COMPS_MIME) || uploadProbe.types.includes(LABEL_MIME)) fail(`image sheet leaked Xiumi native MIME: ${JSON.stringify(uploadProbe)}`);
    if (uploadProbe.htmlImages !== expected.images || uploadProbe.htmlLength < 100) fail(`image sheet did not contain every image: ${JSON.stringify(uploadProbe)}`);
    if (uploadProbe.htmlMixedBlocks !== 0 || uploadProbe.htmlTopBlocks !== expected.images * 2 - 1 || uploadProbe.htmlSpacers !== expected.images - 1 || uploadProbe.htmlText) fail(`image sheet contains text or malformed anti-skip blocks: ${JSON.stringify(uploadProbe)}`);
  }

  if (expected.embedded) {
    const pendingSources = Array.from({ length: expected.images }, (_, index) => index < Math.floor(expected.images / 2)
      ? `https://assets.example.test/xiumi-pending-${index + 1}.png`
      : "data:image/png;base64,aGVsbG8=");
    const pendingResult = await cdp.send("Runtime.evaluate", {
      userGesture: true,
      returnByValue: true,
      expression: `(()=>{
        const sources=${JSON.stringify(pendingSources)};
        const transfer=new DataTransfer();
        transfer.setData(${JSON.stringify(COMPS_MIME)},JSON.stringify({slices:sources.map(src=>({img1:{type:"image",src}}))}));
        document.dispatchEvent(new ClipboardEvent("paste",{clipboardData:transfer,bubbles:true,cancelable:true}));
        return {status:document.getElementById("status").textContent,copyDisabled:document.getElementById("copyButton").disabled};
      })()`,
    });
    const pending = pendingResult.result.value;
    if (!pending.copyDisabled || !pending.status.includes("仍在串行上传图片")) fail(`incomplete image upload was not diagnosed: ${JSON.stringify(pending)}`);

    const remoteSources = Array.from({ length: expected.images }, (_, index) => `https://assets.example.test/xiumi-localized-${index + 1}.png`);
    const pasteResult = await cdp.send("Runtime.evaluate", {
      userGesture: true,
      returnByValue: true,
      expression: `(()=>{
        const sources=${JSON.stringify(remoteSources)};
        const transfer=new DataTransfer();
        transfer.setData(${JSON.stringify(COMPS_MIME)},JSON.stringify({slices:sources.map(src=>({img1:{type:"image",src}}))}));
        const pasted=document.dispatchEvent(new ClipboardEvent("paste",{clipboardData:transfer,bubbles:true,cancelable:true}));
        return {
          pasted,
          embedded:Number(document.getElementById("embeddedCount").textContent),
          remote:Number(document.getElementById("remoteCount").textContent),
          copyDisabled:document.getElementById("copyButton").disabled,
          downloadHidden:document.getElementById("downloadButton").hidden,
          status:document.getElementById("status").textContent
        };
      })()`,
    });
    const localized = pasteResult.result.value;
    if (localized.embedded !== 0 || localized.remote !== expected.remote + expected.embedded) fail(`localization failed: ${JSON.stringify(localized)}`);
    if (localized.copyDisabled || localized.downloadHidden || !localized.status.includes("②已解锁")) fail(`localized document was not unlocked: ${JSON.stringify(localized)}`);
  }
  const finalProbe = await trustedCopy(cdp);
  const evaluation = await cdp.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `({
      status:document.getElementById("status").textContent,
      title:document.getElementById("documentTitle").textContent,
      slices:Number(document.getElementById("sliceCount").textContent),
      components:Number(document.getElementById("componentCount").textContent),
      imageStat:Number(document.getElementById("imageCount").textContent),
      embeddedStat:Number(document.getElementById("embeddedCount").textContent),
      remoteStat:Number(document.getElementById("remoteCount").textContent)
    })`,
  });
  const actual = evaluation.result.value;
  if (!finalProbe?.trusted) fail(`expected a trusted final copy event, got ${JSON.stringify(finalProbe)}`);
  for (const mime of [COMPS_MIME, LABEL_MIME, "text/plain"]) if (!finalProbe.types.includes(mime)) fail(`final copy event is missing ${mime}`);
  for (const key of ["title", "slices", "components"]) if (actual[key] !== expected[key]) fail(`${key}: expected ${expected[key]}, got ${actual[key]}`);
  if (actual.imageStat !== expected.images || actual.embeddedStat !== 0 || actual.remoteStat !== expected.images) fail(`final persistence stats mismatch: ${JSON.stringify(actual)}`);
  if (!actual.status.includes("xiumi-comps 已写入 Chromium")) fail(`unexpected status: ${actual.status}`);
  console.log(JSON.stringify({ ok: true, url, expected, initial, uploadProbe, finalProbe, actual }, null, 2));
} finally {
  if (cdp) cdp.close();
  await stop(chrome);
  await stop(server);
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 8, retryDelay: 150 });
}
