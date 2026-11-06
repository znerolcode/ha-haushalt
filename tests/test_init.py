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
from homeassistant.exceptions import ServiceValidationError
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


async def aufgabe_anlegen(hass, entry, name, typ, details, verpasst=None):
    if verpasst is None:
        verpasst = "weg" if typ == "termin" else "stehen"
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": name, "typ": typ, "verpasst": verpasst}
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
        {"anzahl": 14, "einheit": "tage", "zuletzt_erledigt": "2026-10-16"},
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    r = await aufgabe_anlegen(
        hass, entry, "Altkarton deponieren", "termin",
        {"frist": "morgen", "startdatum": "2026-10-27", "anzahl": 2, "einheit": "wochen"},
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
        {"frist": "abend", "startdatum": "2026-10-29", "anzahl": 1, "einheit": "wochen"},
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
        result["flow_id"], {"name": "Papier", "typ": "termin", "verpasst": "weg"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "anzahl": 4, "einheit": "wochen"}
    )
    assert result["errors"] == {"base": "kein_termin"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "anzahl": 0, "einheit": "wochen", "weitere_daten": "5.11."}
    )
    assert result["errors"] == {"weitere_daten": "ungueltige_daten"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"frist": "abend", "anzahl": 0, "einheit": "wochen", "weitere_daten": "05.11.2026"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bearbeiten(hass, entry):
    await aufgabe_anlegen(
        hass, entry, "Bad putzen", "intervall", {"anzahl": 7, "einheit": "tage", "zuletzt_erledigt": "2026-10-24"}
    )
    bad, sub = sensor_id(hass, entry, "Bad putzen")
    assert hass.states.get(bad).state == "in 5 Tagen"
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": sub.subentry_id},
    )
    assert result["step_id"] == "reconfigure_typ"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bad putzen", "typ": "intervall", "verpasst": "stehen"}
    )
    assert result["step_id"] == "intervall"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"anzahl": 3, "einheit": "tage"}
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
        {"frist": "morgen", "startdatum": "2026-11-03", "anzahl": 2, "einheit": "wochen"},
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


async def sauger_einrichten(hass, entry, punkt=True):
    hass.states.async_set("vacuum.robi", "docked")
    optionen = {"zeit_morgen": "09:00:00", "zeit_abend": "23:59:00", "vorschau_tage": 7,
                "staubsauger": "vacuum.robi"}
    if punkt:
        optionen |= {"reinigung_x": 25500, "reinigung_y": 26000}
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], optionen)
    await hass.async_block_till_done()
    return {
        dienst: async_mock_service(hass, "vacuum", dienst)
        for dienst in ("start", "pause", "return_to_base", "send_command")
    }


def sauger_zeile(hass):
    return hass.states.get("sensor.aufgaben").attributes["sauger"]


async def zeit_vor(hass, freezer, minuten):
    freezer.tick(timedelta(minutes=minuten))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_ohne_sauger_keine_zeile(hass, entry):
    assert sauger_zeile(hass) == ""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "saugen", {}, blocking=True)


async def test_ganze_wohnung_sofort(hass, entry):
    d = await sauger_einrichten(hass, entry)
    assert sauger_zeile(hass) == "bereit||"
    await hass.services.async_call(DOMAIN, "saugen", {"start_in_min": "0"}, blocking=True)
    assert d["start"][0].data == {"entity_id": "vacuum.robi"}
    hass.states.async_set("vacuum.robi", "cleaning")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "saugt||"
    hass.states.async_set("vacuum.robi", "returning")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "zurueck||"
    hass.states.async_set("vacuum.robi", "docked")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "bereit||"


async def test_zimmer_verzoegert(hass, entry, freezer: FrozenDateTimeFactory):
    d = await sauger_einrichten(hass, entry)
    # So schickt es das Display: Zimmer als Text
    await hass.services.async_call(
        DOMAIN, "saugen", {"zimmer": "23,20", "start_in_min": "20"}, blocking=True
    )
    assert sauger_zeile(hass) == "geplant|12:20|23,20"
    await zeit_vor(hass, freezer, 19)
    assert not d["send_command"]
    await zeit_vor(hass, freezer, 2)
    assert d["send_command"][0].data == {
        "entity_id": "vacuum.robi",
        "command": "app_segment_clean",
        "params": [{"segments": [23, 20], "repeat": 1}],
    }
    hass.states.async_set("vacuum.robi", "cleaning")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "saugt||23,20"

    # Pausieren und fortsetzen: bei Zimmern mit resume_segment_clean
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "pausieren"}, blocking=True)
    assert len(d["pause"]) == 1
    hass.states.async_set("vacuum.robi", "paused")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "pausiert||23,20"
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "fortsetzen"}, blocking=True)
    assert d["send_command"][1].data["command"] == "resume_segment_clean"

    # Abbrechen: zurück zur Station
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "abbrechen"}, blocking=True)
    assert len(d["return_to_base"]) == 1


async def test_geplant_abbrechen(hass, entry, freezer: FrozenDateTimeFactory):
    d = await sauger_einrichten(hass, entry)
    await hass.services.async_call(DOMAIN, "saugen", {"start_in_min": 60}, blocking=True)
    assert sauger_zeile(hass) == "geplant|13:00|"
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "abbrechen"}, blocking=True)
    assert sauger_zeile(hass) == "bereit||"
    # Er steht ja noch in der Station
    assert not d["return_to_base"]
    await zeit_vor(hass, freezer, 61)
    assert not d["start"]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "saugen", {"start_in_min": 30}, blocking=True)


