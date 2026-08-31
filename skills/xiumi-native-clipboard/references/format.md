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

Every `_comp` needs a unique `_$uuid`. Use camelCase Xiumi style properties and strings with CSS units. Embed local PNG/JPEG/WebP/GIF/SVG files through `data_uri()`; a finished document must not depend on relative image paths.

The previewer supports the component subset above and renders unknown group-like components generically with a diagnostic warning. Only use additional proprietary templates after a real Xiumi paste test.

## Delivery commands

From the skill directory:

```bash
python3 scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json
python3 scripts/xiumi_clipboard.py pack ARTICLE.xiumi.json -o ARTICLE.bin
python3 scripts/xiumi_clipboard.py unpack ARTICLE.bin -o ROUNDTRIP.xiumi.json
python3 scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

The server binds only to `127.0.0.1`, serves the selected document without copying it, disables caching, and prints a URL whose `src` query has already selected that document.
