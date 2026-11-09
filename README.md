# Haushalt

Home-Assistant-Integration für wiederkehrende Haushaltsaufgaben. Gedacht für ein E-Ink-Display im Flur, funktioniert aber auch allein im Dashboard.

## Aufgabentypen

| Typ | Beispiel | Fällig |
| --- | --- | --- |
| Intervall | Bettwäsche alle 2 Wochen | X Tage, Wochen oder Monate nach dem letzten Abhaken |
| Fester Termin | Altkarton jeden 2. Dienstag, Pflanzen Mo und Do, Miete jeden 31. | ab dem ersten Termin alle X Tage, Wochen (an gewählten Wochentagen) oder Monate (gleiches Datum, sonst Monatsletzter), dazu einzelne Daten |

Bei jeder Aufgabe wählst du, was passiert, **wenn sie verpasst** wird:

- **Bleibt überfällig stehen:** „2 Tage überfällig“, bis sie erledigt ist. Feste Termine haben dann einen Mindestabstand (Standard 3 Tage): Wird die Aufgabe z.B. am Donnerstag erledigt, entfällt der Samstag zwei Tage später.
- **Verschwindet:** Mit Frist „Morgen“ oder „Abend“ am Fälligkeitstag. Danach fällt die Aufgabe weg und kommt beim nächsten Termin wieder; ein Intervall zählt dann ab dem verpassten Tag weiter.

Anzeigetexte: bleibt stehen „in 4 Tagen“, „morgen“, „heute“, „1 Tag überfällig“; verschwindet „bis in 3 Tagen“, „bis morgen früh“, „bis heute Abend“.

Aufgaben aus Version 0.5 und älter werden beim ersten Start automatisch umgewandelt: Intervall → Intervall in Tagen (bleibt stehen), Wochentag → fester Termin in Wochen (bleibt stehen), Termin → fester Termin in Wochen (verschwindet).

## Installation über HACS

1. HACS öffnen, oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/znerolcode/ha-haushalt` eintragen, Typ **Integration**, hinzufügen.
3. „Haushalt“ in HACS suchen, herunterladen, Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Haushalt**.

## Aufgaben erfassen

Unter **Einstellungen → Geräte & Dienste → Haushalt** auf **Aufgabe hinzufügen** klicken. Bestehende Aufgaben lassen sich dort über ⋮ → **Neu konfigurieren** ändern oder löschen.

### Aufgaben ohne Administratorrechte anlegen

Die Haushalt-Seite unter Geräte & Dienste können nur Administratoren bedienen. Für alle anderen Konten bringt die Integration ein Formular als Gerät **Neue Aufgabe** mit (Felder wie `text.neue_aufgabe_name`, `select.neue_aufgabe_typ` und der Knopf `button.neue_aufgabe_anlegen`). Dazu gehört die Dashboard-Vorlage [`dashboard/neue-aufgabe.yaml`](dashboard/neue-aufgabe.yaml), die je nach Typ nur die passenden Felder zeigt:

1. **Einstellungen → Dashboards → Dashboard hinzufügen → Neues Dashboard von Grund auf**, Titel „Neue Aufgabe“, URL `neue-aufgabe`, **Nur für Administratoren** aus.
2. Dashboard öffnen, Stift → ⋮ → **Raw-Konfigurationseditor**, alles durch den Inhalt der Vorlage ersetzen, speichern.
3. Die Seite heisst dann `http://<adresse-deines-ha>:8123/neue-aufgabe/neu`. Diese Adresse fürs Flur-Display als `neue_aufgabe_url` eintragen (siehe `esphome/ANLEITUNG.md`).

Nach **Aufgabe anlegen** ist das Formular wieder leer, darunter steht die zuletzt angelegte Aufgabe. Fehlt etwas (Name, Termin), erscheint unten ein Hinweis. Ändern und löschen bleibt Administratoren vorbehalten.

Feste Termine: Bei „Wochen“ ohne gewählte Wochentage bestimmt das erste Datum den Wochentag. „Wiederholen alle 0“ heisst nicht wiederholen. Unregelmässige Termine (z.B. aus dem Abfuhrkalender) trägst du unter „Weitere einzelne Termine“ ein: `05.11.2026, 19.11.2026`.


Unter **Konfigurieren** stellst du ein, wann die Fristen „Morgen“ (Standard 09:00) und „Abend“ (23:59) enden und wie viele Tage im Voraus Aufgaben erscheinen (Standard 7).

Ebenfalls unter **Konfigurieren** wählst du optional eine **Wetter-Entität** (z.B. `weather.forecast_home` von Met.no). Die Integration fasst deren Vorhersage für heute und die nächsten 2 Tage in Vormittag (6–12 Uhr) und Nachmittag (12–18 Uhr) zusammen. Der heutige Vormittag bleibt auch am Nachmittag stehen.

