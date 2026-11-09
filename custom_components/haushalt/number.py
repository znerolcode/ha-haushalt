"""Zahlenfelder des Formulars 'Neue Aufgabe'."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
            FormularZahl(manager, "anzahl", "mdi:calendar-refresh", 0, 365),
            FormularZahl(manager, "mindestabstand", "mdi:arrow-expand-horizontal", 0, 60),
        ]
    )
    if manager.gefrierer is not None:
        async_add_entities(
            [
                GefriererZahl(manager, "menge", "mdi:counter"),
                GefriererZahl(manager, "haltbar_anzahl", "mdi:timer-sand"),
                GefriererZahl(manager, "entnahme", "mdi:minus-circle-outline"),
            ]
        )


class FormularZahl(FormularEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(self, manager, feld: str, icon: str, minimum: int, maximum: int) -> None:
        self._formular_init(manager, "number", feld)
        self._feld = feld
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> int:
        return getattr(self.formular, self._feld)

    async def async_set_native_value(self, value: float) -> None:
        setattr(self.formular, self._feld, int(value))
        self.async_write_ha_state()


class GefriererZahl(GefriererEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_min_value = 1
    _attr_native_max_value = 10000

    def __init__(self, manager, feld: str, icon: str) -> None:
        super().__init__(manager, "number", feld)
        self._attr_icon = icon

    @property
    def native_value(self) -> int:
        return getattr(self.formular, self._feld)

    async def async_set_native_value(self, value: float) -> None:
        self._setzen(int(value))
