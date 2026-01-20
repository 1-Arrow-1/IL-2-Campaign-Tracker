# Ränge und Auszeichnungen - Übersetzungs-Anleitung

## Übersicht

Es wurden **44 Ränge** (mit Länder-Unterscheidung) und **84 Auszeichnungen** zu den Locale-Dateien hinzugefügt.

- **Englische Werte**: Bereits in `locales/en.json` vorhanden
- **Deutsche Werte**: Leer in `locales/de.json` - müssen von dir übersetzt werden

## Wichtig: Länder-Unterscheidung bei Rängen! 🌍

Einige Ränge haben **identische Namen** über verschiedene Länder hinweg (z.B. "Sergeant", "Major", "Captain"). Diese werden mit **Länder-Präfixen** unterschieden:

- `ger_` = Deutschland (Luftwaffe)
- `raf_` = Großbritannien (RAF)
- `usaaf_` = USA (USAAF)
- `vvs_` = Sowjetunion (VVS)

**Beispiel:**
```json
"raf_sergeant": "Sergeant",      // RAF Sergeant
"vvs_sergeant": "Sergeant",      // Soviet Sergeant
"usaaf_major": "Major",          // US Major
"ger_major": "Major",            // German Major
"vvs_major": "Major"             // Soviet Major
```

## Struktur

Alle Ränge und Auszeichnungen befinden sich in der neuen `progression` Section:

```json
{
  "progression": {
    "ranks": {
      "unteroffizier": "",
      "ger_major": "",
      "raf_sergeant": "",
      "vvs_sergeant": "",
      ...
    },
    "awards": {
      "pilots_badge": "",
      "iron_cross_2nd_class": "",
      ...
    }
  }
}
```

## Ränge (44 total, inkl. Länder-Duplikate)

### Deutschland (11 Ränge)
**Keine Präfixe (eindeutig):**
- `unteroffizier` → "Unteroffizier"
- `feldwebel` → "Feldwebel"
- `oberfeldwebel` → "Oberfeldwebel"
- `leutnant` → "Leutnant"
- `oberleutnant` → "Oberleutnant"
- `hauptmann` → "Hauptmann"
- `oberstleutnant` → "Oberstleutnant"
- `oberst` → "Oberst"
- `generalmajor` → "Generalmajor"
- `generalleutnant` → "Generalleutnant"

**Mit Präfix (Duplikat):**
- `ger_major` → "Major" ⚠️ (existiert auch als usaaf_major, vvs_major)

### Großbritannien (11 Ränge)
**Mit Präfix (Duplikat):**
- `raf_sergeant` → "Sergeant" ⚠️ (existiert auch als vvs_sergeant)

**Keine Präfixe (eindeutig):**
- `flight_sergeant` → "Flight Sergeant"
- `warrant_officer` → "Warrant Officer"
- `pilot_officer` → "Pilot Officer"
- `flying_officer` → "Flying Officer"
- `flight_lieutenant` → "Flight Lieutenant"
- `squadron_leader` → "Squadron Leader"
- `wing_commander` → "Wing Commander"
- `group_captain` → "Group Captain"
- `air_commodore` → "Air Commodore"
- `air_vice_marshal` → "Air Vice Marshal"

### USA (11 Ränge)
**Keine Präfixe (eindeutig):**
- `first_sergeant` → "First Sergeant"
- `flight_officer` → "Flight Officer"
- `chief_warrant_officer` → "Chief Warrant Officer"
- `2nd_lieutenant` → "2nd Lieutenant"
- `1st_lieutenant` → "1st Lieutenant"
- `lt_colonel` → "Lt. Colonel"
- `brigadier_general` → "Brigadier General"

**Mit Präfix (Duplikat):**
- `usaaf_captain` → "Captain" ⚠️ (existiert auch als vvs_captain)
- `usaaf_major` → "Major" ⚠️ (existiert auch als ger_major, vvs_major)
- `usaaf_colonel` → "Colonel" ⚠️ (existiert auch als vvs_colonel)
- `usaaf_major_general` → "Major General" ⚠️ (existiert auch als vvs_major_general)

### Sowjetunion (11 Ränge)
**Mit Präfix (Duplikat):**
- `vvs_sergeant` → "Sergeant" ⚠️ (existiert auch als raf_sergeant)
- `vvs_captain` → "Captain" ⚠️ (existiert auch als usaaf_captain)
- `vvs_major` → "Major" ⚠️ (existiert auch als ger_major, usaaf_major)
- `vvs_colonel` → "Colonel" ⚠️ (existiert auch als usaaf_colonel)
- `vvs_major_general` → "Major General" ⚠️ (existiert auch als usaaf_major_general)

**Keine Präfixe (eindeutig):**
- `senior_sergeant` → "Senior Sergeant"
- `junior_lieutenant` → "Junior Lieutenant"
- `lieutenant` → "Lieutenant"
- `senior_lieutenant` → "Senior Lieutenant"
- `sub_colonel` → "Sub-Colonel"
- `lieutenant_general` → "Lieutenant General"

