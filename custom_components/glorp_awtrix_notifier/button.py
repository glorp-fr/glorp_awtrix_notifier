"""Per-rule test buttons: force a show/clear cycle on demand, to ease testing."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import TriggerSide


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtimes = hass.data[DOMAIN][entry.entry_id]
    for subentry_id, runtime in runtimes.items():
        async_add_entities(
            [
                _TestButton(subentry_id, runtime, side=TriggerSide.SHOW, translation_key="tester_affichage"),
                _TestButton(subentry_id, runtime, side=TriggerSide.CLEAR, translation_key="tester_effacement"),
            ],
            config_subentry_id=subentry_id,
        )


class _TestButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, subentry_id: str, runtime, *, side: TriggerSide, translation_key: str) -> None:
        self._runtime = runtime
        self._side = side
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, subentry_id)}, name=runtime.rule.name)
        self._attr_unique_id = f"{subentry_id}_{translation_key}"

    async def async_press(self) -> None:
        await self._runtime.async_force(self._side)
