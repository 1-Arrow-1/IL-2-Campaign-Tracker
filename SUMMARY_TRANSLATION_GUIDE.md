# Campaign Summary i18n Keys - Übersicht

## Deutsche Übersetzungen erforderlich!

Die folgenden Keys wurden zu `de.json` hinzugefügt und benötigen deutsche Übersetzungen.
Englische Werte sind in `en.json` bereits vorhanden.

### Section Headers (web.section.*)

```json
"missions_flown": "",              // EN: "Missions Flown"
"aircraft_flown": "",              // EN: "Aircraft Flown"
"career_progression": "",          // EN: "Career Progression"
"campaign_timeline": ""            // EN: "Campaign Timeline"
```

### Statistics Labels (web.stat.*)

```json
"overall_score": "",               // EN: "Overall Score"
"missions_completed": "",          // EN: "Missions Completed"
"starting_rank": "",               // EN: "Starting Rank"
"final_rank": "",                  // EN: "Final Rank"
"promotions": "",                  // EN: "Promotions"
"awards": "",                      // EN: "Awards"
"first_mission": "",               // EN: "First Mission"
"last_mission": "",                // EN: "Last Mission"
"duration": "",                    // EN: "Duration"
"duration_days": "",               // EN: "{days} days" (z.B. "42 days")
"no_status_data": ""               // EN: "No status data available"
```

### Combat Results - Categories (web.combat.category.*)

```json
"aircraft": "",                    // EN: "Aircraft"
"vehicles": "",                    // EN: "Vehicles"
"railroad": "",                    // EN: "Railroad"
"armaments": "",                   // EN: "Armaments"
"buildings": "",                   // EN: "Buildings"
"marine": ""                       // EN: "Marine"
```

### Combat Results - Subcategories (web.combat.subcategory.*)

```json
"light": "",                       // EN: "Light"
"medium": "",                      // EN: "Medium"
"heavy": "",                       // EN: "Heavy"
"parked": "",                      // EN: "Parked"
"balloons": "",                    // EN: "Balloons"
"transport": "",                   // EN: "Transport"
"armored_light": "",               // EN: "Armored (Light)"
"armored_medium": "",              // EN: "Armored (Medium)"
"armored_heavy": "",               // EN: "Armored (Heavy)"
"locomotives": "",                 // EN: "Locomotives"
"railroad_cars": "",               // EN: "Railroad Cars"
"station": "",                     // EN: "Station"
"facilities": "",                  // EN: "Facilities"
"machine_guns": "",                // EN: "Machine Guns"
"cannons": "",                     // EN: "Cannons"
"aaa_guns": "",                    // EN: "AAA Guns"
"rocket_launchers": "",            // EN: "Rocket Launchers"
"searchlights": "",                // EN: "Searchlights"
"radars": "",                      // EN: "Radars"
"residential": "",                 // EN: "Residential Buildings"
"bridges": "",                     // EN: "Bridges"
"cargo": "",                       // EN: "Cargo"
"submarines": "",                  // EN: "Submarines"
"destroyers": ""                   // EN: "Destroyers"
```

## Anleitung zum Übersetzen

1. Öffne `campaign_service_record/static/locales/de.json`
2. Suche nach den leeren Strings (`""`)
3. Ersetze sie mit den deutschen Übersetzungen
4. Speichere die Datei

## Beispiel:

**Vorher:**
```json
"missions_flown": "",
"aircraft_flown": "",
```

**Nachher:**
```json
"missions_flown": "Geflogene Missionen",
"aircraft_flown": "Geflogene Flugzeuge",
```

## Wo die Keys verwendet werden

Die Keys werden in `campaign_service_record/static/js/detail.js` verwendet:
- **Section Headers**: `renderSummary()` - Überschriften der Summary-Bereiche
- **Statistics**: `renderMissionsStats()`, `renderCareerProgression()`, `renderTimeline()` - Statistik-Labels
- **Combat Results**: `renderCombatResults()` - Kampfergebnis-Kategorien und Unterkategorien

## Test nach Übersetzung

Nach dem Eintragen der deutschen Übersetzungen:

```bash
set CAMPAIGN_TRACKER_LOCALE=de
python campaign_service_record/app.py
```

Öffne http://localhost:5000 und überprüfe die Campaign Summary (mittlerer Bereich der Detail-Seite):
- ✅ Section-Überschriften (COMBAT RESULTS, MISSIONS FLOWN, etc.)
- ✅ Statistik-Labels (Overall Score, Total Kills, etc.)
- ✅ Kampfergebnis-Kategorien (Aircraft, Vehicles, etc.)
- ✅ Unterkategorien (Light, Medium, Heavy, etc.)
