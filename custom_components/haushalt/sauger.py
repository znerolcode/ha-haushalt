"""Staubsauger fürs Flur-Display: ganze Wohnung oder einzelne Zimmer saugen, sofort
oder später, pausieren, abbrechen und zum Reinigen an einen festen Punkt fahren."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NACHHOLEN_MAX_MIN

_LOGGER = logging.getLogger(__name__)

# Zustände des Staubsaugers in Home Assistant -> Zustand fürs Display
ZUSTAND_HA = {
    "cleaning": "saugt",
    "paused": "pausiert",
    "returning": "zurueck",
    "idle": "steht",
    "error": "fehler",
}


class Sauger:
    """Steuert einen Staubsauger und merkt sich, was er gerade tut.

    daten (wird mit den übrigen Daten gespeichert):
      geplant:  {"zeit": iso, "zimmer": [ids]} oder fehlt
      auftrag:  {"zimmer": [ids]} solange ein Saugen läuft, das hier gestartet wurde
      reinigen: True, solange er zum Reinigungspunkt fährt oder dort steht
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        punkt: tuple[int, int] | None,
        daten: dict,
        speichern: Callable[[], Awaitable[None]],
        geaendert: Callable[[], None],
    ) -> None:
        self.hass = hass
        self.entity_id = entity_id
        self.punkt = punkt
        self._daten = daten
        self._speichern = speichern
        self._geaendert = geaendert
        self._timer: CALLBACK_TYPE | None = None
        self._abmelden: CALLBACK_TYPE | None = None

    # ---- Lebenszyklus ----

    @callback
    def starten(self) -> None:
        """Zustandswechsel beobachten und einen offenen Start wieder planen."""
        self._abmelden = async_track_state_change_event(
            self.hass, [self.entity_id], self._zustand_neu
        )
        if geplant := self._daten.get("geplant"):
            zeit = datetime.fromisoformat(geplant["zeit"])
            jetzt = dt_util.now()
            if zeit < jetzt - timedelta(minutes=NACHHOLEN_MAX_MIN):
                self._daten.pop("geplant")
            else:
                # Etwas Luft lassen, damit der Staubsauger nach dem Start von HA bereit ist
                self._planen(max(zeit, jetzt + timedelta(minutes=1)), geplant["zimmer"])

    @callback
    def stoppen(self) -> None:
        self._timer_stoppen()
        if self._abmelden:
            self._abmelden()
            self._abmelden = None

    @callback
    def _zustand_neu(self, event: Event) -> None:
        neu = event.data.get("new_state")
        if neu is not None and neu.state == "docked":
            # Zurück in der Station: Auftrag und Reinigen sind vorbei
            if self._daten.pop("auftrag", None) is not None or self._daten.pop(
                "reinigen", None
            ):
                self.hass.async_create_task(self._speichern())
        self._geaendert()

    # ---- Anzeige ----

    @property
    def _ha_zustand(self) -> str:
        state = self.hass.states.get(self.entity_id)
        return state.state if state else "unavailable"

    @property
    def zustand(self) -> str:
        ha = self._ha_zustand
        if self._daten.get("reinigen") and ha in ("cleaning", "idle"):
            return "reinigen"
        if ha in ZUSTAND_HA:
            return ZUSTAND_HA[ha]
        if self._daten.get("geplant"):
            return "geplant"
        return "bereit"

    @property
    def startzeit(self) -> datetime | None:
        if geplant := self._daten.get("geplant"):
            return datetime.fromisoformat(geplant["zeit"])
        return None

    @property
    def kachel(self) -> str:
        """Eine Zeile für die Haushalt-Kachel auf dem Homescreen."""
        zustand = self.zustand
        if zustand == "geplant":
            return f"Staubsaugen um {dt_util.as_local(self.startzeit).strftime('%H:%M')}"
        return {
            "saugt": "Staubsauger saugt",
            "pausiert": "Staubsauger pausiert",
            "zurueck": "Staubsauger fährt zurück",
            "reinigen": "Staubsauger beim Reinigungspunkt",
            "fehler": "Staubsauger: Fehler",
        }.get(zustand, "Staubsauger bereit")

    @property
    def anzeige(self) -> str:
        """Für das Display: zustand|uhrzeit|zimmer, z.B. 'geplant|17:05|19,20'."""
        zustand = self.zustand
        zeit = ""
        zimmer: list[int] = []
        if zustand == "geplant":
            zeit = dt_util.as_local(self.startzeit).strftime("%H:%M")
            zimmer = self._daten["geplant"]["zimmer"]
        elif zustand in ("saugt", "pausiert") and (auftrag := self._daten.get("auftrag")):
            zimmer = auftrag["zimmer"]
        return f"{zustand}|{zeit}|{','.join(str(z) for z in zimmer)}"

    # ---- Befehle ----

    async def async_saugen(self, zimmer: list[int], start_in_min: int) -> None:
        if start_in_min:
            self._planen(dt_util.now() + timedelta(minutes=start_in_min), zimmer)
            await self._speichern()
            self._geaendert()
            return
        self._timer_stoppen()
        self._daten.pop("geplant", None)
        await self._jetzt_saugen(zimmer)

    async def async_aktion(self, aktion: str) -> None:
        if aktion == "pausieren":
            await self._dienst("vacuum", "pause")
        elif aktion == "fortsetzen":
            auftrag = self._daten.get("auftrag")
            if auftrag and auftrag["zimmer"]:
                await self._befehl("resume_segment_clean")
            else:
                await self._dienst("vacuum", "start")
        elif aktion == "abbrechen":
            hatte_plan = self._daten.pop("geplant", None) is not None
            self._timer_stoppen()
            self._daten.pop("auftrag", None)
            await self._speichern()
            self._geaendert()
            # Nur zurückschicken, wenn er unterwegs ist; ein geplanter Start steht ja noch in der Station
            if self._ha_zustand in ("cleaning", "paused", "idle", "error") or not hatte_plan:
                await self._dienst("vacuum", "return_to_base")
        elif aktion == "reinigen":
            if self.punkt is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="kein_reinigungspunkt"
                )
            self._daten["reinigen"] = True
            self._daten.pop("auftrag", None)
            await self._speichern()
            await self._befehl("app_goto_target", list(self.punkt))
            self._geaendert()

    @callback
    def _planen(self, zeit: datetime, zimmer: list[int]) -> None:
        self._timer_stoppen()
        self._daten["geplant"] = {"zeit": zeit.isoformat(), "zimmer": zimmer}

        async def _faellig(_jetzt: datetime) -> None:
            self._timer = None
            geplant = self._daten.pop("geplant", None)
            if geplant is not None:
                await self._jetzt_saugen(geplant["zimmer"])

        self._timer = async_track_point_in_time(self.hass, _faellig, zeit)

    @callback
    def _timer_stoppen(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None

    async def _jetzt_saugen(self, zimmer: list[int]) -> None:
        self._daten["auftrag"] = {"zimmer": zimmer}
        self._daten.pop("reinigen", None)
        await self._speichern()
        self._geaendert()
        if zimmer:
            await self._befehl("app_segment_clean", [{"segments": zimmer, "repeat": 1}])
        else:
            await self._dienst("vacuum", "start")

    async def _befehl(self, befehl: str, params: list | None = None) -> None:
        daten: dict = {"command": befehl}
        if params is not None:
            daten["params"] = params
        await self._dienst("vacuum", "send_command", daten)

    async def _dienst(self, domain: str, dienst: str, daten: dict | None = None) -> None:
        try:
            await self.hass.services.async_call(
                domain, dienst, {"entity_id": self.entity_id, **(daten or {})}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.error("%s: %s.%s fehlgeschlagen: %s", self.entity_id, domain, dienst, err)
