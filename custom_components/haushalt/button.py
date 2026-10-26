"""Knopf 'Erledigt' pro Aufgabe."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .entity import AufgabeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for aufgabe_id in manager.aufgaben:
        async_add_entities(
            [ErledigtButton(manager, aufgabe_id)], config_subentry_id=aufgabe_id
        )


class ErledigtButton(AufgabeEntity, ButtonEntity):
    """Hakt die Aufgabe ab."""

    _attr_translation_key = "erledigt"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, manager, aufgabe_id: str) -> None:
        super().__init__(manager, aufgabe_id)
        self._attr_unique_id = f"{aufgabe_id}_erledigt"

    async def async_press(self) -> None:
        await self.manager.async_erledigt(self.aufgabe_id)
