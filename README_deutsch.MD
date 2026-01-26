# IL-2 Fortschritt-Tracker für Kampagnen

Ein umfassendes Tracking-Tool für die Einzelspieler-Kampagnen **WW2** von IL-2 Sturmovik Great Battles.  Überwacht automatisch Ihren Kampagnenfortschritt, berechnet Beförderungen und Auszeichnungen auf der Grundlage historischer Kriterien, erstellt detaillierte Missionsberichte und erstellt PDF-Berichte über die Karriere Ihres Piloten.

![Version](https://img.shields.io/badge/version-2.1-blue)
![Plattform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Spiel](https://img.shields.io/badge/game-IL--2%20Battle%20of%20Stalingrad-orange)
![Sprachen](https://img.shields.io/badge/languages-7-green)

---

## 📋 Inhaltsverzeichnis

- [Funktionen](#features)
- [Unterstützte Nationen](#supported-nations)
- [Unterstützte Sprachen](#supported-languages)
- [Installation](#installation)
- [Erste Einrichtung](#first-run-setup)
- [Einstellungsmanager](#settings-manager)
- [Erkennung und Ausschluss von WW1](#ww1-detection--exclusion)
- [So funktioniert es](#so-funktioniert-es)
- [Beförderungs- und Auszeichnungssystem](#beförderungs-und-auszeichnungssystem)
- [Missionsbesprechungen](#missionsbesprechungen)
- [Missionsbereinigung](#missionsbereinigung)
- [Sicherungs- und Wiederherstellungssystem](#sicherungs-und-wiederherstellungssystem)
- [Kampagnen-Dienstakte](#camapign-service-record)
- [Dateiverweis](#file-reference)
- [Fehlerbehebung](#troubleshooting)
- [FAQ](#faq)

---

## ✨ Funktionen <a id="features"></a>

| Funktion | Beschreibung |
| --- | --- |
| **Automatische Überwachung** | Überwacht Ihre Kampagnen-Speicherdatei und aktualisiert sie in Echtzeit |
| **Beförderungen** | Berechnet Rangbeförderungen basierend auf der gesammelten Punktzahl |
| **Auszeichnungen & Ehrungen** | Verleiht Medaillen basierend auf Abschüssen, geflogenen Missionen und anderen Kriterien |
| **Echtzeit-Popups** | Zeigt während des Spiels Benachrichtigungen zu Beförderungen und Auszeichnungen an |
| **Missionsnachbesprechungen** | Analysiert Missionsprotokolle, um detaillierte Flugberichte zu erstellen |
| **PDF-Berichte** | Erstellt druckbare Karriereübersichten mit Kampfstatistiken |
| **Mehrsprachige Unterstützung** | Vollständige Unterstützung für 7 Sprachen: Englisch, Deutsch, Französisch, Spanisch, Polnisch, Russisch und vereinfachtes Chinesisch |
| **Einstellungsmanager** | Benutzerfreundliche GUI zum Konfigurieren aller Tracker-Einstellungen ohne Bearbeiten von Konfigurationsdateien |
| **Missionen bereinigen** | Entfernt unvollständige Missionen, die nicht ordnungsgemäß abgeschlossen wurden |
| **Backup-System** | Erstellt Backups beim Entfernen unvollständiger Missionen über das Bereinigungstool |
| **Wiederherstellungsfunktion** | Einfache GUI zum Wiederherstellen früherer Kampagnenzustände |
| **Unterstützung mehrerer Kampagnen** | Verfolgt mehrere Kampagnen gleichzeitig |
| **Erkennung und Ausschluss von WW1** | Erkennt Flying Circus (WW1)-Kampagnen und überspringt sie standardmäßig |

---

## 🌍 Unterstützte Nationen <a id="supported-nations"></a>

Der Tracker enthält historisch korrekte Ränge und Auszeichnungen für:

| Nation | Ränge | Auszeichnungen |
| ------ | ----- | ------ |
| 🇩🇪 **Deutschland** | Unteroffizier → Generalleutnant | Eisernes Kreuz, Ritterkreuz usw. |
| 🇷🇺 **Sowjetunion** | Sergeant → Generalleutnant | Orden des Roten Banners, Held der Sowjetunion usw. |
| 🇺🇸 **USA** | Oberfeldwebel → Generalmajor | Distinguished Flying Cross, Ehrenmedaille usw. |
| 🇬🇧 **Großbritannien** | Sergeant → Air Vice Marshal | Distinguished Flying Cross, Victoria-Kreuz usw. |

> **Hinweis 1:** Die sowjetischen Ränge wechseln automatisch zwischen frühen (vor 1943) und späten (nach dem 6. Januar 1943) Abzeichen, basierend auf den Missionsdaten.  
> **Hinweis 2:** Die gezeigten deutschen Auszeichnungen basieren auf den offiziellen Neuauflagen von 1957. Wenn Sie ihr Aussehen anpassen möchten, können Sie die Bilder im Ordner „CampaignRanksAwards\Germany“ ersetzen.

⚠️ Wichtig: Behalten Sie beim Ersetzen der Bilder die ursprünglichen Dateinamen bei – beispielsweise müssen
„iron_cross_2nd.dds“ und „iron_cross_2nd_big.dds“ nach dem Ersetzen genau dieselben Namen behalten.

---

## 🌐 Unterstützte Sprachen <a id="supported-languages"></a>

Der Tracker unterstützt die vollständige Lokalisierung in 7 Sprachen. Alle UI-Elemente, Missionsbesprechungen, PDF-Berichte und Ereignisse im Spiel werden automatisch entsprechend der von Ihnen ausgewählten Sprache übersetzt.  

| Sprache | Code | Besprechungen im Spiel | PDF-Berichte | Einstellungsmanager |
| -------- | ---- | ------------------- | ----------- | ---------------- |
| 🇬🇧 **Englisch** | en | ✅ | ✅ | ✅ |
| 🇩🇪 **Deutsch** | de | ✅ | ✅ | ✅ |
| 🇫🇷 **Französisch** | fr | ✅ | ✅ | ✅ |
| 🇪🇸 **Spanisch** | es | ✅ | ✅ | ✅ |
| 🇵🇱 **Polnisch** | pl | ✅ | ✅ | ✅ |
| 🇷🇺 **Russisch** | ru | ✅ | ✅ | ✅ |
| 🇨🇳 **Chinesisch (vereinfacht)** | zh | ✅ | ✅ | ✅ |

### Sprache ändern

Sie können die Sprache über den **Einstellungsmanager** ändern (siehe Abschnitt [Einstellungsmanager](#settings-manager)):

1. Öffnen Sie `IL2_Settings_Manager.exe`
2. Wählen Sie Ihre bevorzugte Sprache aus der Dropdown-Liste aus.
3. Klicken Sie auf „Übernehmen“ oder „OK“.
4. Der Tracker generiert automatisch alle Nachbesprechungen und PDF-Berichte in der neuen Sprache neu.

> **Hinweis:** Beim Wechseln der Sprache werden alle vorhandenen Kampagnen-Nachbesprechungen und PDF-Berichte automatisch in der ausgewählten Sprache neu generiert. Je nach Anzahl Ihrer Kampagnen kann dies einen Moment dauern.

---

## 📥 Installation <a id="installation"></a>

### Schritt 1: Herunterladen und installieren

1. **Laden Sie** die neueste Version herunter (`IL2_CampaignTracker_Setup_v2.1.zip`)

2. **Entpacken** Sie die `zip`-Datei.

3. **Führen** Sie die entpackte Datei `IL2_CampaignTracker_Setup_v2.1.exe` aus.

4. **Befolgen** Sie die Installationsanweisungen im Setup-Assistenten.

Der Setup-Assistent führt Sie durch die Auswahl des Installationsverzeichnisses und die Konfiguration der grundlegenden Optionen.

### Schritt 2: Standardkampagnen extrahieren (optional, aber empfohlen)

⚠️ **WICHTIG:** Der Tracker kann **nur** Kampagnen überwachen, die sich in `<Pfad zu IL-2 BoS>\data\campaigns` befinden. Standard-IL-2-Kampagnen werden nicht direkt in diesem Ordner gespeichert, sondern intern über `campaigns.gtp` ausgeführt. Daher müssen diese Kampagnen extrahiert werden, bevor sie verfolgt werden können.

🚨 **VORSICHT:** Wenn Sie Missionen einer offiziellen Standardkampagne geändert haben, gehen Sie mit äußerster Vorsicht vor, wenn Sie extrahierte Dateien aus `campaigns.gtp` in den Ordner `<Pfad zu IL-2 BoS>\data\campaigns` kopieren. Vorhandene Dateien werden **überschrieben** und alle benutzerdefinierten Missionsänderungen werden durch die ursprünglichen Standardversionen ersetzt.

**So extrahieren Sie Standardkampagnen:**

1. **Laden Sie** unGTP-IL2 herunter von: <https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip>
2. **Entpacken und verschieben** Sie die Datei „unGTP-IL2.exe“ in den Ordner „<Pfad zu IL-2 BoS>\data“.
3. **Ziehen Sie** die Datei „Campaigns.gtp“ auf „unGTP-IL2.exe“ (ignorieren Sie die Fehlermeldung im cmd-Fenster am Ende – alles wurde extrahiert).
4. **Navigieren** Sie zu `<Pfad zu IL-2 BoS>\data\(null)\campaigns`
5. **Kopieren** Sie alle Unterordner nach `<Pfad zu IL-2 BoS>\data\campaigns`

> **Hinweis:** Der Grund für das Extrahieren der offiziellen Standardkampagnen besteht AUSSCHLIESSLICH darin, sie für den Campaign Tracker nutzbar zu machen. Bitte nehmen Sie keine Änderungen an den offiziellen Kampagnen vor.

### Bereinigungs GUI

```text
┌─────────────────────────────────────────────────────────┐
│        ⚠️ Unvollständige Missionen erkannt                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Die folgenden Missionen wurden nicht ordnungsgemäß abgeschlossen:     │
│                                                          │
│  ☐ Kerch – Mission 05 (14. November 1943)               │
│  ☐ Blazingsteppe – Mission 12 (9. September 1942)       │
│                                                          │
│  Wählen Sie Missionen aus, die Sie aus Ihrem Kampagnen-Speicher entfernen möchten.      │
│                                                          │
│  [🗑️ Ausgewählte entfernen]  [▶ Alle behalten]                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Was passiert, wenn Sie eine Mission entfernen?

1. **Sicherungskopie erstellt** – Der aktuelle Status wird vor Änderungen gespeichert.
2. **Mission entfernt** – Eintrag aus „campaignsstates.txt“ gelöscht.
3. **Popup-Status gelöscht** – Zugehörige Ereignisse aus „campaign_popups_seen.json“ entfernt.
4. **Bereit zum erneuten Spielen** – Sie können die Mission erneut fliegen.

### Was passiert, wenn Sie eine Mission behalten?

Wenn Sie auf „Alle behalten” klicken oder keine Mission auswählen:

- Es wird kein Backup erstellt.
- Es werden keine Änderungen vorgenommen.
- Die Mission bleibt in Ihrer Speicherdatei erhalten.
- Die Bereinigungs-GUI wird beim nächsten Mal erneut angezeigt (für verbleibende unvollständige Missionen).

---

## 💾 Backup- und Wiederherstellungssystem <a id="backup--restore-system"></a>

### Wann werden Backups erstellt?

Backups werden **nur** erstellt, wenn Sie unvollständige Missionen über das Mission Cleanup-Tool entfernen.  Sie werden **nicht** automatisch nach jeder Mission erstellt.

Dadurch wird sichergestellt, dass Sie Ihre Kampagne in den Zustand **vor** dem Entfernen von Missionen zurückversetzen können.

### Wiederherstellungs-GUI

Wenn der Tracker startet und Backups verfügbar sind, wird möglicherweise eine Wiederherstellungs-GUI angezeigt:

```text
┌─────────────────────────────────────────────────────────┐
│           🔄 Kampagnen-Backup wiederherstellen                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Wählen Sie ein Backup zur Wiederherstellung aus:                            │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Datum & Uhrzeit          │ Status           │ Popups   │ │
│  ├──────────────────────┼──────────────────┼──────────┤ │
│  │ 15.01.2024 14:30:22  │ Derzeit aktiv │ ✓ Ja    │ │
│  │ 15.01.2024 12:15:03  │                  │ ✓ Ja    │ │
│  │ 14.01.2024 20:45:11  │                  │ ✗ Nein     | │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  [🔄 Ausgewählte wiederherstellen]  [▶ Weiter]  [✕ Beenden]         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Wenn die GUI angezeigt wird:**

- Es sind mehrere Backups vorhanden ODER
- Es ist ein Backup vorhanden, das **nicht** den aktuellen Status widerspiegelt.

**Wenn die GUI NICHT angezeigt wird:**

- Es sind keine Backups vorhanden.
- Es ist nur ein Backup vorhanden, das bereits den aktiven Status widerspiegelt.

### Wiederherstellungsprozess

1. Wählen Sie ein Backup aus der Liste aus.
2. Klicken Sie auf „Ausgewähltes Backup wiederherstellen”.
3. Bestätigen Sie die Aktion.
4. Der Tracker führt automatisch folgende Schritte aus:
   - Erstellt eine Kopie der Sicherungsdatei (die ursprüngliche Sicherung bleibt erhalten).
   - Löscht die aktuelle Datei „campaignsstates.txt“.
   - Benennt die Sicherungskopie in „campaignsstates.txt“ um.
   - Regeneriert alle Ereignisse.
   - Stellt den entsprechenden Popup-Status wieder her (verhindert doppelte Popups).

### Anwendungsbeispiel

```text
1. Sie fliegen Mission 05 in der Kampagne „kerch“.
2. IL-2 stürzt mitten in der Mission ab → takeoffStatus=1
3. Nächster Tracker-Start: Die Bereinigungs-GUI wird angezeigt.
4. Sie wählen Mission 05 aus und klicken auf „Entfernen“.
5. Der Tracker erstellt eine Sicherung, BEVOR die Mission entfernt wird.
6. Mission 05 wird aus der Speicherdatei entfernt.
7. Sie können nun Mission 05 erneut spielen.

Später, falls erforderlich: 
8. Tracker starten → GUI „Wiederherstellen“ wird angezeigt.
9. Wählen Sie die Sicherung vor dem Entfernen aus.
10. Die Kampagne wird MIT Mission 05 (unvollständig) wiederhergestellt.
```

---

## 📋 Kampagnen-Dienstakte <a id="camapign-service-record"></a>

Der **Kampagnen-Dienstnachweis** ist eine webbasierte Anwendung, die eine elegante, schreibgeschützte Ansicht der Karriere Ihres Piloten über alle laufenden und abgeschlossenen Kampagnen hinweg bietet. Er präsentiert Ihre Dienstgeschichte in einem übersichtlichen, professionellen Format – ideal, um Ihre Erfolge zu überprüfen oder Ihre Kampfbilanz zu teilen.

⚠️ **WICHTIG**: Der Kampagnen-Dienstnachweis ist kein eigenständiges System. Er funktioniert ausschließlich in Verbindung mit dem Tracker und den zugehörigen Dateien, die die erforderlichen Kampagnendaten liefern.

### Funktionen

- **Kampagnenübersicht**: Durchsuchen Sie alle Kampagnen, die Sie geflogen sind, und zeigen Sie abgeschlossene Missionen, verdiente Beförderungen und erhaltene Auszeichnungen an.
- **Detaillierter Dienstnachweis**: Klicken Sie auf eine beliebige Kampagne, um Folgendes anzuzeigen:
  - Vollständige Missionshistorie mit Nachbesprechungen
  - Chronologische Zeitleiste mit Beförderungen und Auszeichnungen
  - Karrierestatistiken (Luftabschüsse, Bodenabschüsse, Missionserfolgsraten)
  - Aufschlüsselung der Flugzeugnutzung und -leistung
- **Pilotprofil**: Zeigen Sie den Namen, das Foto und die persönlichen Daten des Piloten pro Kampagne an und passen Sie diese an.
- **Responsives Design**: Übersichtliche, moderne Benutzeroberfläche, die auf jeder Bildschirmgröße funktioniert.
- **Automatische Generierung**: Liest automatisch Daten aus Ihren Campaign Tracker-Dateien – keine manuelle Eingabe erforderlich

### Verwendung

1. Suchen Sie die Datei „Campaign_Service_Record.exe“ in Ihrem Campaign Tracker-Installationsverzeichnis (siehe Abschnitt „Installation“ oben).
2. Doppelklicken Sie auf „Campaign_Service_Record.exe“, um die Anwendung zu starten.
3. Ihr Standard-Webbrowser wird automatisch geöffnet und zeigt Ihren Service-Datensatz an.
4. Durchsuchen Sie Ihre Kampagnen und klicken Sie auf eine beliebige Kampagne, um detaillierte Statistiken anzuzeigen.
5. Der Server wird nach 60 Sekunden Inaktivität automatisch heruntergefahren.

**Hinweis**: Der Kampagnen-Service-Datensatz benötigt Daten aus dem Campaign Tracker. Sie müssen den Campaign Tracker mindestens einmal ausführen und mindestens eine Mission abschließen, bevor Kampagnen im Service-Datensatz angezeigt werden.

### Übersicht über die Benutzeroberfläche

#### Startseite

- **Linkes Fenster**: Informationen zum Piloten (Foto, Name, Dienstübersicht)
- **Rechtes Fenster**: Liste aller Kampagnen mit abgeschlossenen Missionen
  - Zeigt die Anzahl der Missionen, die verdienten Beförderungen und die erhaltenen Auszeichnungen pro Kampagne an.
  - Klicken Sie auf eine beliebige Kampagne, um den detaillierten Dienstbericht anzuzeigen.

#### Kampagnen-Detailseite

- **Linke Spalte**: Informationen zum Piloten (anpassbares Foto und persönliche Daten), chronologische Zeitleiste mit Beförderungen und Auszeichnungen
- **Mittlere Spalte**: Karriere-Statistiken, darunter:
  - Gesamtzahl der Luft- und Bodenziele
  - Missionsergebnisse
  - Aufschlüsselung der Flugzeugnutzung
  - und mehr
- **Rechte Spalte**: Missionsbesprechungen mit detaillierten Kampfergebnissen
- **Zurück-Button**: Zurück zur Kampagnenübersicht

### Pilotinformationen anpassen

Klicken Sie auf das Foto oder den Namen des Piloten, um folgende Angaben anzupassen:

- **Pilotenfoto**: Klicken Sie hier, um ein neues Foto hochzuladen (gängige Bildformate werden unterstützt).
- **Persönliche Informationen**: Bearbeiten Sie Name, Vorname, Geburtstag, Geburtsort und Geburtsland
- Alle Änderungen werden automatisch gespeichert und bleiben über mehrere Sitzungen hinweg erhalten

### Fehlerbehebung

#### Problem: „Kampagnen werden geladen ...“ wird endlos angezeigt

**Ursache**: Es sind keine Kampagnendaten verfügbar oder die JSON-Dateien sind leer.  
**Lösung**:

- Stellen Sie sicher, dass Sie den Kampagnen-Tracker mindestens einmal ausgeführt haben.
- Schließen Sie mindestens eine Mission in einer beliebigen Kampagne ab.
- Überprüfen Sie, ob Ihre Campaign Tracker-Installation die folgenden Dateien enthält:
  - `campaign_completion_state.json`
  - `campaign_events.json`
  - `campaigns_decoded.json`
  - `campaign_mission_dates.json`

#### Problem: Der Campaign Service Record startet nicht

**Ursache**: Port 5000 wird bereits von einer anderen Anwendung verwendet  
**Lösung**:

- Schließen Sie alle anderen Webserver oder Anwendungen, die Port 5000 verwenden
- Wenn das Problem weiterhin besteht, starten Sie Ihren Computer neu, um den Port freizugeben

#### Problem: Der Browser zeigt „Verbindung nicht möglich“ oder „Seite nicht gefunden“ an

**Ursache**: Der Anwendungsserver konnte nicht gestartet werden  
**Lösung**:

- Überprüfen Sie, ob sowohl `Campaign_Service_Record.exe` als auch der Ordner `_internal` im Installationsverzeichnis vorhanden sind
- Stellen Sie sicher, dass Ihr Antivirenprogramm die Anwendung nicht blockiert
- Versuchen Sie, `Campaign_Service_Record.exe` als Administrator auszuführen

#### Problem: Beim Klicken auf eine Kampagne wird „Fehler beim Laden der Kampagnendetails“ angezeigt

**Ursache**: Fehlende oder beschädigte Kampagnendaten  
**Lösung**:

- Führen Sie den Campaign Tracker erneut aus, um die JSON-Dateien neu zu generieren.
- Stellen Sie sicher, dass die Kampagne mindestens eine abgeschlossene Mission enthält.
- Überprüfen Sie, ob die Kampagnennamen in den JSON-Dateien übereinstimmen.

#### Problem: Pilotfoto wird nicht hochgeladen

**Ursache**: Dateiformat wird nicht unterstützt oder Datei ist zu groß  
**Lösung**:

- Verwenden Sie gängige Bildformate (JPG, PNG, BMP).  
- Stellen Sie sicher, dass die Bilddatei kleiner als 5 MB ist.  
- Versuchen Sie, das Bild in das PNG-Format zu konvertieren.  

#### Problem: Die Anwendung wird unmittelbar nach dem Start geschlossen.  

**Ursache**: Die Zeitüberschreitung bei Inaktivität von 60 Sekunden ist möglicherweise zu kurz oder der Browser wurde nicht geöffnet.  
**Lösung**:

- Doppelklicken Sie erneut auf „Campaign_Service_Record.exe“.
- Öffnen Sie Ihren Browser manuell und navigieren Sie zu „http://127.0.0.1:5000“.
- Lassen Sie die Browser-Registerkarte aktiv, um ein automatisches Schließen zu verhindern.

#### Problem: Deutsche Auszeichnungen und Bilder zeigen kein Hakenkreuz  

**Ursache:**  
Der Campaign Tracker unterstützt, befürwortet oder fördert in keiner Weise die nationalsozialistische Ideologie oder Symbole.  
Um den gesetzlichen Bestimmungen in mehreren Ländern zu entsprechen und die Gemeinschaftsstandards zu respektieren, wurden Hakenkreuze und andere damit verbundene Symbole aus den mit dieser Software gelieferten Standardbildern entfernt.

**Lösung:**  
Benutzer, die historisch korrekte Bilder benötigen, können die Bilder lokal ersetzen:

- Ersetzen Sie die Auszeichnungsbilder in  
  `<Pfad zu IL-2 BoS>\data\swf\CampaignRanksAwards\Germany`
 
- Ersetzen Sie die deutschen Hintergrund- und Flaggenbilder in  
  `<Tracker-Installationsordner>\_internal\static\images\background_Germany.png`  
  `<Tracker-Installationsordner>\_internal\static\images\german_flag.png`  

⚠️ Die ursprünglichen Dateinamen und Dateitypen **müssen nach dem Ersetzen des Bildinhalts beibehalten werden**.

### Technische Informationen

- **Serveradresse**: `http://127.0.0.1:5000` (nur lokaler Rechner)
- **Automatisches Herunterfahren**: Der Server wird nach 60 Sekunden Inaktivität automatisch beendet.
- **Datenstandort**: Liest JSON-Dateien aus demselben Verzeichnis wie die ausführbare Datei.
- **Browserkompatibilität**: Funktioniert mit allen modernen Browsern (Chrome, Firefox, Edge).
- **Netzwerk**: Erfordert keine Internetverbindung; läuft vollständig auf Ihrem lokalen Rechner.

---

## 📁 Dateireferenz <a id="file-reference"></a>

### Konfigurationsdateien

|Datei|Zweck|Vom Benutzer editierbar|
|------|---------|---------------|
|`campaign_progress_config.yaml`|Ränge, Auszeichnungen, Kriterien und Einstellungen|✅ Ja (oder über den Einstellungsmanager)|
|`campaign_mission_dates.json`|Kampagnen-Metadaten, Missionsdaten, Länder|⚠️ Vorsicht (für Offsets den Einstellungsmanager verwenden)|
|`settings.json`|Benutzereinstellungen (Sprache usw.)|✅ Über den Einstellungsmanager|
|`locales/*.yaml`|Sprachübersetzungsdateien|⚠️ Nur für fortgeschrittene Benutzer|

### Konfigurationsdetails

#### campaign_progress_config.yaml

Dies ist die Hauptkonfigurationsdatei mit folgenden Inhalten:

```yaml
# Rangdefinitionen pro Nation
ranks: 
  Deutschland:
    - name: Unteroffizier
      score: 0
      image: unteroffizier.png
    - name: Feldwebel
      score: 80
      image: feldwebel.png
    # ... weitere Ränge

# Auszeichnungsdefinitionen pro Nation
awards: 
  Deutschland:
  - name: Eisernes Kreuz 2. Klasse
    image: iron_cross_2nd.dds
    max_awards: 1
    conditions:
    - air_combat_score: 2
    - missions_completed: 16
  - name: Eisernes Kreuz 1. Klasse
    Bild: iron_cross_1st.dds
    Voraussetzungen: Eisernes Kreuz 2. Klasse
    Maximale Anzahl Auszeichnungen: 1
    Bedingungen:
    - Luftkampfpunktzahl: 8
    - Abgeschlossene Missionen: 64
    # ... weitere Auszeichnungen

# Allgemeine Einstellungen
Einstellungen:
  Popups aktivieren: true

```

#### campaign_mission_dates.json

Wird beim ersten Start automatisch generiert und enthält:

```json
{
  „kerch“: {
    „campaign_name“: „kerch“,
    „country“: „Germany“,
    „is_stock“: true, --> Standard-IL-2-BoS-Kampagne        
    „starting_rank_offset“: 0,
    „mission_count“: 12,
    „missions“: {
      „01“: {
        „raw_date“: „4. November 1943“,
        „normalized_date“: „1943-11-04“,
        „mission_file“: „01.eng“
      },
      „02“: {
        „raw_date“: „6. November 1943“,
        „normalized_date“: „1943-11-06“,
        „mission_file“: „02.eng“
      }, ...
}
```

### Datendateien (automatisch generiert)

| Datei | Zweck | Speicherort |
| ------ | --------- | ---------- |
| `campaigns_decoded.json` | Dekodierte Kampagnenspeicherdaten | Tracker-Ordner |
| `campaign_popups_seen.json` | Verfolgt angezeigte Popups pro Kampagne | Tracker-Ordner |
| `campaign_events.json` | Generierte Ereignisse (Beförderungen/Auszeichnungen) | Tracker-Ordner |
| `campaign_completion_state.json` | Verfolgt den Abschluss von Missionen zwischen Durchläufen | Tracker-Ordner |
| `settings.json` | Benutzereinstellungen (Sprache, Popups usw.) | Tracker-Ordner |

### Sicherungsdateien

| Datei | Zweck | Speicherort |
| ---- | ------- | -------- |
| `campaignsstates_[Zeitstempel].backup` | Sicherung der Kampagnenspeicherung | IL-2-Benutzerspeicherordner |
| `popups_[Zeitstempel].backup` | Sicherung des Popup-Status | IL-2-Benutzerspeicherordner |
| `campaignsstates_hash_index.json` | Backup-Index mit Hashes | IL-2-Benutzerspeicherordner |

### Ausgabedateien

| Datei | Zweck | Speicherort |
| ---- | ------- | -------- |
| `[Kampagne]_Report.pdf` | Karriere-PDF-Bericht | Unterordner `reports/` |

---

## 🔧 Fehlerbehebung <a id="troubleshooting"></a>

### Tracker startet nicht

| Problem | Lösung |
| ------- | -------- |
| Fehlende Datei `campaign_progress_config.yaml` | Stellen Sie sicher, dass sich die Datei im selben Ordner wie die EXE-Datei befindet |
| Blockierung durch Antivirusprogramm | Fügen Sie eine Ausnahme für den Tracker-Ordner hinzu |
| Fehlende Visual C++-Laufzeitumgebung | Installieren Sie [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

### Keine Kampagnen erkannt

| Problem | Lösung |
| ------- | -------- |
| Falscher Ordner ausgewählt | Setup erneut ausführen (`campaign_mission_dates.json` löschen) |
| Noch keine Missionen geflogen | Kampagne in IL-2 starten, mindestens eine Mission fliegen |
| Berechtigungsprobleme | Tracker als Administrator ausführen |

### Popups werden nicht angezeigt

| Problem | Lösung |
| ------- | -------- |
| IL-2 läuft nicht | Popups werden nur angezeigt, wenn IL-2 aktiv ist |
| Bereits gesehen | Überprüfen Sie „campaign_popups_seen.json“ |
| Popups deaktiviert | Überprüfen Sie „enable_popups:  true“ in der Konfiguration |

### PDF-Erstellung schlägt fehl

| Problem | Lösung |
| ------- | -------- |
| Fehlende Abhängigkeiten | Stellen Sie sicher, dass alle erforderlichen DLLs vorhanden sind |
| PDF gesperrt | Schließen Sie die PDF-Datei, wenn sie in einem Viewer geöffnet ist |
| Pfad zu lang | Verschieben Sie den Tracker in einen kürzeren Pfad |

### Ereignisse werden im Spiel nicht angezeigt

| Problem | Lösung |
| ------- | -------- |
| IL-2 speichert Beschreibung im Cache | Starten Sie IL-2 neu, um die aktualisierte Kampagnenbeschreibung anzuzeigen |
| Ereignisse werden in falsche Datei geschrieben | Überprüfen Sie die Länderzuordnung der Kampagne |

---

## ❓ FAQ <a id="faq"></a>

### Warum wird meine benutzerdefinierte Kampagne nicht erkannt / werden Missionen nicht erkannt?

**A:** Der Tracker analysiert Missionsdateien, um Daten und Metadaten zu extrahieren. Befolgen Sie diese goldenen Regeln, um sicherzustellen, dass Ihre benutzerdefinierte Kampagne ordnungsgemäß erkannt wird:

⚠️ *Wichtig: Englische Sprachdateien zum Lesen erforderlich*

Der Tracker liest nur englische Sprachdateien (`.eng`-Briefings und `info.locale=eng.txt`), um Missionsdaten und Kampagneninformationen zu extrahieren. IL-2 speichert die Spracheinstellung des Benutzers intern, und wir haben keine Möglichkeit zu erkennen, welche Sprache Sie im Spiel verwenden. Daher gilt:

- Jede Mission muss über eine entsprechende .eng-Briefing-Datei verfügen (z. B. `01.eng` für `01.Mission`)
- Ihr Kampagnenordner muss eine Datei „info.locale=eng.txt“ für die Kampagnenbeschreibung enthalten.

Auch wenn Sie in einer anderen Sprache spielen, müssen diese englischen Dateien vorhanden sein, damit der Tracker funktioniert. Der Tracker liest keine „.ger“-„.rus“-„.fra“- oder andere Sprachdateien.

Hinweis: Wenn Sie Ereignisse und Nachbesprechungen in Ihre Kampagne zurückschreiben, aktualisiert der Tracker automatisch alle vorhandenen „info.locale=*.txt“-Dateien in der von Ihnen ausgewählten Sprache (siehe [Unterstützte Sprachen](#supported-languages)).

**Benennung von Missionsdateien:**

- Verwenden Sie numerische Präfixe für die Missionsreihenfolge: „01.Mission“, „02.Mission“, „03.Mission“ oder „1.Mission“, „2.Mission“ usw.
- Eine datumsbasierte Benennung ist ebenfalls möglich: „1943-07-04.Mission“, „1943-07-04a.Mission“
- Unterstützte Erweiterungen: `.Mission`, `.mission`, `.msnbin`

Erkennung des Missionsdatums (in `.eng`-Briefing-Dateien):
Der Tracker sucht nach Datumsangaben in dieser Prioritätsreihenfolge:

1. Feld `Date:` im Briefing (z. B. `Date: 4 November, 1943`)
2. Feld „Time:“ für die Startzeit der Mission (z. B. „Time: 09:45“)
3. Dateiname, wenn dieser ein Datum enthält (z. B. „1943-07-04.Mission“)

**Unterstützte Datumsformate:**

- „4. November 1943“ oder „November 4, 1943“
- „4. November 1943“ (ohne Komma)
- „04.11.1943“ oder „11.04.1943“ (TT.MM.JJJJ oder MM.TT.JJJJ)
- „1943-07-04“ (ISO-Format im Dateinamen)

**Struktur des Kampagnenordners:**

`Pfad zu IL-2 Bos\data\Campaigns\IhrKampagnenname\`  
    ├── `info.locale=eng.txt`    (erforderlich zum Lesen – Kampagnenbeschreibung)  
    ├── `info.locale=ger.txt`    (optional – Tracker schreibt auch hier, falls vorhanden)  
    ├── `info.locale=rus.txt`    (optional – Tracker schreibt auch hier, falls vorhanden)  
    ├── `01.Mission`             (Missionsdatei)  
    ├── `01.eng`                 (erforderlich – englische Einweisung mit Datum/Uhrzeit)  
    ├── `02.Mission`  
    ├── `02.eng`                 (erforderlich – englische Einweisung mit Datum/Uhrzeit)  
    └── ...

**Ländererkennung:**
Der Tracker erkennt Ihr Land/Ihre Fraktion automatisch anhand folgender Kriterien:

1. Flugzeugnamen in Missionsdateien (z. B. bf109 → Deutschland, spitfire → Großbritannien)
2. Einheitsnamen, die Länderkennungen enthalten
3. Sie können dies beim ersten Start manuell in der Country Validator-GUI einstellen/korrigieren oder später manuell in der Datei `stock_campaigns.yaml` anpassen.

**Häufige Probleme:**

- Fehlende `.eng`-Briefing-Datei → Daten können nicht extrahiert werden (die Mission wird weiterhin als „Mission 1”, „Mission 2” usw. verfolgt, jedoch ohne Datumsangaben).
- Fehlende Datei „info.locale=eng.txt“ → Kampagnenbeschreibung nicht verfügbar, Tracker kann Kampagneninformationen nicht lesen
- Nicht standardmäßiges Datumsformat im Briefing → verwenden Sie eines der oben unterstützten Formate
- Sonderzeichen im Namen des Kampagnenordners → vermeiden Sie Umlaute oder Sonderzeichen
- Kampagnen aus dem Ersten Weltkrieg (Flying Circus) → standardmäßig für IL-2-Kampagnen ausgeschlossen (siehe Abschnitt „Erkennung und Ausschluss des Ersten Weltkriegs“)

### F: Kann ich mehrere Instanzen des Trackers ausführen?

**A:** Nein. Es sollte immer nur eine Instanz Ihre Kampagnen überwachen.

### F: Verändert der Tracker meine IL-2-Installation?

**A:** Der Tracker verändert nur:

- Kampagnen-Dateien „info.locale=eng.txt“ (fügt den Abschnitt „Events“ hinzu)
- Erstellt Sicherungsdateien im Ordner „usersave“

Er verändert **keine** ausführbaren Dateien oder Kerndateien des Spiels.

### F:  Funktioniert dies mit Mods?

**A:** Ja, solange der Mod die Standard-Kampagnenstruktur verwendet.  Benutzerdefinierte Kampagnen werden bei der Ersteinrichtung automatisch erkannt.

### F:  Kann ich die Konfiguration manuell bearbeiten?

**A:** Ja, aber wir empfehlen, für die meisten Änderungen den **Einstellungsmanager** (`IL2_Settings_Manager.exe`) zu verwenden. Er bietet eine benutzerfreundliche Oberfläche und übernimmt bei Bedarf automatisch die Neugenerierung.

Für erweiterte Anpassungen kann die Datei `campaign_progress_config.yaml` manuell bearbeitet werden, um:

- die Schwellenwerte für Beförderungsnoten anzupassen
- die Vergabekriterien zu ändern
- benutzerdefinierte Auszeichnungen hinzuzufügen
- die Skalierungsfaktoren für Ränge zu ändern

> ⚠️ Erstellen Sie immer eine Sicherungskopie, bevor Sie Konfigurationsdateien manuell bearbeiten.

### F: Wie kann ich alles zurücksetzen?

**A:** Löschen Sie diese Dateien und starten Sie den Tracker neu:

- `campaign_mission_dates.json`
- `campaign_popups_seen.json`
- `campaigns_decoded.json`
- `campaign_events.json`

### F: Wird Multiplayer unterstützt?

**A:** Der Tracker ist für Einzelspieler-Karrierekampagnen ausgelegt.  Multiplayer-Missionen erzeugen nicht die gleiche Speicherdatenstruktur.

### F:  Warum muss ich IL-2 neu starten, um neue Ereignisse zu sehen?

**A:** IL-2 lädt die Kampagnenbeschreibung (`info.locale=eng.txt`) beim Start des Spiels und speichert sie im Arbeitsspeicher. Vom Tracker vorgenommene Änderungen werden in die Datei geschrieben, erscheinen jedoch erst nach einem Neustart von IL-2 im Spiel. **Popups werden jedoch sofort** angezeigt, wenn Sie Beförderungen oder Auszeichnungen erhalten.

### F: Was passiert, wenn ich eine Sicherungsdatei manuell lösche?

**A:** Der Sicherungsindex (`campaignsstates_hash_index.json`) verweist weiterhin darauf, aber die Wiederherstellungs-GUI überspringt alle Sicherungen, bei denen die eigentliche Sicherungsdatei fehlt.

### F: Kann ich den Tracker mit Flying Circus (Erster Weltkrieg) verwenden?

**A:** Flying Circus-Kampagnen werden standardmäßig erkannt und ausgeschlossen. Der Tracker ist für Kampagnen aus dem Zweiten Weltkrieg konzipiert und enthält keine Ränge oder Auszeichnungen aus der Zeit des Ersten Weltkriegs. Sie können Ausschlüsse während der Länderüberprüfung steuern (Kontrollkästchen „Ignorieren“ für den Ersten Weltkrieg), aber Kampagnen aus dem Ersten Weltkrieg verfügen nicht über historisch korrekte Ränge oder Auszeichnungen.

### F: Kann ich den Tracker mit Pat Wilson's Campaing Generator (PWCG) verwenden?

**A:** Nein – dieser Tracker funktioniert NICHT mit PWCG, beeinträchtigt diesen aber auch NICHT.

---

## 📜 Lizenz

Dieses Projekt wird ohne Mängelgewähr für den persönlichen Gebrauch mit IL-2 Sturmovik Great Battles bereitgestellt.

---

## 🙏 Danksagungen

- **1C Game Studios / 777 Studios** – Für die Entwicklung von IL-2 Great Battles
- **Die IL-2-Community** – Für Inspiration und Feedback
- **Kraut1** – Für nützliche Anregungen und umfassende Tests

---

## Viel Spaß beim Fliegen!  ✈️🎖️