## Duplikate im Überblick

Diese 5 Rangnamen existieren in mehreren Ländern:

| Rang | Länder | Keys |
|------|--------|------|
| **Sergeant** | RAF, VVS | `raf_sergeant`, `vvs_sergeant` |
| **Captain** | USAAF, VVS | `usaaf_captain`, `vvs_captain` |
| **Major** | Luftwaffe, USAAF, VVS | `ger_major`, `usaaf_major`, `vvs_major` |
| **Colonel** | USAAF, VVS | `usaaf_colonel`, `vvs_colonel` |
| **Major General** | USAAF, VVS | `usaaf_major_general`, `vvs_major_general` |

## Auszeichnungen (84 total)

### Deutschland (18 Auszeichnungen)
Beispiele:
- pilots_badge → "Pilot's Badge"
- iron_cross_2nd_class → "Iron Cross 2nd Class"
- iron_cross_1st_class → "Iron Cross 1st Class"
- honor_goblet → "Honor Goblet"
- german_cross_in_gold → "German Cross in Gold"
- knights_cross_of_the_iron_cross → "Knight's Cross of the Iron Cross"
- knights_cross_of_the_iron_cross_with_oak_leaves → "Knight's Cross of the Iron Cross with Oak Leaves"
- knights_cross_of_the_iron_cross_with_oak_leaves_and_swords → "Knight's Cross of the Iron Cross with Oak Leaves and Swords"
- knights_cross_of_the_iron_cross_with_oak_leaves_swords_and_diamonds → "Knight's Cross of the Iron Cross with Oak Leaves, Swords and Diamonds"
- knights_cross_of_the_iron_cross_with_golden_oak_leaves_swords_and_diamonds → "Knight's Cross of the Iron Cross with Golden Oak Leaves, Swords and Diamonds"
- front_flying_clasp_for_fighters_in_bronze → "Front Flying Clasp for Fighters in Bronze"
- front_flying_clasp_for_fighters_in_silver → "Front Flying Clasp for Fighters in Silver"
- front_flying_clasp_for_fighters_in_gold → "Front Flying Clasp for Fighters in Gold"
- front_flying_clasp_for_fighters_in_gold_with_pendant → "Front Flying Clasp for Fighters in Gold with Pendant"
- wound_badge_in_black → "Wound Badge in Black"
- wound_badge_in_silver → "Wound Badge in Silver"
- wound_badge_in_gold → "Wound Badge in Gold"

### Großbritannien (16 Auszeichnungen)
Beispiele:
- raf_pilots_badge → "RAF Pilot's Badge"
- mentioned_in_despatches → "Mentioned in Despatches"
- distinguished_flying_medal → "Distinguished Flying Medal"
- bar_to_the_distinguished_flying_medal → "Bar to the Distinguished Flying Medal"
- second_bar_to_the_distinguished_flying_medal → "Second Bar to the Distinguished Flying Medal"
- distinguished_flying_cross → "Distinguished Flying Cross"
- bar_to_the_distinguished_flying_cross → "Bar to the Distinguished Flying Cross"
- second_bar_to_the_distinguished_flying_cross → "Second Bar to the Distinguished Flying Cross"
- distinguished_service_order → "Distinguished Service Order"
- bar_to_the_distinguished_service_order → "Bar to the Distinguished Service Order"
- second_bar_to_the_distinguished_service_order → "Second Bar to the Distinguished Service Order"
- victoria_cross → "Victoria Cross"
- bar_to_the_victoria_cross → "Bar to the Victoria Cross"
- wound_stripe → "Wound Stripe"
- second_wound_stripe → "Second Wound Stripe"
- third_wound_stripe → "Third Wound Stripe"

### USA (23 Auszeichnungen)
Beispiele:
- usaaf_pilots_badge → "USAAF Pilot's Badge"
- air_medal → "Air Medal"
- air_medal_plus_one_oak_leaf_cluster → "Air Medal + One Oak Leaf Cluster"
- air_medal_plus_two_oak_leaf_clusters → "Air Medal + Two Oak Leaf Clusters"
- air_medal_plus_three_oak_leaf_clusters → "Air Medal + Three Oak Leaf Clusters"
- distinguished_service_medal → "Distinguished Service Medal"
- legion_of_merit → "Legion of Merit"
- silver_star_medal → "Silver Star Medal"
- silver_star_plus_one_oak_leaf_cluster → "Silver Star + One Oak Leaf Cluster"
- distinguished_service_cross → "Distinguished Service Cross"
- dsc_plus_one_oak_leaf_cluster → "DSC + One Oak Leaf Cluster"
- dsc_plus_two_oak_leaf_clusters → "DSC + Two Oak Leaf Clusters"
- medal_of_honor → "Medal of Honor"
- medal_of_honor_plus_one_oak_leaf_cluster → "Medal of Honor + One Oak Leaf Cluster"
- purple_heart → "Purple Heart"
- purple_heart_plus_one_oak_leaf_cluster → "Purple Heart + One Oak Leaf Cluster"
- purple_heart_plus_two_oak_leaf_clusters → "Purple Heart + Two Oak Leaf Clusters"

