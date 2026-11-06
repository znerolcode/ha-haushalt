"""Formulare: Integration einrichten, Optionen und Aufgaben erfassen."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DateSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ANZAHL,
    CONF_DATEN,
    CONF_EINHEIT,
    CONF_FRIST,
    CONF_MINDESTABSTAND,
    CONF_NAME,
    CONF_REINIGUNG_X,
    CONF_REINIGUNG_Y,
    CONF_STARTDATUM,
    CONF_STAUBSAUGER,
    CONF_TYP,
    CONF_VERPASST,
    CONF_VORSCHAU,
    CONF_WETTER,
    CONF_WOCHENTAGE,
    CONF_ZEIT_ABEND,
    CONF_ZEIT_MORGEN,
    CONF_ZULETZT,
    DEFAULT_MINDESTABSTAND,
    DEFAULT_VORSCHAU,
    DEFAULT_ZEIT_ABEND,
    DEFAULT_ZEIT_MORGEN,
    DOMAIN,
    EINHEIT_TAGE,
    EINHEIT_WOCHEN,
    EINHEITEN,
    FRIST_ABEND,
    FRIST_MORGEN,
    SUBENTRY_AUFGABE,
    TYP_INTERVALL,
    TYPEN,
    VERPASST,
    VERPASST_STEHEN,
    VERPASST_WEG,
    WOCHENTAGE,
)
from .logic import daten_umwandeln, parse_daten


class HaushaltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Richtet die Integration einmalig ein."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Haushalt", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HaushaltOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_AUFGABE: AufgabeFlow}


class HaushaltOptionsFlow(OptionsFlow):
    """Fristzeiten und Vorschau einstellen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        optionen = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ZEIT_MORGEN,
                    default=optionen.get(CONF_ZEIT_MORGEN, DEFAULT_ZEIT_MORGEN),
                ): TimeSelector(),
                vol.Required(
                    CONF_ZEIT_ABEND,
                    default=optionen.get(CONF_ZEIT_ABEND, DEFAULT_ZEIT_ABEND),
                ): TimeSelector(),
                vol.Required(
                    CONF_VORSCHAU,
                    default=optionen.get(CONF_VORSCHAU, DEFAULT_VORSCHAU),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=60, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_WETTER,
                    description={"suggested_value": optionen.get(CONF_WETTER)},
                ): EntitySelector(EntitySelectorConfig(domain="weather")),
                vol.Optional(
                    CONF_STAUBSAUGER,
                    description={"suggested_value": optionen.get(CONF_STAUBSAUGER)},
                ): EntitySelector(EntitySelectorConfig(domain="vacuum")),
                vol.Optional(
                    CONF_REINIGUNG_X,
                    description={"suggested_value": optionen.get(CONF_REINIGUNG_X)},
                ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=1)),
                vol.Optional(
                    CONF_REINIGUNG_Y,
                    description={"suggested_value": optionen.get(CONF_REINIGUNG_Y)},
                ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=1)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _typ_schema(daten: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=daten.get(CONF_NAME, vol.UNDEFINED)): TextSelector(),
            vol.Required(CONF_TYP, default=daten.get(CONF_TYP, TYP_INTERVALL)): SelectSelector(
                SelectSelectorConfig(
                    options=TYPEN, translation_key="typ", mode=SelectSelectorMode.LIST
                )
            ),
            vol.Required(
                CONF_VERPASST, default=daten.get(CONF_VERPASST, VERPASST_STEHEN)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=VERPASST, translation_key="verpasst", mode=SelectSelectorMode.LIST
                )
            ),
        }
    )


def _einheit_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=EINHEITEN, translation_key="einheit", mode=SelectSelectorMode.DROPDOWN
        )
    )


def _frist_feld(daten: dict[str, Any], felder: dict) -> None:
    felder[vol.Required(CONF_FRIST, default=daten.get(CONF_FRIST, FRIST_ABEND))] = (
        SelectSelector(
            SelectSelectorConfig(
                options=[FRIST_MORGEN, FRIST_ABEND],
                translation_key="frist",
                mode=SelectSelectorMode.LIST,
            )
        )
    )


