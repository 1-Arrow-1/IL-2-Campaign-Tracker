# IL-2 Campaign Progress Tracker

Ein umfassendes Tracking-Tool für IL-2 Sturmovik Great Battles Einzelspieler-**WW2-Kampagnen**. Überwacht automatisch deinen Kampagnenfortschritt, berechnet Beförderungen und Auszeichnungen basierend auf historischen Kriterien, erstellt detaillierte Missionsnachbesprechungen und generiert PDF-Berichte über die Karriere deines Piloten.

![Version](https://img.shields.io/badge/version-2.1-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-IL--2%20Battle%20of%20Stalingrad-orange)
![Languages](https://img.shields.io/badge/Sprachen-7-green)

---

## 📋 Inhaltsverzeichnis

- [Funktionen](#funktionen)
- [Unterstützte Nationen](#unterstützte-nationen)
- [Unterstützte Sprachen](#unterstützte-sprachen)
- [Installation](#installation)
- [Ersteinrichtung](#ersteinrichtung)
- [Einstellungsmanager](#einstellungsmanager)
- [WW1-Erkennung & Ausschluss](#ww1-erkennung--ausschluss)
- [Funktionsweise](#funktionsweise)
- [Beförderungs- & Auszeichnungssystem](#beförderungs---auszeichnungssystem)
- [Missionsnachbesprechungen](#missionsnachbesprechungen)
- [Missionsbereinigung](#missionsbereinigung)
- [Backup- & Wiederherstellungssystem](#backup---wiederherstellungssystem)
- [Kampagnen-Dienstakte](#kampagnen-dienstakte)
- [Dateireferenz](#dateireferenz)
- [Fehlerbehebung](#fehlerbehebung)
- [FAQ](#faq)

---

## ✨ Funktionen <a id="funktionen"></a>

| Funktion | Beschreibung |
| --- | --- |
| **Automatische Überwachung** | Überwacht deine Kampagnen-Speicherdatei und aktualisiert in Echtzeit |
| **Beförderungen** | Berechnet Rangbeförderungen basierend auf dem kumulierten Punktestand |
| **Auszeichnungen & Orden** | Verleiht Medaillen basierend auf Abschüssen, geflogenen Missionen und anderen Kriterien |
| **Echtzeit-Popups** | Zeigt Beförderungs- und Auszeichnungsbenachrichtigungen während des Spielens |
| **Missionsnachbesprechungen** | Parst Missionslogdateien und erstellt detaillierte Flugberichte |
| **PDF-Berichte** | Erstellt druckbare Karriereübersichten mit Kampfstatistiken |
| **Mehrsprachige Unterstützung** | Volle Unterstützung für 7 Sprachen: Englisch, Deutsch, Französisch, Spanisch, Polnisch, Russisch und Chinesisch |
| **Einstellungsmanager** | Benutzerfreundliche GUI zur Konfiguration aller Tracker-Einstellungen ohne Bearbeitung von Konfigurationsdateien |
| **Missionsbereinigung** | Entfernt unvollständige Missionen, die nicht ordnungsgemäß beendet wurden |
| **Backup-System** | Erstellt Backups beim Entfernen unvollständiger Missionen über das Bereinigungstool |
| **Wiederherstellungsfunktion** | Einfache GUI zur Wiederherstellung vorheriger Kampagnenzustände |
| **Multi-Kampagnen-Unterstützung** | Verfolgt mehrere Kampagnen gleichzeitig |
| **WW1-Erkennung & Ausschluss** | Erkennt Flying Circus (WW1) Kampagnen und überspringt sie standardmäßig |

---

## 🌍 Unterstützte Nationen <a id="unterstützte-nationen"></a>

Der Tracker enthält historisch korrekte Ränge und Auszeichnungen für:

| Nation | Ränge | Auszeichnungen |
| ------ | ----- | -------------- |
| 🇩🇪 **Deutschland** | Unteroffizier → Generalleutnant | Eisernes Kreuz, Ritterkreuz, etc. |
| 🇷🇺 **Sowjetunion** | Sergeant → Generalleutnant | Orden des Roten Banners, Held der Sowjetunion, etc. |
| 🇺🇸 **USA** | First Sergeant → Major General | Distinguished Flying Cross, Medal of Honor, etc. |
| 🇬🇧 **Großbritannien** | Sergeant → Air Vice Marshal | Distinguished Flying Cross, Victoria Cross, etc. |

> **Hinweis 1:** Sowjetische Ränge wechseln automatisch zwischen frühen (vor 1943) und späten (nach 6. Januar 1943) Abzeichen basierend auf den Missionsdaten.  
> **Hinweis 2:** Die gezeigten deutschen Auszeichnungen basieren auf den offiziellen Neuausgaben von 1957. Wenn du ihr Aussehen anpassen möchtest, kannst du die Bilder in `CampaignRanksAwards\Germany` ersetzen.

⚠️ Wichtig: Behalte die originalen Dateinamen beim Ersetzen von Bildern bei — zum Beispiel müssen `iron_cross_2nd.dds` und `iron_cross_2nd_big.dds` nach dem Ersetzen exakt die gleichen Namen haben.

---

## 🌐 Unterstützte Sprachen <a id="unterstützte-sprachen"></a>

Der Tracker unterstützt vollständige Lokalisierung in 7 Sprachen. Alle UI-Elemente, Missionsnachbesprechungen, PDF-Berichte, In-Game-Ereignisse und die Kampagnen-Dienstakte werden automatisch basierend auf der gewählten Sprache übersetzt.

| Sprache | Anzeigename | Code | Popups | In-Game-Ereignisse | PDF-Berichte | Dienstakte | Einstellungsmanager |
| ------- | ----------- | ---- | ------ | ------------------ | ------------ | ---------- | ------------------- |
| 🇬🇧 **Englisch** | English | en | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇩🇪 **Deutsch** | Deutsch | de | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇫🇷 **Französisch** | Français | fr | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇪🇸 **Spanisch** | Español | es | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇵🇱 **Polnisch** | Polski | pl | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇷🇺 **Russisch** | Русский | ru | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇨🇳 **Chinesisch (Vereinfacht)** | 简体中文 | zh | ✅ | ✅ | ✅ | ✅ | ✅ |

### Was wird übersetzt

Wenn du eine Sprache auswählst, werden folgende Inhalte in dieser Sprache angezeigt:

- **Popup-Benachrichtigungen** - Beförderungs- und Auszeichnungsankündigungen
- **In-Game-Ereignisse** - Der Ereignis-Abschnitt, der in die Kampagnen-`info.locale=*.txt`-Dateien geschrieben wird
- **Missionsnachbesprechungen** - Flugprotokolle, Abschussberichte, Statusmeldungen
- **PDF-Berichte** - Vollständige Karriereberichte inklusive aller Statistiken
- **Kampagnen-Dienstakte** - Die webbasierte Dienstakten-Oberfläche
- **Einstellungsmanager** - Alle UI-Beschriftungen, Schaltflächen und Meldungen

### Sprache ändern

Du kannst die Sprache über den **Einstellungsmanager** ändern (siehe Abschnitt [Einstellungsmanager](#einstellungsmanager)):

1. Öffne `IL2_Settings_Manager.exe`
2. Wähle deine bevorzugte Sprache aus dem Dropdown (Sprachen werden in ihren nativen Namen angezeigt)
3. Klicke auf "Übernehmen" oder "OK"
4. Der Tracker regeneriert automatisch alle Nachbesprechungen und PDF-Berichte in der neuen Sprache

> **Hinweis:** Beim Sprachwechsel werden alle bestehenden Kampagnennachbesprechungen und PDF-Berichte automatisch in der ausgewählten Sprache neu generiert. Dies kann je nach Anzahl deiner Kampagnen einen Moment dauern.

### IL-2 Sprachdatei-Zuordnung

Der Tracker ordnet IL-2s Sprachcodes den Standard-Locale-Codes zu:

| IL-2 Code | Tracker Code | Sprache |
| --------- | ------------ | ------- |
| eng | en | Englisch |
| ger | de | Deutsch |
| fra | fr | Französisch |
| spa | es | Spanisch |
| pol | pl | Polnisch |
| rus | ru | Russisch |
| chs | zh | Chinesisch (Vereinfacht) |

Beim Schreiben von Ereignissen in Kampagnendateien aktualisiert der Tracker **alle** vorhandenen `info.locale=*.txt`-Dateien einer Kampagne (z.B. `info.locale=eng.txt`, `info.locale=ger.txt`, etc.), jeweils in der entsprechenden Sprache.

---

## 📥 Installation <a id="installation"></a>

### Schritt 1: Herunterladen und Installieren

1. **Lade** die neueste Version herunter (`IL2_CampaignTracker_Setup_v2.2_ML.exe.zip`)

2. **Entpacke** die `zip`-Datei

3. **Führe** die entpackte `IL2_CampaignTracker_Setup_v2.2_ML.exe` aus

4. **Folge** den Installationsanweisungen im Setup-Assistenten

Der Setup-Assistent führt dich durch die Auswahl des Installationsverzeichnisses und die Konfiguration grundlegender Optionen.

### Schritt 2: Standard-Kampagnen extrahieren (Optional aber empfohlen)

⚠️ **WICHTIG:** Der Tracker kann **nur** Kampagnen überwachen, die sich in `<Pfad zu IL-2 BoS>\data\campaigns` befinden. Standard-IL-2-Kampagnen werden nicht direkt in diesem Ordner gespeichert; stattdessen werden sie intern aus `campaigns.gtp` ausgeführt. Daher müssen diese Kampagnen extrahiert werden, bevor sie verfolgt werden können.

🚨 **VORSICHT:** Wenn du Missionen einer offiziellen Standard-Kampagne modifiziert hast, gehe beim Kopieren extrahierter Dateien aus `campaigns.gtp` in den Ordner `<Pfad zu IL-2 BoS>\data\campaigns` mit äußerster Vorsicht vor. Vorhandene Dateien werden **überschrieben**, und alle benutzerdefinierten Missionsänderungen werden durch die Originalversionen ersetzt.

**So extrahierst du Standard-Kampagnen:**

1. **Lade** unGTP-IL2 herunter von: <https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip>
2. **Entpacke & Verschiebe** die `unGTP-IL2.exe` nach `<Pfad zu IL-2 BoS>\data`
3. **Ziehe** `Campaigns.gtp` auf `unGTP-IL2.exe` (ignoriere die Fehlermeldung im CMD-Fenster am Ende - alles wurde extrahiert)
4. **Navigiere** zu `<Pfad zu IL-2 BoS>\data\(null)\campaigns`
5. **Kopiere** alle Unterordner nach `<Pfad zu IL-2 BoS>\data\campaigns`

> **Hinweis:** Das Extrahieren der offiziellen Standard-Kampagnen dient NUR dazu, sie für den Campaign Tracker nutzbar zu machen. Bitte modifiziere die offiziellen Kampagnen nicht.

### Schritt 3: Tracker starten

**Starte** `IL2_Campaign_Tracker.exe` aus deinem Tracker-Installationsverzeichnis.

ℹ️ **HINWEIS**: Standardmäßig wird der Tracker automatisch beendet, wenn IL-2 BoS geschlossen wird. Um den Tracker weiter zu nutzen, musst du ihn entweder manuell neu starten oder eine Windows-Aufgabenplanung konfigurieren, um ihn automatisch beim Windows-Start zu starten.

Eine allgemeine Einrichtungsanleitung findest du hier:
<https://forum.il2-series.com/topic/772-expanded-career-rank-mod/#findComment-4176>

### Installierte Dateien

Der Installer platziert die folgenden Dateien in deinem gewählten Installationsverzeichnis:

```text
IL2_Campaign_Tracker/
├── IL2_Campaign_Tracker.exe              # Hauptprogramm
├── IL2_Settings_Manager.exe              # Einstellungsmanager GUI
├── mlg2txt.exe                           # Hilfsprogramm zum Dekodieren von Missionsberichten
├── Campaign_Service_Record.exe           # Dienstakte-Webanwendung
├── campaign_progress_config.yaml         # Ränge- & Auszeichnungskonfiguration
├── stock_campaigns.yaml                  # Kampagnen-zu-Land-Zuordnung
├── object_categories.yaml                # Missionsnachbesprechungsdaten
├── locales/ (Ordner)                     # Sprachdateien (7 Sprachen)
├── _internal/ (Ordner)                   # Dienstakte-Ressourcen
├── unins000.exe                          # Deinstallationsprogramm
├── unins000.dat                          # Deinstallationsdaten
├── cleanup_tracker_content.exe           # Hilfsprogramm für Deinstallation
└── (weitere Dateien werden beim ersten Start automatisch erstellt)
```

### Deinstallation

1. **Führe** `unins000.exe` aus dem Tracker-Installationspfad aus
   
   🚨 **FÜHRE NICHT** `cleanup_tracker_content.exe` direkt aus - es ist ein Hilfsprogramm für das Deinstallationsprogramm.

2. **Folge** den Deinstallationsanweisungen im Assistenten

ℹ️ **HINWEIS:** Alle In-Game-Nachbesprechungen und -Ereignisse werden entfernt, und die originalen `info.locale=[sprache].txt`-Dateien werden in ihren Originalzustand zurückversetzt.

Wenn du während der Deinstallation wählst, die Konfigurationsdateien zu behalten und später den Tracker in denselben Ordner neu installierst, werden diese Dateien nicht überschrieben. Deine zuvor gespeicherte Konfiguration bleibt erhalten.

---

## 🚀 Ersteinrichtung <a id="ersteinrichtung"></a>

Wenn du den Tracker zum ersten Mal startest, führt dich ein Einrichtungsassistent durch die Konfiguration:

### Schritt 1: Spielverzeichnis auswählen

Ein Ordnerbrowser öffnet sich. Navigiere zu deinem IL-2-Installationsordner:

```bash
Beispiel: C:\Program Files (x86)\Steam\steamapps\common\IL-2 Sturmovik Battle of Stalingrad
```

> **Wichtig:** Wähle den Hauptspielordner, NICHT den Unterordner `data\Campaigns`.

### Schritt 2: Ländervalidierung

Der Tracker scannt alle installierten Kampagnen und versucht, das richtige Land für jede zu erkennen. Eine Validierungs-GUI erscheint, in der du:

- ✅ Automatisch erkannte Länder bestätigen kannst
- ✏️ Falsch identifizierte Kampagnen korrigieren kannst
- 🚫 WW1 (Flying Circus) Kampagnen ausschließen kannst

Dies ist wichtig, da Beförderungen und Auszeichnungen nationsspezifisch sind.  
ℹ️ Nach dem Validieren/Korrigieren der Länder werden diese Kampagnen in die `stock_campaigns.yaml` geschrieben. Wenn du versehentlich das falsche Land zugewiesen hast, kannst du das durch manuelles Bearbeiten des Landes in der `stock_campaigns.yaml` korrigieren.

### WW1 (Flying Circus) Erkennung

Wenn der Tracker Flying Circus Kampagnen erkennt, kannst - oder solltest du besser - sie als **WW1 (ignorieren)** in diesem Bildschirm markieren, damit sie vom Tracking ausgeschlossen werden.

### Schritt 3: Bereit zum Tracken

Nach der Einrichtung:

1. Dekodiert der Tracker deine aktuelle Kampagnen-Speicherdatei
2. Generiert initiale Ereignisse (bestehende Beförderungen/Auszeichnungen)
3. Beginnt mit der Überwachung auf Änderungen

---

## ⚙️ Einstellungsmanager <a id="einstellungsmanager"></a>

Der **Einstellungsmanager** (`IL2_Settings_Manager.exe`) bietet eine benutzerfreundliche GUI zur Konfiguration aller Tracker-Einstellungen, ohne manuell Konfigurationsdateien bearbeiten zu müssen.

### Einstellungsmanager öffnen

1. Finde `IL2_Settings_Manager.exe` in deinem Tracker-Installationsordner
2. Doppelklicke, um den Einstellungsmanager zu öffnen
3. Nimm deine Änderungen vor und klicke auf "Übernehmen" oder "OK"

### Verfügbare Einstellungen

#### Reiter "Allgemein"

| Einstellung | Beschreibung |
| ----------- | ------------ |
| **Sprache** | Wähle die Anzeigesprache (Englisch, Deutsch, Französisch, Spanisch, Polnisch, Russisch, Chinesisch) |
| **Popups aktivieren** | Schalte Beförderungs-/Auszeichnungs-Popup-Benachrichtigungen ein/aus |
| **Rang-Skalierung aktiviert** | Aktiviere/Deaktiviere die Rang-Skalierung basierend auf Kampagnenlänge |

#### Reiter "Rang-Skalierung"

Konfiguriere, wie Ranganforderungen basierend auf der Kampagnenlänge skaliert werden:

| Bereich | Standard-Faktor | Zweck |
| ------- | --------------- | ----- |
| 1-10 Missionen | 1,00x | Kurze Kampagnen (Stock-Kampagnen) |
| 11-20 Missionen | 1,15x | Mittlere-kurze Kampagnen |
| 21-30 Missionen | 1,30x | Mittlere Kampagnen |
| 31-40 Missionen | 1,50x | Mittlere-lange Kampagnen |
| 41-50 Missionen | 1,75x | Lange Kampagnen |
| 51-70 Missionen | 2,00x | Sehr lange Kampagnen |
| 71+ Missionen | 5,50x | Epische Kampagnen |

Du kannst Skalierungsbereiche nach Bedarf hinzufügen, bearbeiten oder entfernen.

#### Reiter "Rangwerte"

Konfiguriere die Beförderungs-Punkteschwellen für jede Nation:

- Ansicht und Bearbeitung der für jeden Rang erforderlichen Punktzahl
- Unterstützt alle vier Nationen (Deutschland, Sowjetunion, USA, Großbritannien)

#### Reiter "Kampagnen"

Konfiguriere kampagnenspezifische Einstellungen:

| Einstellung | Beschreibung | Bereich |
| ----------- | ------------ | ------- |
| **Start-Rang-Offset** | Starte Kampagnen mit höheren Rängen | 0-7 |

> **Tipp:** Verwende höhere Offsets (bis zu 7) für Kampagnen, in denen der Spieler beim Missionsstart bereits Staffelführer ist. Dies ist besonders nützlich für britische Kampagnen aufgrund ihrer vielen niedrigeren Ränge.

### Automatische Neugenerierung

Wenn du bestimmte Einstellungen änderst, regeneriert der Tracker automatisch alle betroffenen Daten:

| Geänderte Einstellung | Automatische Neugenerierung |
| --------------------- | --------------------------- |
| Sprache | ✅ Alle Nachbesprechungen und PDF-Berichte werden in der neuen Sprache neu generiert |
| Rang-Skalierung | ✅ Alle Ereignisse werden basierend auf neuen Skalierungsfaktoren neu berechnet |
| Rangwerte | ✅ Alle Beförderungen werden basierend auf neuen Schwellenwerten neu berechnet |
| Start-Rang-Offset | Manuelle Neugenerierung (Tracker neu starten) |

---

## 🪖 WW1-Erkennung & Ausschluss <a id="ww1-erkennung--ausschluss"></a>

Flying Circus (WW1) Kampagnen werden standardmäßig erkannt und ausgeschlossen, da der Tracker nur WWII-Ränge, -Auszeichnungen und -Nachbesprechungslogik enthält.

**Erkennungssignale umfassen:**

- Missionsdaten im Bereich 1914–1918
- WW1-Flugzeugschlüsselwörter in Kampagnendaten
- "Flying Circus"/WW1-Schlüsselwörter in Kampagnenbeschreibungen

**Wie der Ausschluss funktioniert:**

- Ausgeschlossene Kampagnen werden während der Dekodierung und Ereignisgenerierung übersprungen.
- Der Ausschlussgrund wird in `campaign_mission_dates.json` gespeichert, damit der Tracker sie konsistent ignoriert.
- Du kannst Ausschlüsse überprüfen oder ändern, indem du die Einrichtung erneut durchführst (lösche `campaign_mission_dates.json` und den entsprechenden Eintrag in `stock_campaigns.yaml`) und das Kontrollkästchen **WW1 (ignorieren)** in der Ländervalidierungs-GUI verwendest.

---

## ⚙️ Funktionsweise <a id="funktionsweise"></a>

### Überwachungsschleife

```text
┌─────────────────────────────────────────────────────────┐
│                    TRACKER LÄUFT                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   1. Überwache campaignsstates.txt auf Änderungen       │
│                          ↓                              │
│   2. Erkenne Dateiänderung (Mission abgeschlossen)      │
│                          ↓                              │
│   3. Dekodiere Kampagnen-Speicherdatei                  │
│                          ↓                              │
│   4. Berechne neue Beförderungen/Auszeichnungen         │
│                          ↓                              │
│   5. Zeige Popups für neue Ereignisse                   │
│                          ↓                              │
│   6. Parse Missionslog für Nachbesprechung              │
│                          ↓                              │
│   7. Aktualisiere Kampagnen-Info-Datei                  │
│                          ↓                              │
│   8. Generiere PDF-Bericht                              │
│                          ↓                              │
│   9. Zurück zur Überwachung                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Echtzeit-Popups

Wenn du eine Beförderung oder Auszeichnung erhältst, erscheint eine Popup-Benachrichtigung auf dem Bildschirm:

- 🎖️ Zeigt das Rangabzeichen oder Medaillenbild
- 📅 Zeigt das Datum, an dem es verdient wurde
- ⏱️ Schließt sich automatisch nach 5 Sekunden

> **Hinweis:** Popups erscheinen nur während IL-2 läuft, um Unterbrechungen während anderer Aktivitäten zu vermeiden. Wenn du keine Popups möchtest, gehe zu `campaign_progress_config.yaml` in deinem Tracker-Installationsverzeichnis und setze ```enable_popups: false```

---

## 🎖️ Beförderungs- & Auszeichnungssystem <a id="beförderungs---auszeichnungssystem"></a>

### Wie Beförderungen funktionieren

Beförderungen basieren auf der **kumulierten Punktzahl** über alle abgeschlossenen Missionen (der Punktewert kommt aus der campaignsstates.txt und wird nach internen IL-2 GB-Regeln berechnet):

```text
Gesamtpunktzahl pro Kampagne = ∑ Missionspunktzahlen
Beförderungspunktzahl = Basispunktzahl × Rang-Skalierungsfaktor
```

**Rang-Skalierungsfaktor** passt die Anforderungen basierend auf der Kampagnenlänge an (kann in `campaign_progress_config.yaml` bearbeitet werden):

"1-10":    1.00   # Kurze Kampagnen (Stock-Kampagnen)  
"11-20":   1.15   # Mittlere-kurze Kampagnen  
"21-30":   1.30   # Mittlere Kampagnen  
"31-40":   1.50   # Mittlere-lange Kampagnen  
"41-50":   1.75   # Lange Kampagnen  
"51-70":   2.00   # Sehr lange Kampagnen  
"71+":     5.50   # Epische Kampagnen (70+ Missionen)

Dies verhindert schnelle Beförderungen in langen Kampagnen bei gleichzeitiger fairer Progression in kurzen.

ℹ️ **Beispiel:** In einer 24-Missions-Kampagne beträgt der Skalierungsfaktor 1,3, sodass ein Rang, der 1000 Punkte benötigt, tatsächlich 1300 Punkte (1000 x 1,30) erfordern würde.  
Wenn deine kumulierte Punktzahl den Beförderungsschwellenwert von 1300 Punkten erreicht oder überschreitet, wirst du zum nächsten Rang befördert.

🚨 **WICHTIG**: Wenn du die `campaign_progress_config.yaml` modifizierst, achte darauf, die korrekte Einrückung beizubehalten (YAML-Format). Falsche Einrückung kann zu Parsing-Fehlern führen.

### Wie Auszeichnungen funktionieren

Auszeichnungen werden basierend auf verschiedenen Kriterien verliehen, die in `campaign_progress_config.yaml` definiert sind und vom Karrieremodus in IL-2 BoS abgeleitet sind.
Alle Bedingungen für Auszeichnungen sind `ODER`-Bedingungen:

| Kriterientyp | Beispiel |
| ------------ | -------- |
| **Kumulative Abschüsse** | 8 Luftkampfpunkte → Eisernes Kreuz 1. Klasse |
| **Einzelne Mission** | 7 Abschüsse in einem Einsatz → Medal of Honor |
| **Abgeschlossene Missionen** | 15 Missionen → Orden des Roten Sterns |
| **Im Einsatz verwundet** | Pilotenschaden > 20% → Verwundetenabzeichen |
| **Zufällig + Schwellenwert** | Hohe Abschüsse + Glücksfaktor → Seltene Orden |

Einige Auszeichnungen haben **Voraussetzungen** (z.B. muss Eisernes Kreuz 2. Klasse vor 1. Klasse haben) und **gegenseitige Ausschließlichkeit** (z.B. kann nicht beide Varianten des Verwundetenstreifens in derselben Mission erhalten).

### Start-Rang-Offset

Kampagnen können mit höheren Rängen beginnen (wenn du möchtest). Dies ist nützlich für Kampagnen, in denen dein Pilot beim Missionsstart bereits ein erfahrener Offizier ist. Der Offset kann konfiguriert werden:

**Option 1: Über Einstellungsmanager (Empfohlen)**
1. Öffne `IL2_Settings_Manager.exe`
2. Gehe zum Reiter "Kampagnen"
3. Doppelklicke auf eine Kampagne, um ihren Offset zu bearbeiten
4. Wähle einen Wert von 0-7

**Option 2: Manuelle Bearbeitung in `campaign_mission_dates.json`:**

```json
"kerch": {
  "country": "Germany",
  "starting_rank_offset": 2, --> ändere diese Zahl (0-7, Standard = 0)
  "missions": { ...  }
}
```

> **Hinweis:** Höhere Offset-Werte (bis zu 7) sind besonders nützlich für britische Kampagnen, die viele niedrigere Ränge haben, oder für Kampagnen, in denen der Spieler als Staffelführer beginnt.

ℹ️ **Hinweis:** Du kannst die Beförderungs- und Auszeichnungskriterien nach deinen Wünschen anpassen. Es wird jedoch dringend empfohlen, eine Sicherungskopie der originalen `campaign_progress_config.yaml`-Datei zu erstellen, bevor du Änderungen vornimmst.

---

## 📊 Missionsnachbesprechungen <a id="missionsnachbesprechungen"></a>

### Datenquelle

Nachbesprechungsdaten werden aus IL-2s **Missionslogdateien** (`.mlg`-Dateien) extrahiert:

```text
Speicherort: [IL-2 Verzeichnis]\data\FlightLogs\[mission].mlg
```

Diese Binärdateien enthalten detaillierte Aufzeichnungen über alles, was während der Mission passiert ist.
Diese Binärdateien werden von `mlg2txt.exe` in eine *.txt-Datei "übersetzt" und dann weiter verarbeitet.

### Was wird erfasst

| Kategorie | Details |
| --------- | ------- |
| **Flugzeit** | Dauer von Start bis Landung |
| **Abschüsse** | Luft-, Boden- und Seeziele mit Zeitstempeln |
| **Erlittener Schaden** | Erhaltene Treffer, von wem, Schadensprozent |
| **Pilotenstatus** | "Schaden" % |
| **Status** | Gelandet, Gelandet (verwundet), Harte Landung, Harte Landung (verwundet), Fallschirmabsprung, Fallschirmabsprung (verwundet), KIA/MIA |

### Nachbesprechungsausgabe

Jede Mission generiert detaillierte Ausgaben in zwei Formaten:

1. **In-Game (Flugprotokoll)** - Chronologische Liste der Ereignisse, die in alle Kampagnen-`info.locale=*.txt`-Dateien geschrieben werden (jeweils in der entsprechenden Sprache)
2. **PDF-Bericht** - Detaillierte Abschussaufschlüsselung nach Kategorie passend zum In-Game-Ergebnisbildschirm (in deiner ausgewählten Sprache)

> **Hinweis:** Der Tracker schreibt lokalisierten Inhalt in jede Sprachdatei, die in deinem Kampagnenordner existiert. Wenn deine Kampagne zum Beispiel sowohl `info.locale=eng.txt` als auch `info.locale=ger.txt` hat, enthält die englische Datei englische Nachbesprechungen und die deutsche Datei deutsche Nachbesprechungen.

---

## 🧹 Missionsbereinigung <a id="missionsbereinigung"></a>

### Was ist takeoffStatus?

IL-2 verfolgt den Missionsabschluss mit einem `takeoffStatus`-Flag:

| Wert | Bedeutung |
| ---- | --------- |
| `takeoffStatus=1` | Mission gestartet aber nicht ordnungsgemäß abgeschlossen |
| `takeoffStatus=2` | Mission erfolgreich abgeschlossen |

### Wann die Bereinigungs-GUI erscheint

Die Missionsbereinigung-GUI erscheint beim Tracker-Start, wenn Missionen mit `takeoffStatus=1` erkannt werden.

**Häufige Ursachen für `takeoffStatus=1`:**

- ❌ Missionsziel nicht abgeschlossen
- 🪂 Pilot ist abgesprungen
- 💀 Pilot im Einsatz gefallen (KIA)
- ❓ Pilot vermisst (MIA)
- 💥 IL-2 während der Mission abgestürzt
- 🚫 Erzwungenes Beenden (Alt+F4, Task-Manager)
- 🔌 Stromausfall / Systemabsturz

> **Hinweis:** Nicht alle `takeoffStatus=1`-Missionen sind im traditionellen Sinne "gescheitert". Abspringen oder KIA sein kann beabsichtigtes Gameplay sein. Das Bereinigungstool gibt dir die **Wahl**, ob du diese Missionen entfernen möchtest.

### Bereinigungs-GUI

```text
┌─────────────────────────────────────────────────────────┐
│        ⚠️ Unvollständige Missionen erkannt              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Die folgenden Missionen wurden nicht ordnungsgemäß     │
│  abgeschlossen:                                          │
│                                                          │
│  ☐ kerch - Mission 05 (14. November 1943)               │
│  ☐ blazingsteppe - Mission 12 (9. September 1942)       │
│                                                          │
│  Wähle Missionen zum Entfernen aus deinem                │
│  Kampagnen-Speicher.                                     │
│                                                          │
│  [🗑️ Ausgewählte entfernen]  [▶ Alle behalten]          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Was passiert, wenn du eine Mission entfernst

1. **Backup erstellt** - Aktueller Zustand wird vor Änderungen gespeichert
2. **Mission entfernt** - Eintrag wird aus `campaignsstates.txt` gelöscht
3. **Popup-Status gelöscht** - Zugehörige Ereignisse werden aus `campaign_popups_seen.json` entfernt
4. **Bereit zum Wiederholen** - Du kannst die Mission erneut fliegen

### Was passiert, wenn du eine Mission behältst

Wenn du "Alle behalten" klickst oder keine Mission auswählst:

- Kein Backup wird erstellt
- Keine Änderungen werden vorgenommen
- Die Mission bleibt in deiner Speicherdatei
- Bereinigungs-GUI erscheint beim nächsten Mal wieder (für verbleibende unvollständige Missionen)

---

## 💾 Backup- & Wiederherstellungssystem <a id="backup---wiederherstellungssystem"></a>

### Wann Backups erstellt werden

Backups werden **nur** erstellt, wenn du unvollständige Missionen über das Missionsbereinigungstool entfernst. Sie werden **nicht** automatisch nach jeder Mission erstellt.

Dies stellt sicher, dass du deine Kampagne auf den Zustand **vor** dem Entfernen von Missionen wiederherstellen kannst.

### Wiederherstellungs-GUI

Wenn der Tracker startet und Backups verfügbar sind, kann eine Wiederherstellungs-GUI erscheinen:

```text
┌─────────────────────────────────────────────────────────┐
│           🔄 Kampagnen-Backup wiederherstellen          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Wähle ein Backup zur Wiederherstellung:                │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Datum & Zeit          │ Status           │ Popups  │ │
│  ├──────────────────────┼──────────────────┼─────────┤ │
│  │ 2024-01-15 14:30:22  │ Derzeit aktiv    │ ✓ Ja    │ │
│  │ 2024-01-15 12:15:03  │                  │ ✓ Ja    │ │
│  │ 2024-01-14 20:45:11  │                  │ ✗ Nein  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  [🔄 Ausgewähltes wiederherstellen] [▶ Weiter] [✕ Ende] │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Wann die GUI erscheint:**

- Mehrere Backups existieren, ODER
- Ein Backup existiert, das **nicht** der aktuelle Zustand ist

**Wann die GUI NICHT erscheint:**

- Keine Backups existieren
- Nur ein Backup existiert und es ist bereits der aktive Zustand

### Wiederherstellungsprozess

1. Wähle ein Backup aus der Liste
2. Klicke auf "Ausgewähltes Backup wiederherstellen"
3. Bestätige die Aktion
4. Der Tracker führt automatisch folgendes aus:
   - Erstellt eine Kopie der Backup-Datei (Original-Backup bleibt erhalten)
   - Löscht aktuelle `campaignsstates.txt`
   - Benennt Backup-Kopie in `campaignsstates.txt` um
   - Regeneriert alle Ereignisse
   - Stellt passenden Popup-Status wieder her (verhindert doppelte Popups)

### Anwendungsbeispiel

```text
1. Du fliegst Mission 05 in der "kerch"-Kampagne
2. IL-2 stürzt mitten in der Mission ab → takeoffStatus=1
3. Nächster Tracker-Start: Bereinigungs-GUI erscheint
4. Du wählst Mission 05 und klickst auf "Entfernen"
5. Tracker erstellt Backup VOR dem Entfernen der Mission
6. Mission 05 wird aus der Speicherdatei entfernt
7. Du kannst Mission 05 jetzt erneut fliegen

Später, wenn nötig:
8. Starte Tracker → Wiederherstellungs-GUI erscheint
9. Wähle das Backup von vor dem Entfernen
10. Kampagne wird auf den Zustand MIT Mission 05 (unvollständig) wiederhergestellt
```

---

## 📋 Kampagnen-Dienstakte <a id="kampagnen-dienstakte"></a>

Die **Kampagnen-Dienstakte** ist eine webbasierte Anwendung, die eine elegante, schreibgeschützte Ansicht der Karriere deines Piloten über alle laufenden und abgeschlossenen Kampagnen bietet. Sie präsentiert deine Diensthistorie in einem sauberen, professionellen Format — ideal zum Überprüfen von Erfolgen oder zum Teilen deiner Kampfbilanz.

⚠️ **WICHTIG**: Die Kampagnen-Dienstakte ist kein eigenständiges System. Sie funktioniert ausschließlich in Verbindung mit dem Tracker und seinen zugehörigen Dateien, die die erforderlichen Kampagnendaten liefern.

### Funktionen

- **Kampagnenübersicht**: Durchsuche alle Kampagnen, die du geflogen hast, mit abgeschlossenen Missionen, verdienten Beförderungen und erhaltenen Auszeichnungen
- **Detaillierte Dienstakte**: Klicke auf eine Kampagne, um zu sehen:
  - Vollständige Missionshistorie mit Nachbesprechungen
  - Chronologische Zeitleiste von Beförderungen und Auszeichnungen
  - Karrierestatistiken (Luftabschüsse, Bodenabschüsse, Missionserfolgsraten)
  - Flugzeugnutzung und Leistungsaufschlüsselung
- **Pilotenprofil**: Anzeige und Anpassung von Pilotennamen, Foto und persönlichen Informationen pro Kampagne
- **Responsives Design**: Saubere, moderne Oberfläche, die auf jeder Bildschirmgröße funktioniert
- **Automatisch generiert**: Liest automatisch Daten aus deinen Campaign Tracker-Dateien - keine manuelle Eingabe erforderlich

### Verwendung

1. Finde `Campaign_Service_Record.exe` in deinem Campaign Tracker-Installationsverzeichnis (siehe Installationsabschnitt oben)
2. Doppelklicke auf `Campaign_Service_Record.exe`, um die Anwendung zu starten
3. Dein Standard-Webbrowser öffnet sich automatisch und zeigt deine Dienstakte an
4. Durchsuche deine Kampagnen und klicke auf eine Kampagne, um detaillierte Statistiken zu sehen
5. Der Server wird nach 60 Sekunden Inaktivität automatisch beendet

**Hinweis**: Die Kampagnen-Dienstakte benötigt Daten vom Campaign Tracker. Du musst den Campaign Tracker mindestens einmal ausführen und mindestens eine Mission abschließen, bevor Kampagnen in der Dienstakte erscheinen.

### Oberflächen-Übersicht

#### Startseite

- **Linkes Panel**: Piloteninformationen (Foto, Name, Dienstübersicht)
- **Rechtes Panel**: Liste aller Kampagnen mit abgeschlossenen Missionen
  - Zeigt Missionsanzahl, verdiente Beförderungen und erhaltene Auszeichnungen pro Kampagne
  - Klicke auf eine Kampagne, um die detaillierte Dienstakte zu sehen

#### Kampagnen-Detailseite

- **Linke Spalte**: Piloteninformationen (anpassbares Foto & persönliche Daten), Chronologische Zeitleiste von Beförderungen und Auszeichnungen
- **Mittlere Spalte**: Karrierestatistiken inklusive:
  - Gesamt-Luft- und Bodenabschüsse
  - Missionsergebnisse
  - Flugzeugnutzungsaufschlüsselung
  - und mehr
- **Rechte Spalte**: Missionsnachbesprechungen mit detaillierten Kampfergebnissen
- **Zurück-Button**: Zurück zur Kampagnenübersicht

### Piloteninformationen anpassen

Klicke auf das Pilotenfoto oder die Namensfelder zum Anpassen:

- **Pilotenfoto**: Klicke, um ein neues Foto hochzuladen (unterstützt gängige Bildformate)
- **Persönliche Informationen**: Bearbeite Name, Vorname, Geburtstag, Geburtsort und Geburtsland
- Alle Änderungen werden automatisch gespeichert und bleiben über Sitzungen hinweg erhalten

### Fehlerbehebung

#### Problem: "Lade Kampagnen..." erscheint ewig

**Ursache**: Keine Kampagnendaten verfügbar oder JSON-Dateien sind leer  
**Lösung**:

- Stelle sicher, dass du den Campaign Tracker mindestens einmal ausgeführt hast
- Schließe mindestens eine Mission in einer Kampagne ab
- Prüfe, ob deine Campaign Tracker-Installation diese Dateien enthält:
  - `campaign_completion_state.json`
  - `campaign_events.json`
  - `campaigns_decoded.json`
  - `campaign_mission_dates.json`

#### Problem: Kampagnen-Dienstakte startet nicht

**Ursache**: Port 5000 wird bereits von einer anderen Anwendung verwendet  
**Lösung**:

- Schließe alle anderen Webserver oder Anwendungen, die Port 5000 verwenden
- Wenn das Problem weiterhin besteht, starte deinen Computer neu, um den Port freizugeben

#### Problem: Browser zeigt "Verbindung nicht möglich" oder "Seite nicht gefunden"

**Ursache**: Der Anwendungsserver konnte nicht starten  
**Lösung**:

- Prüfe, ob sowohl `Campaign_Service_Record.exe` als auch der Ordner `_internal` im Installationsverzeichnis vorhanden sind
- Stelle sicher, dass dein Antivirus die Anwendung nicht blockiert
- Versuche, `Campaign_Service_Record.exe` als Administrator auszuführen

#### Problem: Klick auf eine Kampagne zeigt "Kampagnendetails konnten nicht geladen werden"

**Ursache**: Fehlende oder beschädigte Kampagnendaten  
**Lösung**:

- Führe den Campaign Tracker erneut aus, um JSON-Dateien neu zu generieren
- Stelle sicher, dass die Kampagne mindestens eine abgeschlossene Mission hat
- Prüfe, ob Kampagnennamen in den JSON-Dateien konsistent sind

#### Problem: Pilotenfoto kann nicht hochgeladen werden

**Ursache**: Dateiformat wird nicht unterstützt oder Datei ist zu groß  
**Lösung**:

- Verwende gängige Bildformate (JPG, PNG, BMP)
- Stelle sicher, dass die Bilddatei kleiner als 5MB ist
- Versuche, das Bild ins PNG-Format zu konvertieren

#### Problem: Anwendung schließt sich sofort nach dem Start

**Ursache**: Das 60-Sekunden-Leerlauf-Timeout ist möglicherweise zu kurz, oder der Browser hat sich nicht geöffnet  
**Lösung**:

- Doppelklicke erneut auf `Campaign_Service_Record.exe`
- Öffne manuell deinen Browser und navigiere zu `http://127.0.0.1:5000`
- Halte den Browser-Tab aktiv, um automatisches Beenden zu verhindern

#### Problem: Deutsche Auszeichnungen und Bilder zeigen kein Hakenkreuz

**Ursache:**  
Der Campaign Tracker unterstützt, befürwortet oder fördert keine nationalsozialistische Ideologie oder Symbole in irgendeiner Form.  
Um die rechtlichen Vorschriften in mehreren Ländern einzuhalten und Gemeinschaftsstandards zu respektieren, wurden Hakenkreuze und andere verwandte Symbole aus den Standard-Bildern entfernt, die mit dieser Software geliefert werden.

**Lösung:**  
Benutzer, die historisch korrekte Bilder benötigen, können die Bilder lokal ersetzen:

- Ersetze Auszeichnungsbilder in  
  `<Pfad zu IL-2 BoS>\data\swf\CampaignRanksAwards\Germany`
 
- Ersetze die deutschen Hintergrund- und Flaggenbilder in  
  `<Tracker-Installationsordner>\_internal\static\images\background_Germany.png`  
  `<Tracker-Installationsordner>\_internal\static\images\german_flag.png`

⚠️ Die originalen Dateinamen und Dateitypen **müssen** nach dem Ersetzen des Bildinhalts beibehalten werden.

### Technische Informationen

- **Server-Adresse**: `http://127.0.0.1:5000` (nur lokaler Rechner)
- **Automatisches Beenden**: Server stoppt automatisch nach 60 Sekunden Inaktivität
- **Datenspeicherort**: Liest JSON-Dateien aus demselben Verzeichnis wie die ausführbare Datei
- **Browser-Kompatibilität**: Funktioniert mit allen modernen Browsern (Chrome, Firefox, Edge)
- **Netzwerk**: Erfordert keine Internetverbindung; läuft vollständig auf deinem lokalen Rechner

---

## 📁 Dateireferenz <a id="dateireferenz"></a>

### Konfigurationsdateien

| Datei | Zweck | Benutzer bearbeitbar |
| ----- | ----- | -------------------- |
| `campaign_progress_config.yaml` | Ränge, Auszeichnungen, Kriterien und Einstellungen | ✅ Ja (oder Einstellungsmanager verwenden) |
| `campaign_mission_dates.json` | Kampagnen-Metadaten, Missionsdaten, Länder | ⚠️ Vorsichtig (Einstellungsmanager für Offsets verwenden) |
| `settings.json` | Benutzereinstellungen (Sprache, etc.) | ✅ Über Einstellungsmanager |
| `locales/*.json` | Sprachübersetzungsdateien | ⚠️ Nur für fortgeschrittene Benutzer |

### Konfigurationsdetails

#### campaign_progress_config.yaml

Dies ist die Hauptkonfigurationsdatei, die enthält:

```yaml
# Rangdefinitionen pro Nation
ranks: 
  Germany:
    - name: Unteroffizier
      score: 0
      image: unteroffizier.png
    - name: Feldwebel
      score: 80
      image: feldwebel.png
    # ... weitere Ränge

# Auszeichnungsdefinitionen pro Nation
awards: 
  Germany:
  - name: Iron Cross 2nd Class
    image: iron_cross_2nd.dds
    max_awards: 1
    conditions:
    - air_combat_score: 2
    - missions_completed: 16
  - name: Iron Cross 1st Class
    image: iron_cross_1st.dds
    requires: Iron Cross 2nd Class
    max_awards: 1
    conditions:
    - air_combat_score: 8
    - missions_completed: 64
    # ... weitere Auszeichnungen

# Allgemeine Einstellungen
settings:
  enable_popups: true
```

#### campaign_mission_dates.json

Wird beim ersten Start automatisch generiert und enthält:

```json
{
  "kerch": {
    "campaign_name": "kerch",
    "country": "Germany",
    "is_stock": true,
    "starting_rank_offset": 0,
    "mission_count": 12,
    "missions": {
      "01": {
        "raw_date": "4 November, 1943",
        "normalized_date": "1943-11-04",
        "mission_file": "01.eng"
      },
      "02": {
        "raw_date": "6 November, 1943",
        "normalized_date": "1943-11-06",
        "mission_file": "02.eng"
      }, ...
}
```

### Datendateien (automatisch generiert)

| Datei | Zweck | Speicherort |
| ----- | ----- | ----------- |
| `campaigns_decoded.json` | Dekodierte Kampagnen-Speicherdaten | Tracker-Ordner |
| `campaign_popups_seen.json` | Verfolgt angezeigte Popups pro Kampagne | Tracker-Ordner |
| `campaign_events.json` | Generierte Ereignisse (Beförderungen/Auszeichnungen) | Tracker-Ordner |
| `campaign_completion_state.json` | Verfolgt Missionsabschluss zwischen Durchläufen | Tracker-Ordner |
| `settings.json` | Benutzereinstellungen (Sprache, Popups, etc.) | Tracker-Ordner |

### Backup-Dateien

| Datei | Zweck | Speicherort |
| ----- | ----- | ----------- |
| `campaignsstates_[zeitstempel].backup` | Kampagnen-Speicher-Backup | IL-2 Usersave-Ordner |
| `popups_[zeitstempel].backup` | Popup-Status-Backup | IL-2 Usersave-Ordner |
| `campaignsstates_hash_index.json` | Backup-Index mit Hashes | IL-2 Usersave-Ordner |

### Ausgabedateien

| Datei | Zweck | Speicherort |
| ----- | ----- | ----------- |
| `[Kampagne]_Report.pdf` | Karriere-PDF-Bericht | `reports/` Unterordner |

---

## 🔧 Fehlerbehebung <a id="fehlerbehebung"></a>

### Tracker startet nicht

| Problem | Lösung |
| ------- | ------ |
| Fehlende `campaign_progress_config.yaml` | Stelle sicher, dass die Datei im gleichen Ordner wie die EXE ist |
| Antivirus blockiert | Füge eine Ausnahme für den Tracker-Ordner hinzu |
| Fehlendes Visual C++ Runtime | Installiere [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

### Keine Kampagnen erkannt

| Problem | Lösung |
| ------- | ------ |
| Falscher Ordner ausgewählt | Führe Setup erneut aus (lösche `campaign_mission_dates.json`) |
| Noch keine Missionen geflogen | Starte eine Kampagne in IL-2, fliege mindestens eine Mission |
| Berechtigungsprobleme | Führe Tracker als Administrator aus |

### Popups erscheinen nicht

| Problem | Lösung |
| ------- | ------ |
| IL-2 läuft nicht | Popups erscheinen nur während IL-2 aktiv ist |
| Bereits gesehen | Prüfe `campaign_popups_seen.json` |
| Popups deaktiviert | Prüfe `enable_popups: true` in der Konfiguration |

### PDF-Generierung schlägt fehl

| Problem | Lösung |
| ------- | ------ |
| Fehlende Abhängigkeiten | Stelle sicher, dass alle erforderlichen DLLs vorhanden sind |
| PDF gesperrt | Schließe das PDF, wenn es in einem Viewer geöffnet ist |
| Pfad zu lang | Verschiebe Tracker zu kürzerem Pfad |

### Ereignisse erscheinen nicht im Spiel

| Problem | Lösung |
| ------- | ------ |
| IL-2 speichert Beschreibung | Starte IL-2 neu, um aktualisierte Kampagnenbeschreibung zu sehen |
| Ereignisse in falsche Datei geschrieben | Prüfe Kampagnen-Länderzuweisung |

---

## ❓ FAQ <a id="faq"></a>

### Warum wird meine benutzerdefinierte Kampagne nicht erkannt / werden Missionen nicht erkannt?

**A:** Der Tracker parst Missionsdateien, um Daten und Metadaten zu extrahieren. Um sicherzustellen, dass deine benutzerdefinierte Kampagne korrekt erkannt wird, befolge diese goldenen Regeln:

⚠️ *Wichtig: Englische Locale-Dateien für das Lesen erforderlich*

Der Tracker liest nur englische Locale-Dateien (`.eng`-Briefings und `info.locale=eng.txt`), um Missionsdaten und Kampagneninformationen zu extrahieren. IL-2 speichert die Sprachpräferenz des Benutzers intern, und wir haben keine Möglichkeit zu erkennen, welche Sprache du im Spiel verwendest. Daher:

- Jede Mission muss eine entsprechende `.eng`-Briefing-Datei haben (z.B. `01.eng` für `01.Mission`)
- Dein Kampagnenordner muss eine `info.locale=eng.txt`-Datei für die Kampagnenbeschreibung enthalten

Auch wenn du in einer anderen Sprache spielst, müssen diese englischen Dateien vorhanden sein, damit der Tracker funktioniert. Der Tracker liest keine `.ger`, `.rus`, `.fra` oder andere Sprachdateien zur Datenextraktion.

ℹ️ *Mehrsprachige Ausgabe*

Beim Zurückschreiben von Ereignissen und Nachbesprechungen in deine Kampagne aktualisiert der Tracker automatisch **alle** vorhandenen `info.locale=*.txt`-Dateien. Jede Datei wird in der entsprechenden Sprache geschrieben:

- `info.locale=eng.txt` → Englischer Inhalt
- `info.locale=ger.txt` → Deutscher Inhalt (Deutsch)
- `info.locale=fra.txt` → Französischer Inhalt (Français)
- `info.locale=spa.txt` → Spanischer Inhalt (Español)
- `info.locale=pol.txt` → Polnischer Inhalt (Polski)
- `info.locale=rus.txt` → Russischer Inhalt (Русский)
- `info.locale=chs.txt` → Chinesischer Inhalt (简体中文)

Siehe [Unterstützte Sprachen](#unterstützte-sprachen) für weitere Details.

**Missionsdatei-Benennung:**

- Verwende numerische Präfixe für die Missionsreihenfolge: `01.Mission`, `02.Mission`, `03.Mission` oder `1.Mission`, `2.Mission`, etc.
- Datumsbasierte Benennung funktioniert auch: `1943-07-04.Mission`, `1943-07-04a.Mission`
- Unterstützte Erweiterungen: `.Mission`, `.mission`, `.msnbin`

Missionsdatum-Erkennung (in `.eng`-Briefing-Dateien):
Der Tracker sucht nach Datumsinformationen in dieser Prioritätsreihenfolge:

1. `Date:`-Feld im Briefing (z.B. `Date: 4 November, 1943`)
2. `Time:`-Feld für Missionsstartzeit (z.B. `Time: 09:45`)
3. Dateiname, wenn er ein Datum enthält (z.B. `1943-07-04.Mission`)

**Unterstützte Datumsformate:**

- `4 November, 1943` oder `November 4, 1943`
- `4 November 1943` (ohne Komma)
- `04.11.1943` oder `11.04.1943` (TT.MM.JJJJ oder MM.TT.JJJJ)
- `1943-07-04` (ISO-Format im Dateinamen)

**Kampagnenordner-Struktur:**

```
Pfad zu IL-2 BoS\data\Campaigns\DeinKampagnenName\
    ├── info.locale=eng.txt    (erforderlich zum Lesen - Kampagnenbeschreibung)
    ├── info.locale=ger.txt    (optional - Tracker schreibt deutschen Inhalt hierher)
    ├── info.locale=fra.txt    (optional - Tracker schreibt französischen Inhalt hierher)
    ├── info.locale=rus.txt    (optional - Tracker schreibt russischen Inhalt hierher)
    ├── 01.Mission             (Missionsdatei)
    ├── 01.eng                 (erforderlich - Englisches Briefing mit Datum/Zeit)
    ├── 02.Mission
    ├── 02.eng                 (erforderlich - Englisches Briefing mit Datum/Zeit)
    └── ...
```

**Ländererkennung:**
Der Tracker erkennt automatisch dein Land/deine Fraktion aus:

1. Flugzeugnamen in Missionsdateien (z.B. bf109 → Deutschland, spitfire → Großbritannien)
2. Einheitsnamen mit Länder-Kennungen
3. Du kannst dies manuell im Ländervalidierungs-GUI beim ersten Start setzen/korrigieren oder später manuell in der `stock_campaigns.yaml` anpassen

**Häufige Probleme:**

- Fehlende `.eng`-Briefing-Datei → Daten können nicht extrahiert werden (Mission wird trotzdem als "Mission 1", "Mission 2", etc. verfolgt, aber ohne Datumsinformationen)
- Fehlende `info.locale=eng.txt` → Kampagnenbeschreibung nicht verfügbar, Tracker kann Kampagneninfo nicht lesen
- Nicht-standardmäßiges Datumsformat im Briefing → verwende eines der oben genannten unterstützten Formate
- Sonderzeichen im Kampagnenordnernamen → vermeide Umlaute oder Sondersymbole
- WW1-Kampagnen (Flying Circus) → standardmäßig ausgeschlossen (siehe Abschnitt WW1-Erkennung & Ausschluss)

### F: Kann ich mehrere Instanzen des Trackers ausführen?

**A:** Nein. Nur eine Instanz sollte deine Kampagnen gleichzeitig überwachen.

### F: Modifiziert der Tracker meine IL-2-Installation?

**A:** Der Tracker modifiziert nur:

- Kampagnen-`info.locale=*.txt`-Dateien (fügt Ereignis-Abschnitt hinzu)
- Erstellt Backup-Dateien im Usersave-Ordner

Er modifiziert **keine** Spiel-Executables oder Kerndateien.

### F: Funktioniert das mit Mods?

**A:** Ja, solange der Mod die Standard-Kampagnenstruktur verwendet. Benutzerdefinierte Kampagnen werden während der Ersteinrichtung automatisch erkannt.

### F: Kann ich die Konfiguration manuell bearbeiten?

**A:** Ja, aber wir empfehlen die Verwendung des **Einstellungsmanagers** (`IL2_Settings_Manager.exe`) für die meisten Änderungen. Er bietet eine benutzerfreundliche Oberfläche und handhabt die Neugenerierung automatisch, wenn nötig.

Für fortgeschrittene Anpassungen kann `campaign_progress_config.yaml` manuell bearbeitet werden, um:

- Beförderungs-Punkteschwellen anzupassen
- Auszeichnungskriterien zu modifizieren
- Benutzerdefinierte Auszeichnungen hinzuzufügen
- Rang-Skalierungsfaktoren zu ändern

> ⚠️ Erstelle immer ein Backup, bevor du Konfigurationsdateien manuell bearbeitest.

### F: Wie setze ich alles zurück?

**A:** Lösche diese Dateien und starte den Tracker neu:

- `campaign_mission_dates.json`
- `campaign_popups_seen.json`
- `campaigns_decoded.json`
- `campaign_events.json`

### F: Wird Multiplayer unterstützt?

**A:** Der Tracker ist für Einzelspieler-Karrierekampagnen konzipiert. Multiplayer-Missionen generieren nicht die gleiche Speicherdatenstruktur.

### F: Warum muss ich IL-2 neu starten, um neue Ereignisse zu sehen?

**A:** IL-2 lädt die Kampagnenbeschreibung (`info.locale=*.txt`) beim Spielstart und speichert sie im Speicher. Änderungen des Trackers werden in die Datei geschrieben, erscheinen aber erst im Spiel, wenn du IL-2 neu startest. Du siehst jedoch **Popups sofort**, wenn du Beförderungen oder Auszeichnungen erhältst.

### F: Was passiert, wenn ich eine Backup-Datei manuell lösche?

**A:** Der Backup-Index (`campaignsstates_hash_index.json`) wird sie weiterhin referenzieren, aber die Wiederherstellungs-GUI wird alle Backups überspringen, bei denen die eigentliche Backup-Datei fehlt.

### F: Kann ich den Tracker mit Flying Circus (WWI) verwenden?

**A:** Flying Circus Kampagnen werden standardmäßig erkannt und ausgeschlossen. Der Tracker ist für WWII-Kampagnen konzipiert und enthält keine WWI-Ränge oder -Auszeichnungen. Du kannst Ausschlüsse während des Ländervalidierungsschritts kontrollieren (WW1 "ignorieren"-Kontrollkästchen), aber WW1-Kampagnen werden keine historisch korrekten Ränge oder Auszeichnungen haben.

### F: Kann ich den Tracker mit Pat Wilson's Campaign Generator (PWCG) verwenden?

**A:** Nein - dieser Tracker funktioniert NICHT mit PWCG, stört es aber auch NICHT

---

## 📜 Lizenz

Dieses Projekt wird ohne Gewähr für den persönlichen Gebrauch mit IL-2 Sturmovik Great Battles zur Verfügung gestellt.

---

## 🙏 Danksagungen

- **1C Game Studios / 777 Studios** - Für die Entwicklung von IL-2 Great Battles
- **Die IL-2 Community** - Für Inspiration und Feedback
- **Kraut1** - Für nützlichen Input und umfassende Tests

---

## Guten Flug! ✈️🎖️
