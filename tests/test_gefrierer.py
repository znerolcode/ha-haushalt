"""Tests des Gefrierers: Logik, Dienste, Formular und Display-Zeilen."""

from datetime import date, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.haushalt.const import DOMAIN
from custom_components.haushalt.gefrierer import (
    Gefrierer,
    GefriererFehler,
    haltbar_bis,
    menge_text,
    rest_text,
)

from .test_init import entry  # noqa: F401

HEUTE = date(2026, 10, 26)


# ---- Logik ----


def test_haltbarkeit():
    assert haltbar_bis(HEUTE, "meal_prep", "kategorie") == date(2027, 1, 26)
    assert haltbar_bis(HEUTE, "gemuese_obst", "kategorie") == date(2027, 10, 26)
    assert haltbar_bis(HEUTE, "fleisch", "zeitraum", 2, "wochen") == date(2026, 11, 9)
    assert haltbar_bis(HEUTE, "fleisch", "datum", datum=date(2027, 2, 1)) == date(2027, 2, 1)
    with pytest.raises(GefriererFehler):
        haltbar_bis(HEUTE, "benutzerdefiniert", "kategorie")
    with pytest.raises(GefriererFehler):
        haltbar_bis(HEUTE, "fleisch", "datum")


def test_texte():
    assert menge_text(1, "portionen") == "1 Portion"
    assert menge_text(7, "portionen", kurz=True) == "7 Port."
    assert menge_text(500, "gramm") == "500 g"
    assert menge_text(1500, "gramm") == "1,5 kg"
    assert menge_text(2000, "gramm") == "2 kg"
    assert rest_text(-3) == "seit 3 Tagen"
    assert rest_text(-1) == "seit 1 Tag"
    assert rest_text(0) == "läuft heute ab"
    assert rest_text(12) == "noch 12 Tage"
    assert rest_text(95) == "noch 3 Monate"


def test_gruppieren_und_entnehmen():
    g = Gefrierer({})
    g.einfrieren("Chili", "meal_prep", 4, "portionen", HEUTE, date(2026, 11, 20))
    g.einfrieren("chili ", "meal_prep", 3, "portionen", HEUTE, date(2026, 11, 10))
    g.einfrieren("Erbsen", "gemuese_obst", 500, "gramm", HEUTE, date(2026, 10, 23))
    artikel = g.artikel()
    assert [a.name for a in artikel] == ["Erbsen", "Chili"]
    chili = artikel[1]
    assert chili.menge == 7
    assert chili.haltbar_bis == date(2026, 11, 10)
    assert chili.entnahme_optionen() == [
        (1, "1 Port."), (2, "2 Port."), (3, "3 Port."), (7, "alle 7")
    ]
    # Zuerst aus der Packung, die früher abläuft (3 Port. bis 10.11.)
    g.entnehmen(chili.schluessel, 4)
    chili = g.finden(chili.schluessel)
    assert chili.menge == 3
    assert len(chili.packungen) == 1
    assert chili.haltbar_bis == date(2026, 11, 20)
    g.entnehmen(chili.schluessel)
    assert g.finden(chili.schluessel) is None
    erbsen = g.artikel()[0]
    assert erbsen.entnahme_optionen() == [(100, "100 g"), (250, "250 g"), (500, "alle 500 g")]


def test_anzeige_und_kachel():
    g = Gefrierer({})
    assert g.kachel(HEUTE).split("\n")[0] == "Leer||"
    g.einfrieren("Chili", "meal_prep", 7, "portionen", HEUTE, HEUTE + timedelta(days=12))
    g.einfrieren("Erbsen", "gemuese_obst", 500, "gramm", HEUTE, HEUTE - timedelta(days=3))
    g.einfrieren("Lachs|frisch", "fisch", 2, "stueck", HEUTE, HEUTE + timedelta(days=90))
    assert g.anzeige(HEUTE).split("\n") == [
        ("erbsen~gramm|Abgelaufen|Erbsen|500 g|seit 3 Tagen|1|0|100:100 g;250:250 g;500:alle 500 g"
        "|Gemüse/Obst|500 g~26.10.26~23.10.26"),
        ("chili~portionen|Bald aufbrauchen|Chili|7 Port.|noch 12 Tage|0|1|"
        "1:1 Port.;2:2 Port.;3:3 Port.;7:alle 7|Meal-Prep|7 Port.~26.10.26~07.11.26"),
        ("lachs/frisch~stueck|Später|Lachs/frisch|2 Stück|noch 3 Monate|0|0|1:1 Stück;2:alle 2"
        "|Fisch|2 Stück~26.10.26~24.01.27"),
    ]
    assert g.kachel(HEUTE).split("\n") == [
        "3 Artikel · |1 abgelaufen| · 1 bald",
        "Meal-Prep: Chili 7||",
        "Zuerst: Erbsen, Chili, Lachs/frisch||",
    ]


