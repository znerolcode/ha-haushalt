// Bedienlogik des Flur-Displays: Liste, Auswahl, Bestätigung, QR-Code.
// Wird von flur-display.yaml eingebunden; gezeichnet wird dort im Display-Lambda.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <vector>

namespace flur {

enum Modus { LISTE, BESTAETIGEN, AUSWAHL, QR };

// Startzeit-Auswahl für Aufgaben mit Staubsauger, in Minuten
static const int START_OPTIONEN[] = {0, 5, 20, 60};
static const int ANZAHL_OPTIONEN = 4;

struct Eintrag {
  std::string id, gruppe, name, text;
  bool ueberfaellig = false;
  bool staubsauger = false;
  bool neu = false;  // der Eintrag "+ Neue Aufgabe"
};

inline Modus modus = LISTE;
inline int cursor = -1;          // -1: kein Pfeil sichtbar
inline std::string cursor_id;    // damit der Pfeil bei neuen Daten auf derselben Aufgabe bleibt
inline int auswahl = 0;          // Index in START_OPTIONEN
inline int oben = 0;             // erstes sichtbares Element der Liste

// Gerade abgehakt, aber von Home Assistant noch nicht entfernt
inline std::set<std::string> versteckt;

// Wird von der YAML abgeholt und an haushalt.erledigt geschickt
inline bool senden = false;
inline std::string senden_id;
inline int senden_min = 0;

inline std::vector<std::string> teilen(const std::string &text, char trenner) {
  std::vector<std::string> teile;
  size_t start = 0;
  while (true) {
    size_t pos = text.find(trenner, start);
    teile.push_back(text.substr(start, pos == std::string::npos ? std::string::npos : pos - start));
    if (pos == std::string::npos)
      break;
    start = pos + 1;
  }
  return teile;
}

// Zeilen aus sensor.aufgaben, Attribut anzeige: id|gruppe|name|text|ueberfaellig|startzeit_auswahl
inline std::vector<Eintrag> eintraege(const std::string &roh) {
  std::vector<Eintrag> liste;
  std::set<std::string> vorhanden;
  for (auto &zeile : teilen(roh, '\n')) {
    auto f = teilen(zeile, '|');
    if (f.size() < 5 || f[0].empty())
      continue;
    vorhanden.insert(f[0]);
    if (versteckt.count(f[0]))
      continue;
    Eintrag e;
    e.id = f[0];
    e.gruppe = f[1];
    e.name = f[2];
    e.text = f[3];
    e.ueberfaellig = f[4] == "1";
    e.staubsauger = f.size() > 5 && f[5] == "1";
    liste.push_back(e);
  }
  // Was Home Assistant entfernt hat, muss nicht mehr versteckt werden
  for (auto it = versteckt.begin(); it != versteckt.end();) {
    if (vorhanden.count(*it))
      ++it;
    else
      it = versteckt.erase(it);
  }
  Eintrag neu;
  neu.name = "+ Neue Aufgabe";
  neu.neu = true;
  liste.push_back(neu);
  return liste;
}

// Pfeil nach neuen Daten wieder auf dieselbe Aufgabe setzen
inline void abgleichen(const std::vector<Eintrag> &liste) {
  if (cursor < 0)
    return;
  int n = liste.size();
  for (int i = 0; i < n; i++) {
    if (liste[i].id == cursor_id) {
      cursor = i;
      return;
    }
  }
  cursor = std::min(cursor, n - 1);
  cursor_id = liste[cursor].id;
  if (modus == BESTAETIGEN || modus == AUSWAHL)
    modus = LISTE;
}

inline void drehen(int richtung, const std::string &roh) {
  auto liste = eintraege(roh);
  abgleichen(liste);
  int n = liste.size();
  if (modus == QR) {
    modus = LISTE;
    return;
  }
  if (modus == AUSWAHL) {
    auswahl = (auswahl + richtung + ANZAHL_OPTIONEN) % ANZAHL_OPTIONEN;
    return;
  }
  modus = LISTE;  // Drehen bricht "Erledigt?" ab
  if (cursor < 0)
    cursor = richtung > 0 ? 0 : n - 1;
  else
    cursor = std::max(0, std::min(n - 1, cursor + richtung));
  cursor_id = liste[cursor].id;
}

inline void druecken(const std::string &roh) {
  auto liste = eintraege(roh);
  abgleichen(liste);
  if (modus == QR) {
    modus = LISTE;
    return;
  }
  if (cursor < 0) {
    cursor = 0;
    cursor_id = liste[0].id;
    return;
  }
  const Eintrag &e = liste[cursor];
  if (e.neu) {
    modus = QR;
    return;
  }
  if (modus == LISTE) {
    modus = e.staubsauger ? AUSWAHL : BESTAETIGEN;
    auswahl = 0;
    return;
  }
  senden = true;
  senden_id = e.id;
  senden_min = modus == AUSWAHL ? START_OPTIONEN[auswahl] : 0;
  versteckt.insert(e.id);
  modus = LISTE;
}

// Nach einer Weile ohne Bedienung: Auswahl abbrechen bzw. Pfeil ausblenden
inline void auswahl_abbrechen() {
  if (modus == BESTAETIGEN || modus == AUSWAHL)
    modus = LISTE;
}

inline void ruhe() {
  modus = LISTE;
  cursor = -1;
  cursor_id.clear();
  oben = 0;
}

}  // namespace flur
