"""Haushalt: wiederkehrende Aufgaben für Home Assistant."""

from __future__ import annotations

from datetime import date, time, timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AUFGABE_ID,
    CONF_ALLE_WOCHEN,
    CONF_DATEN,
    CONF_FRIST,
    CONF_STARTDATUM,
    CONF_TAGE,
    CONF_TYP,
    CONF_VORSCHAU,
    CONF_ZEIT_ABEND,
    CONF_ZEIT_MORGEN,
    CONF_ZULETZT,
    DEFAULT_VORSCHAU,
    DEFAULT_ZEIT_ABEND,
    DEFAULT_ZEIT_MORGEN,
    DOMAIN,
    FRIST_ABEND,
    SERVICE_ERLEDIGT,
    SIGNAL_UPDATE,
    SUBENTRY_AUFGABE,
    TYP_INTERVALL,
)
from .logic import (
    Aufgabe,
    Status,
    anzeige_zeilen,
    berechne_intervall,
    berechne_termin,
    naechster_termin,
    parse_daten,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]
STORAGE_VERSION = 1

type HaushaltConfigEntry = ConfigEntry[HaushaltManager]


def aufgabe_aus_subentry(subentry_id: str, title: str, data: dict) -> Aufgabe:
    start = data.get(CONF_STARTDATUM)
    return Aufgabe(
        id=subentry_id,
        name=title,
        typ=data[CONF_TYP],
        tage=int(data.get(CONF_TAGE, 7)),
        frist=data.get(CONF_FRIST, FRIST_ABEND),
        startdatum=date.fromisoformat(start) if start else None,
        alle_wochen=int(data.get(CONF_ALLE_WOCHEN, 0)),
        daten=parse_daten(data.get(CONF_DATEN)),
    )


class HaushaltManager:
    """Hält Aufgaben und den Erledigt-Zustand, rechnet den aktuellen Status aus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        # zuletzt: {aufgabe_id: iso-datum}, erledigt: {aufgabe_id: [iso-datum, ...]}
        self._daten: dict = {"zuletzt": {}, "erledigt": {}}
        self.aufgaben: dict[str, Aufgabe] = {}
        self.stati: dict[str, Status] = {}

    @property
    def signal(self) -> str:
        return SIGNAL_UPDATE.format(self.entry.entry_id)

    @property
    def _zeit_morgen(self) -> time:
        return time.fromisoformat(
            self.entry.options.get(CONF_ZEIT_MORGEN, DEFAULT_ZEIT_MORGEN)
        )

    @property
    def _zeit_abend(self) -> time:
        return time.fromisoformat(
            self.entry.options.get(CONF_ZEIT_ABEND, DEFAULT_ZEIT_ABEND)
        )

    @property
    def _vorschau(self) -> int:
        return int(self.entry.options.get(CONF_VORSCHAU, DEFAULT_VORSCHAU))

    async def async_laden(self) -> None:
        if gespeichert := await self._store.async_load():
            self._daten = gespeichert
        self._daten.setdefault("zuletzt", {})
        self._daten.setdefault("erledigt", {})

        heute = dt_util.now().date()
        for subentry in self.entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_AUFGABE:
                continue
            try:
                aufgabe = aufgabe_aus_subentry(
                    subentry.subentry_id, subentry.title, dict(subentry.data)
                )
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Aufgabe %s ungültig: %s", subentry.title, err)
                continue
            self.aufgaben[aufgabe.id] = aufgabe
            if aufgabe.typ == TYP_INTERVALL and aufgabe.id not in self._daten["zuletzt"]:
                start = subentry.data.get(CONF_ZULETZT) or heute.isoformat()
                self._daten["zuletzt"][aufgabe.id] = start

        # Daten gelöschter Aufgaben entfernen
        for schluessel in ("zuletzt", "erledigt"):
            for aufgabe_id in list(self._daten[schluessel]):
                if aufgabe_id not in self.aufgaben:
                    del self._daten[schluessel][aufgabe_id]
        await self._store.async_save(self._daten)
        self.berechnen()

    @callback
    def berechnen(self) -> None:
        jetzt = dt_util.now()
        stati: dict[str, Status] = {}
        for aufgabe in self.aufgaben.values():
            if aufgabe.typ == TYP_INTERVALL:
                zuletzt = date.fromisoformat(self._daten["zuletzt"][aufgabe.id])
                stati[aufgabe.id] = berechne_intervall(
                    aufgabe, zuletzt, jetzt.date(), self._vorschau
                )
            else:
                stati[aufgabe.id] = berechne_termin(
                    aufgabe,
                    self._erledigte_termine(aufgabe.id),
                    jetzt,
                    self._zeit_morgen,
                    self._zeit_abend,
                    self._vorschau,
                )
        self.stati = stati

    def _erledigte_termine(self, aufgabe_id: str) -> set[date]:
        return {
            date.fromisoformat(d) for d in self._daten["erledigt"].get(aufgabe_id, [])
        }

    @property
    def anzeige(self) -> str:
        return anzeige_zeilen(list(self.stati.values()))

    @callback
    def aktualisieren(self, *_args) -> None:
        self.berechnen()
        async_dispatcher_send(self.hass, self.signal)

    async def async_erledigt(self, aufgabe_id: str) -> None:
        aufgabe = self.aufgaben.get(aufgabe_id)
        if aufgabe is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unbekannte_aufgabe",
                translation_placeholders={"aufgabe_id": aufgabe_id},
            )
        jetzt = dt_util.now()
        if aufgabe.typ == TYP_INTERVALL:
            self._daten["zuletzt"][aufgabe_id] = jetzt.date().isoformat()
        else:
            erledigt = self._erledigte_termine(aufgabe_id)
            datum = naechster_termin(
                aufgabe, erledigt, jetzt, self._zeit_morgen, self._zeit_abend
            )
            if datum is None:
                return
            # Nur die jüngsten Einträge behalten, ältere sind vorbei
            neu = sorted(erledigt | {datum})[-10:]
            self._daten["erledigt"][aufgabe_id] = [d.isoformat() for d in neu]
        await self._store.async_save(self._daten)
        self.aktualisieren()


async def async_setup_entry(hass: HomeAssistant, entry: HaushaltConfigEntry) -> bool:
    manager = HaushaltManager(hass, entry)
    await manager.async_laden()
    entry.runtime_data = manager

    entry.async_on_unload(
        async_track_time_interval(hass, manager.aktualisieren, timedelta(minutes=1))
    )
    entry.async_on_unload(entry.add_update_listener(_async_neu_laden))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _service_registrieren(hass)
    return True


async def _async_neu_laden(hass: HomeAssistant, entry: HaushaltConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HaushaltConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HaushaltConfigEntry) -> None:
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


@callback
def _service_registrieren(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ERLEDIGT):
        return

    async def erledigt(call: ServiceCall) -> None:
        aufgabe_id = call.data[ATTR_AUFGABE_ID]
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if aufgabe_id in entry.runtime_data.aufgaben:
                await entry.runtime_data.async_erledigt(aufgabe_id)
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unbekannte_aufgabe",
            translation_placeholders={"aufgabe_id": aufgabe_id},
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ERLEDIGT,
        erledigt,
        schema=vol.Schema({vol.Required(ATTR_AUFGABE_ID): cv.string}),
    )