# ---- In Home Assistant ----


async def gefrierer_einschalten(hass, entry):  # noqa: F811
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"zeit_morgen": "09:00:00", "zeit_abend": "23:59:00", "vorschau_tage": 7,
         "gefrierer": True},
    )
    await hass.async_block_till_done()


async def setzen(hass, plattform, feld, **daten):
    dienst = {
        "text": "set_value", "number": "set_value", "date": "set_value",
        "select": "select_option",
    }[plattform]
    await hass.services.async_call(
        plattform, dienst, {"entity_id": f"{plattform}.gefrierer_{feld}", **daten},
        blocking=True,
    )


async def druecken(hass, feld):
    await hass.services.async_call(
        "button", "press", {"entity_id": f"button.gefrierer_{feld}"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_ausgeschaltet(hass: HomeAssistant, entry):  # noqa: F811
    assert hass.states.get("sensor.gefrierer") is None
    assert hass.states.get("text.gefrierer_name") is None
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "einfrieren", {"name": "Chili", "menge": 2}, blocking=True
        )


async def test_dienste(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):  # noqa: F811
    await gefrierer_einschalten(hass, entry)
    assert hass.states.get("sensor.gefrierer").state == "0"
    await hass.services.async_call(
        DOMAIN, "einfrieren", {"name": "Chili", "menge": 4}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "einfrieren",
        {"name": "Kürbissuppe", "kategorie": "benutzerdefiniert", "menge": 1000,
         "einheit": "gramm", "haltbar_anzahl": 2, "haltbar_einheit": "wochen"},
        blocking=True,
    )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "einfrieren",
            {"name": "X", "kategorie": "benutzerdefiniert", "menge": 1}, blocking=True,
        )
    state = hass.states.get("sensor.gefrierer")
    assert state.state == "2"
    assert [a["name"] for a in state.attributes["artikel"]] == ["Kürbissuppe", "Chili"]
    assert state.attributes["artikel"][0]["haltbar_bis"] == "2026-11-09"
    assert [a["name"] for a in state.attributes["meal_prep"]] == ["Chili"]

    # Das Display schickt die Menge als Text
    await hass.services.async_call(
        DOMAIN, "entnehmen", {"artikel": "chili~portionen", "menge": "1"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "entnehmen", {"artikel": "kürbissuppe~gramm"}, blocking=True
    )
    state = hass.states.get("sensor.gefrierer")
    assert state.attributes["anzeige"] == (
        "chili~portionen|Später|Chili|3 Port.|noch 3 Monate|0|1|1:1 Port.;2:2 Port.;3:alle 3"
        "|Meal-Prep|3 Port.~26.10.26~26.01.27"
    )
    assert hass.states.get("sensor.gefrierer_meldung").state == "Entnommen: Kürbissuppe, 1 kg"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "entnehmen", {"artikel": "gibts~nicht"}, blocking=True
        )

    # Nach Ablauf rutscht der Artikel in "Abgelaufen", auch ohne Änderung
    freezer.tick(timedelta(days=95))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "|Abgelaufen|" in hass.states.get("sensor.gefrierer").attributes["anzeige"]

    # Inhalt bleibt nach dem Neuladen erhalten
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.gefrierer").state == "1"