Optional wählst du unter **Konfigurieren** auch einen **Staubsauger** (getestet mit Roborock). Dann zeigt das Flur-Display zuoberst die Zeile „Staubsaugen“: ganze Wohnung oder einzelne Zimmer, sofort oder in 5, 20 oder 60 Minuten, dazu Pausieren, Fortsetzen und Abbrechen. Für **Sauger reinigen** trägst du den **Reinigungspunkt** (X und Y) ein, an den er zum Leeren fährt. Die Koordinaten liest du so aus: Sauger in der Roborock-App mit „Pin & Go“ an den Punkt schicken, dann unter **Entwicklerwerkzeuge → Aktionen** `roborock.get_vacuum_current_position` mit dem Staubsauger ausführen.

## Gefrierer

Optional verwaltet die Integration auch den Inhalt des Gefrierers: was drin ist, wie viel davon und bis wann es haltbar ist. Einschalten unter **Konfigurieren → Gefrierer verwalten**.

- **Einfrieren:** Name, Kategorie, Menge (Portionen, Stück oder Gramm) und Datum. Haltbar ist es wie die Kategorie (Meal-Prep 3 Monate, Fleisch 6, Hackfleisch 3, Fisch 4, Gemüse/Obst 12, Brot/Backwaren 3), für einen eigenen Zeitraum oder bis zu einem Datum. Bei **Benutzerdefiniert** wählst du den Zeitraum immer selbst.
- **Entnehmen:** Menge angeben, zuerst kommt sie aus der Packung, die am frühesten abläuft. Wird dasselbe (gleicher Name, gleiche Einheit) mehrmals eingefroren, bleiben es eigene Packungen mit eigenem Datum, erscheinen aber zusammen als ein Artikel, z.B. „Chili 7 Port.“.
- **Gruppen:** abgelaufen, bald aufbrauchen (weniger als 30 Tage) und später.

Für Konten ohne Administratorrechte gibt es das Gerät **Gefrierer** mit Formularfeldern und die Dashboard-Vorlage [`dashboard/gefrierer.yaml`](dashboard/gefrierer.yaml) mit den Tabs Inhalt, Einfrieren und Entnehmen:

1. **Einstellungen → Dashboards → Dashboard hinzufügen → Neues Dashboard von Grund auf**, Titel „Gefrierer“, URL `haushalt-gefrierer` (HA verlangt einen Bindestrich), **Nur für Administratoren** aus.
2. Dashboard öffnen, Stift → ⋮ → **Raw-Konfigurationseditor**, alles durch den Inhalt der Vorlage ersetzen, speichern.
3. Der Tab Einfrieren heisst dann `http://<adresse-deines-ha>:8123/haushalt-gefrierer/einfrieren`. Diese Adresse fürs Flur-Display als `gefrierer_url` eintragen (siehe `esphome/ANLEITUNG.md`).

Mit eingeschaltetem Gefrierer zeigt das Flur-Display als Ruheansicht einen Homescreen mit den Kacheln Haushalt und Gefrierer.

## Entitäten

