"""Auswahlfelder des Formulars 'Neue Aufgabe'."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HaushaltConfigEntry
from .const import (
    EINHEITEN,
    FRIST_ABEND,
    FRIST_MORGEN,
    GEF_EINHEITEN,
    HALTBARKEITEN,
    KATEGORIEN,
    TYPEN,
    VERPASST,
)
from .formular import FormularEntity
from .gefrierer_formular import (
    LEER,
    GefriererEntity,
    artikel_optionen,
    gewaehlter_artikel,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaushaltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            FormularAuswahl(manager, "typ", "mdi:shape-outline", TYPEN),
            FormularAuswahl(manager, "verpasst", "mdi:calendar-alert", VERPASST),
            FormularAuswahl(manager, "einheit", "mdi:timer-sand", EINHEITEN),
            FormularAuswahl(
                manager, "frist", "mdi:clock-outline", [FRIST_MORGEN, FRIST_ABEND]
            ),
        ]
    )
    if manager.gefrierer is not None:
        async_add_entities(
            [
                GefriererAuswahl(manager, "kategorie", "mdi:shape-outline", list(KATEGORIEN)),
                GefriererAuswahl(manager, "einheit", "mdi:scale-balance", GEF_EINHEITEN),
                GefriererAuswahl(manager, "haltbarkeit", "mdi:timer-sand", HALTBARKEITEN),
                GefriererAuswahl(
                    manager, "haltbar_einheit", "mdi:calendar-range", EINHEITEN
                ),
                GefriererArtikel(manager),
            ]
        )


class FormularAuswahl(FormularEntity, SelectEntity):
    def __init__(self, manager, feld: str, icon: str, optionen: list[str]) -> None:
        self._formular_init(manager, "select", feld)
        self._feld = feld
        self._attr_icon = icon
        self._attr_options = optionen

    @property
    def current_option(self) -> str:
        return getattr(self.formular, self._feld)

    async def async_select_option(self, option: str) -> None:
        setattr(self.formular, self._feld, option)
        self.async_write_ha_state()


class GefriererAuswahl(GefriererEntity, SelectEntity):
    def __init__(self, manager, feld: str, icon: str, optionen: list[str]) -> None:
        super().__init__(manager, "select", feld)
        self._attr_icon = icon
        self._attr_options = optionen

    @property
    def current_option(self) -> str:
        return getattr(self.formular, self._feld)

    async def async_select_option(self, option: str) -> None:
        if self._feld == "kategorie":
            self.formular.kategorie_waehlen(option)
        self._setzen(option)


class GefriererArtikel(GefriererEntity, SelectEntity):
    """Welcher Artikel entnommen wird, z.B. 'Chili · 7 Portionen'."""

    _attr_icon = "mdi:snowflake"

    def __init__(self, manager) -> None:
        super().__init__(manager, "select", "artikel")

    @property
    def options(self) -> list[str]:
        return list(artikel_optionen(self.manager)) or [LEER]

    @property
    def current_option(self) -> str:
        key = gewaehlter_artikel(self.manager)
        for text, schluessel in artikel_optionen(self.manager).items():
            if schluessel == key:
                return text
        return LEER

    async def async_select_option(self, option: str) -> None:
        self._setzen(artikel_optionen(self.manager).get(option))
