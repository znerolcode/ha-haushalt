# Flur-Display: Anleitung

E-Ink-Display (Waveshare 7,5" V2, schwarz-weiss) mit Drehregler (KY-040) an einem ESP32-Devboard. Es zeigt die Aufgaben aus der Haushalt-Integration und das Wetter, und hakt Aufgaben direkt in Home Assistant ab.

## Was du brauchst

- Haushalt-Integration ab Version 0.4.0, unter **Konfigurieren** eine Wetter-Entität gewählt (sonst bleibt die Wetterspalte leer)
- In Home Assistant die App (Add-on) **ESPHome Device Builder**
- Waveshare 7,5" e-Paper HAT (V2) mit Treiberplatine und Kabel
- KY-040 Drehregler
- ESP32-Devboard (30 Pins, z.B. „ESP32S“), USB-Kabel, USB-Netzteil
- Dupont-Kabel Buchse–Buchse

## Verkabelung

Alles wird gesteckt, nichts gelötet. Strom erst anschliessen, wenn alles verkabelt ist.

### Display (Treiberplatine) → ESP32

Massgebend ist die Beschriftung auf der Treiberplatine. Die Kabelfarben gelten für die Treiberplatine Rev 2.3 und können bei anderen Versionen abweichen.

| Treiberplatine | Kabelfarbe | ESP32-Pin | Beschriftung auf dem Board |
|---|---|---|---|
| VCC | rot | 3V3 | 3V3 |
| GND | schwarz | GND | GND |
| DIN | blau | GPIO23 | D23 |
| CLK | gelb | GPIO18 | D18 |
| CS | orange | GPIO5 | D5 |
| DC | grün | GPIO17 | TX2 |
| RST | weiss | GPIO16 | RX2 |
| BUSY | violett | GPIO4 | D4 |
| PWR (nur falls vorhanden, 9. Ader) | braun | GPIO26 | D26 |

Auf der Treiberplatine gibt es zwei kleine Schalter. **Interface Config** muss auf **0** stehen (4-Draht-SPI). **Display Config** auf **B** (0.47R).

### Drehregler (KY-040) → ESP32

| KY-040 | ESP32-Pin | Beschriftung auf dem Board |
|---|---|---|
| CLK | GPIO33 | D33 |
| DT | GPIO32 | D32 |
| SW | GPIO25 | D25 |
| GND | GND (der zweite GND-Pin) | GND |
| + | GPIO27 | D27 |

Der „+“-Pin kommt an D27: Das ESP32 hat nur einen 3V3-Pin, und der wird fürs Display gebraucht. Die Firmware schaltet D27 deshalb dauerhaft auf 3.3 V. So halten die Widerstände auf der KY-040 die Leitungen stabil, und der Regler springt nicht von selbst.

## Firmware aufspielen

### 1. Gerät in ESPHome anlegen

1. In Home Assistant **ESPHome Device Builder** öffnen, **+ New device** wählen.
2. Name `flur-display`, Typ **ESP32**. ESPHome erzeugt eine Konfiguration mit WLAN, Schlüssel und Passwörtern.
3. Beim Gerät auf **Edit** klicken. Ganz unten diesen Teil anfügen (das Beispiel steht vollständig in [beispiel-geraet.yaml](beispiel-geraet.yaml)):

```yaml
substitutions:
  innen_temperatur: sensor.flur_temperatur  # deinen Temperatursensor eintragen

packages:
  flur_display:
    url: https://github.com/znerolcode/ha-haushalt
    ref: main
    files: [esphome/flur-display.yaml]
    refresh: 0s
```

4. Bei `innen_temperatur` die Entität deines Temperatursensors eintragen (in HA unter Einstellungen → Entitäten zu finden).
5. **Save**.

ESPHome holt die eigentliche Firmware aus diesem Repository. Mit `refresh: 0s` lädt es bei jedem Aufspielen den neusten Stand, Verbesserungen kommen so automatisch dazu.

### 2. Das erste Mal per USB aufspielen

1. Beim Gerät **Install** → **Manual download** → **Factory format** wählen. Das Kompilieren dauert beim ersten Mal einige Minuten.
2. ESP32 per USB an den Computer anschliessen.
3. In Chrome oder Edge <https://web.esphome.io> öffnen, **Connect**, den Port wählen, **Install** und die heruntergeladene Datei wählen.
4. Erscheint kein Port: Das Board braucht einen USB-Treiber (meist CH340 oder CP2102, steht auf dem kleinen Chip neben dem USB-Anschluss).

Danach geht jedes weitere Aufspielen über WLAN direkt aus ESPHome (**Install** → **Wirelessly**).

### 3. In Home Assistant freigeben

1. Home Assistant meldet das neue Gerät unter **Einstellungen → Geräte & Dienste**. Hinzufügen.
2. Bei der ESPHome-Integration beim Gerät **Konfigurieren** öffnen und **Allow the device to perform Home Assistant actions** einschalten. Ohne das kann das Display keine Aufgaben abhaken.

## Bedienung

- **Homescreen** (nur wenn in der Haushalt-Integration der Gefrierer eingeschaltet ist): Links stehen die Kacheln **Haushalt** und **Gefrierer** mit einer kurzen Zusammenfassung, rechts das Wetter. Drehen wählt eine Kachel, Drücken öffnet sie. In beiden Listen steht zuoberst **Zurück**. Ohne Gefrierer zeigt das Display direkt die Aufgaben, wie bisher.
- **Gefrierer:** Liste nach Ablauf sortiert (abgelaufen, bald aufbrauchen, später), Meal-Prep mit Topf-Symbol. Drücken auf einen Artikel zeigt **Wie viel entnehmen?** mit Knöpfen passend zur Einheit (z.B. 1, 2, 3 Portionen oder alle); Drehen wählt, Drücken entnimmt. Ganz unten steht **+ Einfrieren** mit einem QR-Code zum Dashboard „Gefrierer“ (Einrichtung siehe README, Abschnitt „Gefrierer“). Die Adresse steht unter `substitutions:` als `gefrierer_url`, z.B. `http://192.168.178.65:8123/haushalt-gefrierer/einfrieren`.
- **Drehen** bewegt den Pfeil durch die Liste. Passen nicht alle Aufgaben aufs Display, scrollt sie mit; unten steht, wie viele weitere es gibt.
- **Drücken** fragt „Erledigt?“, **nochmals drücken** hakt ab. Drehen bricht ab.
- Zuoberst steht die Zeile **Staubsaugen** (nur wenn in der Haushalt-Integration ein Staubsauger gewählt ist). Drücken öffnet **Ganze Wohnung**, **Einzelne Zimmer** und **Sauger reinigen**. Danach Startzeit wählen und die Rückfrage mit **Ja** bestätigen. Bei einzelnen Zimmern erscheint der Grundriss: Drehen springt von Zimmer zu Zimmer, Drücken markiert es schwarz, nach dem letzten Zimmer kommen **Weiter** und **Zurück**, dann wieder das erste Zimmer.
- Läuft oder wartet der Staubsauger, zeigt die Zeile das an. Drücken bietet dann **Pausieren**/**Fortsetzen**, **Abbrechen** (zurück zur Station) und **Zurück**.
- Der Grundriss und die Raum-IDs stehen in `grundriss.h`. Für eine andere Wohnung dort anpassen.
- Ganz unten steht **+ Neue Aufgabe**. Drücken zeigt einen QR-Code, der am Handy das Dashboard „Neue Aufgabe“ öffnet (Einrichtung siehe README, Abschnitt „Aufgaben ohne Administratorrechte anlegen“). Die Adresse steht in der Gerätekonfiguration unter `substitutions:` als `neue_aufgabe_url`. Ohne Eintrag öffnet der QR-Code die Haushalt-Seite in HA, die nur Administratoren bedienen können.
- Ohne Drehregler geht dasselbe in Home Assistant: Das Gerät hat die Tasten **Hoch**, **Runter** und **Drücken**.
- 10 Sekunden ohne Bedienung brechen eine offene Auswahl ab, nach 60 Sekunden verschwindet der Pfeil und das Display kehrt zum Homescreen (bzw. zur Aufgabenliste) zurück.
- Ohne Bedienung aktualisiert sich das Display alle 5 Minuten und wenn sich in Home Assistant etwas ändert, jeweils gründlich (ca. 4 s Flackern, voller Kontrast). Beim Drehen geht es schnell, dafür etwas blasser; 60 Sekunden nach der letzten Bedienung wird wieder gründlich gezeichnet. Von 23 bis 6 Uhr bleibt es stehen.
- Wie kräftig das Bild beim Drehen ist, stellst du in Home Assistant beim Gerät unter **Konfiguration → Kontrast beim Drehen** ein: 0 = schnell und blass, 10 = kräftig, aber träger. Am besten Regler verschieben, am Knopf drehen und vergleichen. Die Stufe bleibt nach einem Neustart erhalten.

## Wenn etwas nicht stimmt

- **Display bleibt weiss oder zeigt Streifen**: Verkabelung prüfen, vor allem BUSY, RST und DC. Dann den Schalter **Display Config** umstellen und neu starten.
- **Ein Rastschritt springt zwei Zeilen** oder **drehen geht in die falsche Richtung**: in der Gerätekonfiguration ergänzen und neu aufspielen:

```yaml
sensor:
  - id: !extend regler
    resolution: 2   # bei Doppelsprüngen
```

  Für die Richtung CLK und DT am ESP32 tauschen.
- **Gerät startet immer wieder neu** („Task wdt“ im Protokoll): Die Firmware setzt `watchdog_timeout: 30s`. Steht in deiner Gerätekonfiguration unter `esp32:` ein kleinerer Wert, diesen entfernen.
- **Kein Port beim Aufspielen**: anderes USB-Kabel probieren (viele können nur laden) oder den Treiber für den USB-Chip installieren (CP2102 oder CH340, steht auf dem Chip neben dem USB-Anschluss).
- **Home Assistant findet das Gerät nicht unter `name.local`**: die IP-Adresse eintragen, sie steht im Protokoll bei „IP Address“.
- **Abhaken tut nichts**: Schritt 3 („Allow the device to perform Home Assistant actions“) prüfen.
- **Wetter fehlt**: In der Haushalt-Integration unter **Konfigurieren** eine Wetter-Entität wählen. Es muss `sensor.display_wetter` geben.
