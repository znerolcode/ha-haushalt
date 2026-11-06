"""Formular 'Neue Aufgabe' für Konten ohne Administratorrechte.

Aufgaben werden sonst über die Konfiguration der Integration angelegt, die HA nur
Administratoren zeigt. Die Felder des Formulars sind deshalb eigene Entitäten
(Text, Auswahl, Zahl, Schalter, Datum), die jedes Konto in einem Dashboard
ausfüllen darf. Der Knopf 'Anlegen' macht daraus eine normale Aufgabe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.util import dt as dt_util

from .config_flow import aufgabe_daten, termin_pruefen
from .const import (
    CONF_ANZAHL,
    CONF_DATEN,
    CONF_EINHEIT,
    CONF_FRIST,
    CONF_MINDESTABSTAND,
    CONF_STARTDATUM,
    CONF_WOCHENTAGE,
    CONF_ZULETZT,
    DEFAULT_MINDESTABSTAND,
    DOMAIN,
    EINHEIT_WOCHEN,
    FRIST_ABEND,
    SUBENTRY_AUFGABE,
    TYP_INTERVALL,
    VERPASST_STEHEN,
)

if TYPE_CHECKING:
    from . import HaushaltManager

# Alle Entitäten des Formulars heissen <plattform>.neue_aufgabe_<feld>,
# darauf verweist die Dashboard-Vorlage (esphome/dashboard-neue-aufgabe.yaml)
PRAEFIX = "neue_aufgabe"


@dataclass
class Formular:
    """Inhalt des Formulars. Lebt nur im Speicher und startet nach dem Anlegen leer."""

    name: str = ""
    typ: str = TYP_INTERVALL
    verpasst: str = VERPASST_STEHEN
    anzahl: int = 1
    einheit: str = EINHEIT_WOCHEN
    zuletzt: date | None = None
    wochentage: set[str] = field(default_factory=set)
    mindestabstand: int = DEFAULT_MINDESTABSTAND
    datum: date | None = None
    frist: str = FRIST_ABEND
    weitere: str = ""

    def daten(self) -> tuple[str, dict[str, Any]]:
        """Name und Daten der Aufgabe, so wie sie das Konfigurationsformular speichert."""
        name = self.name.strip()
        if not name:
            raise _fehler("kein_name")
        eingabe: dict[str, Any] = {
            CONF_ANZAHL: self.anzahl,
            CONF_EINHEIT: self.einheit,
            CONF_FRIST: self.frist,
        }
        if self.typ == TYP_INTERVALL:
            eingabe[CONF_ZULETZT] = (self.zuletzt or dt_util.now().date()).isoformat()
        else:
            eingabe.update(
                {
                    CONF_STARTDATUM: self.datum.isoformat() if self.datum else None,
                    CONF_WOCHENTAGE: list(self.wochentage),
                    CONF_DATEN: self.weitere,
                    CONF_MINDESTABSTAND: self.mindestabstand,
                }
            )
            if fehler := termin_pruefen(eingabe):
                raise _fehler(next(iter(fehler.values())))
        return name, aufgabe_daten(self.typ, self.verpasst, eingabe)


def _fehler(schluessel: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=schluessel)


async def async_aufgabe_anlegen(manager: HaushaltManager) -> str:
    """Legt die Aufgabe aus dem Formular an. Die Integration lädt danach neu."""
    name, daten = manager.formular.daten()
    await manager.async_formular_meldung(name)
    manager.hass.config_entries.async_add_subentry(
        manager.entry,
        ConfigSubentry(
            data=MappingProxyType(daten),
            subentry_type=SUBENTRY_AUFGABE,
            title=name,
            unique_id=None,
        ),
    )
    return name


def formular_geraet(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{PRAEFIX}")},
        name="Neue Aufgabe",
        manufacturer="Haushalt",
        model="Formular",
        entry_type=DeviceEntryType.SERVICE,
    )


class FormularEntity:
    """Gemeinsames für alle Felder des Formulars (als Mixin vor der HA-Klasse)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def _formular_init(self, manager: HaushaltManager, plattform: str, feld: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{PRAEFIX}_{feld}"
        self._attr_translation_key = f"{PRAEFIX}_{feld}"
        self._attr_device_info = formular_geraet(manager.entry.entry_id)
        self.entity_id = f"{plattform}.{PRAEFIX}_{feld}"

    @property
    def formular(self) -> Formular:
        return self.manager.formular
