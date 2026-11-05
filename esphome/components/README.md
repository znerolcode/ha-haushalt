# Angepasste ESPHome-Komponenten

`waveshare_epaper` ist eine Kopie aus ESPHome 2026.10.2. Einzige Änderung: Beim Modell `7.50inv2p` wird der Bildpuffer in einer SPI-Übertragung gesendet (`send_buffer_`) statt Byte für Byte. Das verkürzt jeden Schritt am Display von mehreren Sekunden auf einen Bruchteil.

Die Firmware (`flur-display.yaml`) bindet sie über `external_components` ein.

Zweite Änderung: `gruendlich_naechstes()` lässt die nächste Aktualisierung mit der normalen, langsamen Wellenform laufen (wie Modell `7.50inV2`). Das löscht die Geisterbilder des Schnellmodus. Die Firmware nutzt das nach dem Start, zur vollen Stunde und über die Taste „Display reinigen“.
