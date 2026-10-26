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

Die Farben sind die des Waveshare-Kabels. Massgebend ist die Beschriftung auf der Treiberplatine.

| Treiberplatine | Kabelfarbe | ESP32-Pin | Beschriftung auf dem Board |
|---|---|---|---|
| VCC | grau | 3V3 | 3V3 |
| GND | braun | GND | GND |
| DIN | blau | GPIO23 | D23 |
| CLK | gelb | GPIO18 | D18 |
| CS | orange | GPIO5 | D5 |
| DC | grün | GPIO17 | TX2 |
| RST | weiss | GPIO16 | RX2 |
| BUSY | violett | GPIO4 | D4 |
| PWR (nur falls vorhanden, 9. Ader) | rot | GPIO26 | D26 |

Auf der Treiberplatine gibt es zwei kleine Schalter. **Interface Config** muss auf **0** stehen (4-Draht-SPI). **Display Config** lässt du vorerst, wie er geliefert wurde.

### Drehregler (KY-040) → ESP32

| KY-040 | ESP32-Pin | Beschriftung auf dem Board |
|---|---|---|
| CLK | GPIO32 | D32 |
| DT | GPIO33 | D33 |
| SW | GPIO25 | D25 |
| GND | GND (der zweite GND-Pin) | GND |
| + | **nicht anschliessen** | |

Der „+“-Pin bleibt frei: Das ESP32 hat nur einen 3V3-Pin, und der wird fürs Display gebraucht. Der Regler funktioniert trotzdem, weil die Firmware die internen Pull-ups des ESP32 einschaltet.

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
    refresh: 1d
```

4. Bei `innen_temperatur` die Entität deines Temperatursensors eintragen (in HA unter Einstellungen → Entitäten zu finden).
5. **Save**.

ESPHome holt die eigentliche Firmware aus diesem Repository. Verbesserungen kommen so mit dem nächsten Aufspielen automatisch dazu.

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

- **Drehen** bewegt den Pfeil durch die Liste. Passen nicht alle Aufgaben aufs Display, scrollt sie mit; unten steht, wie viele weitere es gibt.
- **Drücken** fragt „Erledigt?“, **nochmals drücken** hakt ab. Drehen bricht ab.
- Bei Aufgaben mit Staubsauger wählst du nach dem ersten Drücken die Startzeit (sofort, 5, 20, 60 Min) und bestätigst mit Drücken.
- Ganz unten steht **+ Neue Aufgabe**. Drücken zeigt einen QR-Code, der am Handy die Haushalt-Seite in Home Assistant öffnet.
- 10 Sekunden ohne Bedienung brechen eine offene Auswahl ab, nach 30 Sekunden verschwindet der Pfeil.
- Ohne Bedienung aktualisiert sich das Display alle 15 Minuten und wenn sich in Home Assistant etwas ändert. Von 23 bis 6 Uhr bleibt es stehen.

## Wenn etwas nicht stimmt

- **Display bleibt weiss oder zeigt Streifen**: Verkabelung prüfen, vor allem BUSY, RST und DC. Dann den Schalter **Display Config** umstellen und neu starten.
- **Ein Rastschritt springt zwei Zeilen** oder **drehen geht in die falsche Richtung**: in der Gerätekonfiguration ergänzen und neu aufspielen:

```yaml
sensor:
  - id: !extend regler
    resolution: 2   # bei Doppelsprüngen
```

  Für die Richtung CLK und DT am ESP32 tauschen.
- **Abhaken tut nichts**: Schritt 3 („Allow the device to perform Home Assistant actions“) prüfen.
- **Wetter fehlt**: In der Haushalt-Integration unter **Konfigurieren** eine Wetter-Entität wählen. Es muss `sensor.display_wetter` geben.
