"""Tests der Wetter-Zusammenfassung."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from custom_components.haushalt.wetter import (
    NACHMITTAG,
    VORMITTAG,
    Haelfte,
    anzeige_zeile,
    haelfte_aus_stunden,
    haelfte_aus_tag,
)

from .test_init import START, entry  # noqa: F401

ZONE = ZoneInfo("Europe/Zurich")
TAG = date(2026, 10, 27)


def stunde(h, zustand, temp, prozent=None, mm=None, tag=TAG):
    zeit = datetime(tag.year, tag.month, tag.day, h, tzinfo=ZONE).astimezone(ZoneInfo("UTC"))
    e = {"datetime": zeit.isoformat(), "condition": zustand, "temperature": temp}
    if prozent is not None:
        e["precipitation_probability"] = prozent
    if mm is not None:
        e["precipitation"] = mm
    return e


def test_vormittag_haeufigster_zustand_max_temp_und_regen():
    stunden = [
        stunde(5, "pouring", 3, 90),  # vor 6 Uhr, zählt nicht
        stunde(6, "clear-night", 4, 0),
        stunde(7, "sunny", 5, 10),
        stunde(8, "cloudy", 7, 20),
        stunde(9, "cloudy", 8, 40),
        stunde(10, "sunny", 9, 30),
        stunde(11, "partlycloudy", 9.6, 30),
        stunde(12, "rainy", 11, 80),  # gehört zum Nachmittag
    ]
    h = haelfte_aus_stunden(stunden, TAG, VORMITTAG, ZONE)
    # sunny 3x (inkl. klarer Nacht), cloudy 2x
    assert h == Haelfte("sunny", 10, "40 %")


def test_gleichstand_nimmt_das_schlechtere_wetter():
    stunden = [stunde(12, "sunny", 10, 0), stunde(13, "rainy", 11, 60)]
    assert haelfte_aus_stunden(stunden, TAG, NACHMITTAG, ZONE).zustand == "rainy"


def test_regen_in_mm_wenn_keine_wahrscheinlichkeit():
    stunden = [stunde(12, "rainy", 10, mm=0.4), stunde(13, "rainy", 11, mm=0.8)]
    assert haelfte_aus_stunden(stunden, TAG, NACHMITTAG, ZONE).regen == "1,2 mm"


def test_sechsstuendliche_eintraege():
    stunden = [stunde(6, "cloudy", 5, 20), stunde(12, "rainy", 9, 70)]
    assert haelfte_aus_stunden(stunden, TAG, VORMITTAG, ZONE) == Haelfte("cloudy", 5, "20 %")
    assert haelfte_aus_stunden(stunden, TAG, NACHMITTAG, ZONE) == Haelfte("rainy", 9, "70 %")


def test_keine_daten():
    assert haelfte_aus_stunden([], TAG, VORMITTAG, ZONE) is None


def test_tagesvorhersage_als_ersatz():
    tage = [{"datetime": "2026-10-27T11:00:00+00:00", "condition": "snowy", "temperature": 2.4}]
    assert haelfte_aus_tag(tage, TAG, ZONE) == Haelfte("snowy", 2, "")
    assert haelfte_aus_tag(tage, TAG + timedelta(days=1), ZONE) is None


def test_anzeige_zeile():
    assert (
        anzeige_zeile("Heute", Haelfte("sunny", 8, "0 %"), None)
        == "Heute|sunny|8|0 %|||"
    )


def _wetterdienst_registrieren(hass: HomeAssistant, aufrufe: list):
    async def get_forecasts(call: ServiceCall):
        aufrufe.append(call.data["type"])
        jetzt = datetime.now(ZONE).replace(minute=0, second=0, microsecond=0)
        if call.data["type"] == "hourly":
            forecast = [
                {
                    "datetime": (jetzt + timedelta(hours=i)).isoformat(),
                    "condition": "rainy" if i % 24 < 6 else "sunny",
                    "temperature": 10 + (i % 24) / 4,
                    "precipitation_probability": 50 if i % 24 < 6 else 0,
                }
                for i in range(60)
            ]
        else:
            forecast = [
                {
                    "datetime": (jetzt + timedelta(days=i)).isoformat(),
                    "condition": "cloudy",
                    "temperature": 15,
                    "templow": 5,
                }
                for i in range(5)
            ]
        return {"weather.zuhause": {"forecast": forecast}}

    hass.services.async_register(
        "weather", "get_forecasts", get_forecasts, supports_response=SupportsResponse.ONLY
    )


async def test_sensor(hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory):  # noqa: F811
    aufrufe = []
    _wetterdienst_registrieren(hass, aufrufe)
    assert hass.states.get("sensor.display_wetter") is None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "zeit_morgen": "09:00:00",
            "zeit_abend": "23:59:00",
            "vorschau_tage": 7,
            "wetter": "weather.zuhause",
        },
    )
    await hass.async_block_till_done()

    zustand = hass.states.get("sensor.display_wetter")
    assert zustand is not None
    # START ist Montag 12:00: Vorhersage ab jetzt, also kein stündlicher Vormittag
    zeilen = zustand.attributes["anzeige"].splitlines()
    assert len(zeilen) == 3
    assert zeilen[0] == "Heute|cloudy|15||rainy|11|50 %"
    assert zeilen[1].startswith("Dienstag|sunny|")
    assert zeilen[2].startswith("Mittwoch|")
    assert zustand.state == "rainy"
    assert aufrufe == ["hourly", "daily"]

    # Nach 30 Minuten wird neu geholt
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aufrufe == ["hourly", "daily"] * 2


async def test_vormittag_bleibt_nachmittags_stehen(
    hass: HomeAssistant, entry, freezer: FrozenDateTimeFactory  # noqa: F811
):
    freezer.move_to(START.replace(hour=8))
    _wetterdienst_registrieren(hass, [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"zeit_morgen": "09:00:00", "zeit_abend": "23:59:00", "vorschau_tage": 7,
         "wetter": "weather.zuhause"},
    )
    await hass.async_block_till_done()
    vormittag = hass.states.get("sensor.display_wetter").attributes["anzeige"].split("\n")[0]
    assert vormittag.startswith("Heute|rainy|11|50 %|")

    # Um 14 Uhr liefert die Vorhersage keinen Vormittag mehr, er kommt aus dem Speicher
    freezer.move_to(START.replace(hour=14))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    jetzt = hass.states.get("sensor.display_wetter").attributes["anzeige"].split("\n")[0]
    assert jetzt.split("|")[1:4] == vormittag.split("|")[1:4]
