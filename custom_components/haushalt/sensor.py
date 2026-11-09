"""Sensoren: Status pro Aufgabe und eine Gesamtliste für das Display."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HaushaltConfigEntry
from .entity import AufgabeEntity, HaushaltEntity
from .formular import FormularEntity
from .logic import Status
from .gefrierer_formular import GefriererEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities([ListeSensor(manager, entry.entry_id), MeldungSensor(manager)])
    if manager.wetter is not None:
        async_add_entities([WetterSensor(manager, entry.entry_id)])
    if manager.gefrierer is not None:
        async_add_entities(
            [
                GefriererSensor(manager, entry.entry_id),
                GefriererMeldung(manager, "sensor", "meldung"),
                GefriererHaltbarBis(manager, "sensor", "haltbar_bis"),
            ]
        )
    for aufgabe_id in manager.aufgaben:
        async_add_entities(
            [AufgabeSensor(manager, aufgabe_id)], config_subentry_id=aufgabe_id
        )


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
        }


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
                }
                for s in sichtbar
            ],
            "anzeige": self.manager.anzeige,
            # Haushalt-Kachel auf dem Homescreen des Displays
            "kachel": self.manager.kachel,
            # Staubsauger-Zeile fürs Display, leer ohne Staubsauger
            "sauger": self.manager.sauger.anzeige if self.manager.sauger else "",
        }


class GefriererSensor(HaushaltEntity, SensorEntity):
    """Anzahl Artikel im Gefrierer, mit Liste, Display-Zeilen und Kachel als Attribute."""

    _attr_translation_key = "gefrierer"
    _attr_icon = "mdi:snowflake"
    _attr_native_unit_of_measurement = "Artikel"

    def __init__(self, manager, entry_id: str) -> None:
        super().__init__(manager)
        self._attr_unique_id = f"{entry_id}_gefrierer"
        # Fester Name, darauf verweisen Display und Dashboard-Vorlage
        self.entity_id = "sensor.gefrierer"

    @property
    def native_value(self) -> int:
        return len(self.manager.gefrierer.artikel())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        heute = dt_util.now().date()
        gefrierer = self.manager.gefrierer
        artikel = [a.info(heute) for a in gefrierer.artikel()]
        return {
            "artikel": artikel,
            "meal_prep": [a for a in artikel if a["meal_prep"]],
            "anzeige": gefrierer.anzeige(heute),
            "kachel": gefrierer.kachel(heute),
        }


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


class MeldungSensor(FormularEntity, SensorEntity):
    """Zuletzt über das Formular angelegte Aufgabe, als Bestätigung im Dashboard."""

    _attr_icon = "mdi:check"

    def __init__(self, manager) -> None:
        self._formular_init(manager, "sensor", "meldung")

    @property
    def native_value(self) -> str | None:
        return self.manager.formular_meldung.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"zeit": self.manager.formular_meldung.get("zeit")}


class GefriererMeldung(GefriererEntity, SensorEntity):
    """Zuletzt eingefroren oder entnommen, als Bestätigung im Dashboard."""

    _attr_icon = "mdi:check"

    @property
    def native_value(self) -> str | None:
        return self.manager.gefrierer.meldung.get("text")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"zeit": self.manager.gefrierer.meldung.get("zeit")}


class GefriererHaltbarBis(GefriererEntity, SensorEntity):
    """Haltbar bis, wie es das Formular gerade ausrechnet."""

    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return self.formular.vorschau()
