"""Wetter fürs Display: pro Tag Vormittag und Nachmittag zusammengefasst."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, tzinfo
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Stunden [von, bis) des Vormittags und des Nachmittags
VORMITTAG = (6, 12)
NACHMITTAG = (12, 18)
ANZAHL_TAGE = 3

WOCHENTAG_NAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

# Bei Gleichstand gewinnt der Zustand, der weiter hinten steht
SCHWERE = [
    "sunny",
    "partlycloudy",
    "windy",
    "windy-variant",
    "cloudy",
    "fog",
    "exceptional",
    "rainy",
    "snowy-rainy",
    "snowy",
    "hail",
    "pouring",
    "lightning",
    "lightning-rainy",
]


@dataclass
class Haelfte:
    """Zusammenfassung eines halben Tages."""

    zustand: str
    temperatur: int | None
    regen: str  # Wahrscheinlichkeit, z.B. "40 %"; leer, wenn unbekannt
    menge: str = ""  # Regenmenge, z.B. "1,2 mm"; leer, wenn unbekannt oder 0


def _zustand(werte: list[str]) -> str:
    # Klare Nacht kommt frühmorgens vor, tagsüber zählt sie als sonnig
    werte = ["sunny" if w == "clear-night" else w for w in werte if w]
    if not werte:
        return ""
    zaehler = Counter(werte)
    return max(
        zaehler,
        key=lambda w: (zaehler[w], SCHWERE.index(w) if w in SCHWERE else -1),
    )


def _regen(eintraege: list[dict[str, Any]]) -> str:
    prozent = [
        e["precipitation_probability"]
        for e in eintraege
        if e.get("precipitation_probability") is not None
    ]
    return f"{round(max(prozent))} %" if prozent else ""


def _menge(eintraege: list[dict[str, Any]]) -> str:
    mm = [e["precipitation"] for e in eintraege if e.get("precipitation") is not None]
    summe = round(sum(mm), 1)
    if summe <= 0:
        return ""
    return f"{summe:g} mm".replace(".", ",")


def _lokal(eintrag: dict[str, Any], zone: tzinfo) -> datetime | None:
    wert = eintrag.get("datetime")
    if isinstance(wert, datetime):
        zeit = wert
    elif isinstance(wert, str):
        zeit = dt_util.parse_datetime(wert)
    else:
        return None
    if zeit is None:
        return None
    if zeit.tzinfo is None:
        zeit = zeit.replace(tzinfo=dt_util.UTC)
    return zeit.astimezone(zone)


def haelfte_aus_stunden(
    stunden: list[dict[str, Any]], tag: date, von_bis: tuple[int, int], zone: tzinfo
) -> Haelfte | None:
    """Fasst stündliche (oder 6-stündliche) Einträge eines halben Tages zusammen."""
    von, bis = von_bis
    passend = []
    for eintrag in stunden:
        zeit = _lokal(eintrag, zone)
        if zeit is not None and zeit.date() == tag and von <= zeit.hour < bis:
            passend.append(eintrag)
    if not passend:
        return None
    temperaturen = [e["temperature"] for e in passend if e.get("temperature") is not None]
    return Haelfte(
        zustand=_zustand([e.get("condition") or "" for e in passend]),
        temperatur=round(max(temperaturen)) if temperaturen else None,
        regen=_regen(passend),
        menge=_menge(passend),
    )


def haelfte_aus_tag(
    tage: list[dict[str, Any]], tag: date, zone: tzinfo
) -> Haelfte | None:
    """Ersatz aus der Tagesvorhersage, wenn keine stündlichen Daten da sind."""
    for eintrag in tage:
        zeit = _lokal(eintrag, zone)
        if zeit is not None and zeit.date() == tag:
            temperatur = eintrag.get("temperature")
            return Haelfte(
                zustand=_zustand([eintrag.get("condition") or ""]),
                temperatur=round(temperatur) if temperatur is not None else None,
                regen=_regen([eintrag]),
                menge=_menge([eintrag]),
            )
    return None


def tag_name(tag: date, heute: date) -> str:
    if tag == heute:
        return "Heute"
    return WOCHENTAG_NAMEN[tag.weekday()]


def anzeige_zeile(name: str, vm: Haelfte | None, nm: Haelfte | None) -> str:
    """name|zustand|temp|regen|menge|zustand|temp|regen|menge, unbekannte Felder leer."""
    felder = [name]
    for h in (vm, nm):
        if h is None:
            felder += ["", "", "", ""]
        else:
            temp = "" if h.temperatur is None else str(h.temperatur)
            felder += [h.zustand, temp, h.regen, h.menge]
    return "|".join(felder)


class WetterDienst:
    """Holt die Vorhersage einer Wetter-Entität und fasst sie halbtageweise zusammen."""

    def __init__(self, hass: HomeAssistant, entity_id: str, cache: dict) -> None:
        self.hass = hass
        self.entity_id = entity_id
        # Der Vormittag von heute fehlt nachmittags in der Vorhersage, darum merken.
        # cache: {"datum": iso, "vm": {...}, "nm": {...}}
        self._cache = cache
        self.tage: list[tuple[str, Haelfte | None, Haelfte | None]] = []

    async def _vorhersage(self, art: str) -> list[dict[str, Any]]:
        try:
            antwort = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self.entity_id, "type": art},
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            _LOGGER.debug("Keine %s-Vorhersage von %s: %s", art, self.entity_id, err)
            return []
        if not antwort:
            return []
        return list(antwort.get(self.entity_id, {}).get("forecast") or [])

    async def async_aktualisieren(self) -> bool:
        """Liefert True, wenn sich der Cache für heute geändert hat."""
        stunden = await self._vorhersage("hourly")
        tage = await self._vorhersage("daily")
        if not stunden and not tage:
            return False
        jetzt = dt_util.now()
        zone = jetzt.tzinfo or dt_util.get_default_time_zone()
        heute = jetzt.date()

        cache = self._cache if self._cache.get("datum") == heute.isoformat() else {}
        neue_tage = []
        for i in range(ANZAHL_TAGE):
            tag = heute + timedelta(days=i)
            haelften = []
            for schluessel, von_bis in (("vm", VORMITTAG), ("nm", NACHMITTAG)):
                h = haelfte_aus_stunden(stunden, tag, von_bis, zone)
                if h is None and i == 0 and schluessel in cache:
                    h = Haelfte(**cache[schluessel])
                if h is None:
                    h = haelfte_aus_tag(tage, tag, zone)
                haelften.append(h)
            neue_tage.append((tag_name(tag, heute), haelften[0], haelften[1]))
        self.tage = neue_tage

        _, vm, nm = neue_tage[0]
        neuer_cache = {"datum": heute.isoformat()}
        if vm is not None:
            neuer_cache["vm"] = asdict(vm)
        if nm is not None:
            neuer_cache["nm"] = asdict(nm)
        if neuer_cache == self._cache:
            return False
        self._cache.clear()
        self._cache.update(neuer_cache)
        return True

    @property
    def anzeige(self) -> str:
        return "\n".join(anzeige_zeile(*t) for t in self.tage)

    @property
    def aktuell(self) -> Haelfte | None:
        """Die Hälfte von heute, die gerade gilt (ab Mittag der Nachmittag)."""
        if not self.tage:
            return None
        _, vm, nm = self.tage[0]
        if dt_util.now().hour >= VORMITTAG[1]:
            return nm or vm
        return vm or nm
