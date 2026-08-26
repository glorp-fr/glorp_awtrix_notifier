"""Pure MQTT payload construction. No Home Assistant dependency.

Same JSON shape the existing `script.awtrix_custom` / `script.awtrix_remove`
scripts already publish. The topic embeds a slug of the rule name so each
rule owns its own Awtrix "custom app" and never collides with another rule
targeting the same display.
"""

from __future__ import annotations

import re

from .models import Rule, Target

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    return slug or "_"


def _topic(rule: Rule, target: Target) -> str:
    return f"{target.mqtt_prefix}/custom/{slugify(rule.name)}"


def build_show_payload(rule: Rule, target: Target, rendered_text: str, rendered_icon: str) -> tuple[str, dict]:
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
