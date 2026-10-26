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
    CONF_ALLE_WOCHEN,
    CONF_DATEN,
    CONF_FRIST,
    CONF_NAME,
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
    FRIST_MORGEN,
    SUBENTRY_AUFGABE,
    TYP_INTERVALL,
    TYP_TERMIN,
)
from .logic import parse_daten


class HaushaltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Richtet die Integration einmalig ein."""

    VERSION = 1

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
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _typ_schema(daten: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=daten.get(CONF_NAME, vol.UNDEFINED)): TextSelector(),
            vol.Required(CONF_TYP, default=daten.get(CONF_TYP, TYP_INTERVALL)): SelectSelector(
                SelectSelectorConfig(
                    options=[TYP_INTERVALL, TYP_TERMIN],
                    translation_key="typ",
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _intervall_schema(daten: dict[str, Any], neu: bool) -> vol.Schema:
    felder: dict = {
        vol.Required(CONF_TAGE, default=daten.get(CONF_TAGE, 7)): NumberSelector(
            NumberSelectorConfig(min=1, max=365, mode=NumberSelectorMode.BOX)
        ),
    }
    if neu:
        felder[
            vol.Required(CONF_ZULETZT, default=dt_util.now().date().isoformat())
        ] = DateSelector()
    return vol.Schema(felder)


def _termin_schema(daten: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_FRIST, default=daten.get(CONF_FRIST, FRIST_ABEND)): SelectSelector(
                SelectSelectorConfig(
                    options=[FRIST_MORGEN, FRIST_ABEND],
                    translation_key="frist",
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_STARTDATUM,
                description={"suggested_value": daten.get(CONF_STARTDATUM)},
            ): DateSelector(),
            vol.Required(CONF_ALLE_WOCHEN, default=daten.get(CONF_ALLE_WOCHEN, 1)): NumberSelector(
                NumberSelectorConfig(min=0, max=52, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_DATEN,
                description={"suggested_value": daten.get(CONF_DATEN)},
            ): TextSelector(),
        }
    )


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
        self._daten = {**subentry.data, CONF_NAME: subentry.title}
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
            user_input[CONF_TAGE] = int(user_input[CONF_TAGE])
            return self._fertig(user_input)
        return self.async_show_form(
            step_id="intervall", data_schema=_intervall_schema(self._daten, self._neu)
        )

    async def async_step_termin(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        fehler: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_ALLE_WOCHEN] = int(user_input[CONF_ALLE_WOCHEN])
            try:
                daten = parse_daten(user_input.get(CONF_DATEN))
            except ValueError:
                fehler[CONF_DATEN] = "ungueltige_daten"
            else:
                if not daten and not user_input.get(CONF_STARTDATUM):
                    fehler["base"] = "kein_termin"
            if not fehler:
                return self._fertig(user_input)
        return self.async_show_form(
            step_id="termin",
            data_schema=self.add_suggested_values_to_schema(
                _termin_schema(self._daten), user_input
            )
            if user_input
            else _termin_schema(self._daten),
            errors=fehler,
        )

    def _fertig(self, user_input: dict[str, Any]) -> SubentryFlowResult:
        name = self._daten[CONF_NAME]
        typ = self._daten[CONF_TYP]
        if typ == TYP_INTERVALL:
            data = {CONF_TYP: typ, CONF_TAGE: user_input[CONF_TAGE]}
            if CONF_ZULETZT in user_input:
                data[CONF_ZULETZT] = user_input[CONF_ZULETZT]
        else:
            data = {
                CONF_TYP: typ,
                CONF_FRIST: user_input[CONF_FRIST],
                CONF_STARTDATUM: user_input.get(CONF_STARTDATUM),
                CONF_ALLE_WOCHEN: user_input[CONF_ALLE_WOCHEN],
                CONF_DATEN: user_input.get(CONF_DATEN, ""),
            }
        if self._neu:
            return self.async_create_entry(title=name, data=data)
        return self.async_update_and_abort(
            self._get_entry(), self._get_reconfigure_subentry(), title=name, data=data
        )
