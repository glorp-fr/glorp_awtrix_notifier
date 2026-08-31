"""Pure MQTT payload construction. No Home Assistant dependency.

Two Awtrix firmwares, two wire formats, picked per-target via `target.firmware_type`:

- "legacy" (Awtrix Light/3): same JSON shape the existing `script.awtrix_custom` /
  `script.awtrix_remove` scripts already publish, topic `{prefix}/custom/{slug}`.
- "ng" (Awtrix NG, a from-scratch rewrite): topic `{prefix}/cmd/apps/pushed/{slug}`,
  `color` renamed to `textColor` (hash-prefixed), no infinite repeat (-1 -> 0), no `hold`
  (NG documents it as notification-only, not for pushed apps), `pushIcon` replaced by
  `iconMode` (always "fixed" here, matching our constant pushIcon=0 on legacy — untested
  against real NG hardware, revisit if it turns out wrong).

The topic embeds a slug of the rule name so each rule owns its own Awtrix "app" and never
collides with another rule targeting the same display.
"""

from __future__ import annotations

import re

from .models import Rule, Target

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    return slug or "_"


def _topic(rule: Rule, target: Target) -> str:
    slug = slugify(rule.name)
    if target.firmware_type == "ng":
        return f"{target.mqtt_prefix}/cmd/apps/pushed/{slug}"
    return f"{target.mqtt_prefix}/custom/{slug}"


def _ng_color(color: str) -> str:
    return color if color.startswith("#") else f"#{color}"


def build_show_payload(rule: Rule, target: Target, rendered_text: str, rendered_icon: str) -> tuple[str, dict]:
    if target.firmware_type == "ng":
        payload = {
            "text": rendered_text,
            "icon": rendered_icon,
            "textColor": _ng_color(rule.color),
            "repeat": 0 if rule.repeat == -1 else rule.repeat,
            "effect": rule.effect,
            "iconMode": "fixed",
        }
        return _topic(rule, target), payload

    payload = {
        "text": rendered_text,
        "icon": rendered_icon,
        "color": rule.color,
        "repeat": rule.repeat,
        "effect": rule.effect,
        "hold": rule.hold,
    }
    return _topic(rule, target), payload


def build_clear_payload(rule: Rule, target: Target) -> tuple[str, dict]:
    return _topic(rule, target), {}
