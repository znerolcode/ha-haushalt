"""Tests der Integration in Home Assistant."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.haushalt.const import DOMAIN, SUBENTRY_AUFGABE

START = datetime(2026, 10, 26, 12, 0, tzinfo=ZoneInfo("Europe/Zurich"))


@pytest.fixture
async def entry(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> MockConfigEntry:
    await hass.config.async_set_time_zone("Europe/Zurich")
    freezer.move_to(START)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def aufgabe_anlegen(hass, entry, name, typ, details):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": name, "typ": typ}
    )
    assert result["step_id"] == typ
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], details)
    await hass.async_block_till_done()
    return result


def sensor_id(hass, entry, name):
    reg = er.async_get(hass)
    sub = next(s for s in entry.subentries.values() if s.title == name)
    return reg.async_get_entity_id("sensor", DOMAIN, f"{sub.subentry_id}_faelligkeit"), sub


async def test_ablauf(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):
    r = await aufgabe_anlegen(
        hass, entry, "Bettwäsche waschen", "intervall",
        {"tage": 14, "zuletzt_erledigt": "2026-10-16"},
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    r = await aufgabe_anlegen(
        hass, entry, "Altkarton deponieren", "termin",
        {"frist": "morgen", "startdatum": "2026-10-27", "alle_wochen": 2},
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY

    bett, bett_sub = sensor_id(hass, entry, "Bettwäsche waschen")
    karton, karton_sub = sensor_id(hass, entry, "Altkarton deponieren")
    assert hass.states.get(bett).state == "in 4 Tagen"
    assert hass.states.get(karton).state == "bis morgen früh"

    liste = hass.states.get("sensor.aufgaben")
    assert liste.state == "2"
    assert liste.attributes["anzeige"].splitlines()[0].startswith(
        f"{karton_sub.subentry_id}|Morgen|Altkarton deponieren|bis morgen früh|0"
    )

    # Abhaken per Knopf
    reg = er.async_get(hass)
    knopf = reg.async_get_entity_id("button", DOMAIN, f"{bett_sub.subentry_id}_erledigt")
    await hass.services.async_call("button", "press", {"entity_id": knopf}, blocking=True)
    assert hass.states.get(bett).state == "in 14 Tagen"

    # Abhaken per Dienst (so macht es das Display)
    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": karton_sub.subentry_id}, blocking=True
    )
    assert hass.states.get(karton).state == "bis in 15 Tagen"
    assert hass.states.get("sensor.aufgaben").state == "0"

    # Nach Neustart bleibt der Zustand erhalten
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(bett).state == "in 14 Tagen"
    assert hass.states.get(karton).attributes["faellig_am"] == "2026-11-10"


async def test_termin_verschwindet(hass, entry, freezer: FrozenDateTimeFactory):
    await aufgabe_anlegen(
        hass, entry, "Kehricht", "termin",
        {"frist": "abend", "startdatum": "2026-10-29", "alle_wochen": 1},
    )
    kehricht, _ = sensor_id(hass, entry, "Kehricht")
    assert hass.states.get(kehricht).state == "bis in 3 Tagen"
    freezer.move_to(datetime(2026, 10, 29, 20, 0, tzinfo=START.tzinfo))
    hass.config_entries.async_get_entry(entry.entry_id).runtime_data.aktualisieren()
    await hass.async_block_till_done()
    assert hass.states.get(kehricht).state == "bis heute Abend"
    freezer.move_to(datetime(2026, 10, 30, 0, 5, tzinfo=START.tzinfo))
    hass.config_entries.async_get_entry(entry.entry_id).runtime_data.aktualisieren()
    await hass.async_block_till_done()
    assert hass.states.get(kehricht).state == "bis in 6 Tagen"


async def test_termin_fehler(hass, entry):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Papier", "typ": "termin"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "alle_wochen": 4}
    )
    assert result["errors"] == {"base": "kein_termin"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "alle_wochen": 0, "weitere_daten": "5.11."}
    )
    assert result["errors"] == {"weitere_daten": "ungueltige_daten"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "alle_wochen": 0, "weitere_daten": "05.11.2026"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bearbeiten(hass, entry):
    await aufgabe_anlegen(
        hass, entry, "Bad putzen", "intervall", {"tage": 7, "zuletzt_erledigt": "2026-10-24"}
    )
    bad, sub = sensor_id(hass, entry, "Bad putzen")
    assert hass.states.get(bad).state == "in 5 Tagen"
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": sub.subentry_id},
    )
    assert result["step_id"] == "reconfigure_typ"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bad putzen", "typ": "intervall"}
    )
    assert result["step_id"] == "intervall"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"tage": 3}
    )
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert hass.states.get(bad).state == "morgen"


async def test_nur_eine_instanz(hass, entry):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT


async def test_optionen(hass, entry):
    await aufgabe_anlegen(
        hass, entry, "Altkarton", "termin",
        {"frist": "morgen", "startdatum": "2026-11-03", "alle_wochen": 2},
    )
    karton, _ = sensor_id(hass, entry, "Altkarton")
    assert hass.states.get(karton).state == "bis in 8 Tagen"
    assert hass.states.get("sensor.aufgaben").state == "0"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"zeit_morgen": "07:00:00", "zeit_abend": "22:00:00", "vorschau_tage": 10},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.aufgaben").state == "1"
