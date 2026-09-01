# Xiumi document format

Read this reference when creating or repairing a `.xiumi.json` document.

## Envelope

Use schema version 1:

```json
{
  "$schema": "https://gih10012.github.io/xiumi-native-clipboard/schema/xiumi-document.schema.json",
  "format": "xiumi-native-clipboard",
  "formatVersion": 1,
  "meta": {"title": "Article title", "previewWidth": 415},
  "clipboard": {
    "refreshLabelTimestamp": true,
    "formats": [
      {
        "mime": "application/xiumi-comps; category=paper.comp",
        "encoding": "json",
        "data": {"version": 5, "deskVersion": 5, "type": "paper", "category": "comp", "pageRuntimeKey": -1, "_comp": {"style": null}, "slices": []}
      },
      {
        "mime": "application/xiumi-label; origin=studio",
        "encoding": "json",
        "data": {"timestamp": "$now", "user": {"unique_uid": "optional-local-profile"}}
      }
    ]
  }
}
```

The `application/xiumi-comps` entry is required. Keep the label entry when a working Xiumi UID is available; `$now` is replaced with the current Unix time in milliseconds when copying or packing. A UID is local account metadata, not article content, so do not put a real UID in public examples.

## Native component subset

Prefer the builders from `scripts/xiumi_components.py`:

- `text()` creates `paper-cp:header/1-txt-normal`.
- `image()` creates `paper-cp:image/img-autowidth`.
- `wrapper()` creates a flexible single container.
- `row1()` creates a styled one-column group or card.
- `row2()` creates a true two-column native layout; nest rows for three or more visual columns.
- Place a transparent `image()` after a card with a negative `marginTop` to create editable out-of-frame decoration.

Every `_comp` needs a unique `_$uuid`. Use camelCase Xiumi style properties and strings with CSS units. Embed local PNG/JPEG/WebP/GIF/SVG files through `data_uri()` while authoring so the draft stays portable and does not depend on relative paths.

## Image persistence states

A Base64 `data:image/...;base64,...` source is draft transport, not final storage. When that source is copied inside `application/xiumi-comps`, Xiumi takes the native-component branch and bypasses its normal pasted-image upload step. The image can render immediately but the article may fail to save.

A save-ready image source for native components is a persistent HTTP(S) URL returned after Xiumi has accepted the image into the current account. Use the preview tool's image-localization workflow:

1. Copy only the images as ordinary `text/html` plus an empty/invisible `text/plain` fallback, without Xiumi custom MIME. Emit an image-only top-level block for every real image occurrence. Immediately follow each embedded Base64 real image with a unique transparent 1×1 Base64 marker block; do not add a marker after an already-persistent HTTP(S) image. Xiumi currently reuses a global Base64 regular expression across sources and consequently classifies alternating sources incorrectly; each marker absorbs the failed scan after its real image. On return, discard marked sources or, for an all-embedded complete alternating sequence whose marker fragments were rewritten, keep the odd-position images. Do not include article text, headings, cards, rows, or decorative layout in this pass.
2. Paste the sheet into a blank temporary Xiumi article and wait for every Base64 image upload to finish.
3. Use Xiumi's “复制全文” and paste it back into the tool. Do not rely on a manual visible-area selection.
4. The tool replaces matching data URIs in the original native components with the returned permanent URLs.
5. Copy `xiumi-comps` and paste into a blank final Xiumi article to generate the full native layout.

After localization, the tool records `meta.imagePersistence: "xiumi-remote"`, `meta.localizedImageCount`, and `meta.localizedAt`. These fields are informative; save-readiness is determined by the absence of embedded image data URIs. The image-only first pass is disposable and is never the final article. Never directly hand off or pack an embedded-image draft as a final article.

The previewer supports the component subset above and renders unknown group-like components generically with a diagnostic warning. Only use additional proprietary templates after a real Xiumi paste test.

## Delivery commands

From the skill directory:

```bash
python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json
python3 scripts/xiumi_clipboard.py validate ARTICLE.save-ready.xiumi.json --save-ready
python3 scripts/xiumi_clipboard.py pack ARTICLE.xiumi.json -o ARTICLE.bin
python3 scripts/xiumi_clipboard.py unpack ARTICLE.bin -o ROUNDTRIP.xiumi.json
python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

The server binds only to `127.0.0.1`, disables caching, and prints a URL whose `src` query has already selected that document. Its tokenized `copy` endpoint accepts the current browser-side save-ready document and, on Linux, writes `chromium/x-web-custom-data` through `wl-copy` or `xclip`; it rejects documents that still contain embedded draft images. On Windows or macOS, and whenever no Linux helper is available, use a real `Ctrl+C` in desktop Edge/Chrome/Chromium. Mobile browsers, Firefox, and Safari are not supported delivery targets.
