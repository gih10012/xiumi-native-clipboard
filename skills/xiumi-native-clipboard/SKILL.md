---
name: xiumi-native-clipboard
description: Generate, validate, preview, and hand off polished Xiumi-native component JSON when a user wants an article or layout that can be copied directly into Xiumi. Use for Xiumi clipboard deliverables; do not use for ordinary HTML-only publishing.
---

# Xiumi Native Clipboard

Create one self-contained `.xiumi.json` draft whose local images are embedded and whose layout uses Xiumi-native component data. Treat embedded images as transport-only: a document containing Base64 data URIs is previewable but is not save-ready in Xiumi.

Before authoring a document, read [references/format.md](references/format.md). Use [scripts/xiumi_components.py](scripts/xiumi_components.py) instead of retyping fragile component envelopes. Preserve the user's visual direction; the helpers define transport structure, not a mandatory editorial style.

After generation:

1. Run `python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json`.
2. Start `python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json` in a persistent process.
3. Give the user the printed localhost URL. Keep the process alive while they preview and copy.
4. If the tool reports embedded images, have the user click “① 复制图片上传单” and press a real `Ctrl+C` in the preview page. The upload sheet deliberately contains `text/html` and no Xiumi custom MIME.
5. Have the user paste the upload sheet into a blank temporary Xiumi article, wait until every image appears, copy that temporary article in Xiumi, return to the preview tool, and press `Ctrl+V`. This lets Xiumi upload the images to the current account and lets the tool replace data URIs with persistent image URLs.
6. Continue only after the tool says “保存就绪”. Download the save-ready JSON and run `python3 scripts/xiumi_clipboard.py validate ARTICLE.save-ready.xiumi.json --save-ready` when the file is available.
7. Use “② 复制保存版到秀米” for the final native-component copy. The localhost button uses a same-origin system clipboard bridge when `wl-copy` or `xclip` is available; otherwise have the user press a real `Ctrl+C` in the preview page.
8. Ask the user to verify that the pasted article can actually be saved in Xiumi. A successful paste alone is not final acceptance for an image-containing article.

Text-only documents and documents already containing persistent HTTP(S) image URLs can skip steps 4–6. `pack` rejects embedded image drafts by default; use `--allow-embedded-draft` only for protocol diagnosis, never for final delivery.

If clipboard compatibility needs diagnosis, run `pack`, inspect the binary with `unpack`, and compare the round trip.

Use the exact Xiumi MIME names documented in the reference. Ordinary HTML is allowed only for the temporary image-upload sheet; do not use it for final layout delivery and do not substitute Async Clipboard `web ...` formats. Never commit a user's article images, localized private image URLs, or Xiumi UID to a public repository unless they explicitly authorize publication.
