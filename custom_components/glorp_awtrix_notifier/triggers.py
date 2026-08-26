"""HA listener wiring for a rule's show/clear triggers and conditions.

Any entity referenced by a show/clear *condition* is also tracked here as an
implicit entity-change trigger, on top of whatever triggers were explicitly
configured, so the rule reacts immediately when the condition's entity
changes instead of waiting for the next scheduled/interval trigger.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)

from .const import WEEKDAYS
from .models import Rule, Trigger, TriggerKind

UnsubType = Callable[[], None]


def async_track_rule(hass: HomeAssistant, rule: Rule, on_show: Callable[[], None], on_clear: Callable[[], None]) -> list[UnsubType]:
    """Wire up every listener for one rule. Returns the unsub callables."""
    unsubs: list[UnsubType] = []

    for trigger in rule.show_triggers:
        unsubs.append(_async_track_trigger(hass, trigger, on_show))
    if rule.show_condition is not None:
        unsubs.append(
            async_track_state_change_event(hass, [rule.show_condition.entity_id], lambda event: on_show())
        )

    for trigger in rule.clear_triggers:
        unsubs.append(_async_track_trigger(hass, trigger, on_clear))
    if rule.clear_condition is not None:
        unsubs.append(
            async_track_state_change_event(hass, [rule.clear_condition.entity_id], lambda event: on_clear())
        )

    return unsubs


def _async_track_trigger(hass: HomeAssistant, trigger: Trigger, on_fire: Callable[[], None]) -> UnsubType:
    if trigger.kind is TriggerKind.INTERVAL:
        return async_track_time_interval(hass, lambda now: on_fire(), timedelta(minutes=trigger.interval_minutes))

    if trigger.kind is TriggerKind.TIME_OF_DAY:

        def _on_time(now: datetime) -> None:
            if trigger.weekdays and WEEKDAYS[now.weekday()] not in trigger.weekdays:
                return
            on_fire()

        return async_track_time_change(
            hass, _on_time, hour=trigger.at.hour, minute=trigger.at.minute, second=trigger.at.second
        )

    return async_track_state_change_event(hass, [trigger.entity_id], lambda event: on_fire())
