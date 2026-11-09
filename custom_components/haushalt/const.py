"""Konstanten der Haushalt-Integration."""

DOMAIN = "haushalt"

SUBENTRY_AUFGABE = "aufgabe"

# Intervall: alle X Einheiten ab dem letzten Abhaken. Termin: feste Daten ab einem Startdatum.
TYP_INTERVALL = "intervall"
TYP_TERMIN = "termin"
# Bis 0.6 ein eigener Typ, wird beim Laden in einen Termin umgewandelt
TYP_WOCHENTAG = "wochentag"
TYPEN = [TYP_INTERVALL, TYP_TERMIN]

EINHEIT_TAGE = "tage"
EINHEIT_WOCHEN = "wochen"
EINHEIT_MONATE = "monate"
EINHEITEN = [EINHEIT_TAGE, EINHEIT_WOCHEN, EINHEIT_MONATE]

# Was mit einer verpassten Aufgabe passiert
VERPASST_STEHEN = "stehen"
VERPASST_WEG = "weg"
VERPASST = [VERPASST_STEHEN, VERPASST_WEG]

FRIST_MORGEN = "morgen"
FRIST_ABEND = "abend"

GRUPPE_UEBERFAELLIG = "Überfällig"
GRUPPE_HEUTE = "Heute"
GRUPPE_MORGEN = "Morgen"
GRUPPE_NAECHSTE = "Nächste Tage"

# Felder einer Aufgabe
CONF_NAME = "name"
CONF_TYP = "typ"
CONF_TAGE = "tage"  # bis 0.6, jetzt anzahl + einheit
CONF_ANZAHL = "anzahl"
CONF_EINHEIT = "einheit"
CONF_VERPASST = "verpasst"
CONF_ZULETZT = "zuletzt_erledigt"
CONF_FRIST = "frist"
CONF_STARTDATUM = "startdatum"
CONF_ALLE_WOCHEN = "alle_wochen"  # bis 0.6, jetzt anzahl + einheit
CONF_DATEN = "weitere_daten"
CONF_WOCHENTAGE = "wochentage"
CONF_MINDESTABSTAND = "mindestabstand"

WOCHENTAGE = ["mo", "di", "mi", "do", "fr", "sa", "so"]
DEFAULT_MINDESTABSTAND = 3

# Optionen der Integration
CONF_ZEIT_MORGEN = "zeit_morgen"
CONF_ZEIT_ABEND = "zeit_abend"
CONF_VORSCHAU = "vorschau_tage"
CONF_WETTER = "wetter"
CONF_STAUBSAUGER = "staubsauger"
CONF_REINIGUNG_X = "reinigung_x"
CONF_REINIGUNG_Y = "reinigung_y"

DEFAULT_ZEIT_MORGEN = "09:00:00"
DEFAULT_ZEIT_ABEND = "23:59:00"
DEFAULT_VORSCHAU = 7

SERVICE_ERLEDIGT = "erledigt"
ATTR_AUFGABE_ID = "aufgabe_id"
ATTR_START_IN_MIN = "start_in_min"

SERVICE_SAUGEN = "saugen"
SERVICE_SAUGER = "sauger"
ATTR_ZIMMER = "zimmer"
ATTR_AKTION = "aktion"
AKTIONEN = ["pausieren", "fortsetzen", "abbrechen", "reinigen"]

# Startzeit-Auswahl fürs Staubsaugen, in Minuten
START_OPTIONEN = [0, 5, 20, 60]
# Ein verpasster Saugstart (z.B. HA war aus) wird nur so lange nachgeholt
NACHHOLEN_MAX_MIN = 15

EVENT_ERLEDIGT = "haushalt_erledigt"

SIGNAL_UPDATE = "haushalt_update_{}"

# So oft wird die Wettervorhersage neu geholt
WETTER_INTERVALL_MIN = 30

# Gefrierer (optional, unter Konfigurieren einschalten)
CONF_GEFRIERER = "gefrierer"

GEF_EINHEIT_PORTIONEN = "portionen"
GEF_EINHEIT_STUECK = "stueck"
GEF_EINHEIT_GRAMM = "gramm"
GEF_EINHEITEN = [GEF_EINHEIT_PORTIONEN, GEF_EINHEIT_STUECK, GEF_EINHEIT_GRAMM]

KAT_MEAL_PREP = "meal_prep"
KAT_BENUTZERDEFINIERT = "benutzerdefiniert"
# Kategorie und Standard-Haltbarkeit in Monaten (benutzerdefiniert: Zeitraum wählen)
KATEGORIEN = {
    KAT_MEAL_PREP: 3,
    "fleisch": 6,
    "hackfleisch": 3,
    "fisch": 4,
    "gemuese_obst": 12,
    "brot": 3,
    KAT_BENUTZERDEFINIERT: None,
}

# Wie die Haltbarkeit beim Einfrieren bestimmt wird
HALTBAR_KATEGORIE = "kategorie"
HALTBAR_ZEITRAUM = "zeitraum"
HALTBAR_DATUM = "datum"
HALTBARKEITEN = [HALTBAR_KATEGORIE, HALTBAR_ZEITRAUM, HALTBAR_DATUM]

# Weniger Tage bis zum Ablauf: "bald aufbrauchen"
GEF_BALD_TAGE = 30

SERVICE_EINFRIEREN = "einfrieren"
SERVICE_ENTNEHMEN = "entnehmen"
ATTR_NAME = "name"
ATTR_KATEGORIE = "kategorie"
ATTR_MENGE = "menge"
ATTR_EINHEIT = "einheit"
ATTR_EINGEFROREN = "eingefroren"
ATTR_HALTBAR_BIS = "haltbar_bis"
ATTR_HALTBAR_ANZAHL = "haltbar_anzahl"
ATTR_HALTBAR_EINHEIT = "haltbar_einheit"
ATTR_ARTIKEL = "artikel"
