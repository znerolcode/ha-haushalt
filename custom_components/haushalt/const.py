"""Konstanten der Haushalt-Integration."""

DOMAIN = "haushalt"

SUBENTRY_AUFGABE = "aufgabe"

TYP_INTERVALL = "intervall"
TYP_TERMIN = "termin"

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

# Optionen der Integration
CONF_ZEIT_MORGEN = "zeit_morgen"
CONF_ZEIT_ABEND = "zeit_abend"
CONF_VORSCHAU = "vorschau_tage"

DEFAULT_ZEIT_MORGEN = "09:00:00"
DEFAULT_ZEIT_ABEND = "23:59:00"
DEFAULT_VORSCHAU = 7

SERVICE_ERLEDIGT = "erledigt"
ATTR_AUFGABE_ID = "aufgabe_id"

SIGNAL_UPDATE = "haushalt_update_{}"
