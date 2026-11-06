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
    daten_umwandeln,
    faellig_termin_stehen,
    parse_daten,
    plus,
    termine_ab,
)

TZ = ZoneInfo("Europe/Zurich")
MORGEN = time(9, 0)
ABEND = time(23, 59)


def jetzt(tag: int, stunde: int = 12, monat: int = 10) -> datetime:
    # 26.10.2026 ist ein Montag
    return datetime(2026, monat, tag, stunde, 0, tzinfo=TZ)


def intervall(anzahl=14, einheit="tage", verpasst="stehen", **kw):
    return Aufgabe(id="a", name="Bettwäsche", typ="intervall", anzahl=anzahl,
                   einheit=einheit, verpasst=verpasst, **kw)


def iv(a, zuletzt, wann=None):
    return berechne_intervall(a, zuletzt, wann or jetzt(26), MORGEN, ABEND, 7)


# --- Intervall ---


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
    s = iv(intervall(), zuletzt)
    assert s.text == text
    assert s.gruppe == gruppe
    assert s.sichtbar


def test_intervall_ausserhalb_vorschau():
    assert not iv(intervall(30), date(2026, 10, 25)).sichtbar


def test_intervall_wochen_und_monate():
    assert iv(intervall(2, "wochen"), date(2026, 10, 19)).datum == date(2026, 11, 2)
    assert iv(intervall(1, "monate"), date(2026, 10, 1)).datum == date(2026, 11, 1)
    # 31.1. + 1 Monat = 28.2.
    assert plus(date(2027, 1, 31), 1, "monate") == date(2027, 2, 28)
    assert plus(date(2026, 11, 30), 3, "monate") == date(2027, 2, 28)


def test_intervall_verschwindet():
    a = intervall(14, verpasst="weg", frist=FRIST_ABEND)
    # fällig heute (26.10.), Frist abends -> noch da, mit Frist-Text
    s = iv(a, date(2026, 10, 12))
    assert (s.text, s.gruppe) == ("bis heute Abend", "Heute")
    # gestern verpasst -> weg, zählt ab dem verpassten Tag weiter: 25.10. + 14 = 8.11.
    s = iv(a, date(2026, 10, 11))
    assert s.datum == date(2026, 11, 8)
    assert not s.sichtbar
    assert s.gruppe != "Überfällig"
    # mehrmals verpasst: 15.9., 29.9., 13.10. vorbei -> 27.10.
    assert iv(a, date(2026, 9, 1)).datum == date(2026, 10, 27)


def test_intervall_verschwindet_frist_morgen():
    a = intervall(14, verpasst="weg", frist=FRIST_MORGEN)
    s = iv(a, date(2026, 10, 12), jetzt(26, 8))
    assert s.text == "bis heute früh"
    assert iv(a, date(2026, 10, 12), jetzt(26, 10)).datum == date(2026, 11, 9)


def test_parse_daten():
    assert parse_daten("05.11.2026, 19.11.2026") == [date(2026, 11, 5), date(2026, 11, 19)]
    assert parse_daten("") == []
    with pytest.raises(ValueError):
        parse_daten("5.11.")


# --- Fester Termin, verschwindet ---


def karton(frist=FRIST_MORGEN, **kw):
    # Dienstag 27.10.2026, alle 2 Wochen
    return Aufgabe(id="k", name="Altkarton", typ="termin", frist=frist, verpasst="weg",
                   startdatum=date(2026, 10, 27), anzahl=2, einheit="wochen", **kw)


def tm(a, wann, erledigt=frozenset(), zuletzt=None, erstellt=date(2026, 10, 1)):
    return berechne_termin(a, zuletzt, erstellt, set(erledigt), wann, MORGEN, ABEND, 7)


def test_termine_ab_regel_und_einzeldaten():
    a = karton(daten=[date(2026, 10, 29)])
    a.startdatum = date(2026, 10, 6)
    assert termine_ab(a, date(2026, 10, 26), 3) == [
        date(2026, 10, 29), date(2026, 11, 3), date(2026, 11, 17),
    ]


def test_termin_texte():
    assert tm(karton(), jetzt(23)).text == "bis in 4 Tagen"
    s = tm(karton(), jetzt(26))
    assert (s.text, s.gruppe) == ("bis morgen früh", "Morgen")
    s = tm(karton(), jetzt(27, 7))
    assert (s.text, s.gruppe) == ("bis heute früh", "Heute")
    assert tm(karton(FRIST_ABEND), jetzt(27, 20)).text == "bis heute Abend"


def test_termin_verschwindet_nach_frist():
    s = tm(karton(), jetzt(27, 10))
    # nächster Termin ist der 10.11., also 14 Tage weg und nicht sichtbar
    assert s.datum == date(2026, 11, 10)
    assert not s.sichtbar
    assert s.gruppe != "Überfällig"


def test_termin_erledigt():
    assert tm(karton(), jetzt(26), {date(2026, 10, 27)}).datum == date(2026, 11, 10)


def test_einmaliger_termin_vorbei():
    a = Aufgabe(id="e", name="Sperrgut", typ="termin", verpasst="weg", anzahl=0,
                einheit="wochen", startdatum=date(2026, 10, 20))
    s = tm(a, jetzt(26))
    assert s.datum is None and not s.sichtbar


