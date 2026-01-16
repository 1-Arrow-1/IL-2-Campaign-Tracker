# IL-2 Campaign Progress Tracker

A comprehensive tracking tool for IL-2 Sturmovik Great Battles single-player **WW2 campaigns**.  Automatically monitors your campaign progress, calculates promotions and awards based on historical criteria, generates detailed mission debriefings, and creates PDF reports of your pilot's career.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-IL--2%20Battle%20of%20Stalingrad-orange)

---

## 📋 Table of Contents

- [Features](#features)
- [Supported Nations](#supported-nations)
- [Installation (manual)](#installation_manual)
- [Installation via IL2_CampaignTracker_Setup_v2.0.exe](#installation_exe)
- [First Run Setup](#first-run-setup)
- [WW1 Detection & Exclusion](#ww1-detection--exclusion)
- [How It Works](#how-it-works)
- [Promotions & Awards System](#promotions--awards-system)
- [Mission Debriefings](#mission-debriefings)
- [Mission Cleanup](#mission-cleanup)
- [Backup & Restore System](#backup--restore-system)
- [Campaign Service Record](#camapign-service-record)
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
| **Mission Cleanup** | Removes incomplete missions that weren't properly finished |
| **Backup System** | Creates backups when removing incomplete missions via cleanup tool |
| **Restore Function** | Easy GUI to restore previous campaign states |
| **Multi-Campaign Support** | Tracks multiple campaigns simultaneously |
| **WW1 Detection & Exclusion** | Detects Flying Circus (WW1) campaigns and skips them by default |

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

## 📥 Installation (manual) <a id="installation_manual"></a>

1. **Download** the latest release (`IL2_Campaign_Tracker_v2.0.zip`)

2. **Extract** to a folder of your choice (e.g., `C:IL2_Campaign_Tracker_v2.0`)

3. **Copy** the extracted `CampaignRanksAwards` folder to `<Path to IL-2 BoS>\data\swf`<br>

Before proceeding to the **optional** step 4:  

⚠️ **IMPORTANT**
The tracker can monitor **only** campaigns located in `<Path to Il-2 BoS>\data\campaigns`. Standard IL-2 campaigns are not stored directly in this folder; instead, they are run internally from `campaigns.gtp`. As a result, these campaigns must be extracted before they can be tracked (see **Step 4**).

🚨 **IMPORTANT**
If you have modified missions belonging to a standard official campaign, proceed with extreme caution when copying extracted files from `campaigns.gtp` into the `<Path to Il-2 BoS>\data\campaigns` folder. Existing files will be **overwritten**, and any custom mission modifications will be replaced by the original out-of-the-box versions.  

ℹ️ 4.  **OPTIONAL:**  
Note: The intention of the extraction of the standard official campaigns is ONLY to make them usable for the Campaign Tracker. Please do not change the official campaigns.  

- **Extract** Campaigns.gtp (standard IL-2 BoS campaigns) from `<Path to Il-2 BoS>\data` with the help of unGTP-IL2 (download it here: <https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip>).
- **Unzip & Move** the `unGTP-IL2.exe` to `<Path to Il-2 BoS>\data`.  
- **Drag** `Campaigns.gtp` onto `unGTP-IL2.exe`. Ignore the error warning in the cmd-window at the end (don't worry - everything has beed extracted).  
- **Goto** `<Path to Il-2 BoS>\data\(null)\campaigns`.  
- **Copy** the subfolders of `<Path to Il-2 BoS>\data\(null)\campaigns` to `<Path to Il-2 BoS>\data\campaigns`  

1. **Run** `IL2_Campaign_Tracker_v2.0.exe` from your Tracker installation directory.

ℹ️ **NOTE**: By default, the tracker shuts down automatically when IL-2 BoS is closed. To continue using the tracker, you must either restart it manually or configure a Windows Task Scheduler task to launch it automatically when Windows starts.

A general setup guide can be found here:
<https://forum.il2-series.com/topic/772-expanded-career-rank-mod/#findComment-4176>

Please adjust the executable names and file paths according to your local installation.

### PDF Requirements

PDF export uses `pdfkit`, which requires `wkhtmltopdf` to be installed or bundled. If `wkhtmltopdf` is missing, PDF export is skipped (see `step3_generate_events.py`) and the tracker continues without generating PDFs. You can install `wkhtmltopdf` from the official site: <https://wkhtmltopdf.org/downloads.html>.

**Packaged EXE:** The PyInstaller build is configured to bundle `wkhtmltopdf.exe` when available during the build. If it is not bundled, the tracker expects `wkhtmltopdf` to be available on your system `PATH`.

### Required Files

Ensure these files are in the same folder as the executable:

```text
IL2_Campaign_Tracker_v2.0/
├── IL2_Campaign_Tracker_v2.0.exe        # Main executable
├── mlg2txt.exe                          # Helper-exe for decoding missionreports (mlg files)
├── campaign_progress_config.yaml        # Ranks & awards configuration
├── stock_campaigns.yaml                 # Campaign to Country allocation 
├── object_categories.yaml               # Needed for mission debriefing
├── Campaign_Service_Record.exe          # Main executable for the Service Record
├── _internal (folder)                   # Needed for the Service Record (contains images, css, js, etc.)
└──(other files created automatically on first run)
```

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

**Uninstall**

1. **Delete** the tracker folder manually
2. **Delete** the folder `<Path to IL-2 BoS>\data\swf\CampaignRanksAwards` manually
3. **Delete** the following files (if existent) from your IL-2 usersave folder `<Path to IL-2 BoS>\data\swf\usersave\{UUID}\campaign` (if you want to remove all tracker data):
   - `campaignsstates_hash_index.json`
   - `campaignsstates_[timestamp].backup` (all backup files)
   - `popups_[timestamp].backup` (all popup state backups)  

⚠️ NOTE: All in-game debriefings and events will still remain in your campaign files `info.locale=[language].txt`. You will need to remove their content manually if you want to revert to the original state.

---

## 🪖 WW1 Detection & Exclusion <a id="ww1-detection--exclusion"></a>

Flying Circus (WW1) campaigns are detected and excluded by default because the tracker only includes WWII ranks, awards, and debriefing logic.

**Detection signals include:**

- Mission dates in the 1914–1918 range
- WW1 aircraft keywords in campaign data
- “Flying Circus”/WW1 keywords in campaign descriptions

**How exclusion works:**

- Excluded campaigns are skipped during decoding and event generation.
- The exclusion reason is stored in `campaign_mission_dates.json` so the tracker consistently ignores them.
- You can review or change exclusions by re-running setup (delete `campaign_mission_dates.json` and the respective entry in the `stock_campaigns.yaml`) and using the **WW1 (ignore)** checkbox in the country validation GUI.

---

## 📥 Installation via IL2_CampaignTracker_Setup_v2.0.exe (RECOMMENDED) <a id="installation_exe"></a>

1. **Download** the latest release (`IL2_CampaignTracker_Setup_v2.0.zip`)

2. **Extract** the `zip` file

3. **Run** the extracted `IL2_CampaignTracker_Setup_v2.0.exe`

4. **Follow** the installation instructions in the setup wizard

5. **Run** `IL2_Campaign_Tracker_v2.0.exe` from Tracker installation path.

ℹ️ Rest of the setup is the same as the manual installation method. You will have addional files:

- `unins000.exe` - uninstaller
- `unins000.dat` - uninstaller data
- `cleanup_tracker_content.exe` - helper for `unins000.exe` (removes all tracker generated content from in-game debriefings/events)

**Uninstall**

1. **Run** `unins000.exe` from Tracker installation path. 🚨 **DO NOT RUN** `cleanup_tracker_content.exe` directly.

2. **Follow** the uninstallation instructions in the wizard.

ℹ️ **NOTE:** All in-game debriefings and events will be removed, and the original info-locale=[language].txt files will be restored to their out-of-the-box state.

If you choose to keep the configuration files during uninstallation and later reinstall the tracker into the same folder, those files will not be overwritten. Your previously saved configuration will be retained.

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
│   9. Return to monitoring                               │
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

**Rank Scaling Factor** adjusts requirements based on campaign length (can be editited in `campaign_progress_config.yaml`):  

"1-10":    1.00   # Short campaigns (stock campaigns)  
"11-20":   1.15   # Medium-short campaigns  
"21-30":   1.30   # Medium campaigns  
"31-40":   1.50   # Medium-long campaigns  
"41-50":   1.75   # Long campaigns  
"51-70":   2.00   # Very long campaigns  
"71+":     5.50   # Epic campaigns (70+ missions)

This prevents rapid promotions in long campaigns while ensuring fair progression in short ones.  

ℹ️ **Example:** In a 24-mission campaign, the scaling factor is 1.3, so a rank requiring 1000 points would need  1300 actual points (1000 x 1.30) to achieve.  
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

Campaigns can start with higher ranks (if you want to).  This is configurable per-campaign in `campaign_mission_dates.json`:

```json
"kerch": {
  "country": "Germany",
  "starting_rank_offset": 2, --> change this number (default = 0, starting at the lowest rank)
  "missions": { ...  }
}
```

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

1. **In-Game (Flight Log)** - Chronological list of events written to the campaign's `info.locale=eng.txt`
2. **PDF Report** - Detailed kill breakdown by category matching the in-game results screen

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

## 📋 Campaign Service Record <a id="camapign-service-record"></a>

The **Campaign Service Record** is a web-based application that provides an elegant, read-only view of your pilot’s career across all ongoing and completed campaigns. It presents your service history in a clean, professional format—ideal for reviewing achievements or sharing your combat record.

⚠️ **IMPORTANT**: The Campaign Service Record is not a standalone system. It operates exclusively in conjunction with the tracker and its associated files, which supply the required campaign data.

### Features

- **Campaign Overview**: Browse all campaigns you've flown, showing missions completed, promotions earned, and awards received
- **Detailed Service Record**: Click any campaign to view:
  - Complete mission history with debriefings
  - Chronological timeline of promotions and awards
  - Career statistics (air kills, ground kills, mission success rates)
  - Aircraft usage and performance breakdown
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
- **Right Column**: Mission debriefings with detailed combat results
- **Back Button**: Return to campaign overview

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

**Cause**: I do not support, endorse, or promote National Socialist ideology or symbols in any form.
**Solution**: Exchange awards pictures in the `<path to IL-2 BoS>\data\swf\CampaignRanksAwards\Germany`. Make sure to keep the exact filename after replacing the image content.
Exchange German flag and background picture in `<tracker installation folder>\_internal\static\images\background_Germany.png` and `<tracker installation folder>\_internal\static\images\german_flag_png`. Also make sure here to keep the exact filename after changing the image content.

### Technical Information

- **Server Address**: `http://127.0.0.1:5000` (local machine only)
- **Auto-Shutdown**: Server automatically stops after 60 seconds of inactivity
- **Data Location**: Reads JSON files from the same directory as the executable
- **Browser Compatibility**: Works with all modern browsers (Chrome, Firefox, Edge)
- **Network**: Does not require internet connection; runs entirely on your local machine

---

## 📁 File Reference <a id="file-reference"></a>

### Configuration Files

|File|Purpose|User Editable|
|------|---------|---------------|
|`campaign_progress_config.yaml`|Ranks, awards, criteria, and settings|✅ Yes|
|`campaign_mission_dates.json`|Campaign metadata, mission dates, countries|⚠️ Careful|

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

#### campaign_mission_dates.json

Auto-generated during first run, contains:

```json
{
  "kerch": {
    "campaign_name": "kerch",
    "country": "Germany",
    "is_stock": true, --> Standard IL-2 BoS campaign        
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

### Data Files (Auto-Generated)

| File | Purpose | Location |
| ------ | --------- | ---------- |
| `campaigns_decoded.json` | Decoded campaign save data | Tracker folder |
| `campaign_popups_seen.json` | Tracks shown popups per campaign | Tracker folder |
| `campaign_events.json` | Generated events (promotions/awards) | Tracker folder |
| `campaign_completion_state.json` | Tracks mission completion between runs | Tracker folder |

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

---

## ❓ FAQ <a id="faq"></a>

### Why is my custom campaign not detected / missions are not detected?

**A:** The tracker parses mission files to extract dates and metadata. To ensure your custom campaign is properly detected, follow these golden rules:

⚠️ *Important: English Locale Files Required for Reading*

The tracker only reads English locale files (`.eng` briefings and `info.locale=eng.txt`) to extract mission dates and campaign information. IL-2 stores the user's language preference internally, and we have no way to detect which language you're using in-game. Therefore:

- Every mission must have a corresponding .eng briefing file (e.g., `01.eng` for `01.Mission`)
- Your campaign folder must contain an `info.locale=eng.txt` file for the campaign description

Even if you play in another language, these English files must exist for the tracker to work. The tracker will not read `.ger`, `.rus`, `.fra` or other language files.

Note: When writing Events and Debriefings back to your campaign, the tracker automatically updates all existing `info.locale=*.txt`

⚠️ *Important: All Debriefings/Events are in English, independent of your in-game chosen language. NO multi-language support yet*

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

`Path to IL-2 Bos\data\Campaigns\YourCampaignName\`  
    ├── `info.locale=eng.txt`    (required for reading - campaign description)  
    ├── `info.locale=ger.txt`    (optional - tracker will also write here if present)  
    ├── `info.locale=rus.txt`    (optional - tracker will also write here if present)  
    ├── `01.Mission`             (mission file)  
    ├── `01.eng`                 (required - English briefing with date/time)  
    ├── `02.Mission`  
    ├── `02.eng`                 (required - English briefing with date/time)  
    └── ...  

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
- WW1 campaigns (Flying Circus) → excluded by default for IL-2 campaigns (see WW1 Detection & Exclusion section)

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

**A:** Yes!  `campaign_progress_config.yaml` can be edited to:

- Adjust promotion score thresholds
- Modify award criteria
- Add custom awards
- Change rank scaling factors

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

**A:** Flying Circus campaigns are detected and excluded by default. The tracker is designed for WWII campaigns and does not include WWI-era ranks or awards. You can control exclusions during the country validation step (WW1 “ignore” checkbox), but WW1 campaigns won’t have historically accurate ranks or awards.

### Q: Can I use the tracker Pat Wilson's Campaing Generator (PWCG)?

**A:** No - this tracker does NOT work wit PWCG but also does NOT interfere with it

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
