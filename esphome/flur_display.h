// Bedienlogik des Flur-Displays: Liste, Bestätigung, QR-Code und Staubsauger.
// Wird von flur-display.yaml eingebunden; gezeichnet wird dort im Display-Lambda.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "grundriss.h"

namespace flur {

enum Modus {
  LISTE,
  BESTAETIGEN,  // "Erledigt? Nochmals drücken"
  QR,           // QR-Code für neue Aufgaben
  SAUG_MENU,    // Menü unter der Staubsauger-Zeile
  ZIMMER,       // Zimmer im Grundriss wählen
  SAUG_ZEIT,    // Startzeit wählen
  SAUG_FRAGE,   // "Ganze Wohnung in 20 Min saugen?" Ja / Zurück
};

// Startzeit-Auswahl, in Minuten
static const int START_OPTIONEN[] = {0, 5, 20, 60};
static const int ANZAHL_OPTIONEN = 4;
static const char *const START_NAMEN[] = {"sofort", "5 Min", "20 Min", "60 Min"};

static const char *const SAUGER_ID = "#sauger";

struct Eintrag {
  std::string id, gruppe, name, text;
  bool ueberfaellig = false;
  bool neu = false;     // der Eintrag "+ Neue Aufgabe"
  bool sauger = false;  // die Staubsauger-Zeile ganz oben
};

// Eine Option in einem Menü: Beschriftung und was sie auslöst
struct Option {
  const char *name;
  const char *aktion;
};

inline Modus modus = LISTE;
inline int cursor = -1;          // -1: kein Pfeil sichtbar
inline std::string cursor_id;    // damit der Pfeil bei neuen Daten auf derselben Aufgabe bleibt
inline int auswahl = 0;          // gewählte Option im offenen Menü
inline int oben = 0;             // erstes sichtbares Element der Liste

// Staubsauger aus sensor.aufgaben, Attribut sauger: zustand|uhrzeit|zimmer-ids
inline std::string sauger_roh;
inline std::vector<int> gewaehlt;  // gewählte Zimmer (Segment-IDs), leer = ganze Wohnung
inline int zimmer_cursor = 0;      // 0..ANZAHL_ZIMMER-1 Zimmer, dann Weiter, Zurück
inline bool zimmer_hinweis = false;  // "Erst ein Zimmer wählen"

// Gerade abgehakt, aber von Home Assistant noch nicht entfernt
inline std::set<std::string> versteckt;

// Wird von der YAML abgeholt und an Home Assistant geschickt
inline bool senden = false;        // haushalt.erledigt
inline std::string senden_id;
inline std::string saug_aktion;    // haushalt.saugen ("saugen") bzw. haushalt.sauger (sonst)
inline std::string saug_zimmer;    // "19,20", leer = ganze Wohnung
inline int saug_min = 0;

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

// ---- Staubsauger ----

struct Sauger {
  std::string zustand;  // bereit, geplant, saugt, pausiert, zurueck, reinigen, steht, fehler
  std::string zeit;     // Startzeit bei "geplant", z.B. "17:05"
  std::vector<int> zimmer;
};

inline Sauger sauger_lesen() {
  Sauger s;
  auto f = teilen(sauger_roh, '|');
  f.resize(3);
  s.zustand = f[0];
  s.zeit = f[1];
  if (!f[2].empty())
    for (auto &t : teilen(f[2], ','))
      if (!t.empty())
        s.zimmer.push_back(atoi(t.c_str()));
  return s;
}

inline std::string zimmer_text(const std::vector<int> &ids) {
  if (ids.empty())
    return "Ganze Wohnung";
  std::string t;
  for (int i = 0; i < ANZAHL_ZIMMER; i++) {
    if (std::find(ids.begin(), ids.end(), ZIMMER_LISTE[i].id) == ids.end())
      continue;
    if (!t.empty())
      t += ", ";
    t += ZIMMER_LISTE[i].name;
  }
  return t;
}

// Optionen im Menü unter der Staubsauger-Zeile, je nach Zustand
inline std::vector<Option> saug_optionen(const std::string &zustand) {
  if (zustand == "bereit" || zustand.empty())
    return {{"Ganze Wohnung", "wohnung"}, {"Einzelne Zimmer", "zimmer"}, {"Sauger reinigen", "reinigen"}};
  if (zustand == "geplant")
    return {{"Abbrechen", "abbrechen"}, {"Zurück", ""}};
  if (zustand == "saugt")
    return {{"Pausieren", "pausieren"}, {"Abbrechen", "abbrechen"}, {"Zurück", ""}};
  if (zustand == "pausiert")
    return {{"Fortsetzen", "fortsetzen"}, {"Abbrechen", "abbrechen"}, {"Zurück", ""}};
  if (zustand == "zurueck")
    return {{"Anhalten", "pausieren"}, {"Zurück", ""}};
  // reinigen, steht, fehler
  return {{"Zur Station", "abbrechen"}, {"Zurück", ""}};
}

// Menüs, deren Optionen untereinander statt nebeneinander stehen
inline bool saug_menu_senkrecht(const std::string &zustand) { return zustand == "bereit" || zustand.empty(); }

// ---- Liste ----

// Zeilen aus sensor.aufgaben, Attribut anzeige: id|gruppe|name|text|ueberfaellig
inline std::vector<Eintrag> eintraege(const std::string &roh) {
  std::vector<Eintrag> liste;
  if (!sauger_roh.empty()) {
    Eintrag s;
    s.id = SAUGER_ID;
    s.sauger = true;
    liste.push_back(s);
  }
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

inline bool saug_modus() { return modus == SAUG_MENU || modus == ZIMMER || modus == SAUG_ZEIT || modus == SAUG_FRAGE; }

// Pfeil nach neuen Daten wieder auf dieselbe Aufgabe setzen
inline void abgleichen(const std::vector<Eintrag> &liste) {
  if (cursor < 0)
    return;
  int n = liste.size();
  for (int i = 0; i < n; i++) {
    if (liste[i].id == cursor_id) {
      cursor = i;
      // Zustand des Saugers hat gewechselt: Menü passt nicht mehr
      if (modus == SAUG_MENU)
        auswahl = std::min(auswahl, (int) saug_optionen(sauger_lesen().zustand).size() - 1);
      return;
    }
  }
  cursor = std::min(cursor, n - 1);
  cursor_id = liste[cursor].id;
  if (modus == BESTAETIGEN || saug_modus())
    modus = LISTE;
}

inline void drehen(int richtung, const std::string &roh) {
  auto liste = eintraege(roh);
  abgleichen(liste);
  int n = liste.size();
  switch (modus) {
    case QR:
      modus = LISTE;
      return;
    case SAUG_MENU: {
      int k = saug_optionen(sauger_lesen().zustand).size();
      auswahl = std::max(0, std::min(k - 1, auswahl + richtung));
      return;
    }
    case ZIMMER:
      zimmer_hinweis = false;
      // Läuft im Kreis: nach Zurück wieder das erste Zimmer
      zimmer_cursor = (zimmer_cursor + richtung + ANZAHL_ZIMMER + 2) % (ANZAHL_ZIMMER + 2);
      return;
    case SAUG_ZEIT:
      auswahl = std::max(0, std::min(ANZAHL_OPTIONEN - 1, auswahl + richtung));
      return;
    case SAUG_FRAGE:
      auswahl = std::max(0, std::min(1, auswahl + richtung));
      return;
    default:
      break;
  }
  modus = LISTE;  // Drehen bricht "Erledigt?" ab
  if (cursor < 0)
    cursor = richtung > 0 ? 0 : n - 1;
  else
    cursor = std::max(0, std::min(n - 1, cursor + richtung));
  cursor_id = liste[cursor].id;
}

inline void saug_senden(const std::string &aktion) {
  saug_aktion = aktion;
  saug_zimmer.clear();
  if (aktion == "saugen") {
    for (int id : gewaehlt) {
      if (!saug_zimmer.empty())
        saug_zimmer += ",";
      saug_zimmer += std::to_string(id);
    }
  }
  modus = LISTE;
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
  switch (modus) {
    case SAUG_MENU: {
      auto opt = saug_optionen(sauger_lesen().zustand);
      std::string a = opt[std::min(auswahl, (int) opt.size() - 1)].aktion;
      if (a.empty()) {
        modus = LISTE;
      } else if (a == "wohnung") {
        gewaehlt.clear();
        modus = SAUG_ZEIT;
        auswahl = 0;
      } else if (a == "zimmer") {
        gewaehlt.clear();
        zimmer_cursor = 0;
        zimmer_hinweis = false;
        modus = ZIMMER;
      } else {
        saug_senden(a);
      }
      return;
    }
    case ZIMMER:
      if (zimmer_cursor < ANZAHL_ZIMMER) {
        int id = ZIMMER_LISTE[zimmer_cursor].id;
        auto it = std::find(gewaehlt.begin(), gewaehlt.end(), id);
        if (it == gewaehlt.end())
          gewaehlt.push_back(id);
        else
          gewaehlt.erase(it);
      } else if (zimmer_cursor == ANZAHL_ZIMMER) {  // Weiter
        if (gewaehlt.empty()) {
          zimmer_hinweis = true;
        } else {
          modus = SAUG_ZEIT;
          auswahl = 0;
        }
      } else {  // Zurück
        modus = SAUG_MENU;
        auswahl = 1;
      }
      return;
    case SAUG_ZEIT:
      saug_min = START_OPTIONEN[auswahl];
      modus = SAUG_FRAGE;
      auswahl = 0;
      return;
    case SAUG_FRAGE:
      if (auswahl == 0) {
        saug_senden("saugen");
      } else {
        modus = SAUG_ZEIT;
        for (int o = 0; o < ANZAHL_OPTIONEN; o++)
          if (START_OPTIONEN[o] == saug_min)
            auswahl = o;
      }
      return;
    default:
      break;
  }
  if (e.sauger) {
    modus = SAUG_MENU;
    auswahl = 0;
    return;
  }
  if (e.neu) {
    modus = QR;
    return;
  }
  if (modus == LISTE) {
    modus = BESTAETIGEN;
    return;
  }
  senden = true;
  senden_id = e.id;
  versteckt.insert(e.id);
  modus = LISTE;
}

// Läuft gerade eine Auswahl, die nach einer Weile ohne Bedienung abbricht?
inline bool auswahl_offen() { return modus == BESTAETIGEN || saug_modus(); }

inline void auswahl_abbrechen() {
  if (auswahl_offen())
    modus = LISTE;
}

inline void ruhe() {
  modus = LISTE;
  cursor = -1;
  cursor_id.clear();
  oben = 0;
}

}  // namespace flur
