"""Gemeinsame Basis der Haushalt-Entitäten."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import HaushaltManager
from .const import DOMAIN


class HaushaltEntity(Entity):
    """Entität, die bei jeder Neuberechnung aktualisiert wird."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: HaushaltManager) -> None:
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.manager.signal, self._neu)
        )

    @callback
    def _neu(self) -> None:
        self.async_write_ha_state()


class AufgabeEntity(HaushaltEntity):
    """Entität, die zu einer einzelnen Aufgabe gehört."""

    def __init__(self, manager: HaushaltManager, aufgabe_id: str) -> None:
        super().__init__(manager)
        self.aufgabe_id = aufgabe_id
        aufgabe = manager.aufgaben[aufgabe_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, aufgabe_id)},
            name=aufgabe.name,
            manufacturer="Haushalt",
            model="Intervall-Aufgabe" if aufgabe.typ == "intervall" else "Termin-Aufgabe",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return self.aufgabe_id in self.manager.stati
