#!/usr/bin/env python3
"""Validate, pack, unpack, and locally serve Xiumi clipboard documents."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import json
import os
import secrets
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


COMPS_MIME = "application/xiumi-comps; category=paper.comp"
LABEL_MIME = "application/xiumi-label; origin=studio"
MAX_DOCUMENT_BYTES = 80 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[3]


class DocumentError(ValueError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    size = source.stat().st_size
    if size > MAX_DOCUMENT_BYTES:
        raise DocumentError(f"document is too large: {size} bytes (limit {MAX_DOCUMENT_BYTES})")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentError(f"cannot read JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise DocumentError("document root must be an object")
    return value


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def validate_document(document: dict[str, Any], *, allow_remote_images: bool = False) -> dict[str, int]:
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("format") != "xiumi-native-clipboard":
        errors.append("format must be 'xiumi-native-clipboard'")
    if document.get("formatVersion") != 1:
        errors.append("formatVersion must be 1")
    meta = document.get("meta")
    if not isinstance(meta, dict) or not isinstance(meta.get("title"), str) or not meta.get("title", "").strip():
        errors.append("meta.title must be a non-empty string")
    clipboard = document.get("clipboard")
    formats = clipboard.get("formats") if isinstance(clipboard, dict) else None
    if not isinstance(formats, list) or not formats:
        errors.append("clipboard.formats must be a non-empty array")
        formats = []
    seen_mimes: set[str] = set()
    comps: dict[str, Any] | None = None
    for index, entry in enumerate(formats):
        if not isinstance(entry, dict):
            errors.append(f"clipboard.formats[{index}] must be an object")
            continue
        mime = entry.get("mime")
        if not isinstance(mime, str) or not mime:
            errors.append(f"clipboard.formats[{index}].mime must be a non-empty string")
            continue
        if mime in seen_mimes:
            errors.append(f"duplicate clipboard MIME: {mime}")
        seen_mimes.add(mime)
        if entry.get("encoding") != "json":
            errors.append(f"{mime}: encoding must be 'json'")
        if not isinstance(entry.get("data"), (dict, list)):
            errors.append(f"{mime}: data must be a JSON object or array")
        if mime == COMPS_MIME and isinstance(entry.get("data"), dict):
            comps = entry["data"]
    if comps is None:
        errors.append(f"required clipboard MIME missing: {COMPS_MIME}")
        comps = {}
    for key, expected in (("version", 5), ("deskVersion", 5), ("type", "paper"), ("category", "comp")):
        if comps.get(key) != expected:
            errors.append(f"Xiumi component payload {key!r} must be {expected!r}")
    slices = comps.get("slices")
    if not isinstance(slices, list) or not slices:
        errors.append("Xiumi component payload slices must be a non-empty array")
        slices = []

    uuids: set[str] = set()
    image_count = 0
    component_count = 0
    for node in _walk(slices):
        comp = node.get("_comp")
        if isinstance(comp, dict):
            component_count += 1
            item_uuid = comp.get("_$uuid")
            if not isinstance(item_uuid, str) or not item_uuid:
                errors.append(f"component #{component_count} is missing _comp._$uuid")
            elif item_uuid in uuids:
                errors.append(f"duplicate component UUID: {item_uuid}")
            else:
                uuids.add(item_uuid)
        if node.get("type") == "image":
            image_count += 1
            src = node.get("src")
            if not isinstance(src, str) or not src:
                errors.append(f"image #{image_count} has no src")
            elif src.startswith("data:"):
                if ";base64," not in src:
                    errors.append(f"image #{image_count} data URI is not base64 encoded")
                else:
                    try:
                        base64.b64decode(src.split(",", 1)[1], validate=True)
                    except (binascii.Error, ValueError):
                        errors.append(f"image #{image_count} has invalid base64 data")
            elif not allow_remote_images:
                errors.append(f"image #{image_count} is not embedded as a data URI")
            else:
                warnings.append(f"image #{image_count} uses a remote source")
    if image_count > 60:
        warnings.append(f"document contains {image_count} images; clipboard size may be large")
    if errors:
        raise DocumentError("\n".join(errors))
    return {
        "formats": len(formats),
        "slices": len(slices),
        "components": component_count,
        "images": image_count,
        "warnings": len(warnings),
    }


def _replace_now(value: Any, now_ms: str) -> Any:
    if value == "$now":
        return now_ms
    if isinstance(value, dict):
        return {key: _replace_now(child, now_ms) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_now(child, now_ms) for child in value]
    return value


def materialize_formats(document: dict[str, Any], now_ms: str | None = None) -> list[tuple[str, str]]:
    now_ms = now_ms or str(int(time.time() * 1000))
    output: list[tuple[str, str]] = []
    for entry in document["clipboard"]["formats"]:
        data = copy.deepcopy(entry["data"])
        if document["clipboard"].get("refreshLabelTimestamp", True) and entry["mime"] == LABEL_MIME:
            if isinstance(data, dict):
                data["timestamp"] = now_ms
        data = _replace_now(data, now_ms)
        output.append((entry["mime"], json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    return output


def pack_custom(entries: list[tuple[str, str]]) -> bytes:
    body = bytearray(struct.pack("<I", len(entries)))
    for key, value in entries:
        key_bytes = key.encode("utf-16le")
        value_bytes = value.encode("utf-16le")
        body.extend(struct.pack("<I", len(key_bytes) // 2))
        body.extend(key_bytes)
        body.extend(struct.pack("<I", len(value_bytes) // 2))
        body.extend(value_bytes)
        while len(body) % 4:
            body.append(0)
    return struct.pack("<I", len(body)) + body


def unpack_custom(blob: bytes) -> list[tuple[str, str]]:
    if len(blob) < 8:
        raise DocumentError("clipboard binary is shorter than its header")
    declared_size, count = struct.unpack_from("<II", blob, 0)
    if declared_size != len(blob) - 4:
        raise DocumentError(f"clipboard binary size mismatch: header={declared_size}, actual={len(blob) - 4}")
    offset = 8
    entries: list[tuple[str, str]] = []
    try:
        for _ in range(count):
            key_units = struct.unpack_from("<I", blob, offset)[0]
            offset += 4
            key = blob[offset : offset + key_units * 2].decode("utf-16le")
            offset += key_units * 2
            value_units = struct.unpack_from("<I", blob, offset)[0]
            offset += 4
            value = blob[offset : offset + value_units * 2].decode("utf-16le")
            offset += value_units * 2
            offset = (offset + 3) & ~3
            entries.append((key, value))
    except (struct.error, UnicodeDecodeError) as exc:
        raise DocumentError(f"malformed clipboard binary near byte {offset}: {exc}") from exc
    if offset != len(blob):
        raise DocumentError(f"clipboard binary has {len(blob) - offset} trailing bytes")
    return entries


def document_from_entries(entries: list[tuple[str, str]], title: str) -> dict[str, Any]:
    formats: list[dict[str, Any]] = []
    for mime, value in entries:
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise DocumentError(f"{mime} does not contain JSON: {exc}") from exc
        formats.append({"mime": mime, "encoding": "json", "data": data})
    return {
        "$schema": "https://gih10012.github.io/xiumi-native-clipboard/schema/xiumi-document.schema.json",
        "format": "xiumi-native-clipboard",
        "formatVersion": 1,
        "meta": {"title": title, "previewWidth": 415, "generator": "xiumi-native-clipboard unpack"},
        "clipboard": {"refreshLabelTimestamp": False, "formats": formats},
    }


def write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def start_clipboard_provider(blob: bytes) -> subprocess.Popen:
    if shutil.which("wl-copy") and os.environ.get("WAYLAND_DISPLAY"):
        command = ["wl-copy", "--foreground", "--type", "chromium/x-web-custom-data"]
    elif shutil.which("xclip") and os.environ.get("DISPLAY"):
        command = ["xclip", "-selection", "clipboard", "-target", "chromium/x-web-custom-data", "-in"]
    else:
        raise DocumentError("no supported system clipboard helper; use a real Ctrl+C in desktop Chromium")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        assert process.stdin is not None
        process.stdin.write(blob)
        process.stdin.close()
    except (BrokenPipeError, OSError) as exc:
        process.terminate()
        raise DocumentError(f"clipboard provider failed: {exc}") from exc
    time.sleep(0.04)
    if process.poll() not in (None, 0):
        raise DocumentError(f"clipboard provider exited with status {process.returncode}")
    return process


def serve_document(document_path: Path, port: int, open_browser: bool) -> None:
    document = load_json(document_path)
    document_bytes = document_path.read_bytes()
    index_bytes = (REPO_ROOT / "index.html").read_bytes()
    token = secrets.token_urlsafe(18)
    document_route = f"/document/{token}.json"
    copy_route = f"/copy/{token}"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/index.html"):
                self._send(index_bytes, "text/html; charset=utf-8")
            elif path == document_route:
                self._send(document_bytes, "application/json; charset=utf-8")
            elif path == "/schema/xiumi-document.schema.json":
                self._send((REPO_ROOT / "schema" / "xiumi-document.schema.json").read_bytes(), "application/schema+json")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self):  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path != copy_route:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                blob = pack_custom(materialize_formats(document))
                previous = getattr(self.server, "clipboard_process", None)
                if previous and previous.poll() is None:
                    previous.terminate()
                    try:
                        previous.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        previous.kill()
                provider = start_clipboard_provider(blob)
                self.server.clipboard_process = provider
                self._send(
                    json.dumps({"ok": True, "bytes": len(blob)}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
            except (DocumentError, OSError) as exc:
                payload = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.NOT_IMPLEMENTED)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

        def _send(self, payload: bytes, content_type: str):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            sys.stderr.write("[xiumi-preview] " + fmt % args + "\n")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    actual_port = server.server_address[1]
    source = urllib.parse.quote(document_route, safe="/")
    copy_endpoint = urllib.parse.quote(copy_route, safe="/")
    url = f"http://127.0.0.1:{actual_port}/?src={source}&copy={copy_endpoint}"
    print(url, flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        provider = getattr(server, "clipboard_process", None)
        if provider and provider.poll() is None:
            provider.terminate()
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a .xiumi.json document")
    validate.add_argument("file", type=Path)
    validate.add_argument("--allow-remote-images", action="store_true")
    pack = subparsers.add_parser("pack", help="pack JSON into Chromium DataTransfer custom binary")
    pack.add_argument("file", type=Path)
    pack.add_argument("-o", "--output", required=True, type=Path)
    pack.add_argument("--timestamp", help="fixed timestamp for reproducible tests")
    unpack = subparsers.add_parser("unpack", help="unpack Chromium custom binary into JSON")
    unpack.add_argument("file", type=Path)
    unpack.add_argument("-o", "--output", required=True, type=Path)
    unpack.add_argument("--title", default="Unpacked Xiumi document")
    serve = subparsers.add_parser("serve", help="serve a preloaded local preview URL")
    serve.add_argument("file", type=Path)
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--open", action="store_true", dest="open_browser")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate":
            document = load_json(args.file)
            stats = validate_document(document, allow_remote_images=args.allow_remote_images)
            print("valid " + " ".join(f"{key}={value}" for key, value in stats.items()))
        elif args.command == "pack":
            document = load_json(args.file)
            validate_document(document)
            blob = pack_custom(materialize_formats(document, args.timestamp))
            args.output.write_bytes(blob)
            print(f"packed bytes={len(blob)} output={args.output}")
        elif args.command == "unpack":
            entries = unpack_custom(args.file.read_bytes())
            document = document_from_entries(entries, args.title)
            validate_document(document, allow_remote_images=True)
            write_json(args.output, document)
            print(f"unpacked formats={len(entries)} output={args.output}")
        elif args.command == "serve":
            document = load_json(args.file)
            validate_document(document)
            serve_document(args.file.resolve(), args.port, args.open_browser)
        return 0
    except (DocumentError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