def _intervall_schema(daten: dict[str, Any], neu: bool) -> vol.Schema:
    felder: dict = {
        vol.Required(CONF_ANZAHL, default=daten.get(CONF_ANZAHL, 7)): NumberSelector(
            NumberSelectorConfig(min=1, max=365, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_EINHEIT, default=daten.get(CONF_EINHEIT, EINHEIT_TAGE)): (
            _einheit_selector()
        ),
    }
    if daten.get(CONF_VERPASST) == VERPASST_WEG:
        _frist_feld(daten, felder)
    if neu:
        felder[
            vol.Required(CONF_ZULETZT, default=dt_util.now().date().isoformat())
        ] = DateSelector()
    return vol.Schema(felder)


def _termin_schema(daten: dict[str, Any], neu: bool) -> vol.Schema:
    felder: dict = {
        vol.Optional(
            CONF_STARTDATUM,
            description={
                "suggested_value": daten.get(CONF_STARTDATUM)
                if not neu
                else dt_util.now().date().isoformat()
            },
        ): DateSelector(),
        vol.Required(CONF_ANZAHL, default=daten.get(CONF_ANZAHL, 1)): NumberSelector(
            NumberSelectorConfig(min=0, max=365, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_EINHEIT, default=daten.get(CONF_EINHEIT, EINHEIT_WOCHEN)): (
            _einheit_selector()
        ),
        vol.Optional(CONF_WOCHENTAGE, default=daten.get(CONF_WOCHENTAGE, [])): SelectSelector(
            SelectSelectorConfig(
                options=WOCHENTAGE,
                multiple=True,
                translation_key="wochentag",
                mode=SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_DATEN, description={"suggested_value": daten.get(CONF_DATEN)}
        ): TextSelector(),
    }
    if daten.get(CONF_VERPASST) == VERPASST_WEG:
        _frist_feld(daten, felder)
    else:
        felder[
            vol.Required(
                CONF_MINDESTABSTAND,
                default=daten.get(CONF_MINDESTABSTAND, DEFAULT_MINDESTABSTAND),
            )
        ] = NumberSelector(NumberSelectorConfig(min=0, max=60, mode=NumberSelectorMode.BOX))
        if neu:
            felder[vol.Optional(CONF_ZULETZT)] = DateSelector()
    return vol.Schema(felder)


def termin_pruefen(daten: dict[str, Any]) -> dict[str, str]:
    """Fehler eines Termins: braucht ein Startdatum, einzelne Daten oder Wochentage."""
    try:
        einzelne = parse_daten(daten.get(CONF_DATEN))
    except ValueError:
        return {CONF_DATEN: "ungueltige_daten"}
    wochentage = daten.get(CONF_EINHEIT) == EINHEIT_WOCHEN and daten.get(CONF_WOCHENTAGE)
    if not einzelne and not daten.get(CONF_STARTDATUM) and not wochentage:
        return {"base": "kein_termin"}
    return {}


def aufgabe_daten(typ: str, verpasst: str, eingabe: dict[str, Any]) -> dict[str, Any]:
    """Gespeicherte Daten einer Aufgabe (auch vom Formular 'Neue Aufgabe' benutzt)."""
    data: dict[str, Any] = {
        CONF_TYP: typ,
        CONF_VERPASST: verpasst,
        CONF_ANZAHL: int(eingabe[CONF_ANZAHL]),
        CONF_EINHEIT: eingabe[CONF_EINHEIT],
        CONF_FRIST: eingabe.get(CONF_FRIST, FRIST_ABEND),
    }
    if typ == TYP_INTERVALL:
        data[CONF_ANZAHL] = max(data[CONF_ANZAHL], 1)
    else:
        data[CONF_STARTDATUM] = eingabe.get(CONF_STARTDATUM) or None
        data[CONF_WOCHENTAGE] = (
            [t for t in WOCHENTAGE if t in eingabe.get(CONF_WOCHENTAGE, [])]
            if data[CONF_EINHEIT] == EINHEIT_WOCHEN
            else []
        )
        data[CONF_DATEN] = (eingabe.get(CONF_DATEN) or "").strip()
        data[CONF_MINDESTABSTAND] = int(
            eingabe.get(CONF_MINDESTABSTAND, DEFAULT_MINDESTABSTAND)
        )
    if eingabe.get(CONF_ZULETZT):
        data[CONF_ZULETZT] = eingabe[CONF_ZULETZT]
    return data


class AufgabeFlow(ConfigSubentryFlow):
    """Aufgabe hinzufügen oder bearbeiten."""

    def __init__(self) -> None:
        self._daten: dict[str, Any] = {}

    @property
    def _neu(self) -> bool:
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._schritt_typ(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        self._daten = {**daten_umwandeln(dict(subentry.data)), CONF_NAME: subentry.title}
        return await self._schritt_typ(None, step_id="reconfigure_typ")

    async def async_step_reconfigure_typ(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._schritt_typ(user_input, step_id="reconfigure_typ")

    async def _schritt_typ(
        self, user_input: dict[str, Any] | None, step_id: str = "user"
    ) -> SubentryFlowResult:
        if user_input is not None:
            user_input[CONF_NAME] = user_input[CONF_NAME].strip()
            self._daten.update(user_input)
            if user_input[CONF_TYP] == TYP_INTERVALL:
                return await self.async_step_intervall()
            return await self.async_step_termin()
        return self.async_show_form(step_id=step_id, data_schema=_typ_schema(self._daten))

    async def async_step_intervall(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            return self._fertig(user_input)
        return self.async_show_form(
            step_id="intervall", data_schema=_intervall_schema(self._daten, self._neu)
        )

    async def async_step_termin(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        fehler: dict[str, str] = {}
        if user_input is not None:
            fehler = termin_pruefen(user_input)
            if not fehler:
                return self._fertig(user_input)
        schema = _termin_schema(self._daten, self._neu)
        return self.async_show_form(
            step_id="termin",
            data_schema=self.add_suggested_values_to_schema(schema, user_input)
            if user_input
            else schema,
            errors=fehler,
        )

    def _fertig(self, user_input: dict[str, Any]) -> SubentryFlowResult:
        name = self._daten[CONF_NAME]
        data = aufgabe_daten(self._daten[CONF_TYP], self._daten[CONF_VERPASST], user_input)
        if self._neu:
            return self.async_create_entry(title=name, data=data)
        return self.async_update_and_abort(
            self._get_entry(), self._get_reconfigure_subentry(), title=name, data=data
        )