### Sowjetunion (27 Auszeichnungen)
Beispiele:
- aviation_badge → "Aviation Badge"
- medal_for_battle_merit → "Medal 'For Battle Merit'"
- medal_for_courage → "Medal for Courage"
- order_of_the_red_star → "Order of the Red Star"
- order_of_the_red_star_2nd_awarding → "Order of the Red Star (2nd awarding)"
- order_of_the_red_star_3rd_awarding → "Order of the Red Star (3rd awarding)"
- order_of_the_patriotic_war_2nd_class → "Order of the Patriotic War 2nd Class"
- order_of_the_patriotic_war_1st_class → "Order of the Patriotic War 1st Class"
- order_of_alexander_nevsky → "Order of Alexander Nevsky"
- order_of_suvorov_3rd_class → "Order of Suvorov 3rd Class"
- order_of_the_red_banner → "Order of the Red Banner"
- order_of_the_red_banner_2nd_awarding → "Order of the Red Banner (2nd awarding)"
- order_of_the_red_banner_3rd_awarding → "Order of the Red Banner (3rd awarding)"
- hero_of_the_soviet_union → "Hero of the Soviet Union"
- hero_of_the_soviet_union_2nd_awarding → "Hero of the Soviet Union (2nd awarding)"
- hero_of_the_soviet_union_3rd_awarding → "Hero of the Soviet Union (3rd awarding)"
- order_of_lenin → "Order of Lenin"
- order_of_lenin_2nd_awarding → "Order of Lenin (2nd awarding)"
- order_of_lenin_3rd_awarding → "Order of Lenin (3rd awarding)"
- 5_combat_sorties_bonus_1500_rubles → "5 Combat Sorties Bonus (1500 rubles)"
- 15_combat_sorties_bonus_2000_rubles → "15 Combat Sorties Bonus (2000 rubles)"
- 25_combat_sorties_bonus_3000_rubles → "25 Combat Sorties Bonus (3000 rubles)"
- 40_combat_sorties_bonus_5000_rubles → "40 Combat Sorties Bonus (5000 rubles)"
- red_wound_stripe → "Red Wound Stripe"
- yellow_wound_stripe → "Yellow Wound Stripe"

## Wie übersetzen?

1. Öffne `locales/de.json`
2. Gehe zur `progression` Section
3. Ersetze die leeren Strings (`""`) mit deutschen Übersetzungen
4. **Beachte die Länder-Präfixe** bei doppelten Rängen!
5. Für englische/amerikanische/russische Auszeichnungen kannst du:
   - Die originalen Namen beibehalten
   - Oder eine deutsche Beschreibung hinzufügen

## Beispiel:

**Vorher:**
```json
"progression": {
  "ranks": {
    "unteroffizier": "",
    "ger_major": "",
    "raf_sergeant": "",
    "vvs_sergeant": "",
    "usaaf_major": "",
    "vvs_major": ""
  },
  "awards": {
    "iron_cross_2nd_class": "",
    "knights_cross_of_the_iron_cross": ""
  }
}
```

**Nachher:**
```json
"progression": {
  "ranks": {
    "unteroffizier": "Unteroffizier",
    "ger_major": "Major",
    "raf_sergeant": "Sergeant",
    "vvs_sergeant": "Сержант",  // oder "Sergeant (VVS)"
    "usaaf_major": "Major",
    "vvs_major": "Майор"  // oder "Major (VVS)"
  },
  "awards": {
    "iron_cross_2nd_class": "Eisernes Kreuz 2. Klasse",
    "knights_cross_of_the_iron_cross": "Ritterkreuz des Eisernen Kreuzes"
  }
}
```

**Übersetzungs-Tipps für doppelte Ränge:**
- Du kannst die Originalnamen verwenden (z.B. alle "Major" → "Major")
- Oder Länder-Kennzeichnung hinzufügen (z.B. "Major (Luftwaffe)", "Major (USAAF)", "Major (VVS)")
- Oder die original-sprachlichen Namen verwenden (z.B. vvs_major → "Майор")

## Wo werden diese Keys verwendet?

- **Campaign Tracker Popups**: `popups_min.py` zeigt Beförderungen und Auszeichnungen an
- **Service Record Web UI**: `campaign_service_record` zeigt Career Progression und Awards
- **PDF Reports**: Wenn PDF-Generierung i18n nutzt

## Test nach Übersetzung

```bash
set CAMPAIGN_TRACKER_LOCALE=de
python popups_min.py
python campaign_service_record/app.py
```

Überprüfe:
- ✅ Popup-Fenster zeigen deutsche Ränge/Auszeichnungen
- ✅ Service Record zeigt deutsche Texte in Career Progression
- ✅ Awards-Liste verwendet deutsche Namen
