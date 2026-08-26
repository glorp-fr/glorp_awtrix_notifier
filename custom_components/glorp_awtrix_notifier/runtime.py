"""Per-rule runtime: wires triggers, drives decide/render/publish, tracks diagnostics."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import REASON_TEMPLATE_ERROR_PREFIX
from .decision import decide
from .models import Action, Rule, Target, TriggerSide
from .publisher import build_clear_payload, build_show_payload
from .render import async_render_rule
from .triggers import async_track_rule

_LOGGER = logging.getLogger(__name__)


class RuleRuntime:
    """Owns one rule's listeners and its diagnostic state (last action/reason/send time)."""

    def __init__(self, hass: HomeAssistant, rule: Rule, targets: list[Target]) -> None:
        self.hass = hass
        self.rule = rule
        self.targets = targets
        self.last_action: Action | None = None
        self.last_reason: str | None = None
        self.last_sent: datetime | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._listeners: list[Callable[[], None]] = []

    def register_listener(self, listener: Callable[[], None]) -> None:
        """Register a callback invoked after every decision cycle (used by sensors)."""
        self._listeners.append(listener)

    def async_start(self) -> None:
        self._unsubs = async_track_rule(self.hass, self.rule, self._on_show, self._on_clear)

    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    def _on_show(self) -> None:
        self.hass.async_create_task(self._async_handle(TriggerSide.SHOW))

    def _on_clear(self) -> None:
        self.hass.async_create_task(self._async_handle(TriggerSide.CLEAR))

    async def _async_handle(self, side: TriggerSide) -> None:
        inputs = self._resolve_condition_inputs()
        action, reason = decide(self.rule, inputs, side)

        if action is Action.SHOW:
            await self._async_show(reason)
        elif action is Action.CLEAR:
            await self._async_clear(reason)
        else:
            self._update(action, reason)

    async def _async_show(self, reason: str) -> None:
        result = await async_render_rule(self.hass, self.rule)
        if result.error is not None:
            self._update(Action.NONE, f"{REASON_TEMPLATE_ERROR_PREFIX}:{result.error}")
            return
        for target in self.targets:
            topic, payload = build_show_payload(self.rule, target, result.text, result.icon)
            await self._async_publish(topic, payload)
        self._update(Action.SHOW, reason)

    async def _async_clear(self, reason: str) -> None:
        for target in self.targets:
            topic, payload = build_clear_payload(self.rule, target)
            await self._async_publish(topic, payload)
        self._update(Action.CLEAR, reason)

    async def _async_publish(self, topic: str, payload: dict) -> None:
        await self.hass.services.async_call(
            "mqtt", "publish", {"topic": topic, "payload": json.dumps(payload)}, blocking=True
        )

    def _resolve_condition_inputs(self) -> dict[str, str | None]:
        inputs: dict[str, str | None] = {}
        for condition in (self.rule.show_condition, self.rule.clear_condition):
            if condition is None:
                continue
            state = self.hass.states.get(condition.entity_id)
            inputs[condition.entity_id] = state.state if state is not None else None
        return inputs

    def _update(self, action: Action, reason: str) -> None:
        self.last_action = action
        self.last_reason = reason
        if action is not Action.NONE:
            self.last_sent = dt_util.utcnow()
        for listener in self._listeners:
            listener()
