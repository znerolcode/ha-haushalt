"""Wochentage im Formular 'Neue Aufgabe', je ein Schalter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .const import WOCHENTAGE
from .formular import FormularEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities([FormularWochentag(manager, tag) for tag in WOCHENTAGE])


class FormularWochentag(FormularEntity, SwitchEntity):
    def __init__(self, manager, tag: str) -> None:
        self._formular_init(manager, "switch", tag)
        self._tag = tag

    @property
    def is_on(self) -> bool:
        return self._tag in self.formular.wochentage

    @property
    def icon(self) -> str:
        # Im Dashboard sieht man so auf einen Blick, welche Tage gewählt sind
        if self.is_on:
            return "mdi:checkbox-marked-circle"
        return "mdi:checkbox-blank-circle-outline"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.formular.wochentage.add(self._tag)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.formular.wochentage.discard(self._tag)
        self.async_write_ha_state()
