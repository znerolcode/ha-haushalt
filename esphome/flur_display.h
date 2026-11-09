// Bedienlogik des Flur-Displays: Homescreen, Aufgabenliste, Gefrierer, QR-Codes und Staubsauger.
// Wird von flur-display.yaml eingebunden; gezeichnet wird dort im Display-Lambda.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "grundriss.h"

namespace flur {

// Was links angezeigt wird. Den Homescreen gibt es nur mit Gefrierer.
enum Ansicht {
  HOME,       // zwei Kacheln: Haushalt und Gefrierer
  HAUSHALT,   // Aufgabenliste
  GEFRIERER,  // Inhalt des Gefrierers
};

enum Modus {
  LISTE,
  BESTAETIGEN,  // "Erledigt? Nochmals drücken"
  QR,           // QR-Code für neue Aufgaben bzw. zum Einfrieren
  GEF_MENU,     // "Wie viel entnehmen?" unter einem Artikel
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
static const char *const ZURUECK_ID = "#zurueck";
static const char *const NEU_ID = "#neu";

struct Eintrag {
  std::string id, gruppe, name, text;
  bool ueberfaellig = false;  // bzw. beim Gefrierer: abgelaufen
  bool neu = false;           // der Eintrag "+ Neue Aufgabe" bzw. "+ Einfrieren"
  bool sauger = false;        // die Staubsauger-Zeile ganz oben
  bool zurueck = false;       // "Zurück" zum Homescreen, ganz oben
  bool meal = false;          // Gefrierer: Meal-Prep (Topf-Symbol)
  // Gefrierer: für die Details rechts
  std::string menge, rest, kategorie;
  struct Packung {
    std::string menge, eingefroren, bis;
  };
  std::vector<Packung> packungen;
  // Gefrierer: Entnahme-Knöpfe als (Menge, Beschriftung)
  std::vector<std::pair<std::string, std::string>> optionen;
};

// Eine Option in einem Menü: Beschriftung und was sie auslöst
struct Option {
  const char *name;
  const char *aktion;
};

inline Ansicht ansicht = HOME;
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

// Gefrierer aus sensor.gefrierer (Attribut anzeige) und die Kacheln für den Homescreen
// (Attribut kachel von sensor.aufgaben und sensor.gefrierer), je 3 Zeilen 'vor|hervor|nach'
inline std::string gef_roh;
inline std::string kachel_haushalt;
inline std::string kachel_gefrierer;
inline std::string details_roh;      // sensor.aufgaben, Attribut details: id|rhythmus|zuletzt|termin,termin,termin
inline std::string sauger_letzter;   // "Mo 09.11.|14:05|14:50|19,20", Zimmer "app" oder leer = ganze Wohnung

// Gerade abgehakt, aber von Home Assistant noch nicht entfernt
inline std::set<std::string> versteckt;

// Wird von der YAML abgeholt und an Home Assistant geschickt
inline bool senden = false;        // haushalt.erledigt
inline std::string senden_id;
inline std::string saug_aktion;    // haushalt.saugen ("saugen") bzw. haushalt.sauger (sonst)
inline std::string saug_zimmer;    // "19,20", leer = ganze Wohnung
inline int saug_min = 0;
inline bool gef_senden = false;    // haushalt.entnehmen
inline std::string gef_artikel;
inline std::string gef_menge;

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

// Homescreen nur, wenn die Integration einen Gefrierer liefert
inline bool home_aktiv() { return !kachel_gefrierer.empty(); }

// Details zu einer Aufgabe für die rechte Spalte
struct Details {
  std::string rhythmus, zuletzt;
  std::vector<std::string> termine;
};

inline Details details_fuer(const std::string &id) {
  Details d;
  for (auto &zeile : teilen(details_roh, '\n')) {
    auto f = teilen(zeile, '|');
    if (f.size() < 4 || f[0] != id)
      continue;
    d.rhythmus = f[1];
    d.zuletzt = f[2];
    for (auto &t : teilen(f[3], ','))
      if (!t.empty())
        d.termine.push_back(t);
    break;
  }
  return d;
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

inline Eintrag zurueck_eintrag() {
  Eintrag z;
  z.id = ZURUECK_ID;
  z.zurueck = true;
  return z;
}

// Zeilen aus sensor.aufgaben, Attribut anzeige: id|gruppe|name|text|ueberfaellig
inline std::vector<Eintrag> aufgaben_eintraege(const std::string &roh) {
  std::vector<Eintrag> liste;
  if (home_aktiv())
    liste.push_back(zurueck_eintrag());
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
  neu.id = NEU_ID;
  neu.name = "+ Neue Aufgabe";
  neu.neu = true;
  liste.push_back(neu);
  return liste;
}

// Zeilen aus sensor.gefrierer, Attribut anzeige:
// artikel|gruppe|name|menge|rest|abgelaufen|meal_prep|menge:beschriftung;...|kategorie|menge~eingefroren~bis;...
inline std::vector<Eintrag> gefrierer_eintraege() {
  std::vector<Eintrag> liste;
  liste.push_back(zurueck_eintrag());
  for (auto &zeile : teilen(gef_roh, '\n')) {
    auto f = teilen(zeile, '|');
    if (f.size() < 8 || f[0].empty())
      continue;
    Eintrag e;
    e.id = f[0];
    e.gruppe = f[1];
    e.name = f[2];
    e.text = f[3] + " · " + f[4];
    e.menge = f[3];
    e.rest = f[4];
    if (f.size() >= 10) {
      e.kategorie = f[8];
      for (auto &p : teilen(f[9], ';')) {
        auto t = teilen(p, '~');
        if (t.size() == 3)
          e.packungen.push_back({t[0], t[1], t[2]});
      }
    }
    e.ueberfaellig = f[5] == "1";
    e.meal = f[6] == "1";
    for (auto &o : teilen(f[7], ';')) {
      size_t p = o.find(':');
      if (p != std::string::npos)
        e.optionen.push_back({o.substr(0, p), o.substr(p + 1)});
    }
    liste.push_back(e);
  }
  Eintrag neu;
  neu.id = NEU_ID;
  neu.name = "+ Einfrieren";
  neu.neu = true;
  liste.push_back(neu);
  return liste;
}

inline std::vector<Eintrag> home_eintraege() {
  Eintrag h, g;
  h.id = "#haushalt";
  h.name = "Haushalt";
  g.id = "#gefrierer";
  g.name = "Gefrierer";
  return {h, g};
}

// Einträge der aktuellen Ansicht
inline std::vector<Eintrag> eintraege(const std::string &roh) {
  if (!home_aktiv())
    ansicht = HAUSHALT;
  if (ansicht == HOME)
    return home_eintraege();
  if (ansicht == GEFRIERER)
    return gefrierer_eintraege();
  return aufgaben_eintraege(roh);
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
      // Menge hat sich geändert: weniger Knöpfe
      if (modus == GEF_MENU)
        auswahl = std::min(auswahl, std::max(0, (int) liste[i].optionen.size() - 1));
      return;
    }
  }
  cursor = std::min(cursor, n - 1);
  cursor_id = liste[cursor].id;
  if (modus == BESTAETIGEN || modus == GEF_MENU || saug_modus())
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
    case GEF_MENU: {
      int k = cursor >= 0 && cursor < n ? liste[cursor].optionen.size() : 1;
      auswahl = std::max(0, std::min(k - 1, auswahl + richtung));
      return;
    }
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
  if (modus == GEF_MENU) {
    if (auswahl < (int) e.optionen.size()) {
      gef_senden = true;
      gef_artikel = e.id;
      gef_menge = e.optionen[auswahl].first;
    }
    modus = LISTE;
    return;
  }
  // Homescreen: Kachel öffnen, Pfeil auf den ersten Eintrag nach "Zurück"
  if (ansicht == HOME) {
    ansicht = cursor == 0 ? HAUSHALT : GEFRIERER;
    modus = LISTE;
    oben = 0;
    auto neu = eintraege(roh);
    cursor = std::min(1, (int) neu.size() - 1);
    cursor_id = neu[cursor].id;
    return;
  }
  if (e.zurueck) {
    cursor = ansicht == GEFRIERER ? 1 : 0;
    ansicht = HOME;
    modus = LISTE;
    oben = 0;
    cursor_id = home_eintraege()[cursor].id;
    return;
  }
  if (ansicht == GEFRIERER) {
    if (e.neu) {
      if (!home_aktiv())
        modus = QR;
    } else if (!e.optionen.empty()) {
      modus = GEF_MENU;
      auswahl = 0;
    }
    return;
  }
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
    // Mit Homescreen steht der QR-Code schon rechts, sobald die Zeile gewählt ist
    if (!home_aktiv())
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
inline bool auswahl_offen() { return modus == BESTAETIGEN || modus == GEF_MENU || saug_modus(); }

inline void auswahl_abbrechen() {
  if (auswahl_offen())
    modus = LISTE;
}

inline void ruhe() {
  ansicht = home_aktiv() ? HOME : HAUSHALT;
  modus = LISTE;
  cursor = -1;
  cursor_id.clear();
  oben = 0;
}

}  // namespace flur
