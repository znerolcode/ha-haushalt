# Haushalt

Home-Assistant-Integration für wiederkehrende Haushaltsaufgaben. Gedacht für ein E-Ink-Display im Flur, funktioniert aber auch allein im Dashboard.

## Aufgabentypen

| Typ | Beispiel | Fällig | Wenn verpasst |
| --- | --- | --- | --- |
| Intervall | Bettwäsche alle 14 Tage | X Tage nach dem letzten Abhaken | bleibt stehen, „2 Tage überfällig“ |
| Wochentag | Bad putzen jeden Samstag | an den gewählten Wochentagen (auch mehrere, auch alle X Wochen) | bleibt stehen, bis erledigt |
| Termin | Altkarton alle 2 Wochen dienstags | am Termintag, Frist „Morgen“ oder „Abend“ | verschwindet nach der Frist |

Wochentag-Aufgaben haben einen Mindestabstand (Standard 3 Tage): Wird die Aufgabe z.B. am Donnerstag erledigt, entfällt der Samstag zwei Tage später, fällig ist erst der übernächste Samstag.

Anzeigetexte: Intervall und Wochentag „in 4 Tagen“, „morgen“, „heute“, „1 Tag überfällig“. Termin „bis in 3 Tagen“, „bis morgen früh“, „bis heute Abend“.

## Installation über HACS

1. HACS öffnen, oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/znerolcode/ha-haushalt` eintragen, Typ **Integration**, hinzufügen.
3. „Haushalt“ in HACS suchen, herunterladen, Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Haushalt**.

## Aufgaben erfassen

Unter **Einstellungen → Geräte & Dienste → Haushalt** auf **Aufgabe hinzufügen** klicken. Bestehende Aufgaben lassen sich dort über ⋮ → **Neu konfigurieren** ändern oder löschen.

Termin-Aufgaben: Das erste Datum bestimmt den Wochentag, „alle X Wochen“ die Wiederholung. Unregelmässige Termine (z.B. aus dem Abfuhrkalender) trägst du unter „Weitere einzelne Termine“ ein: `05.11.2026, 19.11.2026`.

Optional kannst du einer Aufgabe einen **Staubsauger** zuordnen (z.B. „Zum Staubsaugen vorbereiten“ mit dem Roborock). Beim Abhaken wählst du dann, ob er sofort oder in 5, 20 oder 60 Minuten startet. Er saugt die ganze Wohnung (`vacuum.start`).

Unter **Konfigurieren** stellst du ein, wann die Fristen „Morgen“ (Standard 09:00) und „Abend“ (23:59) enden und wie viele Tage im Voraus Aufgaben erscheinen (Standard 7).

Ebenfalls unter **Konfigurieren** wählst du optional eine **Wetter-Entität** (z.B. `weather.forecast_home` von Met.no). Die Integration fasst deren Vorhersage für heute und die nächsten 2 Tage in Vormittag (6–12 Uhr) und Nachmittag (12–18 Uhr) zusammen. Der heutige Vormittag bleibt auch am Nachmittag stehen.

## Entitäten

- Pro Aufgabe ein Sensor **Fälligkeit** (Zustand z.B. „in 4 Tagen“, Attribute `faellig_am`, `tage`, `gruppe`, `aufgabe_id`) und ein Knopf **Erledigt**.
- Aufgaben mit Staubsauger haben zusätzlich: Knöpfe **Erledigt, sofort saugen** und **Erledigt, saugen in 5/20/60 Min**, einen Sensor **Saugstart** (Zeitpunkt des geplanten Starts, leer wenn nichts geplant) und einen Knopf **Saugstart abbrechen**. Ein geplanter Start übersteht einen Neustart von HA. War HA länger als 15 Minuten über den geplanten Zeitpunkt hinaus aus, entfällt der Start.
- `sensor.aufgaben`: Anzahl sichtbarer Aufgaben. Attribut `aufgaben` als Liste, Attribut `anzeige` als Text für das Display, eine Zeile pro Aufgabe: `aufgabe_id|gruppe|name|text|ueberfaellig|startzeit_auswahl` (die letzten beiden 0 oder 1; `startzeit_auswahl` = 1, wenn die Aufgabe einen Staubsauger hat). Attribut `saugstart`: Uhrzeit des nächsten geplanten Saugstarts (`17:05`), leer wenn keiner geplant ist.
- `sensor.display_wetter` (nur mit Wetter-Entität): Zustand ist das Wetter des aktuellen Halbtags. Attribut `tage` als Liste, Attribut `anzeige` als Text, eine Zeile pro Tag: `tag|zustand|temperatur|regen|zustand|temperatur|regen` (erst Vormittag, dann Nachmittag). `zustand` ist ein Wetterzustand von Home Assistant (`sunny`, `rainy`, …), `temperatur` die höchste Temperatur in °C, `regen` die höchste Regenwahrscheinlichkeit (`40 %`) oder, wenn die Vorhersage keine liefert, die Regenmenge (`1,2 mm`). Fehlende Werte bleiben leer. Für den Zustand zählt der häufigste der Stunden, bei Gleichstand der schlechtere. Fehlen stündliche Daten, kommen die Werte aus der Tagesvorhersage.

## Dienst

`haushalt.erledigt` mit `aufgabe_id` hakt eine Aufgabe ab. Bei Termin-Aufgaben wird der nächste offene Termin abgehakt. Optional `start_in_min` (0, 5, 20 oder 60) für Aufgaben mit Staubsauger; ohne Angabe startet er sofort.

## Ereignis

Nach jedem Abhaken feuert `haushalt_erledigt` mit `aufgabe_id`, `name` und `start_in_min` (bei Aufgaben ohne Staubsauger leer). Damit lassen sich eigene Automationen auslösen.

## Entwicklung

```
pip install -r requirements_test.txt
pytest
```

Neue Versionen: Wird die `version` in `manifest.json` erhöht und auf `main` gemergt, legt GitHub automatisch ein Release `vX.Y.Z` an. HACS zeigt dann die Versionsnummer und bietet das Update an.
