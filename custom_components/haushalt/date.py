"""Datumsfelder des Formulars 'Neue Aufgabe'."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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
            FormularDatum(manager, "datum", "mdi:calendar-start", heute=False),
            FormularDatum(manager, "zuletzt", "mdi:calendar-check", heute=True),
        ]
    )
    if manager.gefrierer is not None:
        async_add_entities(
            [
                GefriererDatum(manager, "eingefroren", "mdi:calendar-today"),
                GefriererDatum(manager, "haltbar_datum", "mdi:calendar-end"),
            ]
        )


class FormularDatum(FormularEntity, DateEntity):
    def __init__(self, manager, feld: str, icon: str, heute: bool) -> None:
        self._formular_init(manager, "date", feld)
        self._feld = feld
        self._attr_icon = icon
        # 'Zuletzt erledigt' zeigt heute an, solange nichts gewählt ist
        self._heute = heute

    @property
    def native_value(self) -> date | None:
        wert = getattr(self.formular, self._feld)
        if wert is None and self._heute:
            return dt_util.now().date()
        return wert

    async def async_set_value(self, value: date) -> None:
        setattr(self.formular, self._feld, value)
        self.async_write_ha_state()


class GefriererDatum(GefriererEntity, DateEntity):
    def __init__(self, manager, feld: str, icon: str) -> None:
        super().__init__(manager, "date", feld)
        self._attr_icon = icon

    @property
    def native_value(self) -> date | None:
        if self._feld == "eingefroren":
            return self.formular.eingefroren_am
        return getattr(self.formular, self._feld)

    async def async_set_value(self, value: date) -> None:
        self._setzen(value)
