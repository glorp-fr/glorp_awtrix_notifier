"""Config flow for Glorp's Awtrix Notifier.

The main flow only checks that MQTT is set up (everything is published
through the `mqtt.publish` service) and creates the single config entry.
Targets and rules are then managed entirely as subentries, added/edited from
the integration's "..." menu in Settings -> Devices & services.

The rule subentry flow is a small wizard rather than one giant form: a
target must exist before a rule can reference it, and each show/clear
trigger has different fields depending on its kind, so the fields shown
genuinely depend on earlier answers.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AT,
    CONF_CLEAR_CONDITION,
    CONF_CLEAR_TRIGGERS,
    CONF_COLOR,
    CONF_CONDITION_OP,
    CONF_CONDITION_VALUE,
    CONF_EFFECT,
    CONF_ENTITY_ID,
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
    DEFAULT_COLOR,
    DEFAULT_EFFECT,
    DEFAULT_HOLD,
    DEFAULT_REPEAT,
    DOMAIN,
    SUBENTRY_TYPE_RULE,
    SUBENTRY_TYPE_TARGET,
    WEEKDAYS,
)
from .publisher import slugify

MAX_TRIGGERS = 3

_TRIGGER_KIND_OPTIONS = ["interval", "time_of_day", "entity_change"]
_CONDITION_OP_OPTIONS = ["above", "below", "equals"]


def _optional_marker(key: str, existing_value: Any) -> vol.Optional:
    """vol.Optional for a selector field with no meaningful empty value.

    Selectors like EntitySelector/SelectSelector reject `None` outright, so a
    bare `vol.Optional(key, default=None)` would make the *whole schema*
    reject an empty submission instead of letting the field be skipped.
    Only pass a default when there is a real value to pre-fill.
    """
    if existing_value:
        return vol.Optional(key, default=existing_value)
    return vol.Optional(key)


def _target_schema(*, name_default: str = "", prefix_default: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name_default): selector.TextSelector(),
            vol.Required(CONF_MQTT_PREFIX, default=prefix_default): selector.TextSelector(),
        }
    )


class AwtrixNotifierConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the (single) config flow for Glorp's Awtrix Notifier."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if "mqtt" not in self.hass.config.components:
            return self.async_abort(reason="mqtt_not_configured")
        return self.async_create_entry(title="Glorp's Awtrix Notifier", data={})

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_TYPE_TARGET: TargetSubentryFlow,
            SUBENTRY_TYPE_RULE: RuleSubentryFlow,
        }


class TargetSubentryFlow(ConfigSubentryFlow):
    """Add or edit a Target subentry: a friendly name plus an MQTT prefix."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step(user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step(user_input)

    async def _async_step(self, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        is_reconfigure = self.source == SOURCE_RECONFIGURE
        current_subentry = self._get_reconfigure_subentry() if is_reconfigure else None
        current_subentry_id = current_subentry.subentry_id if current_subentry else None

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            prefix = user_input[CONF_MQTT_PREFIX].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not prefix:
                errors[CONF_MQTT_PREFIX] = "mqtt_prefix_required"
            elif self._prefix_in_use(prefix, exclude_subentry_id=current_subentry_id):
                errors[CONF_MQTT_PREFIX] = "mqtt_prefix_already_used"
            else:
                data = {CONF_NAME: name, CONF_MQTT_PREFIX: prefix}
                if is_reconfigure:
                    return self.async_update_and_abort(self._get_entry(), current_subentry, title=name, data=data)
                return self.async_create_entry(title=name, data=data)

        defaults = current_subentry.data if current_subentry else {}
        schema = _target_schema(
            name_default=defaults.get(CONF_NAME, ""), prefix_default=defaults.get(CONF_MQTT_PREFIX, "")
        )
        return self.async_show_form(
            step_id="reconfigure" if is_reconfigure else "user", data_schema=schema, errors=errors
        )

    def _prefix_in_use(self, prefix: str, *, exclude_subentry_id: str | None) -> bool:
        entry = self._get_entry()
        for subentry in entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_TYPE_TARGET:
                continue
            if subentry.subentry_id == exclude_subentry_id:
                continue
            if subentry.data.get(CONF_MQTT_PREFIX) == prefix:
                return True
        return False


class RuleSubentryFlow(ConfigSubentryFlow):
    """Add or edit a Rule subentry: trigger(s), condition, content, target(s)."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {
            CONF_NAME: "",
            CONF_TARGET_NAMES: [],
            CONF_SHOW_TRIGGERS: [],
            CONF_SHOW_CONDITION: None,
            CONF_TEXT_TEMPLATE: "",
            CONF_ICON_TEMPLATE: "",
            CONF_COLOR: DEFAULT_COLOR,
            CONF_EFFECT: DEFAULT_EFFECT,
            CONF_HOLD: DEFAULT_HOLD,
            CONF_REPEAT: DEFAULT_REPEAT,
            CONF_CLEAR_TRIGGERS: [],
            CONF_CLEAR_CONDITION: None,
        }
        self._configure_clear = False

    # -- entry points -----------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self.async_step_basics(user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if not user_input:
            subentry = self._get_reconfigure_subentry()
            self._data = dict(subentry.data)
            self._configure_clear = bool(self._data[CONF_CLEAR_TRIGGERS] or self._data[CONF_CLEAR_CONDITION])
        return await self.async_step_basics(user_input)

    # -- step 1: name + targets --------------------------------------------

    async def async_step_basics(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        target_names = self._existing_target_names()
        if not target_names:
            return self.async_abort(reason="no_targets")

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            targets = user_input[CONF_TARGET_NAMES]
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not targets:
                errors[CONF_TARGET_NAMES] = "at_least_one_target_required"
            else:
                self._data[CONF_NAME] = name
                self._data[CONF_TARGET_NAMES] = targets
                self._data[CONF_SHOW_TRIGGERS] = []
                return await self.async_step_show_trigger()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self._data[CONF_NAME]): selector.TextSelector(),
                vol.Required(CONF_TARGET_NAMES, default=self._data[CONF_TARGET_NAMES]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=target_names, multiple=True, mode=selector.SelectSelectorMode.LIST
                    )
                ),
            }
        )
        return self.async_show_form(step_id="basics", data_schema=schema, errors=errors)

    # -- step 2: show trigger(s), one at a time ----------------------------

    async def async_step_show_trigger(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_trigger(
            user_input, step_id="show_trigger", triggers_key=CONF_SHOW_TRIGGERS, more_step="show_trigger_more"
        )

    async def async_step_show_trigger_more(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_trigger_more(
            user_input,
            step_id="show_trigger_more",
            triggers_key=CONF_SHOW_TRIGGERS,
            add_another_step="show_trigger",
            done_step="show_condition",
        )

    # -- step 3: show condition (optional) ---------------------------------

    async def async_step_show_condition(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_condition(
            user_input, step_id="show_condition", condition_key=CONF_SHOW_CONDITION, next_step="content"
        )

    # -- step 4: content ----------------------------------------------------

    async def async_step_content(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            self._data[CONF_TEXT_TEMPLATE] = user_input[CONF_TEXT_TEMPLATE]
            self._data[CONF_ICON_TEMPLATE] = user_input[CONF_ICON_TEMPLATE]
            self._data[CONF_COLOR] = user_input[CONF_COLOR]
            self._data[CONF_EFFECT] = user_input[CONF_EFFECT]
            self._data[CONF_HOLD] = user_input[CONF_HOLD]
            self._data[CONF_REPEAT] = int(user_input[CONF_REPEAT])
            return await self.async_step_clear_intro()

        schema = vol.Schema(
            {
                vol.Required(CONF_TEXT_TEMPLATE, default=self._data[CONF_TEXT_TEMPLATE]): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
                vol.Required(CONF_ICON_TEMPLATE, default=self._data[CONF_ICON_TEMPLATE]): selector.TextSelector(),
                vol.Required(CONF_COLOR, default=self._data[CONF_COLOR]): selector.TextSelector(),
                vol.Optional(CONF_EFFECT, default=self._data[CONF_EFFECT]): selector.TextSelector(),
                vol.Required(CONF_HOLD, default=self._data[CONF_HOLD]): selector.BooleanSelector(),
                vol.Required(CONF_REPEAT, default=self._data[CONF_REPEAT]): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-1, max=3600, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="content", data_schema=schema)

    # -- step 5: whether to configure a clear rule at all -------------------

    async def async_step_clear_intro(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            self._configure_clear = user_input["configure_clear"]
            if not self._configure_clear:
                self._data[CONF_CLEAR_TRIGGERS] = []
                self._data[CONF_CLEAR_CONDITION] = None
                return await self.async_step_finish()
            self._data[CONF_CLEAR_TRIGGERS] = []
            return await self.async_step_clear_trigger()

        schema = vol.Schema({vol.Required("configure_clear", default=self._configure_clear): selector.BooleanSelector()})
        return self.async_show_form(step_id="clear_intro", data_schema=schema)

    # -- step 6: clear trigger(s), one at a time ----------------------------

    async def async_step_clear_trigger(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_trigger(
            user_input, step_id="clear_trigger", triggers_key=CONF_CLEAR_TRIGGERS, more_step="clear_trigger_more"
        )

    async def async_step_clear_trigger_more(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_trigger_more(
            user_input,
            step_id="clear_trigger_more",
            triggers_key=CONF_CLEAR_TRIGGERS,
            add_another_step="clear_trigger",
            done_step="clear_condition",
        )

    # -- step 7: clear condition (optional) ----------------------------------

    async def async_step_clear_condition(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._async_step_condition(
            user_input, step_id="clear_condition", condition_key=CONF_CLEAR_CONDITION, next_step="finish"
        )

    # -- step 8: commit -------------------------------------------------------

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        name = self._data[CONF_NAME]
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(self._get_entry(), self._get_reconfigure_subentry(), title=name, data=self._data)
        return self.async_create_entry(title=name, data=self._data, unique_id=slugify(name))

    # -- shared trigger loop implementation -----------------------------------

    async def _async_step_trigger(
        self, user_input: dict[str, Any] | None, *, step_id: str, triggers_key: str, more_step: str
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            kind = user_input[CONF_TRIGGER_KIND]
            trigger = {
                CONF_TRIGGER_KIND: kind,
                CONF_INTERVAL_MINUTES: user_input.get(CONF_INTERVAL_MINUTES),
                CONF_AT: user_input.get(CONF_AT),
                CONF_WEEKDAYS: user_input.get(CONF_WEEKDAYS, []),
                CONF_ENTITY_ID: user_input.get(CONF_ENTITY_ID),
            }
            if kind == "interval" and not trigger[CONF_INTERVAL_MINUTES]:
                errors[CONF_INTERVAL_MINUTES] = "interval_minutes_required"
            elif kind == "time_of_day" and not trigger[CONF_AT]:
                errors[CONF_AT] = "at_required"
            elif kind == "entity_change" and not trigger[CONF_ENTITY_ID]:
                errors[CONF_ENTITY_ID] = "entity_id_required"
            else:
                self._data[triggers_key] = [*self._data[triggers_key], trigger]
                return await getattr(self, f"async_step_{more_step}")()

        schema = vol.Schema(
            {
                vol.Required(CONF_TRIGGER_KIND): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_TRIGGER_KIND_OPTIONS,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_TRIGGER_KIND,
                    )
                ),
                vol.Optional(CONF_INTERVAL_MINUTES): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=1440, step=1, unit_of_measurement="min")
                ),
                vol.Optional(CONF_AT): selector.TimeSelector(),
                vol.Optional(CONF_WEEKDAYS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=WEEKDAYS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_WEEKDAYS,
                    )
                ),
                vol.Optional(CONF_ENTITY_ID): selector.EntitySelector(),
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def _async_step_trigger_more(
        self, user_input: dict[str, Any] | None, *, step_id: str, triggers_key: str, add_another_step: str, done_step: str
    ) -> SubentryFlowResult:
        if user_input is not None:
            if user_input["add_another"] and len(self._data[triggers_key]) < MAX_TRIGGERS:
                return await getattr(self, f"async_step_{add_another_step}")()
            return await getattr(self, f"async_step_{done_step}")()

        can_add_more = len(self._data[triggers_key]) < MAX_TRIGGERS
        schema = vol.Schema({vol.Required("add_another", default=False): selector.BooleanSelector()})
        if not can_add_more:
            return await getattr(self, f"async_step_{done_step}")()
        return self.async_show_form(step_id=step_id, data_schema=schema)

    # -- shared condition step implementation ---------------------------------

    async def _async_step_condition(
        self, user_input: dict[str, Any] | None, *, step_id: str, condition_key: str, next_step: str
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input.get(CONF_ENTITY_ID)
            if not entity_id:
                self._data[condition_key] = None
            else:
                op = user_input.get(CONF_CONDITION_OP)
                value = user_input.get(CONF_CONDITION_VALUE)
                if not op:
                    errors[CONF_CONDITION_OP] = "op_required"
                elif not value:
                    errors[CONF_CONDITION_VALUE] = "value_required"
                else:
                    self._data[condition_key] = {
                        CONF_ENTITY_ID: entity_id,
                        CONF_CONDITION_OP: op,
                        CONF_CONDITION_VALUE: value,
                    }
            if not errors:
                return await getattr(self, f"async_step_{next_step}")()

        existing = self._data.get(condition_key) or {}
        schema = vol.Schema(
            {
                _optional_marker(CONF_ENTITY_ID, existing.get(CONF_ENTITY_ID)): selector.EntitySelector(),
                _optional_marker(CONF_CONDITION_OP, existing.get(CONF_CONDITION_OP)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_CONDITION_OP_OPTIONS,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_CONDITION_OP,
                    )
                ),
                _optional_marker(CONF_CONDITION_VALUE, existing.get(CONF_CONDITION_VALUE)): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    def _existing_target_names(self) -> list[str]:
        entry = self._get_entry()
        return [
            subentry.data[CONF_NAME]
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_TARGET
        ]
