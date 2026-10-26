"""Konstanten der Haushalt-Integration."""

DOMAIN = "haushalt"

SUBENTRY_AUFGABE = "aufgabe"

TYP_INTERVALL = "intervall"
TYP_TERMIN = "termin"
TYP_WOCHENTAG = "wochentag"

FRIST_MORGEN = "morgen"
FRIST_ABEND = "abend"

GRUPPE_UEBERFAELLIG = "Überfällig"
GRUPPE_HEUTE = "Heute"
GRUPPE_MORGEN = "Morgen"
GRUPPE_NAECHSTE = "Nächste Tage"

# Felder einer Aufgabe
CONF_NAME = "name"
CONF_TYP = "typ"
CONF_TAGE = "tage"
CONF_ZULETZT = "zuletzt_erledigt"
CONF_FRIST = "frist"
CONF_STARTDATUM = "startdatum"
CONF_ALLE_WOCHEN = "alle_wochen"
CONF_DATEN = "weitere_daten"
CONF_STAUBSAUGER = "staubsauger"
CONF_WOCHENTAGE = "wochentage"
CONF_MINDESTABSTAND = "mindestabstand"

WOCHENTAGE = ["mo", "di", "mi", "do", "fr", "sa", "so"]
DEFAULT_MINDESTABSTAND = 3

# Optionen der Integration
CONF_ZEIT_MORGEN = "zeit_morgen"
CONF_ZEIT_ABEND = "zeit_abend"
CONF_VORSCHAU = "vorschau_tage"
CONF_WETTER = "wetter"

DEFAULT_ZEIT_MORGEN = "09:00:00"
DEFAULT_ZEIT_ABEND = "23:59:00"
DEFAULT_VORSCHAU = 7

SERVICE_ERLEDIGT = "erledigt"
ATTR_AUFGABE_ID = "aufgabe_id"
ATTR_START_IN_MIN = "start_in_min"

# Startzeit-Auswahl für Aufgaben mit Staubsauger, in Minuten
START_OPTIONEN = [0, 5, 20, 60]
# Ein verpasster Saugstart (z.B. HA war aus) wird nur so lange nachgeholt
NACHHOLEN_MAX_MIN = 15

EVENT_ERLEDIGT = "haushalt_erledigt"

SIGNAL_UPDATE = "haushalt_update_{}"

# So oft wird die Wettervorhersage neu geholt
WETTER_INTERVALL_MIN = 30
