"""Knöpfe pro Aufgabe: 'Erledigt' und, mit Staubsauger, die Startzeit-Auswahl."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .const import START_OPTIONEN
from .entity import AufgabeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for aufgabe_id, aufgabe in manager.aufgaben.items():
        knoepfe: list[ButtonEntity] = [ErledigtButton(manager, aufgabe_id)]
        if aufgabe.staubsauger:
            knoepfe += [
                ErledigtButton(manager, aufgabe_id, minuten)
                for minuten in START_OPTIONEN
                if minuten
            ]
            knoepfe.append(SaugstartAbbrechenButton(manager, aufgabe_id))
        async_add_entities(knoepfe, config_subentry_id=aufgabe_id)


class ErledigtButton(AufgabeEntity, ButtonEntity):
    """Hakt die Aufgabe ab. Mit Staubsauger: startet ihn nach `minuten`."""

    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, manager, aufgabe_id: str, minuten: int = 0) -> None:
        super().__init__(manager, aufgabe_id)
        self._minuten = minuten
        if minuten:
            self._attr_unique_id = f"{aufgabe_id}_erledigt_{minuten}"
            self._attr_translation_key = "erledigt_start_in"
            self._attr_translation_placeholders = {"minuten": str(minuten)}
            self._attr_icon = "mdi:robot-vacuum"
        else:
            self._attr_unique_id = f"{aufgabe_id}_erledigt"
            self._attr_translation_key = (
                "erledigt_sofort"
                if manager.aufgaben[aufgabe_id].staubsauger
                else "erledigt"
            )

    async def async_press(self) -> None:
        await self.manager.async_erledigt(self.aufgabe_id, self._minuten)


class SaugstartAbbrechenButton(AufgabeEntity, ButtonEntity):
    """Bricht einen geplanten Saugstart ab."""

    _attr_translation_key = "saugstart_abbrechen"
    _attr_icon = "mdi:timer-cancel-outline"

    def __init__(self, manager, aufgabe_id: str) -> None:
        super().__init__(manager, aufgabe_id)
        self._attr_unique_id = f"{aufgabe_id}_saugstart_abbrechen"

    async def async_press(self) -> None:
        await self.manager.async_saugstart_abbrechen(self.aufgabe_id)
