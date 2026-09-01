---
name: xiumi-native-clipboard
description: Generate, validate, preview, and hand off polished Xiumi article JSON through saveable formatted HTML first and optional native components. Use for Xiumi clipboard deliverables; do not use for ordinary HTML-only publishing.
---

# Xiumi Native Clipboard

Create one self-contained `.xiumi.json` draft whose local images are embedded and whose layout uses Xiumi-native component data. Embedded images are safe in the formatted-HTML delivery path but not in direct `xiumi-comps` delivery.

Before authoring a document, read [references/format.md](references/format.md). Use [scripts/xiumi_components.py](scripts/xiumi_components.py) instead of retyping fragile component envelopes. Preserve the user's visual direction; the helpers define transport structure, not a mandatory editorial style.

After generation:

1. Run `python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json`.
2. Start `python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json` in a persistent process.
3. Give the user the printed localhost URL. Keep the process alive while they preview and copy.
4. Have the user click “① 复制带格式 HTML” and press a real `Ctrl+C` in the preview page. This clipboard write must contain the complete article as `text/html` plus `text/plain`, and no Xiumi custom MIME. Pasting it once into Xiumi lets Xiumi upload Base64 images and creates the default saveable result.
5. If the HTML result is satisfactory, ask the user to verify that it saves and stop. Native replacement is optional.
6. For optional native replacement, have the user wait for all first-step images to load, select and copy the imported Xiumi body, return to the tool, and press `Ctrl+V`. The tool uses the returned permanent URLs to unlock “② 复制 xiumi-comps（可选）”.
7. Copy②. Back in Xiumi, select the whole first-step body before pasting, so the native components replace the HTML version instead of being appended. The localhost button can write the private clipboard through `wl-copy` or `xclip`; otherwise use a real `Ctrl+C` in the preview page.
8. If a save-ready JSON is downloaded, validate it with `python3 scripts/xiumi_clipboard.py validate ARTICLE.save-ready.xiumi.json --save-ready`. Verify that the final chosen version actually saves in Xiumi.

Documents already containing only persistent HTTP(S) images can use② immediately, but keep① as the default delivery. `pack` rejects embedded image drafts by default; use `--allow-embedded-draft` only for protocol diagnosis, never for final delivery.

If clipboard compatibility needs diagnosis, run `pack`, inspect the binary with `unpack`, and compare the round trip.

Use the exact Xiumi MIME names documented in the reference. Step① deliberately uses ordinary formatted HTML as the default saveable delivery; step② uses the Xiumi custom MIME only after image persistence. Do not substitute Async Clipboard `web ...` formats. Never commit a user's article images, localized private image URLs, or Xiumi UID to a public repository unless they explicitly authorize publication.
