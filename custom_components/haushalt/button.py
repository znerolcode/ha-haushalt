"""Knopf 'Erledigt' pro Aufgabe."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .entity import AufgabeEntity
from .formular import FormularEntity, async_aufgabe_anlegen
from .gefrierer_formular import GefriererEntity, gewaehlter_artikel


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities([AnlegenButton(manager)])
    if manager.gefrierer is not None:
        async_add_entities(
            [
                EinfrierenButton(manager, "button", "einfrieren"),
                EntnehmenButton(manager, "button", "entnehmen"),
            ]
        )
    for aufgabe_id in manager.aufgaben:
        async_add_entities(
            [ErledigtButton(manager, aufgabe_id)], config_subentry_id=aufgabe_id
        )


class ErledigtButton(AufgabeEntity, ButtonEntity):
    """Hakt die Aufgabe ab."""

    _attr_icon = "mdi:check-circle-outline"
    _attr_translation_key = "erledigt"

    def __init__(self, manager, aufgabe_id: str) -> None:
        super().__init__(manager, aufgabe_id)
        self._attr_unique_id = f"{aufgabe_id}_erledigt"

    async def async_press(self) -> None:
        await self.manager.async_erledigt(self.aufgabe_id)


class AnlegenButton(FormularEntity, ButtonEntity):
    """Legt die Aufgabe aus dem Formular 'Neue Aufgabe' an."""

    _attr_icon = "mdi:plus-circle-outline"

    def __init__(self, manager) -> None:
        self._formular_init(manager, "button", "anlegen")

    async def async_press(self) -> None:
        await async_aufgabe_anlegen(self.manager)


class EinfrierenButton(GefriererEntity, ButtonEntity):
    _attr_icon = "mdi:snowflake-variant"

    async def async_press(self) -> None:
        f = self.formular
        await self.manager.async_einfrieren(
            f.name, f.kategorie, f.menge, f.einheit, f.eingefroren_am,
            f.haltbar_datum, f.haltbar_anzahl, f.haltbar_einheit, f.haltbarkeit,
        )
        f.einfrieren_leeren()
        self.manager.aktualisieren()


class EntnehmenButton(GefriererEntity, ButtonEntity):
    _attr_icon = "mdi:minus-circle-outline"

    async def async_press(self) -> None:
        key = gewaehlter_artikel(self.manager)
        if key is None:
            return
        await self.manager.async_entnehmen(key, self.formular.entnahme)
        self.formular.entnahme = 1
        self.manager.aktualisieren()
