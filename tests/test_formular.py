"""Tests des Formulars 'Neue Aufgabe' (für Konten ohne Administratorrechte)."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .test_init import entry, sensor_id  # noqa: F401


async def setzen(hass, plattform, feld, **daten):
    dienst = {
        "text": "set_value",
        "number": "set_value",
        "date": "set_value",
        "select": "select_option",
    }[plattform]
    await hass.services.async_call(
        plattform, dienst, {"entity_id": f"{plattform}.neue_aufgabe_{feld}", **daten},
        blocking=True,
    )


async def anlegen(hass):
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.neue_aufgabe_anlegen"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_felder_vorhanden(hass: HomeAssistant, entry):  # noqa: F811
    assert hass.states.get("select.neue_aufgabe_typ").state == "intervall"
    assert hass.states.get("number.neue_aufgabe_anzahl").state == "1"
    assert hass.states.get("select.neue_aufgabe_einheit").state == "wochen"
    assert hass.states.get("select.neue_aufgabe_verpasst").state == "stehen"
    assert hass.states.get("date.neue_aufgabe_zuletzt").state == "2026-10-26"
    assert hass.states.get("date.neue_aufgabe_datum").state == "unknown"
    assert hass.states.get("switch.neue_aufgabe_mo").state == "off"
    assert hass.states.get("text.neue_aufgabe_name").state == ""
    assert hass.states.get("sensor.neue_aufgabe_meldung").state == "unknown"


async def test_intervall(hass: HomeAssistant, entry):  # noqa: F811
    await setzen(hass, "text", "name", value="Bettwäsche")
    await setzen(hass, "number", "anzahl", value=2)
    await setzen(hass, "date", "zuletzt", date="2026-10-16")
    await anlegen(hass)

    bett, sub = sensor_id(hass, entry, "Bettwäsche")
    assert sub.data == {
        "typ": "intervall", "verpasst": "stehen", "anzahl": 2, "einheit": "wochen",
        "frist": "abend", "zuletzt_erledigt": "2026-10-16",
    }
    assert hass.states.get(bett).state == "in 4 Tagen"
    assert hass.states.get("sensor.neue_aufgabe_meldung").state == "Bettwäsche"
    # Formular ist danach wieder leer
    assert hass.states.get("text.neue_aufgabe_name").state == ""
    assert hass.states.get("number.neue_aufgabe_anzahl").state == "1"
    assert hass.states.get("select.neue_aufgabe_einheit").state == "wochen"
    assert hass.states.get("select.neue_aufgabe_verpasst").state == "stehen"


async def test_wochentag(hass: HomeAssistant, entry):  # noqa: F811
    await setzen(hass, "text", "name", value="Pflanzen giessen")
    await setzen(hass, "select", "typ", option="termin")
    with pytest.raises(ServiceValidationError):
        await anlegen(hass)
    for tag in ("do", "mo"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": f"switch.neue_aufgabe_{tag}"}, blocking=True
        )
    await setzen(hass, "number", "anzahl", value=2)
    await anlegen(hass)
    pflanzen, sub = sensor_id(hass, entry, "Pflanzen giessen")
    # Nach dem Neuladen läuft die Integration weiter (Plattform date.py vs. datetime.date)
    assert hass.states.get(pflanzen).state == "heute"
    assert sub.data == {
        "typ": "termin", "verpasst": "stehen", "anzahl": 2, "einheit": "wochen",
        "frist": "abend", "startdatum": None, "wochentage": ["mo", "do"],
        "weitere_daten": "", "mindestabstand": 3,
    }


async def test_termin(hass: HomeAssistant, entry):  # noqa: F811
    await setzen(hass, "text", "name", value="Altkarton")
    await setzen(hass, "select", "typ", option="termin")
    await setzen(hass, "select", "verpasst", option="weg")
    await setzen(hass, "number", "anzahl", value=0)
    with pytest.raises(ServiceValidationError):
        await anlegen(hass)
    await setzen(hass, "text", "weitere", value="5.11.2026, 32.11.2026")
    with pytest.raises(ServiceValidationError):
        await anlegen(hass)
    await setzen(hass, "text", "weitere", value="27.10.2026")
    await setzen(hass, "select", "frist", option="morgen")
    await anlegen(hass)
    karton, sub = sensor_id(hass, entry, "Altkarton")
    assert sub.data["frist"] == "morgen"
    assert sub.data["anzahl"] == 0
    assert hass.states.get(karton).state == "bis morgen früh"


async def test_ohne_name(hass: HomeAssistant, entry):  # noqa: F811
    await setzen(hass, "text", "name", value="   ")
    with pytest.raises(ServiceValidationError):
        await anlegen(hass)
    assert not entry.subentries
