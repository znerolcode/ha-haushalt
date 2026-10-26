# Haushalt

Home-Assistant-Integration für wiederkehrende Haushaltsaufgaben. Gedacht für ein E-Ink-Display im Flur, funktioniert aber auch allein im Dashboard.

## Aufgabentypen

| Typ | Beispiel | Fällig | Wenn verpasst |
| --- | --- | --- | --- |
| Intervall | Bettwäsche alle 14 Tage | X Tage nach dem letzten Abhaken | bleibt stehen, „2 Tage überfällig“ |
| Termin | Altkarton alle 2 Wochen dienstags | am Termintag, Frist „Morgen“ oder „Abend“ | verschwindet nach der Frist |

Anzeigetexte: Intervall „in 4 Tagen“, „morgen“, „heute“, „1 Tag überfällig“. Termin „bis in 3 Tagen“, „bis morgen früh“, „bis heute Abend“.

## Installation über HACS

1. HACS öffnen, oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/znerolcode/ha-haushalt` eintragen, Typ **Integration**, hinzufügen.
3. „Haushalt“ in HACS suchen, herunterladen, Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Haushalt**.

## Aufgaben erfassen

Unter **Einstellungen → Geräte & Dienste → Haushalt** auf **Aufgabe hinzufügen** klicken. Bestehende Aufgaben lassen sich dort über ⋮ → **Neu konfigurieren** ändern oder löschen.

Termin-Aufgaben: Das erste Datum bestimmt den Wochentag, „alle X Wochen“ die Wiederholung. Unregelmässige Termine (z.B. aus dem Abfuhrkalender) trägst du unter „Weitere einzelne Termine“ ein: `05.11.2026, 19.11.2026`.

Unter **Konfigurieren** stellst du ein, wann die Fristen „Morgen“ (Standard 09:00) und „Abend“ (23:59) enden und wie viele Tage im Voraus Aufgaben erscheinen (Standard 7).

## Entitäten

- Pro Aufgabe ein Sensor **Fälligkeit** (Zustand z.B. „in 4 Tagen“, Attribute `faellig_am`, `tage`, `gruppe`, `aufgabe_id`) und ein Knopf **Erledigt**.
- `sensor.aufgaben`: Anzahl sichtbarer Aufgaben. Attribut `aufgaben` als Liste, Attribut `anzeige` als Text für das Display, eine Zeile pro Aufgabe: `aufgabe_id|gruppe|name|text|ueberfaellig`.

## Dienst

`haushalt.erledigt` mit `aufgabe_id` hakt eine Aufgabe ab. Bei Termin-Aufgaben wird der nächste offene Termin abgehakt.

## Entwicklung

```
pip install -r requirements_test.txt
pytest
```
