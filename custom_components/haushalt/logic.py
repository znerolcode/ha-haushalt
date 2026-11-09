"""Berechnung von Fälligkeit, Gruppe und Anzeigetext. Ohne Home-Assistant-Abhängigkeiten."""

from __future__ import annotations

from dataclasses import dataclass, field
import calendar
from datetime import date, datetime, time, timedelta
import re

from .const import (
    EINHEIT_TAGE,
    EINHEIT_WOCHEN,
    FRIST_ABEND,
    FRIST_MORGEN,
    GRUPPE_HEUTE,
    GRUPPE_MORGEN,
    GRUPPE_NAECHSTE,
    GRUPPE_UEBERFAELLIG,
    TYP_INTERVALL,
    TYP_TERMIN,
    TYP_WOCHENTAG,
    VERPASST_STEHEN,
    VERPASST_WEG,
)

GRUPPEN_REIHENFOLGE = [GRUPPE_UEBERFAELLIG, GRUPPE_HEUTE, GRUPPE_MORGEN, GRUPPE_NAECHSTE]


@dataclass
class Aufgabe:
    """Eine erfasste Aufgabe."""

    id: str
    name: str
    typ: str
    # Alle `anzahl` Einheiten. Beim Termin heisst 0: nicht wiederholen.
    anzahl: int = 7
    einheit: str = EINHEIT_TAGE
    verpasst: str = VERPASST_STEHEN
    # Nur bei verpasst = weg: bis wann am Fälligkeitstag
    frist: str = FRIST_ABEND
    # Termin
    startdatum: date | None = None
    daten: list[date] = field(default_factory=list)
    # Termin in Wochen (0 = Montag); leer = Wochentag des Startdatums
    wochentage: list[int] = field(default_factory=list)
    # Termin, der stehen bleibt: Plantag entfällt, wenn so kurz vorher erledigt
    mindestabstand: int = 3

    @property
    def verschwindet(self) -> bool:
        return self.verpasst == VERPASST_WEG


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
            0 if self.aufgabe.verschwindet else 1,
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


def plus(datum: date, anzahl: int, einheit: str) -> date:
    """Datum plus `anzahl` Tage, Wochen oder Monate (Monatsende wird gekürzt, 31.1. + 1 = 28.2.)."""
    if einheit == EINHEIT_TAGE:
        return datum + timedelta(days=anzahl)
    if einheit == EINHEIT_WOCHEN:
        return datum + timedelta(weeks=anzahl)
    monate = datum.month - 1 + anzahl
    jahr, monat = datum.year + monate // 12, monate % 12 + 1
    return date(jahr, monat, min(datum.day, calendar.monthrange(jahr, monat)[1]))


def frist_zeitpunkt(
    datum: date, frist: str, zeit_morgen: time, zeit_abend: time, tz
) -> datetime:
    zeit = zeit_morgen if frist == FRIST_MORGEN else zeit_abend
    return datetime.combine(datum, zeit, tzinfo=tz)


def _status(aufgabe: Aufgabe, datum: date | None, heute: date, vorschau_tage: int) -> Status:
    if datum is None:
        return Status(aufgabe, None, None, None, "kein Termin", False)
    tage = (datum - heute).days
    text = text_termin(tage, aufgabe.frist) if aufgabe.verschwindet else text_intervall(tage)
    return Status(
        aufgabe=aufgabe,
        datum=datum,
        tage=tage,
        gruppe=gruppe_fuer(tage),
        text=text,
        sichtbar=tage <= vorschau_tage,
    )


def faellig_intervall(
    aufgabe: Aufgabe, zuletzt: date, jetzt: datetime, zeit_morgen: time, zeit_abend: time
) -> date:
    """Fälligkeit `anzahl` Einheiten nach dem Erledigen.

    Verschwindet die Aufgabe, wenn verpasst: ist die Frist abgelaufen, zählt das
    Intervall ab dem verpassten Tag weiter.
    """
    anzahl = max(aufgabe.anzahl, 1)
    datum = plus(zuletzt, anzahl, aufgabe.einheit)
    if not aufgabe.verschwindet:
        return datum
    k = 1
    while (
        frist_zeitpunkt(datum, aufgabe.frist, zeit_morgen, zeit_abend, jetzt.tzinfo) <= jetzt
        and k < 10000
    ):
        k += 1
        datum = plus(zuletzt, k * anzahl, aufgabe.einheit)
    return datum