async def test_geplant_nach_neustart(hass, entry, freezer: FrozenDateTimeFactory):
    d = await sauger_einrichten(hass, entry)
    await hass.services.async_call(DOMAIN, "saugen", {"start_in_min": 5}, blocking=True)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "geplant|12:05|"
    await zeit_vor(hass, freezer, 6)
    assert len(d["start"]) == 1


async def test_reinigen(hass, entry):
    d = await sauger_einrichten(hass, entry)
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "reinigen"}, blocking=True)
    assert d["send_command"][0].data == {
        "entity_id": "vacuum.robi", "command": "app_goto_target", "params": [25500, 26000],
    }
    hass.states.async_set("vacuum.robi", "cleaning")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "reinigen||"
    hass.states.async_set("vacuum.robi", "idle")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "reinigen||"
    await hass.services.async_call(DOMAIN, "sauger", {"aktion": "abbrechen"}, blocking=True)
    assert len(d["return_to_base"]) == 1
    hass.states.async_set("vacuum.robi", "docked")
    await hass.async_block_till_done()
    hass.states.async_set("vacuum.robi", "idle")
    await hass.async_block_till_done()
    assert sauger_zeile(hass) == "steht||"


async def test_reinigen_ohne_punkt(hass, entry):
    await sauger_einrichten(hass, entry, punkt=False)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "sauger", {"aktion": "reinigen"}, blocking=True)


async def test_erledigt_alter_parameter(hass, entry):
    """Ältere Display-Firmware schickt noch start_in_min mit."""
    await aufgabe_anlegen(
        hass, entry, "Bad putzen", "intervall", {"anzahl": 7, "einheit": "tage", "zuletzt_erledigt": "2026-10-24"}
    )
    _, sub = sensor_id(hass, entry, "Bad putzen")
    await hass.services.async_call(
        DOMAIN, "erledigt", {"aufgabe_id": sub.subentry_id, "start_in_min": "0"}, blocking=True
    )
    assert hass.states.get(knopf_id(hass, sub, "erledigt")).name.endswith("Erledigt")


async def test_alte_aufgaben_umwandeln(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Aufgaben aus 0.6 (Intervall in Tagen, Wochentag, Termin) werden beim Start umgewandelt."""
    await hass.config.async_set_time_zone("Europe/Zurich")
    freezer.move_to(START)
    alt = MockConfigEntry(
        domain=DOMAIN, title="Haushalt", unique_id=DOMAIN, version=1, minor_version=1,
        subentries_data=[
            {"data": {"typ": "intervall", "tage": 14, "zuletzt_erledigt": "2026-10-16"},
             "subentry_type": "aufgabe", "title": "Bettwäsche", "unique_id": None},
            {"data": {"typ": "wochentag", "wochentage": ["sa"], "alle_wochen": 1,
                      "startdatum": None, "mindestabstand": 3},
             "subentry_type": "aufgabe", "title": "Bad", "unique_id": None},
            {"data": {"typ": "termin", "frist": "morgen", "startdatum": "2026-10-27",
                      "alle_wochen": 2, "weitere_daten": ""},
             "subentry_type": "aufgabe", "title": "Altkarton", "unique_id": None},
        ],
    )
    alt.add_to_hass(hass)
    assert await hass.config_entries.async_setup(alt.entry_id)
    await hass.async_block_till_done()
    assert alt.minor_version == 2
    daten = {s.title: dict(s.data) for s in alt.subentries.values()}
    assert daten["Bettwäsche"]["einheit"] == "tage"
    assert daten["Bad"]["typ"] == "termin" and daten["Bad"]["verpasst"] == "stehen"
    assert daten["Altkarton"]["verpasst"] == "weg"
    assert hass.states.get(sensor_id(hass, alt, "Bettwäsche")[0]).state == "in 4 Tagen"
    assert hass.states.get(sensor_id(hass, alt, "Bad")[0]).state == "in 5 Tagen"
    assert hass.states.get(sensor_id(hass, alt, "Altkarton")[0]).state == "bis morgen früh"


async def test_monatlich_verschwindet(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):
    await aufgabe_anlegen(
        hass, entry, "Miete", "termin",
        {"startdatum": "2026-01-31", "anzahl": 1, "einheit": "monate", "frist": "abend"},
    )
    miete, _ = sensor_id(hass, entry, "Miete")
    assert hass.states.get(miete).state == "bis in 5 Tagen"
    freezer.move_to(datetime(2026, 11, 1, 9, 0, tzinfo=START.tzinfo))
    hass.config_entries.async_get_entry(entry.entry_id).runtime_data.aktualisieren()
    await hass.async_block_till_done()
    assert hass.states.get(miete).attributes["faellig_am"] == "2026-11-30"


async def test_wochentag(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AUFGABE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bad putzen", "typ": "termin", "verpasst": "stehen"}
    )
    assert result["step_id"] == "termin"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"wochentage": [], "anzahl": 1, "einheit": "wochen", "mindestabstand": 3}
    )
    assert result["errors"] == {"base": "kein_termin"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"wochentage": ["sa"], "anzahl": 1, "einheit": "wochen", "mindestabstand": 3}
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
