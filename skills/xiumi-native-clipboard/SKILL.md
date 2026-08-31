---
name: xiumi-native-clipboard
description: Generate, validate, preview, and hand off polished Xiumi-native component JSON when a user wants an article or layout that can be copied directly into Xiumi. Use for Xiumi clipboard deliverables; do not use for ordinary HTML-only publishing.
---

# Xiumi Native Clipboard

Create one self-contained `.xiumi.json` document whose images are embedded and whose layout uses Xiumi-native component data.

Before authoring a document, read [references/format.md](references/format.md). Use [scripts/xiumi_components.py](scripts/xiumi_components.py) instead of retyping fragile component envelopes. Preserve the user's visual direction; the helpers define transport structure, not a mandatory editorial style.

After generation:

1. Run `python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json`.
2. Start `python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json` in a persistent process.
3. Give the user the printed localhost URL. Keep the process alive while they preview and copy.
4. If clipboard compatibility needs diagnosis, run `pack`, inspect the binary with `unpack`, and compare the round trip.

Use the exact Xiumi MIME names documented in the reference. Do not substitute ordinary HTML import or Async Clipboard `web ...` formats. Never commit a user's article images or Xiumi UID to a public repository unless they explicitly authorize publication.
