#!/usr/bin/env python3
"""Small, dependency-free builders for Xiumi paper components."""

from __future__ import annotations

import base64
import copy
import json
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


COMPS_MIME = "application/xiumi-comps; category=paper.comp"
LABEL_MIME = "application/xiumi-label; origin=studio"
SCHEMA_URL = "https://gih10012.github.io/xiumi-native-clipboard/schema/xiumi-document.schema.json"
VIEWPORT = {
    "WIDTH": 415,
    "_BACKVIEW": "260533738:1721120895:18565098:78383942:1744288605:24",
    "_FRONTVIEW": "255256073:1721183486:69042341:69042341:2000398190:4",
}


def component_uuid(prefix: str = "comp") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def data_uri(path: str | Path) -> str:
    source = Path(path)
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(source.read_bytes()).decode("ascii")


def text(html: str, style: dict[str, Any] | None = None, component_style: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "_comp": {
            "constraint": {"opMenu": {"text-merged": True}, "pose": {"resize": "h"}},
            "pose": {},
            "style": copy.deepcopy(component_style or {}),
            "tplId": "paper-cp:header/1-txt-normal",
            "_$uuid": component_uuid(),
        },
        "txt1": {"type": "text", "text": html, "style": copy.deepcopy(style or {}), "constraint": {}},
    }


def image(
    src: str,
    width: str = "100%",
    component_style: dict[str, Any] | None = None,
    image_style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outer = {
        "textAlign": "center",
        "marginTop": "0",
        "marginRight": "0",
        "marginBottom": "0",
        "marginLeft": "0",
        "lineHeight": "0",
    }
    outer.update(copy.deepcopy(component_style or {}))
    inner = {"width": width, "height": "auto", "maxWidth": "100%"}
    inner.update(copy.deepcopy(image_style or {}))
    return {
        "_comp": {
            "tplId": "paper-cp:image/img-autowidth",
            "constraint": {"opMenu": {"crop-image-merged": True}, "pose": {"resize": "h"}},
            "style": outer,
            "pose": {"position": "static", "width": None, "height": None, "zIndex": 1},
            "_$uuid": component_uuid(),
        },
        "img1": {"type": "image", "src": src, "style": inner, "constraint": {}},
    }


def wrapper(items: Iterable[dict[str, Any]], style: dict[str, Any] | None = None, cell_style: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "_comp": {
            "constraint": {"pose": {"resize": "h"}},
            "pose": {},
            "style": copy.deepcopy(style or {}),
            "tplId": "paper-cp:layout/wrapper-flex",
            "_$uuid": component_uuid(),
            "_viewport": copy.deepcopy(VIEWPORT),
        },
        "col1": {
            "type": "container",
            "constraint": {"childLayout": "static", "containerUsage": "flex-box"},
            "items": list(items),
            "style": copy.deepcopy(cell_style or {}),
        },
    }


def row1(items: Iterable[dict[str, Any]], style: dict[str, Any] | None = None, cell_style: dict[str, Any] | None = None) -> dict[str, Any]:
    root_style = {
        "textAlign": "center",
        "justifyContent": "center",
        "display": "flex",
        "flexDirection": "row",
        "flexWrap": "nowrap",
    }
    root_style.update(copy.deepcopy(style or {}))
    content_style = {
        "width": "100%",
        "verticalAlign": "top",
        "alignSelf": "flex-start",
        "flex": "0 0 auto",
        "height": "auto",
    }
    content_style.update(copy.deepcopy(cell_style or {}))
    return {
        "_comp": {
            "constraint": {"pose": {"resize": "h"}, "opMenu": {"group-cell-merged": True}},
            "style": root_style,
            "tplId": "paper-cp:layout/row1-r1c1",
            "pose": {"position": "static", "width": None, "height": None},
            "_$uuid": component_uuid(),
            "_viewport": copy.deepcopy(VIEWPORT),
        },
        "col1": {
            "type": "group",
            "constraint": {"childLayout": "static"},
            "items": list(items),
            "style": content_style,
        },
    }


def row2(
    left_items: Iterable[dict[str, Any]],
    right_items: Iterable[dict[str, Any]],
    style: dict[str, Any] | None = None,
    left_style: dict[str, Any] | None = None,
    right_style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_style = {
        "textAlign": "left",
        "justifyContent": "center",
        "display": "flex",
        "flexDirection": "row",
        "flexWrap": "nowrap",
    }
    root_style.update(copy.deepcopy(style or {}))
    base = {"width": "50%", "verticalAlign": "top", "alignSelf": "flex-start", "flex": "1 1 0%", "height": "auto"}
    left = copy.deepcopy(base)
    left.update(copy.deepcopy(left_style or {}))
    right = copy.deepcopy(base)
    right.update(copy.deepcopy(right_style or {}))
    return {
        "_comp": {
            "constraint": {"pose": {"resize": "h"}, "opMenu": {"group-cell-merged": True}},
            "style": root_style,
            "tplId": "paper-cp:layout/row1-r1c2",
            "pose": {"position": "static", "width": None, "height": None},
            "_$uuid": component_uuid(),
            "_viewport": copy.deepcopy(VIEWPORT),
        },
        "col1": {"type": "group", "constraint": {"childLayout": "static"}, "items": list(left_items), "style": left},
        "col2": {"type": "group", "constraint": {"childLayout": "static"}, "items": list(right_items), "style": right},
    }


def document(title: str, slices: Iterable[dict[str, Any]], *, label_uid: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = {
        "title": title,
        "previewWidth": 415,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "xiumi-native-clipboard",
    }
    metadata.update(copy.deepcopy(meta or {}))
    label: dict[str, Any] = {"timestamp": "$now"}
    if label_uid:
        label["user"] = {"unique_uid": label_uid}
    return {
        "$schema": SCHEMA_URL,
        "format": "xiumi-native-clipboard",
        "formatVersion": 1,
        "meta": metadata,
        "clipboard": {
            "refreshLabelTimestamp": True,
            "formats": [
                {
                    "mime": COMPS_MIME,
                    "encoding": "json",
                    "data": {
                        "version": 5,
                        "deskVersion": 5,
                        "type": "paper",
                        "category": "comp",
                        "pageRuntimeKey": -1,
                        "_comp": {"style": None},
                        "slices": list(slices),
                    },
                },
                {"mime": LABEL_MIME, "encoding": "json", "data": label},
            ],
        },
    }


def save_document(value: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
