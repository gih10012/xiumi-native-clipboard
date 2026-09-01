import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "xiumi-native-clipboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import xiumi_clipboard as clipboard  # noqa: E402
import xiumi_components as components  # noqa: E402


class ClipboardBinaryTests(unittest.TestCase):
    def test_utf16_round_trip_including_non_bmp(self):
        entries = [
            (components.COMPS_MIME, '{"title":"军训😀","value":1}'),
            (components.LABEL_MIME, '{"timestamp":"123"}'),
        ]
        blob = clipboard.pack_custom(entries)
        self.assertEqual(clipboard.unpack_custom(blob), entries)
        self.assertEqual(int.from_bytes(blob[:4], "little"), len(blob) - 4)

    def test_materialize_refreshes_label_timestamp(self):
        doc = json.loads((ROOT / "examples" / "demo.xiumi.json").read_text(encoding="utf-8"))
        values = dict(clipboard.materialize_formats(doc, "123456789"))
        label = json.loads(values[components.LABEL_MIME])
        self.assertEqual(label["timestamp"], "123456789")

    def test_pack_unpack_document_round_trip(self):
        doc = json.loads((ROOT / "examples" / "demo.xiumi.json").read_text(encoding="utf-8"))
        original = clipboard.materialize_formats(doc, "42")
        recovered = clipboard.unpack_custom(clipboard.pack_custom(original))
        self.assertEqual(recovered, original)
        rebuilt = clipboard.document_from_entries(recovered, "roundtrip")
        stats = clipboard.validate_document(rebuilt)
        self.assertEqual(stats["formats"], 2)
        self.assertEqual(stats["slices"], 2)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.demo = json.loads((ROOT / "examples" / "demo.xiumi.json").read_text(encoding="utf-8"))

    def test_demo_is_valid(self):
        stats = clipboard.validate_document(self.demo)
        self.assertEqual(
            stats,
            {
                "formats": 2,
                "slices": 2,
                "components": 5,
                "images": 0,
                "embedded_images": 0,
                "remote_images": 0,
                "save_ready": True,
                "warnings": 0,
            },
        )

    def test_duplicate_uuid_is_rejected(self):
        broken = copy.deepcopy(self.demo)
        slices = broken["clipboard"]["formats"][0]["data"]["slices"]
        slices[1]["_$unused"] = True
        slices[1]["_comp"]["_$uuid"] = slices[0]["_comp"]["_$uuid"]
        with self.assertRaisesRegex(clipboard.DocumentError, "duplicate component UUID"):
            clipboard.validate_document(broken)

    def test_builder_embeds_and_validates_image(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "dot.png"
            image_path.write_bytes(__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
            doc = components.document("image", [components.wrapper([components.image(components.data_uri(image_path))])])
            stats = clipboard.validate_document(doc)
            self.assertEqual(stats["images"], 1)
            self.assertEqual(stats["embedded_images"], 1)
            self.assertFalse(stats["save_ready"])
            with self.assertRaisesRegex(clipboard.DocumentError, "not save-ready"):
                clipboard.validate_document(doc, require_save_ready=True)

    def test_remote_image_is_save_ready(self):
        doc = components.document(
            "localized image",
            [components.wrapper([components.image("https://statics.example.test/xiumi-image.png")])],
        )
        stats = clipboard.validate_document(doc, require_save_ready=True)
        self.assertEqual(stats["remote_images"], 1)
        self.assertEqual(stats["embedded_images"], 0)
        self.assertTrue(stats["save_ready"])

    def test_invalid_base64_is_rejected(self):
        image = components.image("data:image/png;base64,not-valid!")
        doc = components.document("bad image", [components.wrapper([image])])
        with self.assertRaisesRegex(clipboard.DocumentError, "invalid base64"):
            clipboard.validate_document(doc)


class StaticToolTests(unittest.TestCase):
    def test_single_file_tool_has_no_external_script(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script src=", html)
        self.assertNotIn('document.execCommand("copy")', html)
        self.assertIn("event.clipboardData.setData(format.mime", html)
        self.assertIn('event.clipboardData.setData("text/html", uploadSheet', html)
        self.assertIn("function uploadSheet(sources)", html)
        self.assertNotIn("fullStyledHTML", html)
        self.assertIn("document.addEventListener(\"copy\", onCopy)", html)
        self.assertIn("document.addEventListener(\"paste\", onPaste)", html)
        self.assertIn("fetch(state.copyEndpoint", html)
        self.assertIn("body: JSON.stringify(state.document)", html)

    def test_schema_is_json(self):
        schema = json.loads((ROOT / "schema" / "xiumi-document.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["format"]["const"], "xiumi-native-clipboard")

    def test_serve_preloads_selected_document(self):
        process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "xiumi_clipboard.py"), "serve", str(ROOT / "examples" / "demo.xiumi.json")],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            url = process.stdout.readline().strip()
            self.assertTrue(url.startswith("http://127.0.0.1:"), url)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("秀米原生剪切板", html)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            source = query["src"][0]
            self.assertTrue(query["copy"][0].startswith("/copy/"))
            base = url.split("/?", 1)[0]
            with opener.open(base + source, timeout=5) as response:
                document = json.loads(response.read())
            self.assertEqual(document["formatVersion"], 1)

            embedded = components.document(
                "draft",
                [components.wrapper([components.image("data:image/png;base64,aGVsbG8=")])],
            )
            request = urllib.request.Request(
                base + query["copy"][0],
                data=json.dumps(embedded).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                opener.open(request, timeout=5)
            try:
                self.assertEqual(raised.exception.code, 422)
                payload = json.loads(raised.exception.read())
                self.assertIn("not save-ready", payload["error"])
            finally:
                raised.exception.close()
        finally:
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