def berechne_intervall(
    aufgabe: Aufgabe,
    zuletzt: date,
    jetzt: datetime,
    zeit_morgen: time,
    zeit_abend: time,
    vorschau_tage: int,
) -> Status:
    datum = faellig_intervall(aufgabe, zuletzt, jetzt, zeit_morgen, zeit_abend)
    return _status(aufgabe, datum, jetzt.date(), vorschau_tage)


def _regel_termine(aufgabe: Aufgabe, ab: date, anzahl: int) -> list[date]:
    """Die nächsten `anzahl` Termine der Wiederholung ab (inklusive) einem Datum."""
    start = aufgabe.startdatum
    schritt = aufgabe.anzahl
    if aufgabe.einheit == EINHEIT_WOCHEN and (aufgabe.wochentage or start is None):
        tage = aufgabe.wochentage or ([start.weekday()] if start else [])
        if not tage:
            return []
        if start is None:
            # Ohne Startdatum (alte Wochentag-Aufgaben) gibt es keine Ankerwoche
            anker, schritt, erster = ab - timedelta(days=ab.weekday()), 1, ab
        else:
            if schritt <= 0:
                return [start] if start >= ab else []
            anker = start - timedelta(days=start.weekday())
            erster = max(ab, start)
        termine = []
        for i in range(7 * schritt * (anzahl + 1)):
            datum = erster + timedelta(days=i)
            if datum.weekday() in tage and ((datum - anker).days // 7) % schritt == 0:
                termine.append(datum)
                if len(termine) >= anzahl:
                    break
        return termine
    if start is None:
        return []
    if schritt <= 0:
        return [start] if start >= ab else []
    k = 0
    if aufgabe.einheit == EINHEIT_TAGE and ab > start:
        k = -(-(ab - start).days // schritt)
    termine = []
    while len(termine) < anzahl and k < 100000:
        datum = plus(start, k * schritt, aufgabe.einheit)
        if datum >= ab:
            termine.append(datum)
        k += 1
    return termine


def termine_ab(aufgabe: Aufgabe, ab: date, anzahl: int = 5) -> list[date]:
    """Die nächsten Termine ab (inklusive) einem Datum, aus Regel und Einzeldaten."""
    kandidaten = {d for d in aufgabe.daten if d >= ab}
    kandidaten.update(_regel_termine(aufgabe, ab, anzahl))
    return sorted(kandidaten)[:anzahl]


def faellig_termin_stehen(
    aufgabe: Aufgabe, zuletzt: date | None, erstellt: date
) -> date | None:
    """Erster Termin, der mindestens `mindestabstand` Tage nach dem Erledigen liegt.

    Noch nie erledigt: erster Termin ab dem Erstellen der Aufgabe.
    """
    if zuletzt is None:
        ab = erstellt
    else:
        ab = zuletzt + timedelta(days=max(aufgabe.mindestabstand, 1))
    termine = termine_ab(aufgabe, ab, 1)
    return termine[0] if termine else None


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
    zuletzt: date | None,
    erstellt: date,
    erledigt: set[date],
    jetzt: datetime,
    zeit_morgen: time,
    zeit_abend: time,
    vorschau_tage: int,
) -> Status:
    if aufgabe.verschwindet:
        datum = naechster_termin(aufgabe, erledigt, jetzt, zeit_morgen, zeit_abend)
    else:
        datum = faellig_termin_stehen(aufgabe, zuletzt, erstellt)
    return _status(aufgabe, datum, jetzt.date(), vorschau_tage)


def daten_umwandeln(daten: dict) -> dict:
    """Daten einer Aufgabe aus Version 0.6 und älter ins neue Format.

    Intervall (tage) -> Intervall in Tagen, bleibt stehen.
    Wochentag -> Termin in Wochen mit Wochentagen, bleibt stehen.
    Termin -> Termin in Wochen, verschwindet.
    """
    if CONF_EINHEIT_KEY in daten:
        return dict(daten)
    neu = dict(daten)
    typ = neu.get("typ")
    if typ == TYP_INTERVALL:
        neu["anzahl"] = int(neu.pop("tage", 7))
        neu["einheit"] = EINHEIT_TAGE
        neu["verpasst"] = VERPASST_STEHEN
        neu.setdefault("frist", FRIST_ABEND)
    elif typ == TYP_WOCHENTAG:
        neu["typ"] = TYP_TERMIN
        neu["anzahl"] = max(int(neu.pop("alle_wochen", 1)), 1)
        neu["einheit"] = EINHEIT_WOCHEN
        neu["verpasst"] = VERPASST_STEHEN
        neu.setdefault("frist", FRIST_ABEND)
    else:
        neu["anzahl"] = int(neu.pop("alle_wochen", 0))
        neu["einheit"] = EINHEIT_WOCHEN
        neu["verpasst"] = VERPASST_WEG
        neu.setdefault("wochentage", [])
    return neu


CONF_EINHEIT_KEY = "einheit"

WOCHENTAG_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def datum_kurz(datum: date, mit_tag: bool = True) -> str:
    """z.B. 'Di 10.11.'"""
    text = datum.strftime("%d.%m.")
    return f"{WOCHENTAG_KURZ[datum.weekday()]} {text}" if mit_tag else text


def _alle(anzahl: int, einheit: str) -> str:
    if anzahl == 1:
        return {EINHEIT_TAGE: "jeden Tag", EINHEIT_WOCHEN: "jede Woche"}.get(einheit, "jeden Monat")
    name = {EINHEIT_TAGE: "Tage", EINHEIT_WOCHEN: "Wochen"}.get(einheit, "Monate")
    return f"alle {anzahl} {name}"


def rhythmus_text(aufgabe: Aufgabe) -> str:
    """Wie oft die Aufgabe kommt, in Worten, z.B. 'Mo, Do, alle 2 Wochen'."""
    if aufgabe.typ == TYP_INTERVALL:
        return f"{_alle(max(aufgabe.anzahl, 1), aufgabe.einheit)} nach dem Erledigen"
    teile = []
    if aufgabe.anzahl <= 0:
        teile.append("einmalig" if aufgabe.startdatum else "")
    elif aufgabe.einheit == EINHEIT_WOCHEN:
        tage = aufgabe.wochentage or ([aufgabe.startdatum.weekday()] if aufgabe.startdatum else [])
        namen = ", ".join(WOCHENTAG_KURZ[t] for t in tage)
        teile.append(f"{namen}, {_alle(aufgabe.anzahl, aufgabe.einheit)}" if namen else _alle(aufgabe.anzahl, aufgabe.einheit))
    elif aufgabe.einheit == EINHEIT_TAGE:
        teile.append(_alle(aufgabe.anzahl, aufgabe.einheit))
    else:
        tag = aufgabe.startdatum.day if aufgabe.startdatum else 1
        teile.append(f"{_alle(aufgabe.anzahl, aufgabe.einheit)} am {tag}.")
    if aufgabe.daten:
        teile.append("einzelne Termine")
    return " + ".join(t for t in teile if t) or "einzelne Termine"


def naechste_termine(aufgabe: Aufgabe, status: Status, anzahl: int = 3) -> list[date]:
    """Die nächsten Termine ab der aktuellen Fälligkeit (Intervall: wenn pünktlich erledigt)."""
    if status.datum is None:
        return []
    if aufgabe.typ == TYP_INTERVALL:
        schritt = max(aufgabe.anzahl, 1)
        return [plus(status.datum, i * schritt, aufgabe.einheit) for i in range(anzahl)]
    return termine_ab(aufgabe, status.datum, anzahl)


def details_zeilen(stati: list[Status], zuletzt: dict[str, str]) -> str:
    """Details pro sichtbarer Aufgabe fürs Display: id|rhythmus|zuletzt|termin,termin,termin"""
    zeilen = []
    for s in sorted((s for s in stati if s.sichtbar), key=Status.sortierschluessel):
        z = zuletzt.get(s.aufgabe.id)
        zuletzt_text = datum_kurz(date.fromisoformat(z)) if z else "noch nie"
        termine = ",".join(datum_kurz(d) for d in naechste_termine(s.aufgabe, s))
        zeilen.append(f"{s.aufgabe.id}|{rhythmus_text(s.aufgabe)}|{zuletzt_text}|{termine}")
    return "\n".join(zeilen)


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
    "TYP_WOCHENTAG",
    "FRIST_ABEND",
    "FRIST_MORGEN",
]
