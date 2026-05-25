# IL-2 Campaign Progress Tracker

A comprehensive tracking tool for IL-2 Sturmovik Great Battles single-player **WW2 campaigns and career mode**.  Automatically monitors your campaign progress, calculates promotions and awards based on historical criteria, generates detailed mission debriefings, creates PDF reports of your pilot's career, and optionally produces AI-generated narrative story chapters for each mission.

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-IL--2%20Great%20Battles-orange)
![Languages](https://img.shields.io/badge/languages-7-green)

---

## 📋 Table of Contents

- [Features](#features)
- [Supported Nations](#supported-nations)
- [Supported Languages](#supported-languages)
- [Installation](#installation)
- [First Run Setup](#first-run-setup)
- [Settings Manager](#settings-manager)
- [WW1 Detection & Exclusion](#ww1-detection--exclusion)
- [How It Works](#how-it-works)
- [Promotions & Awards System](#promotions--awards-system)
- [Mission Debriefings](#mission-debriefings)
- [Mission Cleanup](#mission-cleanup)
- [Backup & Restore System](#backup--restore-system)
- [AI Story Generation](#ai-story-generation)
- [Campaign Service Record](#campaign-service-record)
- [Career Service Record](#career-service-record)
- [File Reference](#file-reference)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## ✨ Features <a id="features"></a>

| Feature | Description |
| --- | --- |
| **Automatic Monitoring** | Watches your campaign save file and updates in real-time |
| **Promotions** | Calculates rank promotions based on accumulated score |
| **Awards & Decorations** | Grants medals based on kills, missions flown, and other criteria |
| **Real-time Popups** | Shows promotion and award notifications while playing |
| **Mission Debriefings** | Parses mission logs to generate detailed flight reports |
| **PDF Reports** | Creates printable career summaries with combat statistics |
| **AI Story Generation** | Generates narrative war-diary chapters for each mission using your choice of LLM provider |
| **Multi-Language Support** | Full support for 7 languages: English, German, French, Spanish, Polish, Russian, and Chinese |
| **Settings Manager** | User-friendly GUI to configure all tracker settings without editing config files; includes a built-in updater to install new versions directly from a zip package |
| **Standard Campaign Import** | One-click extraction of IL-2 built-in campaigns from `Campaigns.gtp` via the Settings Manager |
| **Mission Cleanup** | Removes incomplete missions that weren't properly finished |
| **Backup System** | Creates backups when removing incomplete missions via cleanup tool |
| **Restore Function** | Easy GUI to restore previous campaign states |
| **Multi-Campaign Support** | Tracks multiple campaigns simultaneously |
| **WW1 Detection & Exclusion** | Detects Flying Circus (WW1) campaigns and skips them by default |
| **Control Center GUI** | Central hub to launch Tracker, Settings Manager, and Service Record |
| **Per-Campaign Language** | Override detail page language for individual campaigns in Service Record |
| **Campaign Service Record** | Web viewer for Campaign Mode: shows mission debriefings, promotions, awards, and AI stories |
| **Career Service Record** | Dedicated web viewer for IL-2 Career Mode: reads from `cp.db`, shows theatre chain, all events, debriefings, statistics, and AI stories |
| **German Award Style** | Choose between the 1957 Bundeswehr-era (default) and the original wartime style for German award images |

---

## 🌍 Supported Nations <a id="supported-nations"></a>

The tracker includes historically accurate ranks and awards for:

| Nation | Ranks | Awards |
| ------ | ----- | ------ |
| 🇩🇪 **Germany** | Unteroffizier → Generalleutnant | Iron Cross, Knight's Cross, etc. |
| 🇷🇺 **Soviet Union** | Sergeant → Lieutenant General | Order of the Red Banner, Hero of the Soviet Union, etc. |
| 🇺🇸 **USA** | First Sergeant → Major General | Distinguished Flying Cross, Medal of Honor, etc. |
| 🇬🇧 **Britain** | Sergeant → Air Vice Marshal | Distinguished Flying Cross, Victoria Cross, etc. |

> **Note 1:** Soviet ranks automatically switch between early (pre-1943) and late (post-January 6, 1943) insignia based on mission dates.  
> **Note 2:** The German awards shown are based on the official 1957 reissue versions. If you wish to customize their appearance, you can replace the images located in `CampaignRanksAwards\Germany`.

⚠️ Important: Keep the original filenames when replacing images — for example,
`iron_cross_2nd.dds` and `iron_cross_2nd_big.dds` must retain the exact same names after replacement.

---

## 🌐 Supported Languages <a id="supported-languages"></a>

The tracker supports full localization in 7 languages. All UI elements, mission debriefings, PDF reports, in-game events, and the Campaign Service Record are automatically translated based on your selected language.

| Language | Display Name | Code | Popups | In-Game Events | PDF Reports | Service Record | Settings Manager |
| -------- | ------------ | ---- | ------ | -------------- | ----------- | -------------- | ---------------- |
| 🇬🇧 **English** | English | en | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇩🇪 **German** | Deutsch | de | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇫🇷 **French** | Français | fr | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇪🇸 **Spanish** | Español | es | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇵🇱 **Polish** | Polski | pl | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇷🇺 **Russian** | Русский | ru | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🇨🇳 **Chinese (Simplified)** | 简体中文 | zh | ✅ | ✅ | ✅ | ✅ | ✅ |

### What Gets Translated

When you select a language, the following content is displayed in that language:

- **Popup Notifications** - Promotion and award announcements
- **In-Game Events** - The Events section written to campaign `info.locale=*.txt` files
- **Mission Debriefings** - Flight logs, kill reports, status messages
- **PDF Reports** - Complete career reports including all statistics
- **Campaign Service Record** - The web-based service record interface
- **Settings Manager** - All UI labels, buttons, and messages
- **AI Story Chapters** - Story chapters are generated in the configured story language

### Changing Language

You can change the language using the **Settings Manager** (see [Settings Manager](#settings-manager) section):

1. Open `IL2_Settings_Manager.exe`
2. Select your preferred language from the dropdown (languages are shown in their native names)
3. Click "Apply" or "OK"
4. The tracker will automatically regenerate all debriefings and PDF reports in the new language

> **Note:** When switching languages, all existing campaign debriefings and PDF reports are automatically regenerated in the selected language. This may take a moment depending on the number of campaigns you have.

### IL-2 Language File Mapping

The tracker maps IL-2's language codes to standard locale codes:

| IL-2 Code | Tracker Code | Language |
| --------- | ------------ | -------- |
| eng | en | English |
| ger | de | German |
| fra | fr | French |
| spa | es | Spanish |
| pol | pl | Polish |
| rus | ru | Russian |
| chs | zh | Chinese (Simplified) |

When writing events to campaign files, the tracker updates **all** `info.locale=*.txt` files that exist for a campaign (e.g., `info.locale=eng.txt`, `info.locale=ger.txt`, etc.), each in the appropriate language.

---

## 📥 Installation <a id="installation"></a>

### Step 1: Download and Install

1. **Download** the latest release (`IL2_CampaignTracker_Setup_v3.0.0_ML.exe.zip`)

2. **Extract** the `zip` file

3. **Run** the extracted `IL2_CampaignTracker_Setup_v3.0.0_ML.exe`

4. **Follow** the installation instructions in the setup wizard

The setup wizard will guide you through selecting the installation directory and configuring basic options.

### Step 2: Extract Standard Campaigns

⚠️ **IMPORTANT:** The tracker can monitor **only** campaigns located in `<Path to IL-2 BoS>\data\campaigns`. Standard IL-2 campaigns are not stored directly in this folder — they run internally from `Campaigns.gtp`. These campaigns must be extracted before they can be tracked.

**Option A: Via Settings Manager (Recommended)**

1. Open `IL2_Settings_Manager.exe`
2. Go to the **General** tab
3. Click **"Import Standard Campaigns"**
4. The Settings Manager will extract campaigns from `Campaigns.gtp` (and `Missions.gtp` if present) automatically into your IL-2 `data\Campaigns` folder
5. Only new or missing campaign files are added — no existing files are ever overwritten

**Option B: Manual Extraction**

1. **Download** unGTP-IL2 from: <https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip>
2. **Unzip & Move** the `unGTP-IL2.exe` to `<Path to IL-2 BoS>\data`
3. **Drag** `Campaigns.gtp` onto `unGTP-IL2.exe` (ignore any error warning in the cmd-window at the end — everything has been extracted)
4. **Navigate** to `<Path to IL-2 BoS>\data\(null)\campaigns`
5. **Copy** all subfolders to `<Path to IL-2 BoS>\data\campaigns`

🚨 **CAUTION:** If you have modified missions belonging to a standard official campaign, use Option A (Settings Manager) which never overwrites existing files. Manual copying will replace any files you have modified.

> **Note:** The intention of extracting the standard official campaigns is ONLY to make them usable for the Campaign Tracker. Please do not modify the official campaigns.

### Step 3: Run the Tracker

**Run** `IL2_Campaign_Tracker.exe` from your Tracker installation directory.

ℹ️ **NOTE**: By default, the tracker shuts down automatically when IL-2 BoS is closed. To continue using the tracker, you must either restart it manually or configure a Windows Task Scheduler task to launch it automatically when Windows starts.

A general setup guide can be found here:
<https://forum.il2-series.com/topic/772-expanded-career-rank-mod/#findComment-4176>

### Control Center GUI

The **Control Center** (`IL2_Control_Center.exe`) provides a central hub to launch all tracker components:

```text
┌─────────────────────────────────────────────────────────┐
│              IL-2 Campaign Tracker                      │
│                  Control Center                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   [🚀 Start Tracker]     Launch the Campaign Tracker    │
│                                                         │
│   [❌ Stop Tracker]      Stop the Campaign Tracker      │
│                                                         │
│   [⚙️ Settings]          Open Settings Manager          │
│                                                         │
│   [📋 Service Record]    Open Campaign Service Record   │
│                                                         │
│   [🗑️ Uninstall]         Uninstall the Campaign Tracker │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- One-click access to all tracker components
- Visual status indicators
- Clean, modern interface

### Installed Files

The installer places the following files in your chosen installation directory:

```text
IL2_Campaign_Tracker/
├── IL2_Control_Center.exe                # Control Center GUI (recommended entry point)
├── IL2_Campaign_Tracker.exe              # Main tracker executable
├── IL2_Settings_Manager.exe              # Settings Manager GUI
├── mlg2txt.exe                           # Helper for decoding mission reports
├── Campaign_Service_Record.exe           # Campaign Service Record web application (port 5000)
├── Career_Service_Record.exe             # Career Service Record web application (port 5001)
├── campaign_progress_config.yaml         # Ranks & awards configuration
├── stock_campaigns.yaml                  # Campaign to Country allocation
├── object_categories.yaml                # Mission debriefing data
├── version.txt                           # Current version number (used by Settings Manager updater)
├── locales/ (folder)                     # Language files (7 languages)
├── historical_context/ (folder)          # Squadron historical context for AI stories
├── _internal/ (folder)                   # Service Record resources
├── unins000.exe                          # Uninstaller
├── unins000.dat                          # Uninstaller data
├── cleanup_tracker_content.exe           # Helper for uninstaller
└── (other files created automatically on first run)
```

### Uninstall

1. **Run** `unins000.exe` from Tracker installation path
   
   🚨 **DO NOT RUN** `cleanup_tracker_content.exe` directly - it is a helper for the uninstaller.

2. **Follow** the uninstallation instructions in the wizard

ℹ️ **NOTE:** All in-game debriefings and events will be removed, and the original `info.locale=[language].txt` files will be restored to their out-of-the-box state.

If you choose to keep the configuration files during uninstallation and later reinstall the tracker into the same folder, those files will not be overwritten. Your previously saved configuration will be retained.

---

## 🚀 First Run Setup <a id="first-run-setup"></a>

When you start the tracker for the first time, a setup wizard guides you through the configuration:

### Step 1: Select Game Directory

A folder browser opens.  Navigate to your IL-2 installation folder:

```bash
Example: C:\Program Files (x86)\Steam\steamapps\common\IL-2 Sturmovik Battle of Stalingrad
```

> **Important:** Select the main game folder, NOT the `data\Campaigns` subfolder.  

### Step 2: Country Validation

The tracker scans all installed campaigns and attempts to detect the correct country for each.  A validation GUI appears where you can:

- ✅ Confirm automatically detected countries
- ✏️ Correct any misidentified campaigns
- 🚫 Exclude WW1 (Flying Circus) campaigns

This is important because promotions and awards are nation-specific.  
ℹ️ After validating/correcting countries, those campaigns are written into the `stock_campaigns.yaml`. If you accidentally assigned the wrong country, you can fix that by manually editing the country in the `stock_campaigns.yaml`.

### WW1 (Flying Circus) Detection

If the tracker detects Flying Circus campaigns, you can - or better should - mark them as **WW1 (ignore)** in this screen so they are excluded from tracking.

### Step 3: Ready to Track

After setup, the tracker:

1. Decodes your current campaign save file
2. Generates initial events (existing promotions/awards)
3. Starts monitoring for changes

---

## ⚙️ Settings Manager <a id="settings-manager"></a>

The **Settings Manager** (`IL2_Settings_Manager.exe`) provides a user-friendly GUI to configure all tracker settings without manually editing configuration files.

### Opening the Settings Manager

1. Locate `IL2_Settings_Manager.exe` in your tracker installation folder
2. Double-click to open the Settings Manager
3. Make your changes and click "Apply" or "OK"

### Available Settings

#### General Tab

| Setting | Description |
| ------- | ----------- |
| **Language** | Select display language (English, German, French, Spanish, Polish, Russian, Chinese) |
| **Enable Popups** | Toggle promotion/award popup notifications on/off |
| **Rank Scaling Enabled** | Enable/disable rank scaling based on campaign length |
| **Import Standard Campaigns** | One-click extraction of IL-2 built-in campaigns from `Campaigns.gtp` directly into `data\Campaigns` — only adds missing files, never overwrites |

#### Rank Scaling Tab

Configure how rank requirements scale based on campaign length:

| Bracket | Default Factor | Purpose |
| ------- | -------------- | ------- |
| 1-10 missions | 1.00x | Short campaigns (stock campaigns) |
| 11-20 missions | 1.15x | Medium-short campaigns |
| 21-30 missions | 1.30x | Medium campaigns |
| 31-40 missions | 1.50x | Medium-long campaigns |
| 41-50 missions | 1.75x | Long campaigns |
| 51-70 missions | 2.00x | Very long campaigns |
| 71+ missions | 5.50x | Epic campaigns |

You can add, edit, or remove scaling brackets as needed.

#### Rank Values Tab

Configure promotion score thresholds for each nation:

- View and edit the score required for each rank
- Supports all four nations (Germany, Soviet Union, USA, Britain)

#### Campaigns Tab

Configure per-campaign settings:

| Setting | Description | Range/Options |
| ------- | ----------- | ------------- |
| **Starting Rank Offset** | Start campaigns at higher ranks | 0-7 |
| **Detail Page Language** | Override language for Service Record detail page | Default, English, German, Russian |

> **Tip:** Use higher offsets (up to 7) for campaigns where the player is already a squadron leader at mission start. This is particularly useful for British campaigns due to their many lower ranks.

##### Per-Campaign Language Override

The **Detail Page Language** setting allows you to lock a specific campaign's Service Record detail page to a particular language (English, German, or Russian), independent of the global language setting.

- **Default**: Follows the global language setting dynamically
- **English/German/Russian**: Locks the detail page to that specific language

This is useful when you want to view a German campaign's debriefings in German while keeping the rest of the application in your preferred language. When you change this setting and save, the localized debriefings are automatically regenerated for the affected campaigns.

#### Career Language Tab

Configure language settings specific to the Career Service Record, including per-career language overrides independent of the global setting.

#### German Awards Tab

Switch between the 1957 Bundeswehr-era style (default) and the original wartime style for German award images.

#### Updates Tab

The **Updates** tab lets you install tracker updates directly from within the Settings Manager — no need to run a new installer.

| Action | Description |
| ------ | ----------- |
| **Select Package** | Browse for an update `.zip` file downloaded from the releases page |
| **Install** | Installs the package contents into your tracker installation directory |
| **Restore Backup…** | Open a previous update backup zip to roll back to an earlier version |

**How installation works:**

- Regular files (DLLs, resources, locales, configuration, etc.) are installed immediately
- `IL2_Settings_Manager.exe` itself cannot be replaced while it is running — the new version is saved alongside as a `.pending` file and applied the next time you start the Settings Manager
- A progress bar tracks installation status per file

**Startup banners (shown at the top of the Updates tab):**

- 🟢 **Green banner** — *"Updated successfully"* — shown once after a deferred self-update has been applied on startup
- 🟠 **Orange banner with "Restart & Apply" button** — shown when a deferred exe update is still pending. Click the button to close the Settings Manager, apply the update automatically, and relaunch

> **Note:** Backups of all replaced files are stored as timestamped `.zip` archives in the `backups/` subfolder of your tracker installation directory and can be restored via the **Restore Backup…** button.

#### AI Stories Tab

Configure the AI story generation feature (see [AI Story Generation](#ai-story-generation) for details):

| Setting | Description |
| ------- | ----------- |
| **Enable AI Stories** | Toggle story generation on/off |
| **Provider** | Select your LLM provider: OpenAI, OpenRouter, Anthropic, Google, Microsoft Azure, or Custom |
| **API Key** | Enter your API key for the selected provider (stored per-provider) |
| **Base URL** | API endpoint — pre-filled for known providers, editable for custom endpoints |
| **Model** | Select or enter the model name (e.g., `gpt-4o-mini`, `claude-3-5-haiku-20241022`) |
| **Auto-Generate** | When enabled, a story chapter is generated automatically whenever a mission debriefing is parsed |

### Auto-Regeneration

When you change certain settings, the tracker automatically regenerates all affected data:

| Changed Setting | Auto-Regeneration |
| --------------- | ----------------- |
| Language | ✅ All debriefings and PDF reports regenerated in new language |
| Rank Scaling | ✅ All events recalculated based on new scaling factors |
| Rank Values | ✅ All promotions recalculated based on new thresholds |
| Starting Rank Offset | Manual regeneration (restart tracker) |

---

## 🪖 WW1 Detection & Exclusion <a id="ww1-detection--exclusion"></a>

Flying Circus (WW1) campaigns are detected and excluded by default because the tracker only includes WWII ranks, awards, and debriefing logic.

**Detection signals include:**

- Mission dates in the 1914–1918 range
- WW1 aircraft keywords in campaign data
- "Flying Circus"/WW1 keywords in campaign descriptions

**How exclusion works:**

- Excluded campaigns are skipped during decoding and event generation.
- The exclusion reason is stored in `campaign_mission_dates.json` so the tracker consistently ignores them.
- You can review or change exclusions by re-running setup (delete `campaign_mission_dates.json` and the respective entry in the `stock_campaigns.yaml`) and using the **WW1 (ignore)** checkbox in the country validation GUI.

---

## ⚙️ How It Works <a id="how-it-works"></a>

### Monitoring Loop

```text
┌─────────────────────────────────────────────────────────┐
│                    TRACKER RUNNING                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   1. Watch campaignsstates.txt for changes              │
│                          ↓                              │
│   2. Detect file modification (mission completed)       │
│                          ↓                              │
│   3. Decode campaign save file                          │
│                          ↓                              │
│   4. Calculate new promotions/awards                    │
│                          ↓                              |
|   5. Show popups for new events                         |
|                          ↓                              │                     
│   6. Parse mission log for debriefing                   │
│                          ↓                              │                     
│   7. Update campaign info file                          │
│                          ↓                              │
│   8. Generate PDF report                                │
│                          ↓                              │
│   9. Generate AI story chapter (if enabled)             │
│                          ↓                              │
│  10. Return to monitoring                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Real-time Popups

When you earn a promotion or award, a popup notification appears on screen:

- 🎖️ Shows the rank insignia or medal image
- 📅 Displays the date earned
- ⏱️ Auto-dismisses after 5 seconds

> **Note:** Popups only appear while IL-2 is running to avoid interruptions during other activities. If you don't like popups, go to `campaign_progress_config.yaml` in your tracker installation directory
and set ```enable_popups: false```

---

## 🎖️ Promotions & Awards System <a id="promotions--awards-system"></a>

### How Promotions Work

Promotions are based on **accumulated score** across all completed missions (the score value comes from the campaignsstates.txt and is calculated by IL-2 GB internal rules):

```text
Overall Score per Campaign = ∑ Mission Scores
Promotion Score = Base Score × Rank Scaling Factor
```

**Rank Scaling Factor** adjusts requirements based on campaign length (can be edited in `campaign_progress_config.yaml`):  

"1-10":    1.00   # Short campaigns (stock campaigns)  
"11-20":   1.15   # Medium-short campaigns  
"21-30":   1.30   # Medium campaigns  
"31-40":   1.50   # Medium-long campaigns  
"41-50":   1.75   # Long campaigns  
"51-70":   2.00   # Very long campaigns  
"71+":     5.50   # Epic campaigns (70+ missions)

This prevents rapid promotions in long campaigns while ensuring fair progression in short ones.  

ℹ️ **Example:** In a 24-mission campaign, the scaling factor is 1.3, so a rank requiring 1000 points would need 1300 actual points (1000 x 1.30) to achieve.  
When your accumulated score meets or exceeds the promotion threshold of 1300 points, you are promoted to the next rank.

🚨 **IMPORTANT**: If you modify the `campaign_progress_config.yaml`, be careful to keep indentation correct (YAML format). Improper indentation can lead to parsing errors.

### How Awards Work

Awards are granted based on various criteria defined in `campaign_progress_config.yaml` and are derived from the career mode in IL-2 BoS.
All conditions for awards are `OR` conditions:

| Criteria Type | Example |
| ------------- | ------- |
| **Cumulative Kills** | 8 air combat score → Iron Cross 1st Class |
| **Single Mission** | 7 kills in one sortie → Medal of Honor |
| **Missions Completed** | 15 missions → Order of the Red Star |
| **Wounded in Action** | Pilot damage > 20% → Wound Badge |
| **Random + Threshold** | High kills + luck factor → Rare decorations |

Some awards have **prerequisites** (e.g., must have Iron Cross 2nd Class before 1st Class) and **mutual exclusivity** (e.g., cannot earn both wound stripe variants on same mission).

### Starting Rank Offset

Campaigns can start with higher ranks (if you want to). This is useful for campaigns where your pilot is already an experienced officer at mission start. The offset can be configured:

**Option 1: Via Settings Manager (Recommended)**
1. Open `IL2_Settings_Manager.exe`
2. Go to the "Campaigns" tab
3. Double-click on a campaign to edit its offset
4. Select a value from 0-7

**Option 2: Manual editing in `campaign_mission_dates.json`:**

```json
"kerch": {
  "country": "Germany",
  "starting_rank_offset": 2, --> change this number (0-7, default = 0)
  "missions": { ...  }
}
```

> **Note:** Higher offset values (up to 7) are particularly useful for British campaigns, which have many lower ranks, or for campaigns where the player starts as a squadron leader.

ℹ️ **Note:** You may customize the promotion and award criteria to suit your preferences. However, it is strongly recommended to create a backup copy of the original `campaign_progress_config.yaml` file before making any changes.

---

## 📊 Mission Debriefings <a id="mission-debriefings"></a>

### Data Source

Debriefing data is extracted from IL-2's **mission log files** (`.mlg` files):

```text
Location: [IL-2 Directory]\data\FlightLogs\[mission].mlg
```

These binary files contain detailed records of everything that happened during the mission.
These binary files are "translated" by `mlg2txt.exe` into a *.txt file and is then further processed.

### What's Tracked

| Category | Details |
| -------- | ------- |
| **Flight Time** | Takeoff to landing duration |
| **Kills** | Air, ground, and naval targets with timestamps |
| **Damage Taken** | Hits received, from whom, damage percentage |
| **Pilot Status** | "Damage" % |
| **Status** | Landed, Landed (wounded), Hard Landing, Hard Landing (wounded), Bailout, Bailout (wounded), KIA/MIA |

### Debriefing Output

Each mission generates detailed output in two formats:

1. **In-Game (Flight Log)** - Chronological list of events written to all campaign `info.locale=*.txt` files (each in its respective language)
2. **PDF Report** - Full campaign report including:
   - Per-mission kill breakdown by category (matching the in-game results screen)
   - **Air Kills by Aircraft Type** — a summary table showing your aerial victories grouped by target aircraft type across all missions (e.g., Bf 109 G-6: 12, Il-2 mod.1943: 8, etc.)
   - Campaign statistics (total score, missions flown, air kill count, wounds)
   - Promotions and awards timeline
   - Personal data cover page with pilot photo (if configured)

> **Note:** The tracker writes localized content to each language file that exists in your campaign folder. For example, if your campaign has both `info.locale=eng.txt` and `info.locale=ger.txt`, the English file will contain English debriefings and the German file will contain German debriefings.

---

## 🧹 Mission Cleanup <a id="mission-cleanup"></a>

### What is takeoffStatus?

IL-2 tracks mission completion with a `takeoffStatus` flag:

|Value|Meaning|
|-------|---------|
|`takeoffStatus=1`|Mission started but not completed properly|
|`takeoffStatus=2`|Mission completed successfully|

### When Cleanup GUI Appears

The Mission Cleanup GUI appears at tracker startup when missions with `takeoffStatus=1` are detected.

**Common causes for `takeoffStatus=1`:**

- ❌ Mission objective not completed
- 🪂 Pilot bailed out
- 💀 Pilot killed in action (KIA)
- ❓ Pilot missing in action (MIA)
- 💥 IL-2 crashed during mission
- 🚫 Force quit (Alt+F4, Task Manager)
- 🔌 Power outage / system crash

> **Note:** Not all `takeoffStatus=1` missions are "failed" in the traditional sense.  Bailing out or being KIA may be intentional gameplay.  The cleanup tool gives you the **choice** whether to remove these missions.

### Cleanup GUI

```text
┌─────────────────────────────────────────────────────────┐
│        ⚠️ Incomplete Missions Detected                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  The following missions were not completed properly:     │
│                                                          │
│  ☐ kerch - Mission 05 (November 14, 1943)               │
│  ☐ blazingsteppe - Mission 12 (September 9, 1942)       │
│                                                          │
│  Select missions to remove from your campaign save.      │
│                                                          │
│  [🗑️ Remove Selected]  [▶ Keep All]                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### What Happens When You Remove a Mission

1. **Backup created** - Current state saved before any changes
2. **Mission removed** - Entry deleted from `campaignsstates.txt`
3. **Popup state cleared** - Associated events removed from `campaign_popups_seen.json`
4. **Ready to replay** - You can fly the mission again

### What Happens When You Keep a Mission

If you click "Keep All" or don't select a mission:

- No backup is created
- No changes are made
- The mission remains in your save file
- Cleanup GUI will appear again next time (for remaining incomplete missions)

---

## 💾 Backup & Restore System <a id="backup--restore-system"></a>

### When Backups Are Created

Backups are **only** created when you remove incomplete missions via the Mission Cleanup tool.  They are **not** created automatically after every mission.

This ensures you can restore your campaign to the state **before** you removed any missions.

### Restore GUI

When the tracker starts and backups are available, a restore GUI may appear:

```text
┌─────────────────────────────────────────────────────────┐
│           🔄 Restore Campaign Backup                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Select a backup to restore:                            │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Date & Time          │ Status           │ Popups   │ │
│  ├──────────────────────┼──────────────────┼──────────┤ │
│  │ 2024-01-15 14:30:22  │ Currently Active │ ✓ Yes    │ │
│  │ 2024-01-15 12:15:03  │                  │ ✓ Yes    │ │
│  │ 2024-01-14 20:45:11  │                  │ ✗ No     | │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  [🔄 Restore Selected]  [▶ Continue]  [✕ Exit]         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**When the GUI appears:**

- Multiple backups exist, OR
- One backup exists that is **not** the current state

**When the GUI does NOT appear:**

- No backups exist
- Only one backup exists and it's already the active state

### Restore Process

1. Select a backup from the list
2. Click "Restore Selected Backup"
3. Confirm the action
4. Tracker automatically:
   - Creates a copy of the backup file (original backup preserved)
   - Deletes current `campaignsstates.txt`
   - Renames backup copy to `campaignsstates.txt`
   - Regenerates all events
   - Restores matching popup state (prevents duplicate popups)

### Use Case Example

```text
1. You fly Mission 05 in "kerch" campaign
2. IL-2 crashes mid-mission → takeoffStatus=1
3. Next tracker start: Cleanup GUI appears
4. You select Mission 05 and click "Remove"
5. Tracker creates backup BEFORE removing the mission
6. Mission 05 is removed from save file
7. You can now replay Mission 05

Later, if needed: 
8. Start tracker → Restore GUI appears
9. Select the backup from before removal
10. Campaign restored to state WITH Mission 05 (incomplete)
```

---

## 📖 AI Story Generation <a id="ai-story-generation"></a>

The **AI Story Generation** feature uses a Large Language Model (LLM) to write narrative war-diary chapters for each mission in your career or campaign. Stories are written in third-person historical prose — not mission-report style — and maintain continuity across sessions through a rolling narrative memory.

This feature works for **both Career Mode** (Career Service Record) and **Campaign Mode** (Campaign Service Record). Chapters are displayed in the Service Record detail pages alongside your debriefings.

### Supported Providers

You can use any of the following LLM providers. Each requires its own API key and has its own supported models:

| Provider | Notes |
| -------- | ----- |
| **OpenAI** | GPT-4o, GPT-4o Mini, GPT-5, etc. Default and simplest setup. |
| **OpenRouter** | Aggregates many providers under one API key. Great for model variety. |
| **Anthropic** | Claude 3.5 Haiku, Claude 3.5 Sonnet, etc. |
| **Google** | Gemini 2.0 Flash, Gemini 1.5 Pro, etc. |
| **Microsoft Azure** | GPT-4o and other Azure-deployed OpenAI models. |
| **Custom** | Any OpenAI-compatible endpoint (LM Studio, Ollama, etc.). |

### Setting Up AI Stories

1. Open `IL2_Settings_Manager.exe`
2. Go to the **AI Stories** tab
3. **Enable AI Stories** → set to Yes
4. Select your **Provider** from the dropdown
5. Enter your **API Key** for that provider
6. The **Base URL** is filled in automatically for known providers
7. Select or enter the **Model** name
8. Optionally enable **Auto-Generate** to create a chapter each time a mission is debriefed
9. Click "Apply" or "OK"

### How Stories Are Generated

**For Career Mode:**

Stories are built from data pulled directly from the game's `cp.db` and the parsed mission report:

- **Pilot facts**: rank, squadron, aircraft flown during the sortie
- **Mission facts**: date, time of day (derived), season (derived), result, flight duration, kills
- **Mission type**: tactical role (e.g., Frontline Patrol, Escort Bombers, Bomb Bridge) derived from the mission file
- **Formation**: size and role (leader or wingman) — Luftwaffe terminology (Rotte/Schwarm) for German pilots
- **Career progression**: all awards held, cumulative aerial victories, current rank
- **Mission-specific events**: awards or promotion received after this specific sortie
- **Squadron events**: promotions, awards, KIA/MIA/WIA, and transfers of other pilots in your squadron
- **Historical context**: period-appropriate background for your squadron, auto-enriched via LLM on first encounter
- **Other career incidences**: recovery periods, squadron transfers, commander appointments mentioned as narrative
- **Inter-mission promotions**: promotions that occurred on non-flying days are woven in as background context
- **Theatre transitions**: when the pilot moves to a new theatre, the chapter uses a 4-paragraph structure covering the conclusion of the previous campaign, the transfer period (including any gap awards/promotions), arrival at the new unit, and the opening sortie

**For Campaign Mode:**

Stories use campaign and debriefing data:

- Campaign name and background text (from campaign info file)
- **Mission briefing text** — the actual briefing from the `.eng` mission file (date, time, and briefing body) is extracted and used as story context
- Mission date, time of day, season, result, kills, flight duration
- **Kill cause classification** — how each kill was achieved (e.g., guns, collision, unknown) enriches the narrative
- Tracker-calculated rank and awards
- **Mission type** derived from campaign structure (e.g., escort, intercept, ground attack, offensive reconnaissance)
- **Pilot biography** — if a pilot biography file exists for the campaign, it is used when generating the first chapter to establish the pilot's background, personality, and backstory

### Narrative Continuity

Each story session maintains a **rolling narrative memory** that carries forward between chapters:

- Current rank and squadron
- Recent mission outcomes
- Key career milestones (promotions, significant awards)
- Recurring themes (survival under pressure, combat leadership, etc.)
- Total confirmed aerial victories (authoritative count from the game database)
- Previously used chapter titles (to avoid repetition in structure and weather imagery)

The narrative memory is stored locally and is used as context for each new chapter, so references to past events, established operational context, and character development remain consistent throughout the career.

### Auto-Generate vs Manual

| Mode | Behaviour |
| ---- | --------- |
| **Auto-Generate ON** | A chapter is generated automatically each time a mission is debriefed (Campaign Mode) or when you open the career detail page (Career Mode, background generation for missing chapters) |
| **Auto-Generate OFF** | Stories are only generated when you click "Generate" in the Service Record UI |

### Managing Chapters

In the Service Record detail page:

- **View chapters**: Story chapters appear in chronological order alongside your mission debriefings
- **Delete a chapter**: Click the delete button on any chapter to remove it and its memory entries. The chapter count is renumbered automatically
- **Regenerate**: After deleting, click "Generate" to create a new chapter for that mission
- **Context preview**: An API endpoint lets you inspect the story input for any mission before generating (`/api/stories/<source>/<id>/context_preview`)

> **Same-day chapter grouping**: When a pilot flew multiple sorties on the same calendar day, they are automatically combined into one chapter rather than written as separate entries. The word and paragraph targets scale accordingly (two missions → 3 paragraphs; three or more → 4 paragraphs).

### Story Data Storage

Story chapters and narrative memory are stored outside the application install directory so they survive reinstalls:

```text
%LOCALAPPDATA%\.il2_campaign_service_record\story_data\
    careers\
        <career_id>\
            memory.json          # Rolling narrative state
            chapters\
                0001_1941-06-22.json
                0002_1941-06-23.json
                ...
    campaigns\
        <campaign_name>\
            memory.json
            chapters\
                ...
```

### Historical Context Enrichment

If no historical data exists for your squadron in the local `historical_context/squadrons.json` file, the application calls the LLM to generate a period-accurate background summary and caches it for future use. This happens transparently on first story generation for an unknown squadron.

---

## 📋 Campaign Service Record <a id="campaign-service-record"></a>

The **Campaign Service Record** is a web-based application that provides an elegant, read-only view of your pilot's career across all ongoing and completed campaigns. It presents your service history in a clean, professional format—ideal for reviewing achievements or sharing your combat record.

⚠️ **IMPORTANT**: The Campaign Service Record is not a standalone system. It operates exclusively in conjunction with the tracker and its associated files, which supply the required campaign data.

### Features

- **Campaign Overview**: Browse all campaigns you've flown, showing missions completed, promotions earned, and awards received
- **Detailed Service Record**: Click any campaign to view:
  - Complete mission history with debriefings
  - Chronological timeline of promotions and awards
  - Career statistics (air kills, ground kills, mission success rates)
  - Aircraft usage and performance breakdown
- **AI Story Chapters**: If AI stories are configured, each mission entry shows its generated narrative chapter alongside the debriefing
- **Pilot Profile**: Display and customize pilot name, photo, and personal information per campaign
- **Responsive Design**: Clean, modern interface that works on any screen size
- **Auto-Generated**: Automatically reads data from your Campaign Tracker files - no manual input required

### How to Use

1. Locate `Campaign_Service_Record.exe` in your Campaign Tracker installation directory (see Installation section above)
2. Double-click `Campaign_Service_Record.exe` to start the application
3. Your default web browser will open automatically and display your service record
4. Browse your campaigns and click on any campaign to view detailed statistics
5. The server will shut down automatically after 60 seconds of inactivity

**Note**: The Campaign Service Record requires data from the Campaign Tracker. You must run the Campaign Tracker at least once and complete at least one mission before campaigns will appear in the Service Record.

### Interface Overview

#### Landing Page

- **Left Panel**: Pilot information (photo, name, service overview)
- **Right Panel**: List of all campaigns with completed missions
  - Shows mission count, promotions earned, and awards received per campaign
  - Click any campaign to view detailed service record

#### Campaign Detail Page

- **Left Column**: Pilot information (Customizable photo & personal data), Chronological timeline of promotions and awards
- **Middle Column**: Career statistics including:
  - Total air and ground kills
  - Mission outcomes
  - Aircraft usage breakdown
  - and more
- **Right Column**: Mission debriefings with detailed combat results, and AI story chapters (if generated)
- **Back Button**: Return to campaign overview

**Per-Campaign Language**: The detail page can display in a different language than the global setting. This is configured in the Settings Manager under the Campaigns tab. When a campaign has a specific language override, the detail page (including debriefings) will display in that language, while the landing page remains in your global language.

### Customizing Pilot Information

Click on the pilot photo or name fields to customize:

- **Pilot Photo**: Click to upload a new photo (supports common image formats)
- **Personal Information**: Edit name, first name, birthday, birthplace and birth country
- All changes are saved automatically and persist across sessions

### Troubleshooting

#### Problem: "Loading campaigns..." appears forever

**Cause**: No campaign data available or JSON files are empty  
**Solution**:

- Ensure you have run the Campaign Tracker at least once
- Complete at least one mission in any campaign
- Check that your Campaign Tracker installation contains these files:
  - `campaign_completion_state.json`
  - `campaign_events.json`
  - `campaigns_decoded.json`
  - `campaign_mission_dates.json`

#### Problem: Campaign Service Record won't start

**Cause**: Port 5000 is already in use by another application  
**Solution**:

- Close any other web servers or applications using port 5000
- If the issue persists, restart your computer to free up the port

#### Problem: Browser shows "Cannot connect" or "Page not found"

**Cause**: The application server failed to start  
**Solution**:

- Check that both `Campaign_Service_Record.exe` and the `_internal` folder are present in the installation directory
- Ensure your antivirus is not blocking the application
- Try running `Campaign_Service_Record.exe` as administrator

#### Problem: Clicking a campaign shows "Failed to load campaign details"

**Cause**: Missing or corrupted campaign data  
**Solution**:

- Run the Campaign Tracker again to regenerate JSON files
- Ensure the campaign has at least one completed mission
- Check that campaign names in JSON files are consistent

#### Problem: Pilot photo won't upload

**Cause**: File format not supported or file is too large  
**Solution**:

- Use common image formats (JPG, PNG, BMP)
- Ensure image file is smaller than 5MB
- Try converting the image to PNG format

#### Problem: Application closes immediately after starting

**Cause**: The 60-second idle timeout may be too short, or browser didn't open  
**Solution**:

- Double-click `Campaign_Service_Record.exe` again
- Manually open your browser and navigate to `http://127.0.0.1:5000`
- Keep the browser tab active to prevent automatic shutdown

#### Problem: German awards and pictures don't show the swastika  

**Cause:**  
The Campaign Tracker does not support, endorse, or promote National Socialist ideology or symbols in any form.  
To comply with legal regulations in multiple countries and to respect community standards, swastikas and other related symbols have been removed from the default images shipped with this software.<br>

**Solution:**  
Users who require historically accurate imagery may replace the images locally:

- Replace award images in  
  `<path to IL-2 BoS>\data\swf\CampaignRanksAwards\Germany`
 
- Replace the German background and flag images in  
  `<tracker installation folder>\_internal\static\images\background_Germany.png`  
  `<tracker installation folder>\_internal\static\images\german_flag.png`  

⚠️ The original filenames and filetypes **must be preserved** after replacing the image content.

### Technical Information

- **Server Address**: `http://127.0.0.1:5000` (local machine only)
- **Auto-Shutdown**: Server automatically stops after 60 seconds of inactivity
- **Data Location**: Reads JSON files from the same directory as the executable
- **Browser Compatibility**: Works with all modern browsers (Chrome, Firefox, Edge)
- **Network**: Does not require internet connection; runs entirely on your local machine

---

## 🪖 Career Service Record <a id="career-service-record"></a>

The **Career Service Record** is a separate web-based application for IL-2's built-in **Career Mode** (not Campaign Mode). It reads your career data directly from the game's own `cp.db` SQLite database—no separate tracker or data files required. It presents your pilot's full service history across all theatres, including promotions, awards, missions, debriefings, combat statistics, and AI-generated story chapters.

⚠️ **IMPORTANT**: The Career Service Record requires IL-2 Sturmovik: Great Battles to be installed and at least one Career to have been started in-game. It reads the game's data files directly and does not depend on the Campaign Tracker files.

### Features

- **Theatre Chain Progression**: Displays the full chain of theatres your pilot has served in (e.g., Battle of Moscow → Battle of Stalingrad → Battle of Kursk), in correct chronological order
- **Career Events Timeline**: A chronological list of all career events pulled from the game database:
  - **Promotions** — each rank advancement with date and rank image
  - **Awards & Decorations** — medals earned with images and narratives
  - **Commander Appointments** — when your pilot was appointed squadron commander or deputy commander
  - **Squadron Transfers** — transfers between squadrons showing the source and destination unit
  - **Recovery / Medical Leave** — periods of injury recovery with start date, end date, and duration in days
- **Pilot Role Display**: If your pilot currently holds a command position, the role is shown next to the squadron name:
  - Commander (German: *Staffelkapitän*)
  - Deputy Commander (German: *Stellv. Staffelkapitän*)
- **Career Statistics**: Cumulative combat results read directly from the game pilot table:
  - PCP Score (Pilot Combat Points)
  - Air kills, ground kills, vehicle kills
  - Missions flown and mission outcomes
  - Aircraft usage with correctly resolved display names
- **Mission Debriefings**: Parses linked `missionReport` files and displays detailed debriefings per sortie — including mission type (e.g., Frontline Patrol, Escort Bombers), formation size and role, kills by category, and pilot outcome. Debriefings are cached and built in the background on first load.
- **AI Story Chapters**: When AI stories are configured, a narrative war-diary chapter is displayed alongside each mission debriefing (see [AI Story Generation](#ai-story-generation))
- **Career PDF Report**: Generate a printable PDF of your full career — includes per-mission kill tables, mission statistics, awards and promotions with full-size medal images, AI story chapters, and career-wide summary statistics. Triggered via the "Download PDF" button in the career detail page
- **Pilot Profile**: Customisable pilot photo, birth date, place of birth, and country of birth per career — persisted across sessions
- **German Award Style Selection**: Choose between the default 1957 Bundeswehr-era style and the original wartime style for German award images (configured in Settings Manager)
- **Responsive Design**: Clean, modern interface that works on any screen size
- **Fully Localised**: All UI text, event labels, and rank/award names respect your selected language. Each career can also display in a different language if configured
- **Database Consistency Correction**: At startup, the Career Service Record automatically reconciles kill rollup counters (`killLightPlane`, `killMediumPlane`, `killHeavyPlane`) for AI squadron pilots in `cp.db`, correcting a known game bug where the parent totals go stale

### How to Use

1. Locate `Career_Service_Record.exe` in your Campaign Tracker installation directory
2. Double-click `Career_Service_Record.exe` to start the application (or launch it from the **Control Center GUI**)
3. Your default web browser will open automatically and display your career overview
4. Click on any career to view the full service record with timeline, statistics, and debriefings
5. The server will shut down automatically after 60 seconds of inactivity

**Note**: The Career Service Record connects to the IL-2 game directory. If it cannot find the game's `cp.db`, ensure IL-2 is installed and that you have started at least one Career in-game.

### Interface Overview

#### Landing Page

- **Left Panel**: Pilot photo and service overview (career count, total missions, kill summary)
- **Right Panel**: List of all careers, each showing:
  - Pilot name, country, and rank
  - Theatre chain (e.g., "Battle of Moscow → Stalingrad")
  - Mission count, promotions earned, awards received

#### Career Detail Page

- **Left Column**: Pilot profile (customisable photo and personal data); chronological event timeline showing promotions, awards, appointments, transfers, and recovery periods
- **Middle Column**: Career statistics — PCP Score, kill breakdown (air, ground, vehicles), mission outcomes, and aircraft usage with proper display names
- **Right Column**: Mission debriefings with per-sortie kill details, flight time, mission type, formation details, and pilot outcome; AI story chapters displayed alongside each debriefing
- **Back Button**: Return to career overview

### Customising Pilot Information

Click the pilot photo or any editable field to customise:

- **Pilot Photo**: Click to upload a new photo (JPG, PNG, BMP supported)
- **Birth Date**: Enter in the format `DD Month YYYY` (e.g., `12 March 1918`)
- **Place of Birth**: Free-text entry
- **Country of Birth**: Free-text entry
- All changes are saved automatically and persist across sessions

### Troubleshooting

#### Problem: "Loading careers..." appears forever

**Cause**: Career database not found or no careers exist
**Solution**:

- Ensure IL-2 Sturmovik: Great Battles is installed
- Start at least one Career in the game before launching this application
- Confirm the game directory is set correctly (the Career Service Record auto-detects the IL-2 installation path from the Windows registry)

#### Problem: Career Service Record won't start

**Cause**: Port 5001 is already in use by another application
**Solution**:

- Close any other web servers or applications using port 5001
- If the issue persists, restart your computer to free up the port

#### Problem: Browser shows "Cannot connect" or "Page not found"

**Cause**: The application server failed to start
**Solution**:

- Check that both `Career_Service_Record.exe` and the `_internal` folder are present in the installation directory
- Ensure your antivirus is not blocking the application
- Try running `Career_Service_Record.exe` as administrator
- Manually open your browser and navigate to `http://127.0.0.1:5001`

#### Problem: Events or debriefings are missing

**Cause**: Mission report files have not been parsed yet (first load)
**Solution**:

- Wait a moment after opening the career detail page — debriefings are parsed in the background on first load
- Reload the page after a few seconds; a progress indicator will appear while parsing is in progress

#### Problem: AI story chapters are not appearing

**Cause**: AI Stories are not enabled or not configured
**Solution**:

- Open `IL2_Settings_Manager.exe` → AI Stories tab
- Confirm AI Stories is set to "Yes" and a valid API key and model are entered
- Click "Generate" in the Service Record UI, or enable Auto-Generate in Settings Manager

### Technical Information

- **Server Address**: `http://127.0.0.1:5001` (local machine only)
- **Auto-Shutdown**: Server automatically stops after 60 seconds of inactivity
- **Data Source**: Reads directly from `<IL-2 installation>\data\Career\cp.db`
- **Browser Compatibility**: Works with all modern browsers (Chrome, Firefox, Edge)
- **Network**: Does not require internet connection; runs entirely on your local machine (AI story generation requires an internet connection to reach the configured LLM provider)

---

## 📁 File Reference <a id="file-reference"></a>

### Configuration Files

|File|Purpose|User Editable|
|------|---------|---------------|
|`campaign_progress_config.yaml`|Ranks, awards, criteria, and settings|✅ Yes (or use Settings Manager)|
|`campaign_mission_dates.json`|Campaign metadata, mission dates, countries|⚠️ Careful (use Settings Manager for offsets)|
|`settings.json`|User preferences (language, AI story settings, etc.)|✅ Via Settings Manager|
|`locales/*.json`|Language translation files|⚠️ Advanced users only|

### Configuration Details

#### campaign_progress_config.yaml

This is the main configuration file containing:

```yaml
# Rank definitions per nation
ranks: 
  Germany:
    - name: Unteroffizier
      score: 0
      image: unteroffizier.png
    - name: Feldwebel
      score: 80
      image: feldwebel.png
    # ... more ranks

# Award definitions per nation
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
    # ... more awards

# General settings
settings:
  enable_popups: true

```

#### settings.json

Auto-generated on first run, contains user preferences:

```json
{
  "locale": "en",
  "stories": {
    "enabled": true,
    "provider": "openai",
    "api_keys": {
      "openai": "sk-..."
    },
    "model": "gpt-4o-mini",
    "auto_generate": false
  }
}
```

#### campaign_mission_dates.json

Auto-generated during first run, contains:

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
      }
    }
  }
}
```

### Data Files (Auto-Generated)

| File | Purpose | Location |
| ------ | --------- | ---------- |
| `campaigns_decoded.json` | Decoded campaign save data | Tracker folder |
| `campaign_popups_seen.json` | Tracks shown popups per campaign | Tracker folder |
| `campaign_events.json` | Generated events (promotions/awards) | Tracker folder |
| `campaign_completion_state.json` | Tracks mission completion between runs | Tracker folder |
| `settings.json` | User preferences (language, AI stories, etc.) | Tracker folder |

### Story Data Files (Auto-Generated)

| Location | Purpose |
| -------- | ------- |
| `%LOCALAPPDATA%\.il2_campaign_service_record\story_data\careers\<id>\memory.json` | Rolling narrative memory for a career |
| `%LOCALAPPDATA%\.il2_campaign_service_record\story_data\careers\<id>\chapters\*.json` | Story chapter files for a career |
| `%LOCALAPPDATA%\.il2_campaign_service_record\story_data\campaigns\<name>\memory.json` | Rolling narrative memory for a campaign |
| `%LOCALAPPDATA%\.il2_campaign_service_record\story_data\campaigns\<name>\chapters\*.json` | Story chapter files for a campaign |

### Backup Files

| File | Purpose | Location |
| ---- | ------- | -------- |
| `campaignsstates_[timestamp].backup` | Campaign save backup | IL-2 usersave folder |
| `popups_[timestamp].backup` | Popup state backup | IL-2 usersave folder |
| `campaignsstates_hash_index.json` | Backup index with hashes | IL-2 usersave folder |

### Output Files

| File | Purpose | Location |
| ---- | ------- | -------- |
| `[Campaign]_Report.pdf` | Career PDF report | `reports/` subfolder |

---

## 🔧 Troubleshooting <a id="troubleshooting"></a>

### Tracker Won't Start

| Problem | Solution |
| ------- | -------- |
| Missing `campaign_progress_config.yaml` | Ensure file is in same folder as EXE |
| Antivirus blocking | Add exception for tracker folder |
| Missing Visual C++ Runtime | Install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

### No Campaigns Detected

| Problem | Solution |
| ------- | -------- |
| Wrong folder selected | Re-run setup (delete `campaign_mission_dates.json`) |
| No missions flown yet | Start a campaign in IL-2, fly at least one mission |
| Permission issues | Run tracker as Administrator |

### Popups Not Appearing

| Problem | Solution |
| ------- | -------- |
| IL-2 not running | Popups only show while IL-2 is active |
| Already seen | Check `campaign_popups_seen.json` |
| Popups disabled | Check `enable_popups:  true` in config |

### PDF Generation Fails

| Problem | Solution |
| ------- | -------- |
| Missing dependencies | Ensure all required DLLs are present |
| PDF locked | Close the PDF if open in a viewer |
| Path too long | Move tracker to shorter path |

### Events Not Appearing In-Game

| Problem | Solution |
| ------- | -------- |
| IL-2 caches description | Restart IL-2 to see updated campaign description |
| Events written to wrong file | Check campaign country assignment |

### AI Story Generation Fails

| Problem | Solution |
| ------- | -------- |
| No API key configured | Open Settings Manager → AI Stories tab and enter your API key |
| Wrong model name | Check the provider's documentation for exact model IDs |
| Rate limit hit | Wait and try again, or switch to a different model |
| Custom endpoint unreachable | Verify the base URL is correct and the local server is running |

---

## ❓ FAQ <a id="faq"></a>

### Why is my custom campaign not detected / missions are not detected?

**A:** The tracker parses mission files to extract dates and metadata. To ensure your custom campaign is properly detected, follow these golden rules:

⚠️ *Important: English Locale Files Required for Reading*

The tracker only reads English locale files (`.eng` briefings and `info.locale=eng.txt`) to extract mission dates and campaign information. IL-2 stores the user's language preference internally, and we have no way to detect which language you're using in-game. Therefore:

- Every mission must have a corresponding `.eng` briefing file (e.g., `01.eng` for `01.Mission`)
- Your campaign folder must contain an `info.locale=eng.txt` file for the campaign description

Even if you play in another language, these English files must exist for the tracker to work. The tracker will not read `.ger`, `.rus`, `.fra` or other language files for date extraction.

ℹ️ *Multi-Language Output*

When writing Events and Debriefings back to your campaign, the tracker automatically updates **all** existing `info.locale=*.txt` files. Each file is written in its corresponding language:

- `info.locale=eng.txt` → English content
- `info.locale=ger.txt` → German content (Deutsch)
- `info.locale=fra.txt` → French content (Français)
- `info.locale=spa.txt` → Spanish content (Español)
- `info.locale=pol.txt` → Polish content (Polski)
- `info.locale=rus.txt` → Russian content (Русский)
- `info.locale=chs.txt` → Chinese content (简体中文)

See [Supported Languages](#supported-languages) for more details.

**Mission File Naming:**

- Use numeric prefixes for mission order: `01.Mission`, `02.Mission`, `03.Mission` or `1.Mission`, `2.Mission`, etc.
- Date-based naming also works: `1943-07-04.Mission`, `1943-07-04a.Mission`
- Supported extensions: `.Mission`, `.mission`, `.msnbin`

Mission Date Detection (in `.eng` briefing files):
The tracker looks for date information in this priority order:

1. `Date:` field in briefing (e.g., `Date: 4 November, 1943`)
2. `Time:` field for mission start time (e.g., `Time: 09:45`)
3. Filename if it contains a date (e.g., `1943-07-04.Mission`)

**Supported Date Formats:**

- `4 November, 1943` or `November 4, 1943`
- `4 November 1943` (no comma)
- `04.11.1943` or `11.04.1943` (DD.MM.YYYY or MM.DD.YYYY)
- `1943-07-04` (ISO format in filename)

**Campaign Folder Structure:**

```
Path to IL-2 BoS\data\Campaigns\YourCampaignName\
    ├── info.locale=eng.txt    (required for reading - campaign description)
    ├── info.locale=ger.txt    (optional - tracker writes German content here)
    ├── info.locale=fra.txt    (optional - tracker writes French content here)
    ├── info.locale=rus.txt    (optional - tracker writes Russian content here)
    ├── 01.Mission             (mission file)
    ├── 01.eng                 (required - English briefing with date/time)
    ├── 02.Mission
    ├── 02.eng                 (required - English briefing with date/time)
    └── ...
```

**Country Detection:**
The tracker auto-detects your country/faction from:

1. Aircraft names in mission files (e.g., bf109 → Germany, spitfire → Britain)
2. Unit names containing country identifiers
3. You can manually set/correct this in the Country Validator GUI on first run, or adjust it later manually in the `stock_campaigns.yaml`

**Common Issues:**

- Missing `.eng` briefing file → dates cannot be extracted (mission will still be tracked as "Mission 1", "Mission 2", etc. but without date information)
- Missing `info.locale=eng.txt` → campaign description unavailable, tracker cannot read campaign info
- Non-standard date format in briefing → use one of the supported formats above
- Special characters in campaign folder name → avoid umlauts or special symbols
- WW1 campaigns (Flying Circus) → excluded by default (see WW1 Detection & Exclusion section)

### Q: Can I run multiple instances of the tracker?

**A:** No.  Only one instance should monitor your campaigns at a time.

### Q: Does the tracker modify my IL-2 installation?

**A:** The tracker only modifies:

- Campaign `info.locale=eng.txt` files (adds Events section)
- Creates backup files in the usersave folder

It does **not** modify any game executables or core files.

### Q:  Will this work with mods?

**A:** Yes, as long as the mod uses standard campaign structure.  Custom campaigns are automatically detected during first-run setup.

### Q:  Can I manually edit the configuration?

**A:** Yes, but we recommend using the **Settings Manager** (`IL2_Settings_Manager.exe`) for most changes. It provides a user-friendly interface and automatically handles regeneration when needed.

For advanced customization, `campaign_progress_config.yaml` can be edited manually to:

- Adjust promotion score thresholds
- Modify award criteria
- Add custom awards
- Change rank scaling factors

> ⚠️ Always create a backup before manually editing configuration files.

### Q: How do I reset everything?

**A:** Delete these files and restart the tracker:

- `campaign_mission_dates.json`
- `campaign_popups_seen.json`
- `campaigns_decoded.json`
- `campaign_events.json`

### Q: Is multiplayer supported?

**A:** The tracker is designed for single-player career campaigns.  Multiplayer missions don't generate the same save data structure.

### Q:  Why do I need to restart IL-2 to see new events?

**A:** IL-2 loads the campaign description (`info.locale=eng.txt`) when the game starts and caches it in memory. Changes made by the tracker are written to the file but won't appear in-game until you restart IL-2. However, you'll still see **popups immediately** when you earn promotions or awards.

### Q: What happens if I delete a backup file manually?

**A:** The backup index (`campaignsstates_hash_index.json`) will still reference it, but the Restore GUI will skip any backups where the actual backup file is missing.

### Q: Can I use the tracker with Flying Circus (WWI)?

**A:** Flying Circus campaigns are detected and excluded by default. The tracker is designed for WWII campaigns and does not include WWI-era ranks or awards. You can control exclusions during the country validation step (WW1 "ignore" checkbox), but WW1 campaigns won't have historically accurate ranks or awards.

### Q: Can I use the tracker with Pat Wilson's Campaign Generator (PWCG)?

**A:** No - this tracker does NOT work with PWCG but also does NOT interfere with it.

### Q: Do I need an internet connection to use the tracker?

**A:** No — the tracker and both Service Records work entirely offline. An internet connection is only required when generating AI story chapters (to reach your configured LLM provider). All other features — monitoring, debriefings, promotions, awards, PDF reports, and the Service Record UI — work without an internet connection.

### Q: Which LLM model should I use for AI stories?

**A:** For OpenAI, `gpt-4o-mini` offers the best balance of quality and cost. For OpenRouter, `openai/gpt-4o-mini` is a solid default. For Anthropic, `claude-3-5-haiku-20241022` is fast and capable. Any model that reliably returns JSON and generates coherent prose of 150–400 words per response will work well.

### Q: How much does AI story generation cost?

**A:** Cost depends entirely on your provider and model. A typical career story chapter (180–380 words of output) uses around 1,500–3,000 tokens per mission. At `gpt-4o-mini` pricing (as of 2025), this is less than $0.01 per chapter. A full career of 100 missions would cost roughly $0.50–1.00 with that model.

---

## 📜 License

This project is provided as-is for personal use with IL-2 Sturmovik Great Battles.

---

## 🙏 Acknowledgments

- **1C Game Studios / 777 Studios** - For creating IL-2 Great Battles
- **The IL-2 Community** - For inspiration and feedback
- **Kraut1** - For giving useful input and comprehensive testing

---

## Happy flying!  ✈️🎖️
