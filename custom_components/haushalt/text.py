"""Textfelder des Formulars 'Neue Aufgabe'."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .formular import FormularEntity
from .gefrierer_formular import GefriererEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            FormularText(manager, "name", "mdi:format-text", 60),
            FormularText(manager, "weitere", "mdi:calendar-multiple", 255),
        ]
    )
    if manager.gefrierer is not None:
        async_add_entities([GefriererName(manager, "text", "name")])


class FormularText(FormularEntity, TextEntity):
    _attr_native_min = 0

    def __init__(self, manager, feld: str, icon: str, laenge: int) -> None:
        self._formular_init(manager, "text", feld)
        self._feld = feld
        self._attr_icon = icon
        self._attr_native_max = laenge

    @property
    def native_value(self) -> str:
        return getattr(self.formular, self._feld)

    async def async_set_value(self, value: str) -> None:
        setattr(self.formular, self._feld, value)
        self.async_write_ha_state()


class GefriererName(GefriererEntity, TextEntity):
    _attr_native_min = 0
    _attr_native_max = 60
    _attr_icon = "mdi:format-text"

    @property
    def native_value(self) -> str:
        return self.formular.name

    async def async_set_value(self, value: str) -> None:
        self._setzen(value)
