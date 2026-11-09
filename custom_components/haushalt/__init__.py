"""Haushalt: wiederkehrende Aufgaben für Home Assistant."""

from __future__ import annotations

# "date" ist hier zugleich der Name der Plattform date.py (überschreibt den Import)
from datetime import date as Datum, time, timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    AKTIONEN,
    ATTR_AKTION,
    ATTR_ARTIKEL,
    ATTR_AUFGABE_ID,
    ATTR_EINGEFROREN,
    ATTR_EINHEIT,
    ATTR_HALTBAR_ANZAHL,
    ATTR_HALTBAR_BIS,
    ATTR_HALTBAR_EINHEIT,
    ATTR_KATEGORIE,
    ATTR_MENGE,
    ATTR_NAME,
    ATTR_START_IN_MIN,
    ATTR_ZIMMER,
    CONF_ANZAHL,
    CONF_DATEN,
    CONF_EINHEIT,
    CONF_FRIST,
    CONF_GEFRIERER,
    CONF_REINIGUNG_X,
    CONF_REINIGUNG_Y,
    CONF_STARTDATUM,
    CONF_STAUBSAUGER,
    CONF_VERPASST,
    CONF_TYP,
    CONF_MINDESTABSTAND,
    CONF_VORSCHAU,
    CONF_WETTER,
    CONF_WOCHENTAGE,
    CONF_ZEIT_ABEND,
    CONF_ZEIT_MORGEN,
    CONF_ZULETZT,
    DEFAULT_VORSCHAU,
    DEFAULT_ZEIT_ABEND,
    DEFAULT_ZEIT_MORGEN,
    DOMAIN,
    EINHEIT_MONATE,
    EINHEIT_TAGE,
    EINHEITEN,
    EVENT_ERLEDIGT,
    FRIST_ABEND,
    GEF_EINHEIT_PORTIONEN,
    GEF_EINHEITEN,
    GRUPPE_HEUTE,
    GRUPPE_MORGEN,
    GRUPPE_UEBERFAELLIG,
    HALTBAR_DATUM,
    HALTBAR_KATEGORIE,
    HALTBAR_ZEITRAUM,
    KAT_MEAL_PREP,
    KATEGORIEN,
    SERVICE_EINFRIEREN,
    SERVICE_ENTNEHMEN,
    SERVICE_ERLEDIGT,
    SERVICE_SAUGEN,
    SERVICE_SAUGER,
    SIGNAL_UPDATE,
    START_OPTIONEN,
    SUBENTRY_AUFGABE,
    TYP_INTERVALL,
    TYP_TERMIN,
    VERPASST_STEHEN,
    WETTER_INTERVALL_MIN,
    WOCHENTAGE,
)
from .logic import (
    Aufgabe,
    Status,
    anzeige_zeilen,
    berechne_intervall,
    berechne_termin,
    daten_umwandeln,
    naechster_termin,
    parse_daten,
)
from .formular import Formular
from .gefrierer import Gefrierer, GefriererFehler, haltbar_bis, menge_text
from .sauger import Sauger
from .wetter import WetterDienst

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BUTTON,
    Platform.DATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]
STORAGE_VERSION = 1

type HaushaltConfigEntry = ConfigEntry[HaushaltManager]


