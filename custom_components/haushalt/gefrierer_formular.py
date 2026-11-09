"""Formular 'Gefrierer' für das Handy: einfrieren und entnehmen, auch ohne Administratorrechte.

Wie beim Formular 'Neue Aufgabe' sind die Felder eigene Entitäten (Text, Auswahl, Zahl,
Datum, Knopf), die jedes Konto in einem Dashboard ausfüllen darf. Sie heissen alle
<plattform>.gefrierer_<feld>, darauf verweist die Vorlage dashboard/gefrierer.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EINHEIT_MONATE,
    GEF_EINHEIT_PORTIONEN,
    HALTBAR_KATEGORIE,
    HALTBAR_ZEITRAUM,
    KAT_BENUTZERDEFINIERT,
    KAT_MEAL_PREP,
)
from .entity import HaushaltEntity
from .gefrierer import GefriererFehler, haltbar_bis, menge_text

if TYPE_CHECKING:
    from . import HaushaltManager

PRAEFIX = "gefrierer"
LEER = "Gefrierer ist leer"


@dataclass
class GefriererFormular:
    """Inhalt des Formulars. Lebt nur im Speicher."""

    name: str = ""
    kategorie: str = KAT_MEAL_PREP
    menge: int = 1
    einheit: str = GEF_EINHEIT_PORTIONEN
    eingefroren: date | None = None
    haltbarkeit: str = HALTBAR_KATEGORIE
    haltbar_anzahl: int = 3
    haltbar_einheit: str = EINHEIT_MONATE
    haltbar_datum: date | None = None
    # Entnehmen
    artikel: str | None = None
    entnahme: int = 1

    @property
    def eingefroren_am(self) -> date:
        return self.eingefroren or dt_util.now().date()

    def kategorie_waehlen(self, kategorie: str) -> None:
        self.kategorie = kategorie
        # Benutzerdefiniert hat keinen Standard: dann gleich den Zeitraum anbieten
        if kategorie == KAT_BENUTZERDEFINIERT and self.haltbarkeit == HALTBAR_KATEGORIE:
            self.haltbarkeit = HALTBAR_ZEITRAUM

    def bis(self) -> date:
        return haltbar_bis(
            self.eingefroren_am,
            self.kategorie,
            self.haltbarkeit,
            self.haltbar_anzahl,
            self.haltbar_einheit,
            self.haltbar_datum,
        )

    def vorschau(self) -> date | None:
        try:
            return self.bis()
        except GefriererFehler:
            return None

    def einfrieren_leeren(self) -> None:
        self.name = ""
        self.menge = 1
        self.eingefroren = None
        self.haltbar_datum = None


def gefrierer_geraet(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{PRAEFIX}")},
        name="Gefrierer",
        manufacturer="Haushalt",
        model="Formular",
        entry_type=DeviceEntryType.SERVICE,
    )


class GefriererEntity(HaushaltEntity):
    """Feld des Gefrierer-Formulars. Wird bei jeder Änderung im Gefrierer neu gezeichnet."""

    def __init__(self, manager: HaushaltManager, plattform: str, feld: str) -> None:
        super().__init__(manager)
        self._feld = feld
        self._attr_unique_id = f"{manager.entry.entry_id}_{PRAEFIX}_{feld}"
        self._attr_translation_key = f"{PRAEFIX}_{feld}"
        self._attr_device_info = gefrierer_geraet(manager.entry.entry_id)
        self.entity_id = f"{plattform}.{PRAEFIX}_{feld}"

    @property
    def formular(self) -> GefriererFormular:
        return self.manager.gefrierer_formular

    def _setzen(self, wert) -> None:
        setattr(self.formular, self._feld, wert)
        # Auch die anderen Felder (z.B. 'Haltbar bis') neu zeichnen
        async_dispatcher_send(self.hass, self.manager.signal)


def artikel_optionen(manager: HaushaltManager) -> dict[str, str]:
    """Beschriftung -> Artikel-Kennung für die Auswahl beim Entnehmen."""
    return {
        f"{a.name} · {menge_text(a.menge, a.einheit)}": a.schluessel
        for a in manager.gefrierer.artikel()
    }


def gewaehlter_artikel(manager: HaushaltManager) -> str | None:
    artikel = [a.schluessel for a in manager.gefrierer.artikel()]
    if manager.gefrierer_formular.artikel in artikel:
        return manager.gefrierer_formular.artikel
    return artikel[0] if artikel else None