async def test_formular(hass: HomeAssistant, entry):  # noqa: F811
    await gefrierer_einschalten(hass, entry)
    assert hass.states.get("date.gefrierer_eingefroren").state == "2026-10-26"
    assert hass.states.get("sensor.gefrierer_haltbar_bis").state == "2027-01-26"
    assert hass.states.get("select.gefrierer_artikel").state == "Gefrierer ist leer"

    await setzen(hass, "text", "name", value="Chili con Carne")
    await setzen(hass, "number", "menge", value=4)
    await druecken(hass, "einfrieren")
    assert hass.states.get("sensor.gefrierer_meldung").state == (
        "Eingefroren: Chili con Carne, 4 Portionen"
    )
    assert hass.states.get("text.gefrierer_name").state == ""
    assert hass.states.get("number.gefrierer_menge").state == "1"

    # Benutzerdefiniert: Haltbarkeit springt auf eigenen Zeitraum
    await setzen(hass, "text", "name", value="Kürbissuppe")
    await setzen(hass, "select", "kategorie", option="benutzerdefiniert")
    assert hass.states.get("select.gefrierer_haltbarkeit").state == "zeitraum"
    await setzen(hass, "number", "haltbar_anzahl", value=4)
    assert hass.states.get("sensor.gefrierer_haltbar_bis").state == "2027-02-26"
    await setzen(hass, "select", "haltbarkeit", option="datum")
    assert hass.states.get("sensor.gefrierer_haltbar_bis").state == "unknown"
    with pytest.raises(ServiceValidationError):
        await druecken(hass, "einfrieren")
    await setzen(hass, "date", "haltbar_datum", date="2026-12-24")
    await setzen(hass, "select", "einheit", option="gramm")
    await setzen(hass, "number", "menge", value=800)
    await druecken(hass, "einfrieren")

    artikel = hass.states.get("select.gefrierer_artikel")
    assert artikel.attributes["options"] == [
        "Kürbissuppe · 800 g", "Chili con Carne · 4 Portionen"
    ]
    await setzen(hass, "select", "artikel", option="Chili con Carne · 4 Portionen")
    await setzen(hass, "number", "entnahme", value=2)
    await druecken(hass, "entnehmen")
    assert hass.states.get("select.gefrierer_artikel").state == "Chili con Carne · 2 Portionen"
    assert hass.states.get("number.gefrierer_entnahme").state == "1"
    assert hass.states.get("sensor.gefrierer_meldung").state == (
        "Entnommen: Chili con Carne, 2 Portionen"
    )


async def test_haushalt_kachel(hass: HomeAssistant, entry):  # noqa: F811
    kachel = hass.states.get("sensor.aufgaben").attributes["kachel"]
    assert kachel.split("\n") == ["0 heute · 0 morgen||", "Keine Aufgaben fällig||", "||"]


async def test_aufgaben_details(hass: HomeAssistant, entry):  # noqa: F811
    from .test_init import aufgabe_anlegen

    await aufgabe_anlegen(
        hass, entry, "Bettwäsche", "intervall",
        {"anzahl": 2, "einheit": "wochen", "zuletzt_erledigt": "2026-10-16"},
    )
    await aufgabe_anlegen(
        hass, entry, "Pflanzen", "termin",
        {"startdatum": "2026-10-26", "anzahl": 1, "einheit": "wochen", "wochentage": ["mo", "do"]},
        verpasst="stehen",
    )
    details = hass.states.get("sensor.aufgaben").attributes["details"].split("\n")
    zeilen = {z.split("|")[1]: z.split("|")[2:] for z in details}
    assert zeilen["alle 2 Wochen nach dem Erledigen"] == ["Fr 16.10.", "Fr 30.10.,Fr 13.11.,Fr 27.11."]
    assert zeilen["Mo, Do, jede Woche"] == ["noch nie", "Mo 26.10.,Do 29.10.,Mo 02.11."]


async def test_sauger_letzter_einsatz(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):  # noqa: F811
    from .test_init import sauger_einrichten

    await sauger_einrichten(hass, entry)
    attr = lambda: hass.states.get("sensor.aufgaben").attributes["sauger_letzter"]
    assert attr() == ""
    await hass.services.async_call(DOMAIN, "saugen", {"zimmer": "19,20"}, blocking=True)
    hass.states.async_set("vacuum.robi", "cleaning")
    await hass.async_block_till_done()
    assert attr() == "Mo 26.10.|12:00||19,20"
    freezer.tick(timedelta(minutes=45))
    hass.states.async_set("vacuum.robi", "returning")
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert attr() == "Mo 26.10.|12:00|12:45|19,20"
    # In der Roborock-App gestartet: Zimmer unbekannt
    hass.states.async_set("vacuum.robi", "docked")
    await hass.async_block_till_done()
    hass.states.async_set("vacuum.robi", "cleaning")
    await hass.async_block_till_done()
    assert attr().endswith("||app")
