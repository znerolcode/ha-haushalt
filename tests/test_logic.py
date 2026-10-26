"""Tests der reinen Berechnung."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.haushalt.const import FRIST_ABEND, FRIST_MORGEN
from custom_components.haushalt.logic import (
    Aufgabe,
    anzeige_zeilen,
    berechne_intervall,
    berechne_termin,
    parse_daten,
    termine_ab,
)

TZ = ZoneInfo("Europe/Zurich")
MORGEN = time(9, 0)
ABEND = time(23, 59)


def jetzt(tag: int, stunde: int = 12) -> datetime:
    # 26.10.2026 ist ein Montag
    return datetime(2026, 10, tag, stunde, 0, tzinfo=TZ)


@pytest.mark.parametrize(
    ("zuletzt", "text", "gruppe"),
    [
        (date(2026, 10, 10), "2 Tage überfällig", "Überfällig"),
        (date(2026, 10, 11), "1 Tag überfällig", "Überfällig"),
        (date(2026, 10, 12), "heute", "Heute"),
        (date(2026, 10, 13), "morgen", "Morgen"),
        (date(2026, 10, 16), "in 4 Tagen", "Nächste Tage"),
    ],
)
def test_intervall(zuletzt, text, gruppe):
    a = Aufgabe(id="a", name="Bettwäsche", typ="intervall", tage=14)
    s = berechne_intervall(a, zuletzt, date(2026, 10, 26), 7)
    assert s.text == text
    assert s.gruppe == gruppe
    assert s.sichtbar


def test_intervall_ausserhalb_vorschau():
    a = Aufgabe(id="a", name="Kühlschrank", typ="intervall", tage=30)
    s = berechne_intervall(a, date(2026, 10, 25), date(2026, 10, 26), 7)
    assert not s.sichtbar


def test_parse_daten():
    assert parse_daten("05.11.2026, 19.11.2026") == [date(2026, 11, 5), date(2026, 11, 19)]
    assert parse_daten("") == []
    with pytest.raises(ValueError):
        parse_daten("5.11.")


def test_termine_ab_regel_und_einzeldaten():
    a = Aufgabe(
        id="k", name="Karton", typ="termin", startdatum=date(2026, 10, 6),
        alle_wochen=2, daten=[date(2026, 10, 29)],
    )
    assert termine_ab(a, date(2026, 10, 26), 3) == [
        date(2026, 10, 29), date(2026, 11, 3), date(2026, 11, 17),
    ]


def karton(frist=FRIST_MORGEN):
    # Dienstag 27.10.2026, alle 2 Wochen
    return Aufgabe(id="k", name="Altkarton", typ="termin", frist=frist,
                   startdatum=date(2026, 10, 27), alle_wochen=2)


def test_termin_texte():
    a = karton()
    assert berechne_termin(a, set(), jetzt(23), MORGEN, ABEND, 7).text == "bis in 4 Tagen"
    s = berechne_termin(a, set(), jetzt(26), MORGEN, ABEND, 7)
    assert (s.text, s.gruppe) == ("bis morgen früh", "Morgen")
    s = berechne_termin(a, set(), jetzt(27, 7), MORGEN, ABEND, 7)
    assert (s.text, s.gruppe) == ("bis heute früh", "Heute")
    b = karton(FRIST_ABEND)
    assert berechne_termin(b, set(), jetzt(27, 20), MORGEN, ABEND, 7).text == "bis heute Abend"


def test_termin_verschwindet_nach_frist():
    s = berechne_termin(karton(), set(), jetzt(27, 10), MORGEN, ABEND, 7)
    # nächster Termin ist der 10.11., also 14 Tage weg und nicht sichtbar
    assert s.datum == date(2026, 11, 10)
    assert not s.sichtbar
    assert s.gruppe != "Überfällig"


def test_termin_erledigt():
    s = berechne_termin(karton(), {date(2026, 10, 27)}, jetzt(26), MORGEN, ABEND, 7)
    assert s.datum == date(2026, 11, 10)


def test_einmaliger_termin_vorbei():
    a = Aufgabe(id="e", name="Sperrgut", typ="termin", startdatum=date(2026, 10, 20))
    s = berechne_termin(a, set(), jetzt(26), MORGEN, ABEND, 7)
    assert s.datum is None and not s.sichtbar


def test_anzeige_sortierung():
    heute = date(2026, 10, 26)
    stati = [
        berechne_intervall(Aufgabe("b", "Bettwäsche", "intervall", tage=14), date(2026, 10, 16), heute, 7),
        berechne_intervall(Aufgabe("p", "Bad putzen", "intervall", tage=7), date(2026, 10, 17), heute, 7),
        berechne_termin(karton(), set(), jetzt(26), MORGEN, ABEND, 7),
    ]
    zeilen = anzeige_zeilen(stati).splitlines()
    assert zeilen == [
        "p|Überfällig|Bad putzen|2 Tage überfällig|1",
        "k|Morgen|Altkarton|bis morgen früh|0",
        "b|Nächste Tage|Bettwäsche|in 4 Tagen|0",
    ]
