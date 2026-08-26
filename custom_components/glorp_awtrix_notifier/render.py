"""Template rendering glue for a rule's text/icon fields. Requires Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from .models import Rule


@dataclass
class RenderResult:
    text: str | None
    icon: str | None
    error: str | None


async def async_render_rule(hass: HomeAssistant, rule: Rule) -> RenderResult:
    """Render a rule's text and icon templates.

    Any Jinja error is captured here and reported through `error` rather than
    raised, so a broken template becomes a diagnosable rule error instead of
    crashing the notification cycle.
    """
    try:
        text = Template(rule.text_template, hass).async_render()
    except TemplateError as err:
        return RenderResult(None, None, str(err))
    try:
        icon = Template(rule.icon_template, hass).async_render()
    except TemplateError as err:
        return RenderResult(None, None, str(err))
    return RenderResult(str(text), str(icon), None)
