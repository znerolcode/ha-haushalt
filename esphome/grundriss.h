// Schematischer Grundriss für die Zimmerwahl am Flur-Display.
// Koordinaten aus grundriss-dashboard/wohnung.svg (Einheiten des SVG, ca. 79 = 1 m),
// zwischen Küche und Wohnzimmer eine Lücke ergänzt wie bei den Wänden.
// Für eine andere Wohnung: Zimmer, Segment-IDs (Roborock-Raum-IDs) und Rechtecke hier anpassen.
#pragma once

namespace flur {

struct Rechteck {
  int x, y, b, h;
};

struct Zimmer {
  int id;            // Raum-ID im Staubsauger (app_segment_clean)
  const char *name;
  int anzahl;        // Rechtecke, aus denen das Zimmer besteht
  Rechteck teile[2];
};

// Reihenfolge = Reihenfolge beim Drehen (im Uhrzeigersinn durch die Wohnung)
static const Zimmer ZIMMER_LISTE[] = {
    {21, "Schlafzimmer", 1, {{68, 130, 248, 366}}},
    {23, "Büro", 1, {{326, 130, 342, 214}}},
    {16, "Entrée", 2, {{326, 355, 342, 141}, {326, 496, 79, 59}}},
    {17, "WC", 1, {{588, 506, 80, 134}}},
    {18, "Bad", 1, {{418, 506, 160, 194}}},
    {22, "Réduit", 1, {{418, 712, 160, 96}}},
    {19, "Wohnzimmer", 2, {{68, 648, 248, 512}, {316, 565, 89, 595}}},
    {20, "Küche", 1, {{68, 506, 238, 132}}},
};
static const int ANZAHL_ZIMMER = sizeof(ZIMMER_LISTE) / sizeof(ZIMMER_LISTE[0]);

// Ausschnitt des SVG, der gezeichnet wird
static const int PLAN_X = 68, PLAN_Y = 130, PLAN_B = 600, PLAN_H = 1030;

}  // namespace flur
