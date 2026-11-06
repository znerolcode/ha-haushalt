"""Auswahlfelder des Formulars 'Neue Aufgabe'."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .const import FRIST_ABEND, FRIST_MORGEN, TYP_INTERVALL, TYP_TERMIN, TYP_WOCHENTAG
from .formular import FormularEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            FormularAuswahl(
                manager, "typ", "mdi:shape-outline",
                [TYP_INTERVALL, TYP_WOCHENTAG, TYP_TERMIN],
            ),
            FormularAuswahl(
                manager, "frist", "mdi:clock-outline", [FRIST_MORGEN, FRIST_ABEND]
            ),
        ]
    )


class FormularAuswahl(FormularEntity, SelectEntity):
    def __init__(self, manager, feld: str, icon: str, optionen: list[str]) -> None:
        self._formular_init(manager, "select", feld)
        self._feld = feld
        self._attr_icon = icon
        self._attr_options = optionen

    @property
    def current_option(self) -> str:
        return getattr(self.formular, self._feld)

    async def async_select_option(self, option: str) -> None:
        setattr(self.formular, self._feld, option)
        self.async_write_ha_state()
