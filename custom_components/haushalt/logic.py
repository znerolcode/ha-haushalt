"""Berechnung von Fälligkeit, Gruppe und Anzeigetext. Ohne Home-Assistant-Abhängigkeiten."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import re

from .const import (
    FRIST_ABEND,
    FRIST_MORGEN,
    GRUPPE_HEUTE,
    GRUPPE_MORGEN,
    GRUPPE_NAECHSTE,
    GRUPPE_UEBERFAELLIG,
    TYP_INTERVALL,
    TYP_TERMIN,
)

GRUPPEN_REIHENFOLGE = [GRUPPE_UEBERFAELLIG, GRUPPE_HEUTE, GRUPPE_MORGEN, GRUPPE_NAECHSTE]


@dataclass
class Aufgabe:
    """Eine erfasste Aufgabe."""

    id: str
    name: str
    typ: str
    # Intervall
    tage: int = 7
    # Termin
    frist: str = FRIST_ABEND
    startdatum: date | None = None
    alle_wochen: int = 0
    daten: list[date] = field(default_factory=list)


@dataclass
class Status:
    """Berechneter Zustand einer Aufgabe."""

    aufgabe: Aufgabe
    datum: date | None
    tage: int | None
    gruppe: str | None
    text: str
    sichtbar: bool

    @property
    def ueberfaellig(self) -> bool:
        return self.gruppe == GRUPPE_UEBERFAELLIG

    def sortierschluessel(self) -> tuple:
        frist_rang = 0 if self.aufgabe.frist == FRIST_MORGEN else 1
        return (
            GRUPPEN_REIHENFOLGE.index(self.gruppe) if self.gruppe else 99,
            self.tage if self.tage is not None else 9999,
            0 if self.aufgabe.typ == TYP_TERMIN else 1,
            frist_rang,
            self.aufgabe.name.lower(),
        )


DATUM_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def parse_daten(text: str | None) -> list[date]:
    """Liest Daten wie '05.11.2026, 19.11.2026'. Wirft ValueError bei Unsinn."""
    if not text or not text.strip():
        return []
    daten: list[date] = []
    for teil in re.split(r"[,;\s]+", text.strip()):
        if not teil:
            continue
        m = DATUM_RE.fullmatch(teil)
        if not m:
            raise ValueError(teil)
        tag, monat, jahr = (int(x) for x in m.groups())
        daten.append(date(jahr, monat, tag))
    return sorted(set(daten))


def gruppe_fuer(tage: int) -> str:
    if tage < 0:
        return GRUPPE_UEBERFAELLIG
    if tage == 0:
        return GRUPPE_HEUTE
    if tage == 1:
        return GRUPPE_MORGEN
    return GRUPPE_NAECHSTE


def text_intervall(tage: int) -> str:
    if tage < -1:
        return f"{-tage} Tage überfällig"
    if tage == -1:
        return "1 Tag überfällig"
    if tage == 0:
        return "heute"
    if tage == 1:
        return "morgen"
    return f"in {tage} Tagen"


def text_termin(tage: int, frist: str) -> str:
    zeit = "früh" if frist == FRIST_MORGEN else "Abend"
    if tage == 0:
        return f"bis heute {zeit}"
    if tage == 1:
        return f"bis morgen {zeit}"
    return f"bis in {tage} Tagen"


def berechne_intervall(
    aufgabe: Aufgabe, zuletzt: date, heute: date, vorschau_tage: int
) -> Status:
    datum = zuletzt + timedelta(days=aufgabe.tage)
    tage = (datum - heute).days
    return Status(
        aufgabe=aufgabe,
        datum=datum,
        tage=tage,
        gruppe=gruppe_fuer(tage),
        text=text_intervall(tage),
        sichtbar=tage <= vorschau_tage,
    )


def termine_ab(aufgabe: Aufgabe, ab: date, anzahl: int = 5) -> list[date]:
    """Die nächsten Termine ab (inklusive) einem Datum, aus Regel und Einzeldaten."""
    kandidaten = {d for d in aufgabe.daten if d >= ab}
    if aufgabe.startdatum is not None:
        if aufgabe.alle_wochen > 0:
            schritt = 7 * aufgabe.alle_wochen
            if aufgabe.startdatum >= ab:
                erster = aufgabe.startdatum
            else:
                k = -(-(ab - aufgabe.startdatum).days // schritt)
                erster = aufgabe.startdatum + timedelta(days=k * schritt)
            kandidaten.update(
                erster + timedelta(days=i * schritt) for i in range(anzahl)
            )
        elif aufgabe.startdatum >= ab:
            kandidaten.add(aufgabe.startdatum)
    return sorted(kandidaten)[:anzahl]


def frist_zeitpunkt(
    datum: date, frist: str, zeit_morgen: time, zeit_abend: time, tz
) -> datetime:
    zeit = zeit_morgen if frist == FRIST_MORGEN else zeit_abend
    return datetime.combine(datum, zeit, tzinfo=tz)


def naechster_termin(
    aufgabe: Aufgabe,
    erledigt: set[date],
    jetzt: datetime,
    zeit_morgen: time,
    zeit_abend: time,
) -> date | None:
    """Erster Termin, dessen Frist noch nicht abgelaufen und der nicht erledigt ist."""
    for datum in termine_ab(aufgabe, jetzt.date(), anzahl=len(erledigt) + 3):
        if datum in erledigt:
            continue
        if frist_zeitpunkt(datum, aufgabe.frist, zeit_morgen, zeit_abend, jetzt.tzinfo) <= jetzt:
            continue
        return datum
    return None


def berechne_termin(
    aufgabe: Aufgabe,
    erledigt: set[date],
    jetzt: datetime,
    zeit_morgen: time,
    zeit_abend: time,
    vorschau_tage: int,
) -> Status:
    datum = naechster_termin(aufgabe, erledigt, jetzt, zeit_morgen, zeit_abend)
    if datum is None:
        return Status(aufgabe, None, None, None, "kein Termin", False)
    tage = (datum - jetzt.date()).days
    return Status(
        aufgabe=aufgabe,
        datum=datum,
        tage=tage,
        gruppe=gruppe_fuer(tage),
        text=text_termin(tage, aufgabe.frist),
        sichtbar=tage <= vorschau_tage,
    )


def anzeige_zeilen(stati: list[Status]) -> str:
    """Kompakte Liste für das Display: eine Zeile pro Aufgabe, Felder mit '|' getrennt.

    id|gruppe|name|text|ueberfaellig(0/1)
    """
    zeilen = []
    for s in sorted((s for s in stati if s.sichtbar), key=Status.sortierschluessel):
        name = s.aufgabe.name.replace("|", "/").replace("\n", " ")
        zeilen.append(
            f"{s.aufgabe.id}|{s.gruppe}|{name}|{s.text}|{1 if s.ueberfaellig else 0}"
        )
    return "\n".join(zeilen)


__all__ = [
    "Aufgabe",
    "Status",
    "TYP_INTERVALL",
    "TYP_TERMIN",
    "FRIST_ABEND",
    "FRIST_MORGEN",
]
