"""Sensoren: Status pro Aufgabe und eine Gesamtliste für das Display."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .entity import AufgabeEntity, HaushaltEntity
from .logic import Status


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities([ListeSensor(manager, entry.entry_id)])
    for aufgabe_id, aufgabe in manager.aufgaben.items():
        sensoren: list[SensorEntity] = [AufgabeSensor(manager, aufgabe_id)]
        if aufgabe.staubsauger:
            sensoren.append(SaugstartSensor(manager, aufgabe_id))
        async_add_entities(sensoren, config_subentry_id=aufgabe_id)


class AufgabeSensor(AufgabeEntity, SensorEntity):
    """Zeigt, wann eine Aufgabe fällig ist, z.B. 'in 4 Tagen'."""

    _attr_translation_key = "faelligkeit"

    def __init__(self, manager, aufgabe_id: str) -> None:
        super().__init__(manager, aufgabe_id)
        self._attr_unique_id = f"{aufgabe_id}_faelligkeit"

    @property
    def _status(self) -> Status:
        return self.manager.stati[self.aufgabe_id]

    @property
    def native_value(self) -> str:
        return self._status.text

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._status
        return {
            "typ": s.aufgabe.typ,
            "faellig_am": s.datum.isoformat() if s.datum else None,
            "tage": s.tage,
            "gruppe": s.gruppe,
            "ueberfaellig": s.ueberfaellig,
            "sichtbar": s.sichtbar,
            "aufgabe_id": self.aufgabe_id,
            "staubsauger": s.aufgabe.staubsauger,
        }


class SaugstartSensor(AufgabeEntity, SensorEntity):
    """Zeitpunkt, zu dem der Staubsauger startet. Leer, wenn nichts geplant ist."""

    _attr_translation_key = "saugstart"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:robot-vacuum"

    def __init__(self, manager, aufgabe_id: str) -> None:
        super().__init__(manager, aufgabe_id)
        self._attr_unique_id = f"{aufgabe_id}_saugstart"

    @property
    def native_value(self) -> datetime | None:
        return self.manager.saugstart(self.aufgabe_id)


class ListeSensor(HaushaltEntity, SensorEntity):
    """Anzahl sichtbarer Aufgaben, mit der fertigen Liste als Attribute."""

    _attr_translation_key = "liste"
    _attr_icon = "mdi:broom"
    _attr_native_unit_of_measurement = "Aufgaben"

    def __init__(self, manager, entry_id: str) -> None:
        super().__init__(manager)
        self._attr_unique_id = f"{entry_id}_liste"

    @property
    def native_value(self) -> int:
        return sum(1 for s in self.manager.stati.values() if s.sichtbar)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sichtbar = sorted(
            (s for s in self.manager.stati.values() if s.sichtbar),
            key=Status.sortierschluessel,
        )
        return {
            "aufgaben": [
                {
                    "aufgabe_id": s.aufgabe.id,
                    "name": s.aufgabe.name,
                    "gruppe": s.gruppe,
                    "text": s.text,
                    "ueberfaellig": s.ueberfaellig,
                    "startzeit_auswahl": s.aufgabe.staubsauger is not None,
                }
                for s in sichtbar
            ],
            "anzeige": self.manager.anzeige,
        }
