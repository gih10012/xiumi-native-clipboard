---
name: xiumi-native-clipboard
description: Generate, validate, preview, and hand off polished Xiumi article JSON through image-only HTML localization followed by save-ready native components. Use for Xiumi clipboard deliverables; do not use for ordinary HTML-only publishing.
---

# Xiumi Native Clipboard

Create one self-contained `.xiumi.json` draft whose local images are embedded and whose layout uses Xiumi-native component data. Embedded images are only a transport state: upload them through the image-only first pass, then use permanent Xiumi URLs in the native final pass.

Before authoring a document, read [references/format.md](references/format.md). Use [scripts/xiumi_components.py](scripts/xiumi_components.py) instead of retyping fragile component envelopes. Preserve the user's visual direction; the helpers define transport structure, not a mandatory editorial style.

After generation:

1. Run `python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json`.
2. Start `python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json` in a persistent process.
3. Give the user the printed localhost URL. Keep the process alive while they preview and copy.
4. For a document with embedded images, have the user click “① 复制全部图片（无格式）” and press a real `Ctrl+C` in the preview page. This clipboard write must contain an alternating sequence of one top-level image block and one empty `<p><br></p>` spacer as `text/html`, an empty/invisible `text/plain` fallback, and no article text, layout, or Xiumi custom MIME. Real Xiumi testing showed that adjacent image-only blocks lose every even-numbered image; the sacrificial spacer absorbs that skip. Paste the sheet into a blank temporary Xiumi article.
5. Have the user wait until Xiumi's paste/upload indicator has completely finished, then use Xiumi's “复制全文”, return to the tool, and press `Ctrl+V`. Xiumi uploads Base64 images serially, so visible images do not prove completion. The tool must distinguish pending embedded images from a partial selection and unlock② only after it receives the expected number of permanent URLs.
6. Copy② and paste it into a blank final Xiumi article. This native pass is required for an image-containing draft because the first pass is intentionally only an image upload sheet. The localhost button can write the private clipboard through `wl-copy` or `xclip`; otherwise use a real `Ctrl+C` in the preview page.
7. If a save-ready JSON is downloaded, validate it with `python3 scripts/xiumi_clipboard.py validate ARTICLE.save-ready.xiumi.json --save-ready`. Verify that the final native article actually saves in Xiumi.

Documents already containing only persistent HTTP(S) images, or no images, can use② immediately and skip①. `pack` rejects embedded image drafts by default; use `--allow-embedded-draft` only for protocol diagnosis, never for final delivery.

If clipboard compatibility needs diagnosis, run `pack`, inspect the binary with `unpack`, and compare the round trip.

Use the exact Xiumi MIME names documented in the reference. Step① deliberately uses ordinary image-only HTML solely to localize images; step② uses the Xiumi custom MIME to create the final article after image persistence. Do not substitute Async Clipboard `web ...` formats. Never commit a user's article images, localized private image URLs, or Xiumi UID to a public repository unless they explicitly authorize publication.