def test_termin_tage_und_monate():
    a = Aufgabe(id="t", name="Filter", typ="termin", verpasst="weg", anzahl=10,
                einheit="tage", startdatum=date(2026, 10, 1))
    assert termine_ab(a, date(2026, 10, 26), 2) == [date(2026, 10, 31), date(2026, 11, 10)]
    m = Aufgabe(id="m", name="Miete", typ="termin", verpasst="weg", anzahl=1,
                einheit="monate", startdatum=date(2026, 1, 31))
    assert termine_ab(m, date(2026, 10, 26), 3) == [
        date(2026, 10, 31), date(2026, 11, 30), date(2026, 12, 31),
    ]


def test_anzeige_sortierung():
    stati = [
        iv(intervall(14), date(2026, 10, 16)),
        iv(Aufgabe("p", "Bad putzen", "intervall", anzahl=7), date(2026, 10, 17)),
        tm(karton(), jetzt(26)),
    ]
    stati[0].aufgabe.id = "b"
    zeilen = anzeige_zeilen(stati).splitlines()
    assert zeilen == [
        "p|Überfällig|Bad putzen|2 Tage überfällig|1",
        "k|Morgen|Altkarton|bis morgen früh|0",
        "b|Nächste Tage|Bettwäsche|in 4 Tagen|0",
    ]


# --- Fester Termin, bleibt stehen (früher Typ Wochentag) ---


SA = 5


def bad(**kw):
    kw.setdefault("anzahl", 1)
    kw.setdefault("mindestabstand", 3)
    return Aufgabe(id="w", name="Bad putzen", typ="termin", wochentage=[SA],
                   einheit="wochen", **kw)


def test_stehen_noch_nie_erledigt():
    # erstellt Montag 26.10. -> Samstag 31.10.
    assert faellig_termin_stehen(bad(), None, date(2026, 10, 26)) == date(2026, 10, 31)


def test_stehen_am_donnerstag_erledigt_ueberspringt_samstag():
    # Do 29.10. erledigt, Sa 31.10. nur 2 Tage später -> Sa 7.11.
    assert faellig_termin_stehen(bad(), date(2026, 10, 29), date(2026, 10, 1)) == date(2026, 11, 7)


def test_stehen_am_mittwoch_erledigt_samstag_bleibt():
    assert faellig_termin_stehen(bad(), date(2026, 10, 28), date(2026, 10, 1)) == date(2026, 10, 31)


def test_stehen_mindestabstand_null_nicht_gleicher_tag():
    a = bad(mindestabstand=0)
    assert faellig_termin_stehen(a, date(2026, 10, 31), date(2026, 10, 1)) == date(2026, 11, 7)


def test_stehen_ueberfaellig_bis_erledigt():
    # zuletzt Sa 17.10., fällig Sa 24.10., heute Mo 26.10. -> 2 Tage überfällig
    s = tm(bad(), jetzt(26), zuletzt=date(2026, 10, 17))
    assert (s.text, s.gruppe) == ("2 Tage überfällig", "Überfällig")


def test_stehen_zweimal_pro_woche():
    a = bad()
    a.wochentage = [2, SA]  # Mi und Sa
    assert faellig_termin_stehen(a, date(2026, 10, 28), date(2026, 10, 1)) == date(2026, 10, 31)
    assert faellig_termin_stehen(a, date(2026, 10, 29), date(2026, 10, 1)) == date(2026, 11, 4)


def test_stehen_alle_zwei_wochen():
    # Woche von Sa 31.10. zählt, also Sa 14.11., nicht Sa 7.11.
    a = bad(startdatum=date(2026, 10, 31), anzahl=2)
    assert faellig_termin_stehen(a, date(2026, 10, 31), date(2026, 10, 1)) == date(2026, 11, 14)
    # Startdatum in der Zukunft: frühestens ab dann
    assert faellig_termin_stehen(a, None, date(2026, 10, 26)) == date(2026, 10, 31)


def test_stehen_monatlich():
    # jeden 15., bleibt stehen
    a = Aufgabe(id="r", name="Rechnungen", typ="termin", anzahl=1, einheit="monate",
                startdatum=date(2026, 9, 15), mindestabstand=3)
    s = tm(a, jetzt(26), zuletzt=date(2026, 9, 15))
    assert (s.datum, s.text) == (date(2026, 10, 15), "11 Tage überfällig")


# --- Umwandlung alter Aufgaben ---


def test_daten_umwandeln():
    assert daten_umwandeln({"typ": "intervall", "tage": 14, "zuletzt_erledigt": "2026-10-16"}) == {
        "typ": "intervall", "anzahl": 14, "einheit": "tage", "verpasst": "stehen",
        "frist": "abend", "zuletzt_erledigt": "2026-10-16",
    }
    assert daten_umwandeln({
        "typ": "wochentag", "wochentage": ["mo", "do"], "alle_wochen": 2,
        "startdatum": None, "mindestabstand": 3,
    }) == {
        "typ": "termin", "wochentage": ["mo", "do"], "anzahl": 2, "einheit": "wochen",
        "startdatum": None, "mindestabstand": 3, "verpasst": "stehen", "frist": "abend",
    }
    assert daten_umwandeln({
        "typ": "termin", "frist": "morgen", "startdatum": "2026-10-27",
        "alle_wochen": 2, "weitere_daten": "",
    }) == {
        "typ": "termin", "frist": "morgen", "startdatum": "2026-10-27", "anzahl": 2,
        "einheit": "wochen", "verpasst": "weg", "wochentage": [], "weitere_daten": "",
    }
    # neue Daten bleiben gleich
    neu = {"typ": "intervall", "anzahl": 2, "einheit": "wochen", "verpasst": "weg"}
    assert daten_umwandeln(neu) == neu