- Pro Aufgabe ein Sensor **Fälligkeit** (Zustand z.B. „in 4 Tagen“, Attribute `faellig_am`, `tage`, `gruppe`, `aufgabe_id`) und ein Knopf **Erledigt**.
- Gerät **Neue Aufgabe**: Formularfelder `text.neue_aufgabe_name`, `select.neue_aufgabe_typ`, `select.neue_aufgabe_verpasst`, `number.neue_aufgabe_anzahl`, `select.neue_aufgabe_einheit`, `date.neue_aufgabe_zuletzt`, `switch.neue_aufgabe_mo` … `_so`, `number.neue_aufgabe_mindestabstand`, `date.neue_aufgabe_datum`, `select.neue_aufgabe_frist`, `text.neue_aufgabe_weitere`, Knopf `button.neue_aufgabe_anlegen` und `sensor.neue_aufgabe_meldung` (zuletzt angelegte Aufgabe). Die Werte gelten nur bis zum Anlegen oder bis zum Neustart.
- `sensor.aufgaben`: Anzahl sichtbarer Aufgaben. Attribut `aufgaben` als Liste, Attribut `anzeige` als Text für das Display, eine Zeile pro Aufgabe: `aufgabe_id|gruppe|name|text|ueberfaellig` (`ueberfaellig` 0 oder 1). Attribut `sauger` (nur mit Staubsauger, sonst leer): `zustand|uhrzeit|zimmer`, z.B. `geplant|17:05|19,20` oder `saugt||`. Zustände: `bereit`, `geplant`, `saugt`, `pausiert`, `zurueck`, `reinigen`, `steht`, `fehler`.
- `sensor.aufgaben`, Attribut `kachel`: drei Zeilen für die Haushalt-Kachel auf dem Homescreen, je `vor|hervorgehoben|nach` (der mittlere Teil erscheint weiss auf schwarz).
- `sensor.gefrierer` (nur mit Gefrierer): Anzahl Artikel. Attribute `artikel` (Liste mit `artikel`, `name`, `kategorie`, `menge`, `einheit`, `haltbar_bis`, `tage`, `text`, `gruppe`, `packungen`), `meal_prep` (nur Meal-Prep), `kachel` (wie oben) und `anzeige` für das Display, eine Zeile pro Artikel: `artikel|gruppe|name|menge|rest|abgelaufen|meal_prep|optionen`, z.B. `chili~portionen|Bald aufbrauchen|Chili|7 Port.|noch 12 Tage|0|1|1:1 Port.;2:2 Port.;3:3 Port.;7:alle 7`. `optionen` sind die Entnahme-Knöpfe als `menge:beschriftung`.
- Gerät **Gefrierer** (nur mit Gefrierer): `text.gefrierer_name`, `select.gefrierer_kategorie`, `number.gefrierer_menge`, `select.gefrierer_einheit`, `date.gefrierer_eingefroren`, `select.gefrierer_haltbarkeit`, `number.gefrierer_haltbar_anzahl`, `select.gefrierer_haltbar_einheit`, `date.gefrierer_haltbar_datum`, `sensor.gefrierer_haltbar_bis` (was das Formular gerade ausrechnet), Knopf `button.gefrierer_einfrieren`; zum Entnehmen `select.gefrierer_artikel`, `number.gefrierer_entnahme`, Knopf `button.gefrierer_entnehmen`; `sensor.gefrierer_meldung` (zuletzt eingefroren oder entnommen).
- `sensor.display_wetter` (nur mit Wetter-Entität): Zustand ist das Wetter des aktuellen Halbtags. Attribut `tage` als Liste, Attribut `anzeige` als Text, eine Zeile pro Tag: `tag|zustand|temperatur|regen|menge|zustand|temperatur|regen|menge|tiefst|tiefst` (erst Vormittag, dann Nachmittag; die beiden Tiefstwerte in °C stehen am Schluss). `zustand` ist ein Wetterzustand von Home Assistant (`sunny`, `rainy`, …), `temperatur` die höchste Temperatur in °C, `regen` die höchste Regenwahrscheinlichkeit (`40 %`), `menge` die Niederschlagsmenge (`1,2 mm`, leer bei 0). Fehlende Werte bleiben leer. Für den Zustand zählt der häufigste der Stunden, bei Gleichstand der schlechtere. Fehlen stündliche Daten, kommen die Werte aus der Tagesvorhersage.

## Dienste

- `haushalt.erledigt` mit `aufgabe_id` hakt eine Aufgabe ab. Bei Aufgaben, die verschwinden, wird der nächste offene Termin abgehakt.
- `haushalt.saugen` startet den Staubsauger. `zimmer`: Raum-IDs, z.B. `19,20` (leer = ganze Wohnung, sonst `app_segment_clean`). `start_in_min`: 0, 5, 20 oder 60. Ein geplanter Start übersteht einen Neustart von HA; war HA länger als 15 Minuten über den Zeitpunkt hinaus aus, entfällt er.
- `haushalt.sauger` mit `aktion`: `pausieren`, `fortsetzen`, `abbrechen` (geplanten Start löschen bzw. zurück zur Station) oder `reinigen` (zum Reinigungspunkt fahren).

- `haushalt.einfrieren` mit `name`, `menge`, optional `kategorie` (Standard `meal_prep`), `einheit` (`portionen`, `stueck`, `gramm`), `eingefroren` (Standard heute) und entweder `haltbar_bis` (Datum) oder `haltbar_anzahl` + `haltbar_einheit` (`tage`, `wochen`, `monate`). Ohne beides gilt der Standard der Kategorie.
- `haushalt.entnehmen` mit `artikel` (Kennung aus `sensor.gefrierer`, z.B. `chili~portionen`) und optional `menge` (leer oder 0 = alles).

## Ereignis

Nach jedem Abhaken feuert `haushalt_erledigt` mit `aufgabe_id` und `name`. Damit lassen sich eigene Automationen auslösen.

## Entwicklung

```
pip install -r requirements_test.txt
pytest
```

Neue Versionen: Wird die `version` in `manifest.json` erhöht und auf `main` gemergt, legt GitHub automatisch ein Release `vX.Y.Z` an. HACS zeigt dann die Versionsnummer und bietet das Update an.
