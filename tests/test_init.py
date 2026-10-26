"""Tests der Integration in Home Assistant."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)
import voluptuous as vol

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


def knopf_id(hass, sub, suffix):
    return er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{sub.subentry_id}_{suffix}"
    )


async def staubsaugen_anlegen(hass, entry):
    await aufgabe_anlegen(
        hass, entry, "Zum Staubsaugen vorbereiten", "intervall",
        {"tage": 3, "zuletzt_erledigt": "2026-10-23", "staubsauger": "vacuum.robi"},
    )
    _, sub = sensor_id(hass, entry, "Zum Staubsaugen vorbereiten")
    saugstart = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{sub.subentry_id}_saugstart"
    )
    return sub, saugstart


async def zeit_vor(hass, freezer, minuten):
    freezer.tick(timedelta(minutes=minuten))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_saugen_verzoegert(hass, entry, freezer: FrozenDateTimeFactory):
    starts = async_mock_service(hass, "vacuum", "start")
    events = async_capture_events(hass, "haushalt_erledigt")
    sub, saugstart = await staubsaugen_anlegen(hass, entry)

    zeile = hass.states.get("sensor.aufgaben").attributes["anzeige"]
    assert zeile == f"{sub.subentry_id}|Heute|Zum Staubsaugen vorbereiten|heute|0|1"
    assert hass.states.get(saugstart).state == "unknown"

    await hass.services.async_call(
        "button", "press", {"entity_id": knopf_id(hass, sub, "erledigt_20")}, blocking=True
    )
    assert events[0].data == {
        "aufgabe_id": sub.subentry_id,
        "name": "Zum Staubsaugen vorbereiten",
        "start_in_min": 20,
    }
    assert hass.states.get(saugstart).state == "2026-10-26T11:20:00+00:00"
    assert hass.states.get("sensor.aufgaben").attributes["saugstart"] == "12:20"

    await zeit_vor(hass, freezer, 19)
    assert not starts
    await zeit_vor(hass, freezer, 2)
    assert len(starts) == 1
    assert starts[0].data == {"entity_id": "vacuum.robi"}
    assert hass.states.get(saugstart).state == "unknown"
    assert hass.states.get("sensor.aufgaben").attributes["saugstart"] == ""


async def test_saugen_sofort_und_abbrechen(hass, entry, freezer: FrozenDateTimeFactory):
    starts = async_mock_service(hass, "vacuum", "start")
    sub, saugstart = await staubsaugen_anlegen(hass, entry)

    # Ohne Angabe startet er sofort
    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert len(starts) == 1

    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id, "start_in_min": "60"},
        blocking=True,
    )
    assert hass.states.get(saugstart).state != "unknown"
    await hass.services.async_call(
        "button", "press",
        {"entity_id": knopf_id(hass, sub, "saugstart_abbrechen")}, blocking=True,
    )
    assert hass.states.get(saugstart).state == "unknown"
    await zeit_vor(hass, freezer, 61)
    assert len(starts) == 1

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id, "start_in_min": 30},
            blocking=True,
        )


async def test_saugstart_nach_neustart(hass, entry, freezer: FrozenDateTimeFactory):
    starts = async_mock_service(hass, "vacuum", "start")
    sub, saugstart = await staubsaugen_anlegen(hass, entry)
    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id, "start_in_min": 5},
        blocking=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(saugstart).state == "2026-10-26T11:05:00+00:00"
    await zeit_vor(hass, freezer, 6)
    assert len(starts) == 1


async def test_ohne_staubsauger_keine_auswahl(hass, entry):
    await aufgabe_anlegen(
        hass, entry, "Bad putzen", "intervall", {"tage": 7, "zuletzt_erledigt": "2026-10-24"}
    )
    _, sub = sensor_id(hass, entry, "Bad putzen")
    assert knopf_id(hass, sub, "erledigt_5") is None
    assert hass.states.get(knopf_id(hass, sub, "erledigt")).name.endswith("Erledigt")


async def test_wochentag(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bad putzen", "typ": "wochentag"}
    )
    assert result["step_id"] == "wochentag"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"wochentage": [], "alle_wochen": 1, "mindestabstand": 3}
    )
    assert result["errors"] == {"wochentage": "kein_wochentag"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"wochentage": ["sa"], "alle_wochen": 1, "mindestabstand": 3}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    bad, sub = sensor_id(hass, entry, "Bad putzen")
    # Montag 26.10. -> Samstag 31.10.
    assert hass.states.get(bad).state == "in 5 Tagen"

    # Am Donnerstag erledigt -> Samstag wird übersprungen
    freezer.move_to(datetime(2026, 10, 29, 18, 0, tzinfo=START.tzinfo))
    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id}, blocking=True
    )
    assert hass.states.get(bad).attributes["faellig_am"] == "2026-11-07"

    # Samstag 7.11. verpasst -> am Montag überfällig
    freezer.move_to(datetime(2026, 11, 9, 9, 0, tzinfo=START.tzinfo))
    hass.config_entries.async_get_entry(entry.entry_id).runtime_data.aktualisieren()
    await hass.async_block_till_done()
    assert hass.states.get(bad).state == "2 Tage überfällig"

    # Bleibt nach Neustart erhalten
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(bad).state == "2 Tage überfällig"
