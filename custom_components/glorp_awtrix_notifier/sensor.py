"""Diagnostic sensors: one device per rule, tracking its last action/reason/send time."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtimes = hass.data[DOMAIN][entry.entry_id]
    for subentry_id, runtime in runtimes.items():
        async_add_entities(
            [
                LastActionSensor(subentry_id, runtime),
                ReasonSensor(subentry_id, runtime),
                LastSentSensor(subentry_id, runtime),
            ],
            config_subentry_id=subentry_id,
        )


class _RuleSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, subentry_id: str, runtime) -> None:
        self._runtime = runtime
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, subentry_id)}, name=runtime.rule.name)
        self._attr_unique_id = f"{subentry_id}_{self._attr_translation_key}"

    async def async_added_to_hass(self) -> None:
        self._runtime.register_listener(self.async_write_ha_state)


class LastActionSensor(_RuleSensor):
    _attr_translation_key = "derniere_action"

    @property
    def native_value(self) -> str | None:
        action = self._runtime.last_action
        return action.value if action is not None else None


class ReasonSensor(_RuleSensor):
    _attr_translation_key = "raison"

    @property
    def native_value(self) -> str | None:
        return self._runtime.last_reason


class LastSentSensor(_RuleSensor):
    _attr_translation_key = "dernier_envoi"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return self._runtime.last_sent
