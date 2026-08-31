"""Glorp's Awtrix Notifier integration.

Deliberately keeps this module import-safe without Home Assistant installed
(only `.const` and `.models` are imported at module load time) so the pure
decision/publisher logic stays unit-testable without a full HA environment.
Everything else is imported inside the functions that need it.
"""

from __future__ import annotations

import logging
from datetime import time
from typing import TYPE_CHECKING

from .const import (
    CONF_AT,
    CONF_CLEAR_CONDITION,
    CONF_CLEAR_TRIGGERS,
    CONF_COLOR,
    CONF_CONDITION_OP,
    CONF_CONDITION_VALUE,
    CONF_EFFECT,
    CONF_ENTITY_ID,
    CONF_FIRMWARE_TYPE,
    CONF_HOLD,
    CONF_ICON_TEMPLATE,
    CONF_INTERVAL_MINUTES,
    CONF_MQTT_PREFIX,
    CONF_NAME,
    CONF_REPEAT,
    CONF_SHOW_CONDITION,
    CONF_SHOW_TRIGGERS,
    CONF_TARGET_NAMES,
    CONF_TEXT_TEMPLATE,
    CONF_TRIGGER_KIND,
    CONF_WEEKDAYS,
    DEFAULT_FIRMWARE_TYPE,
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_RULE,
    SUBENTRY_TYPE_TARGET,
)
from .models import ComparisonOp, Condition, Rule, Target, Trigger, TriggerKind

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _target_from_subentry(subentry: "ConfigSubentry") -> Target:
    return Target(
        name=subentry.data[CONF_NAME],
        mqtt_prefix=subentry.data[CONF_MQTT_PREFIX],
        firmware_type=subentry.data.get(CONF_FIRMWARE_TYPE, DEFAULT_FIRMWARE_TYPE),
    )


def _trigger_from_dict(data: dict) -> Trigger:
    at_str = data.get(CONF_AT)
    return Trigger(
        kind=TriggerKind(data[CONF_TRIGGER_KIND]),
        interval_minutes=data.get(CONF_INTERVAL_MINUTES),
        at=time.fromisoformat(at_str) if at_str else None,
        weekdays=data.get(CONF_WEEKDAYS) or [],
        entity_id=data.get(CONF_ENTITY_ID),
    )


def _condition_from_dict(data: dict | None) -> Condition | None:
    if data is None:
        return None
    return Condition(entity_id=data[CONF_ENTITY_ID], op=ComparisonOp(data[CONF_CONDITION_OP]), value=data[CONF_CONDITION_VALUE])


def _rule_from_subentry(subentry: "ConfigSubentry") -> Rule:
    data = subentry.data
    return Rule(
        name=data[CONF_NAME],
        target_names=list(data[CONF_TARGET_NAMES]),
        show_triggers=[_trigger_from_dict(t) for t in data[CONF_SHOW_TRIGGERS]],
        text_template=data[CONF_TEXT_TEMPLATE],
        icon_template=data[CONF_ICON_TEMPLATE],
        show_condition=_condition_from_dict(data.get(CONF_SHOW_CONDITION)),
        color=data[CONF_COLOR],
        effect=data[CONF_EFFECT],
        hold=data[CONF_HOLD],
        repeat=data[CONF_REPEAT],
        clear_triggers=[_trigger_from_dict(t) for t in data.get(CONF_CLEAR_TRIGGERS, [])],
        clear_condition=_condition_from_dict(data.get(CONF_CLEAR_CONDITION)),
    )


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up Glorp's Awtrix Notifier from a config entry."""
    from .runtime import RuleRuntime

    targets_by_name = {
        subentry.data[CONF_NAME]: _target_from_subentry(subentry)
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_TARGET
    }

    runtimes: dict[str, RuleRuntime] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_RULE:
            continue
        rule = _rule_from_subentry(subentry)
        targets = [targets_by_name[name] for name in rule.target_names if name in targets_by_name]
        missing = set(rule.target_names) - targets_by_name.keys()
        if missing:
            _LOGGER.warning(
                "Rule '%s' references missing target(s) %s; it will run with the remaining targets only",
                rule.name,
                sorted(missing),
            )
        if not targets:
            _LOGGER.warning("Rule '%s' has no valid target left; it will not be started", rule.name)
            continue
        runtime = RuleRuntime(hass, rule, targets)
        runtime.async_start()
        runtimes[subentry.subentry_id] = runtime

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = runtimes

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtimes = hass.data[DOMAIN].pop(entry.entry_id)
        for runtime in runtimes.values():
            runtime.async_stop()
    return unload_ok


async def _async_update_listener(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    """Reload the entry when its subentries (targets/rules) change."""
    await hass.config_entries.async_reload(entry.entry_id)
