# Angepasste ESPHome-Komponenten

`waveshare_epaper` ist eine Kopie aus ESPHome 2026.10.2. Einzige Änderung: Beim Modell `7.50inv2p` wird der Bildpuffer in einer SPI-Übertragung gesendet (`send_buffer_`) statt Byte für Byte. Das verkürzt jeden Schritt am Display von mehreren Sekunden auf einen Bruchteil.

Die Firmware (`flur-display.yaml`) bindet sie über `external_components` ein.