def aufgabe_aus_subentry(subentry_id: str, title: str, data: dict) -> Aufgabe:
    data = daten_umwandeln(data)
    start = data.get(CONF_STARTDATUM)
    return Aufgabe(
        id=subentry_id,
        name=title,
        typ=data[CONF_TYP],
        anzahl=int(data.get(CONF_ANZAHL, 7)),
        einheit=data.get(CONF_EINHEIT, EINHEIT_TAGE),
        verpasst=data.get(CONF_VERPASST, VERPASST_STEHEN),
        frist=data.get(CONF_FRIST, FRIST_ABEND),
        startdatum=Datum.fromisoformat(start) if start else None,
        wochentage=sorted(WOCHENTAGE.index(t) for t in data.get(CONF_WOCHENTAGE, [])),
        mindestabstand=int(data.get(CONF_MINDESTABSTAND, 3)),
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
        # zuletzt: {aufgabe_id: iso-datum}, erledigt: {aufgabe_id: [iso-datum, ...]},
        # erstellt: {aufgabe_id: iso-datum} für noch nie erledigte Wochentag-Aufgaben,
        # wetter: Zwischenspeicher für den heutigen Vormittag,
        # sauger: geplanter Start und laufender Auftrag des Staubsaugers,
        # neu: zuletzt über das Formular angelegte Aufgabe {name, zeit},
        # gefrierer: Packungen im Gefrierer und letzte Meldung
        self._daten: dict = {
            "zuletzt": {}, "erledigt": {}, "erstellt": {}, "wetter": {}, "sauger": {},
            "neu": {}, "gefrierer": {},
        }
        self.aufgaben: dict[str, Aufgabe] = {}
        self.stati: dict[str, Status] = {}
        self.wetter: WetterDienst | None = None
        self.sauger: Sauger | None = None
        self.formular = Formular()
        self.gefrierer: Gefrierer | None = None
        self.gefrierer_formular = None

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
        self._daten.setdefault("erstellt", {})
        self._daten.setdefault("wetter", {})
        self._daten.setdefault("sauger", {})
        self._daten.setdefault("neu", {})
        self._daten.setdefault("gefrierer", {})
        if self.entry.options.get(CONF_GEFRIERER):
            from .gefrierer_formular import GefriererFormular

            self.gefrierer = Gefrierer(self._daten["gefrierer"])
            self.gefrierer_formular = GefriererFormular()
        # Saugstarts pro Aufgabe gibt es nicht mehr (bis 0.4)
        self._daten.pop("saugstart", None)
        if wetter_id := self.entry.options.get(CONF_WETTER):
            self.wetter = WetterDienst(self.hass, wetter_id, self._daten["wetter"])
        if sauger_id := self.entry.options.get(CONF_STAUBSAUGER):
            x = self.entry.options.get(CONF_REINIGUNG_X)
            y = self.entry.options.get(CONF_REINIGUNG_Y)
            punkt = (int(x), int(y)) if x is not None and y is not None else None
            self.sauger = Sauger(
                self.hass, sauger_id, punkt, self._daten["sauger"],
                self._async_speichern, self.aktualisieren,
            )
            self.sauger.starten()
        else:
            self._daten["sauger"] = {}

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
            elif (
                aufgabe.typ == TYP_TERMIN
                and not aufgabe.verschwindet
                and aufgabe.id not in self._daten["zuletzt"]
                and aufgabe.id not in self._daten["erstellt"]
            ):
                if zuletzt := subentry.data.get(CONF_ZULETZT):
                    self._daten["zuletzt"][aufgabe.id] = zuletzt
                else:
                    self._daten["erstellt"][aufgabe.id] = heute.isoformat()

        # Daten gelöschter Aufgaben entfernen
        for schluessel in ("zuletzt", "erledigt", "erstellt"):
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
            zuletzt_iso = self._daten["zuletzt"].get(aufgabe.id)
            zuletzt = Datum.fromisoformat(zuletzt_iso) if zuletzt_iso else None
            if aufgabe.typ == TYP_INTERVALL:
                stati[aufgabe.id] = berechne_intervall(
                    aufgabe,
                    zuletzt or jetzt.date(),
                    jetzt,
                    self._zeit_morgen,
                    self._zeit_abend,
                    self._vorschau,
                )
            else:
                erstellt_iso = self._daten["erstellt"].get(aufgabe.id)
                stati[aufgabe.id] = berechne_termin(
                    aufgabe,
                    zuletzt,
                    Datum.fromisoformat(erstellt_iso) if erstellt_iso else jetzt.date(),
                    self._erledigte_termine(aufgabe.id),
                    jetzt,
                    self._zeit_morgen,
                    self._zeit_abend,
                    self._vorschau,
                )
        self.stati = stati

    def _erledigte_termine(self, aufgabe_id: str) -> set[Datum]:
        return {
            Datum.fromisoformat(d) for d in self._daten["erledigt"].get(aufgabe_id, [])
        }

    @property
    def anzeige(self) -> str:
        return anzeige_zeilen(list(self.stati.values()))

    @callback
    def aktualisieren(self, *_args) -> None:
        self.berechnen()
        async_dispatcher_send(self.hass, self.signal)

    async def async_wetter_aktualisieren(self, *_args) -> None:
        if self.wetter is None:
            return
        if await self.wetter.async_aktualisieren():
            await self._store.async_save(self._daten)
        async_dispatcher_send(self.hass, self.signal)

    @property
    def kachel(self) -> str:
        """Drei Zeilen für die Haushalt-Kachel auf dem Homescreen, je 'vor|hervor|nach'."""
        sichtbar = sorted(
            (s for s in self.stati.values() if s.sichtbar), key=Status.sortierschluessel
        )
        zahl = {g: sum(1 for s in sichtbar if s.gruppe == g) for g in
                (GRUPPE_UEBERFAELLIG, GRUPPE_HEUTE, GRUPPE_MORGEN)}
        rest = [f"{zahl[GRUPPE_HEUTE]} heute", f"{zahl[GRUPPE_MORGEN]} morgen"]
        if zahl[GRUPPE_UEBERFAELLIG]:
            zeile1 = f"|{zahl[GRUPPE_UEBERFAELLIG]} überfällig| · " + " · ".join(rest)
        else:
            zeile1 = " · ".join(rest) + "||"
        if sichtbar:
            zeile2 = f"Nächste: {sichtbar[0].aufgabe.name.replace('|', '/')}||"
        else:
            zeile2 = "Keine Aufgaben fällig||"
        zeile3 = f"{self.sauger.kachel}||" if self.sauger else "||"
        return "\n".join([zeile1, zeile2, zeile3])

    @property
    def formular_meldung(self) -> dict:
        return self._daten["neu"]

    async def async_formular_meldung(self, name: str) -> None:
        self._daten["neu"] = {"name": name, "zeit": dt_util.now().isoformat()}
        await self._store.async_save(self._daten)

    def _gefrierer_fehler(self, err: GefriererFehler) -> ServiceValidationError:
        return ServiceValidationError(translation_domain=DOMAIN, translation_key=err.args[0])

    def _gefrierer(self) -> Gefrierer:
        if self.gefrierer is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="kein_gefrierer"
            )
        return self.gefrierer

    async def async_einfrieren(
        self,
        name: str,
        kategorie: str,
        menge: int,
        einheit: str,
        eingefroren: Datum | None = None,
        bis: Datum | None = None,
        anzahl: int | None = None,
        zeiteinheit: str | None = None,
        art: str | None = None,
    ) -> None:
        """Packung einfrieren. Ohne `art`: Datum, sonst Zeitraum, sonst Kategorie."""
        gefrierer = self._gefrierer()
        eingefroren = eingefroren or dt_util.now().date()
        if art is None:
            art = HALTBAR_DATUM if bis else HALTBAR_ZEITRAUM if anzahl else HALTBAR_KATEGORIE
        try:
            datum = haltbar_bis(eingefroren, kategorie, art, anzahl, zeiteinheit, bis)
            packung = gefrierer.einfrieren(name, kategorie, menge, einheit, eingefroren, datum)
        except GefriererFehler as err:
            raise self._gefrierer_fehler(err) from err
        gefrierer.melden(
            f"Eingefroren: {packung.name}, {menge_text(packung.menge, einheit)}",
            dt_util.now().isoformat(),
        )
        await self._store.async_save(self._daten)
        self.aktualisieren()

    async def async_entnehmen(self, artikel: str, menge: int | None = None) -> None:
        """Menge entnehmen (None = alles), zuerst aus der ältesten Packung."""
        gefrierer = self._gefrierer()
        try:
            eintrag, entnommen = gefrierer.entnehmen(artikel, menge)
        except GefriererFehler as err:
            raise self._gefrierer_fehler(err) from err
        gefrierer.melden(
            f"Entnommen: {eintrag.name}, {menge_text(entnommen, eintrag.einheit)}",
            dt_util.now().isoformat(),
        )
        await self._store.async_save(self._daten)
        self.aktualisieren()

    async def _async_speichern(self) -> None:
        await self._store.async_save(self._daten)

    async def async_erledigt(self, aufgabe_id: str) -> None:
        aufgabe = self.aufgaben.get(aufgabe_id)
        if aufgabe is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unbekannte_aufgabe",
                translation_placeholders={"aufgabe_id": aufgabe_id},
            )
        jetzt = dt_util.now()
        if aufgabe.typ == TYP_INTERVALL or not aufgabe.verschwindet:
            self._daten["zuletzt"][aufgabe_id] = jetzt.date().isoformat()
            self._daten["erstellt"].pop(aufgabe_id, None)
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
        self.hass.bus.async_fire(
            EVENT_ERLEDIGT,
            {
                ATTR_AUFGABE_ID: aufgabe_id,
                "name": aufgabe.name,
            },
        )
        self.aktualisieren()

    @callback
    def stoppen(self) -> None:
        if self.sauger is not None:
            self.sauger.stoppen()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """1.1 -> 1.2: Aufgabentypen mit Einheit und 'wenn verpasst' (Version 0.7)."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        for subentry in list(entry.subentries.values()):
            if subentry.subentry_type != SUBENTRY_AUFGABE:
                continue
            hass.config_entries.async_update_subentry(
                entry, subentry, data=daten_umwandeln(dict(subentry.data))
            )
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HaushaltConfigEntry) -> bool:
    manager = HaushaltManager(hass, entry)
    await manager.async_laden()
    entry.runtime_data = manager

    entry.async_on_unload(
        async_track_time_interval(hass, manager.aktualisieren, timedelta(minutes=1))
    )
    entry.async_on_unload(manager.stoppen)
    if manager.wetter is not None:
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                manager.async_wetter_aktualisieren,
                timedelta(minutes=WETTER_INTERVALL_MIN),
            )
        )

        async def _wetter_beim_start(_hass: HomeAssistant) -> None:
            await manager.async_wetter_aktualisieren()

        entry.async_on_unload(async_at_started(hass, _wetter_beim_start))
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

    def _manager_mit_sauger() -> HaushaltManager:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if entry.runtime_data.sauger is not None:
                return entry.runtime_data
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="kein_staubsauger"
        )

    async def saugen(call: ServiceCall) -> None:
        await _manager_mit_sauger().sauger.async_saugen(
            call.data.get(ATTR_ZIMMER, []), call.data.get(ATTR_START_IN_MIN, 0)
        )

    async def sauger(call: ServiceCall) -> None:
        await _manager_mit_sauger().sauger.async_aktion(call.data[ATTR_AKTION])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAUGEN,
        saugen,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ZIMMER, default=[]): _zimmer_liste,
                vol.Optional(ATTR_START_IN_MIN, default=0): vol.All(
                    vol.Coerce(int), vol.In(START_OPTIONEN)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAUGER,
        sauger,
        schema=vol.Schema({vol.Required(ATTR_AKTION): vol.In(AKTIONEN)}),
    )

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

    def _manager_mit_gefrierer() -> HaushaltManager:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if entry.runtime_data.gefrierer is not None:
                return entry.runtime_data
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="kein_gefrierer"
        )

    async def einfrieren(call: ServiceCall) -> None:
        await _manager_mit_gefrierer().async_einfrieren(
            call.data[ATTR_NAME],
            call.data.get(ATTR_KATEGORIE, KAT_MEAL_PREP),
            call.data[ATTR_MENGE],
            call.data.get(ATTR_EINHEIT, GEF_EINHEIT_PORTIONEN),
            call.data.get(ATTR_EINGEFROREN),
            call.data.get(ATTR_HALTBAR_BIS),
            call.data.get(ATTR_HALTBAR_ANZAHL),
            call.data.get(ATTR_HALTBAR_EINHEIT, EINHEIT_MONATE),
        )

    async def entnehmen(call: ServiceCall) -> None:
        menge = call.data.get(ATTR_MENGE)
        await _manager_mit_gefrierer().async_entnehmen(
            call.data[ATTR_ARTIKEL], menge if menge else None
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EINFRIEREN,
        einfrieren,
        schema=vol.Schema(
            {
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_KATEGORIE, default=KAT_MEAL_PREP): vol.In(list(KATEGORIEN)),
                vol.Required(ATTR_MENGE): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(ATTR_EINHEIT, default=GEF_EINHEIT_PORTIONEN): vol.In(GEF_EINHEITEN),
                vol.Optional(ATTR_EINGEFROREN): cv.date,
                vol.Optional(ATTR_HALTBAR_BIS): cv.date,
                vol.Optional(ATTR_HALTBAR_ANZAHL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(ATTR_HALTBAR_EINHEIT, default=EINHEIT_MONATE): vol.In(EINHEITEN),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ENTNEHMEN,
        entnehmen,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ARTIKEL): cv.string,
                # Leer oder 0 = alles; Text, weil das Display Zahlen als Text schickt
                vol.Optional(ATTR_MENGE): vol.Any(None, "", vol.All(vol.Coerce(int), vol.Range(min=0))),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ERLEDIGT,
        erledigt,
        schema=vol.Schema(
            {
                vol.Required(ATTR_AUFGABE_ID): cv.string,
                # Früher für den Saugstart, wird ignoriert (ältere Display-Firmware)
                vol.Optional(ATTR_START_IN_MIN): cv.string,
            }
        ),
    )


def _zimmer_liste(wert) -> list[int]:
    """Zimmer als Liste oder als Text '19,20' (so schickt es das Display)."""
    if wert is None or wert == "":
        return []
    if isinstance(wert, str):
        wert = [t for t in wert.replace(" ", "").split(",") if t]
    if not isinstance(wert, list):
        wert = [wert]
    return [vol.Coerce(int)(z) for z in wert]
