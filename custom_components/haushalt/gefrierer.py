"""Gefrierer: was drin ist, wie viel davon und bis wann es haltbar ist.

Jedes Einfrieren ist eine Packung (Name, Kategorie, Menge, Einheit, Datum). Packungen mit
gleichem Namen und gleicher Einheit erscheinen zusammen als ein Artikel, z.B.
"Chili 7 Port.". Entnommen wird immer zuerst aus der Packung, die am frühesten abläuft.
Ohne Home-Assistant-Abhängigkeiten, damit es sich einfach testen lässt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import uuid

from .const import (
    EINHEIT_MONATE,
    GEF_BALD_TAGE,
    GEF_EINHEIT_GRAMM,
    GEF_EINHEIT_PORTIONEN,
    GEF_EINHEIT_STUECK,
    HALTBAR_DATUM,
    HALTBAR_ZEITRAUM,
    KAT_MEAL_PREP,
    KATEGORIEN,
)
from .logic import plus

GRUPPE_ABGELAUFEN = "Abgelaufen"
GRUPPE_BALD = "Bald aufbrauchen"
GRUPPE_SPAETER = "Später"

# Kürzel fürs Display
EINHEIT_KURZ = {GEF_EINHEIT_PORTIONEN: "p", GEF_EINHEIT_STUECK: "s", GEF_EINHEIT_GRAMM: "g"}
# Entnahme-Knöpfe am Display (dazu kommt immer "alle")
ENTNAHME_SCHRITTE = {
    GEF_EINHEIT_PORTIONEN: [1, 2, 3],
    GEF_EINHEIT_STUECK: [1, 2],
    GEF_EINHEIT_GRAMM: [100, 250],
}


class GefriererFehler(ValueError):
    """Ungültige Eingabe; args[0] ist der Übersetzungsschlüssel."""


@dataclass
class Packung:
    id: str
    name: str
    kategorie: str
    menge: int
    einheit: str
    eingefroren: date
    haltbar_bis: date

    def speichern(self) -> dict:
        d = asdict(self)
        d["eingefroren"] = self.eingefroren.isoformat()
        d["haltbar_bis"] = self.haltbar_bis.isoformat()
        return d

    @classmethod
    def laden(cls, d: dict) -> Packung:
        return cls(
            id=d["id"],
            name=d["name"],
            kategorie=d.get("kategorie", KAT_MEAL_PREP),
            menge=int(d["menge"]),
            einheit=d["einheit"],
            eingefroren=date.fromisoformat(d["eingefroren"]),
            haltbar_bis=date.fromisoformat(d["haltbar_bis"]),
        )

    def sortierschluessel(self) -> tuple:
        return (self.haltbar_bis, self.eingefroren, self.id)


def schluessel(name: str, einheit: str) -> str:
    """Kennung eines Artikels (alle Packungen mit diesem Namen und dieser Einheit)."""
    return f"{name.strip().casefold()}~{einheit}"


def name_bereinigen(name: str) -> str:
    # '|' und Zeilenumbrüche trennen Felder und Zeilen in der Display-Liste
    return " ".join(name.replace("|", "/").split())


def haltbar_bis(
    eingefroren: date,
    kategorie: str,
    art: str,
    anzahl: int | None = None,
    einheit: str | None = None,
    datum: date | None = None,
) -> date:
    """Bis wann eine Packung haltbar ist, je nach gewählter Art."""
    if art == HALTBAR_DATUM:
        if datum is None:
            raise GefriererFehler("kein_haltbar_datum")
        return datum
    if art == HALTBAR_ZEITRAUM:
        if not anzahl or anzahl < 1:
            raise GefriererFehler("kein_zeitraum")
        return plus(eingefroren, int(anzahl), einheit or EINHEIT_MONATE)
    monate = KATEGORIEN.get(kategorie)
    if monate is None:
        raise GefriererFehler("zeitraum_waehlen")
    return plus(eingefroren, monate, EINHEIT_MONATE)


def menge_text(menge: int, einheit: str, kurz: bool = False) -> str:
    if einheit == GEF_EINHEIT_GRAMM:
        if menge >= 1000:
            kg = f"{menge / 1000:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{kg} kg"
        return f"{menge} g"
    if einheit == GEF_EINHEIT_STUECK:
        return f"{menge} Stück"
    if kurz:
        return f"{menge} Port."
    return f"{menge} Portion" if menge == 1 else f"{menge} Portionen"


def rest_text(tage: int) -> str:
    if tage < 0:
        return "seit 1 Tag" if tage == -1 else f"seit {-tage} Tagen"
    if tage == 0:
        return "läuft heute ab"
    if tage == 1:
        return "noch 1 Tag"
    if tage < 60:
        return f"noch {tage} Tage"
    return f"noch {tage // 30} Monate"


def gruppe_fuer(tage: int) -> str:
    if tage < 0:
        return GRUPPE_ABGELAUFEN
    if tage < GEF_BALD_TAGE:
        return GRUPPE_BALD
    return GRUPPE_SPAETER


@dataclass
class Artikel:
    """Alle Packungen mit gleichem Namen und gleicher Einheit."""

    schluessel: str
    packungen: list[Packung] = field(default_factory=list)

    @property
    def erste(self) -> Packung:
        return self.packungen[0]

    @property
    def name(self) -> str:
        return self.erste.name

    @property
    def einheit(self) -> str:
        return self.erste.einheit

    @property
    def kategorie(self) -> str:
        return self.erste.kategorie

    @property
    def meal_prep(self) -> bool:
        return any(p.kategorie == KAT_MEAL_PREP for p in self.packungen)

    @property
    def menge(self) -> int:
        return sum(p.menge for p in self.packungen)

    @property
    def haltbar_bis(self) -> date:
        return self.erste.haltbar_bis

    def tage(self, heute: date) -> int:
        return (self.haltbar_bis - heute).days

    def entnahme_optionen(self) -> list[tuple[int, str]]:
        """(Menge, Beschriftung) der Knöpfe am Display, zuletzt immer 'alle'."""
        menge = self.menge
        optionen = [
            (s, menge_text(s, self.einheit, kurz=True))
            for s in ENTNAHME_SCHRITTE.get(self.einheit, [1])
            if s < menge
        ]
        if self.einheit == GEF_EINHEIT_GRAMM:
            optionen.append((menge, f"alle {menge} g"))
        else:
            optionen.append((menge, f"alle {menge}"))
        return optionen

    def info(self, heute: date) -> dict:
        tage = self.tage(heute)
        return {
            "artikel": self.schluessel,
            "name": self.name,
            "kategorie": self.kategorie,
            "meal_prep": self.meal_prep,
            "menge": self.menge,
            "einheit": self.einheit,
            "menge_text": menge_text(self.menge, self.einheit),
            "haltbar_bis": self.haltbar_bis.isoformat(),
            "tage": tage,
            "text": rest_text(tage),
            "gruppe": gruppe_fuer(tage),
            "packungen": [
                {
                    "menge": p.menge,
                    "eingefroren": p.eingefroren.isoformat(),
                    "haltbar_bis": p.haltbar_bis.isoformat(),
                }
                for p in self.packungen
            ],
        }


class Gefrierer:
    """Inhalt des Gefrierers. `daten` ist der gespeicherte Teil: {"packungen": [...]}."""

    def __init__(self, daten: dict) -> None:
        self._daten = daten
        daten.setdefault("packungen", [])
        daten.setdefault("meldung", {})
        self.packungen: list[Packung] = []
        for d in daten["packungen"]:
            try:
                self.packungen.append(Packung.laden(d))
            except (KeyError, ValueError):
                continue

    def _sichern(self) -> None:
        self._daten["packungen"] = [p.speichern() for p in self.packungen]

    @property
    def meldung(self) -> dict:
        return self._daten["meldung"]

    def melden(self, text: str, zeit: str) -> None:
        self._daten["meldung"] = {"text": text, "zeit": zeit}

    def artikel(self) -> list[Artikel]:
        """Artikel sortiert nach Ablauf (frühester zuerst)."""
        gruppen: dict[str, Artikel] = {}
        for p in sorted(self.packungen, key=Packung.sortierschluessel):
            key = schluessel(p.name, p.einheit)
            gruppen.setdefault(key, Artikel(key)).packungen.append(p)
        return sorted(gruppen.values(), key=lambda a: (a.haltbar_bis, a.name.casefold()))

    def finden(self, key: str) -> Artikel | None:
        for a in self.artikel():
            if a.schluessel == key:
                return a
        return None

    def einfrieren(
        self,
        name: str,
        kategorie: str,
        menge: int,
        einheit: str,
        eingefroren: date,
        bis: date,
    ) -> Packung:
        name = name_bereinigen(name)
        if not name:
            raise GefriererFehler("kein_name")
        if menge < 1:
            raise GefriererFehler("keine_menge")
        if kategorie not in KATEGORIEN:
            raise GefriererFehler("unbekannte_kategorie")
        # Gleiche Schreibweise wie bestehende Packungen, damit sie zusammen erscheinen
        if vorhanden := self.finden(schluessel(name, einheit)):
            name = vorhanden.name
        packung = Packung(
            id=uuid.uuid4().hex[:12],
            name=name,
            kategorie=kategorie,
            menge=int(menge),
            einheit=einheit,
            eingefroren=eingefroren,
            haltbar_bis=bis,
        )
        self.packungen.append(packung)
        self._sichern()
        return packung

    def entnehmen(self, key: str, menge: int | None = None) -> tuple[Artikel, int]:
        """Nimmt `menge` (None = alles) aus dem Artikel, zuerst aus der ältesten Packung.

        Gibt den Artikel (vor der Entnahme) und die tatsächlich entnommene Menge zurück.
        """
        artikel = self.finden(key)
        if artikel is None:
            raise GefriererFehler("unbekannter_artikel")
        rest = artikel.menge if menge is None else min(int(menge), artikel.menge)
        if rest < 1:
            raise GefriererFehler("keine_menge")
        entnommen = rest
        for p in artikel.packungen:
            if rest <= 0:
                break
            weg = min(p.menge, rest)
            p.menge -= weg
            rest -= weg
        self.packungen = [p for p in self.packungen if p.menge > 0]
        self._sichern()
        return artikel, entnommen

    # ---- Ausgaben fürs Display und die Kacheln ----

    def anzeige(self, heute: date) -> str:
        """Eine Zeile pro Artikel, Felder mit '|' getrennt:

        artikel|gruppe|name|menge|rest|abgelaufen(0/1)|meal_prep(0/1)|optionen
        optionen: menge:beschriftung, mit ';' getrennt, z.B. '1:1 Port.;7:alle 7'
        """
        zeilen = []
        for a in self.artikel():
            tage = a.tage(heute)
            optionen = ";".join(f"{m}:{t}" for m, t in a.entnahme_optionen())
            zeilen.append(
                f"{a.schluessel}|{gruppe_fuer(tage)}|{a.name}|"
                f"{menge_text(a.menge, a.einheit, kurz=True)}|{rest_text(tage)}|"
                f"{1 if tage < 0 else 0}|{1 if a.meal_prep else 0}|{optionen}"
            )
        return "\n".join(zeilen)

    def kachel(self, heute: date) -> str:
        """Drei Zeilen für die Kachel auf dem Homescreen, je 'vor|hervorgehoben|nach'."""
        artikel = self.artikel()
        if not artikel:
            return "Leer||\nNichts eingefroren||\n||"
        abgelaufen = sum(1 for a in artikel if a.tage(heute) < 0)
        bald = sum(1 for a in artikel if 0 <= a.tage(heute) < GEF_BALD_TAGE)
        anzahl = f"{len(artikel)} Artikel"
        if abgelaufen:
            zeile1 = f"{anzahl} · |{abgelaufen} abgelaufen|" + (f" · {bald} bald" if bald else "")
        else:
            zeile1 = f"{anzahl}" + (f" · {bald} bald" if bald else "") + "||"
        meals = [
            f"{a.name} {a.menge}" if a.einheit == GEF_EINHEIT_PORTIONEN
            else f"{a.name} {menge_text(a.menge, a.einheit, kurz=True)}"
            for a in artikel if a.meal_prep
        ]
        zeile2 = ("Meal-Prep: " + " · ".join(meals)) if meals else "Meal-Prep: keine"
        zuerst = [a.name for a in artikel[:3]]
        zeile3 = "Zuerst: " + ", ".join(zuerst)
        return "\n".join([zeile1, f"{zeile2}||", f"{zeile3}||"])
