"""Sensoren: Status pro Aufgabe und eine Gesamtliste für das Display."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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
    if manager.wetter is not None:
        async_add_entities([WetterSensor(manager, entry.entry_id)])
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
            "saugstart": self._naechster_saugstart(),
        }

    def _naechster_saugstart(self) -> str:
        """Uhrzeit des nächsten geplanten Saugstarts, z.B. '17:05', sonst leer."""
        starts = [
            zeit
            for aufgabe_id in self.manager.aufgaben
            if (zeit := self.manager.saugstart(aufgabe_id)) is not None
        ]
        if not starts:
            return ""
        return dt_util.as_local(min(starts)).strftime("%H:%M")


class WetterSensor(HaushaltEntity, SensorEntity):
    """Wetter fürs Display: heute und die nächsten 2 Tage, je Vormittag und Nachmittag."""

    _attr_translation_key = "wetter"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, manager, entry_id: str) -> None:
        super().__init__(manager)
        self._attr_unique_id = f"{entry_id}_wetter"

    @property
    def native_value(self) -> str | None:
        aktuell = self.manager.wetter.aktuell
        return aktuell.zustand if aktuell and aktuell.zustand else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        wetter = self.manager.wetter
        return {
            "wetter_entitaet": wetter.entity_id,
            "tage": [
                {
                    "tag": name,
                    "vormittag": asdict(vm) if vm else None,
                    "nachmittag": asdict(nm) if nm else None,
                }
                for name, vm, nm in wetter.tage
            ],
            "anzeige": wetter.anzeige,
        }
