# IL-2 Campaign Progress Tracker

A comprehensive tracking tool for IL-2 Sturmovik Great Battles single-player campaigns.  Automatically monitors your campaign progress, calculates promotions and awards based on historical criteria, generates detailed mission debriefings, and creates PDF reports of your pilot's career.

![Version](https://img.shields.io/badge/version-1.7-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-IL--2%20Great%20Battles-orange)

---

## 📋 Table of Contents

- [Features](#-features)
- [Supported Nations](#-supported-nations)
- [Installation](#-installation)
- [First Run Setup](#-first-run-setup)
- [WW1 Detection & Exclusion](#-ww1-detection--exclusion)
- [How It Works](#-how-it-works)
- [Promotions & Awards System](#-promotions--awards-system)
- [Mission Debriefings](#-mission-debriefings)
- [Backup & Restore System](#-backup--restore-system)
- [Mission Cleanup](#-mission-cleanup)
- [File Reference](#-file-reference)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Automatic Monitoring** | Watches your campaign save file and updates in real-time |
| **Promotions** | Calculates rank promotions based on accumulated score |
| **Awards & Decorations** | Grants medals based on kills, missions flown, and other criteria |
| **Real-time Popups** | Shows promotion and award notifications while playing |
| **Mission Debriefings** | Parses mission logs to generate detailed flight reports |
| **PDF Reports** | Creates printable career summaries with combat statistics |
| **Backup System** | Creates backups when removing incomplete missions via cleanup tool |
| **Restore Function** | Easy GUI to restore previous campaign states |
| **Mission Cleanup** | Removes incomplete missions that weren't properly finished |
| **Multi-Campaign Support** | Tracks multiple campaigns simultaneously |
| **WW1 Detection & Exclusion** | Detects Flying Circus (WW1) campaigns and skips them by default |

---

## 🌍 Supported Nations

The tracker includes historically accurate ranks and awards for: 

| Nation | Ranks | Awards |
|--------|-------|--------|
| 🇩🇪 **Germany** | Unteroffizier → Generalleutnant | Iron Cross, Knight's Cross, etc. |
| 🇷🇺 **Soviet Union** | Sergeant → Lieutenant General | Order of the Red Banner, Hero of the Soviet Union, etc. |
| 🇺🇸 **USA** | First Sergeant → Major General | Distinguished Flying Cross, Medal of Honor, etc.  |
| 🇬🇧 **Britain** | Sergeant → Air Vice Marshal | Distinguished Flying Cross, Victoria Cross, etc. |

> **Note 1:** Soviet ranks automatically switch between early (pre-1943) and late (post-January 6, 1943) insignia based on mission dates.  

> **Note 2:** The German awards shown are based on the official 1957 reissue versions. If you wish to customize their appearance, you can replace the images located in `CampaignRanksAwards\Germany`. 

⚠️ Important: Keep the original filenames when replacing images — for example,
`iron_cross_2nd.dds` and `iron_cross_2nd_big.dds` must retain the exact same names after replacement.
            

---

## 📥 Installation

1. **Download** the latest release (`IL2_Campaign_Tracker_v2.0.zip`)
2. **Extract** to a folder of your choice (e.g., `C:IL2_Campaign_Tracker_v2.0`)
3. **Copy** the extracted `CampaignRanksAwards` folder to <path to game>\data\swf
Before proceeding to step 4:
**WARNING** **IMPORTANT** 
The tracker can monitor **only** campaigns located in `<Path to Il-2 BoS>\data\campaigns`. Standard IL-2 campaigns are not stored directly in this folder; instead, they are run internally from `<Path to Il-2 BoS>\data\campaigns`. As a result, these campaigns must be extracted before they can be tracked (see **Step 4**). 
**DANGER** **IMPORTANT** 
If you have modified missions belonging to a standard campaign, proceed with extreme caution when copying extracted files from `campaigns.gtp` into the `<Path to Il-2 BoS>\data\campaigns` folder. Existing files will be **overwritten**, and any custom mission modifications will be replaced by the original out-of-the-box versions.
4. **OPTIONAL: Extract** Campaigns.gtp (standard IL-2 BoS campaigns) from `<Path to Il-2 BoS>\data` with the help of unGTP-IL2 (download it here https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip). Put the `unGTP-IL2.exe` in `<Path to Il-2 BoS>\data`.
   Drag `Campaigns.gtp` onto `unGTP-IL2.exe`. Ignore the error warning in the cmd-window (don't worry - everything has beed extracted). Goto `<Path to Il-2 BoS>\data\(null)\campaigns`. 
   **Copy** the campaigns folder to `<Path to Il-2 BoS>\data`.   
   **WARNING** **IMPORTANT** Only campaigns in `<Path to Il-2 BoS>\data\campaigns` can be monitored by the tracker. Standard IL-2 campaigns aren't explicitly in the `<Path to Il-2 BoS>\data\campaigns` folder (the game runs them internally from the campaigns.gtp) and therefore need to be extracted (see step 4). 
**DANGER** **IMPORTANT** If you modified a mission of a standard campaign file, be careful when copying the extracted files from the campaigns.gtp to the `<Path to Il-2 BoS>\data\campaigns` folder. They will be overwritten and your modified mission(s) will be replaced by the out-of-the-box mission.
5. **Run** `IL2_Campaign_Tracker_v2.0.exe`

### PDF Requirements

PDF export uses `pdfkit`, which requires `wkhtmltopdf` to be installed or bundled. If `wkhtmltopdf` is missing, PDF export is skipped (see `step3_generate_events.py`) and the tracker continues without generating PDFs. You can install `wkhtmltopdf` from the official site: https://wkhtmltopdf.org/downloads.html.

**Packaged EXE:** The PyInstaller build is configured to bundle `wkhtmltopdf.exe` when available during the build. If it is not bundled, the tracker expects `wkhtmltopdf` to be available on your system `PATH`.

### Required Files

Ensure these files are in the same folder as the executable:

```
IL2_Campaign_Tracker_v2.0/
├── IL2_Campaign_Tracker_v2.0.exe        # Main executable
├── mlg2txt.exe                          # Helper-exe for decoding missionreports (mlg files)
├── campaign_progress_config.yaml        # Ranks & awards configuration
├── stock_campaigns.yaml                 # Campaign to Country allocation 
├── object_categories.yaml               # Needed for mission debriefing
└──(other files created automatically on first run)
```

---

## 🚀 First Run Setup

When you start the tracker for the first time, a setup wizard guides you through the configuration:

### Step 1: Select Game Directory

A folder browser opens.  Navigate to your IL-2 installation folder: 

```
Example: C:\Program Files (x86)\Steam\steamapps\common\IL-2 Sturmovik Battle of Stalingrad
```

> **Important:** Select the main game folder, NOT the `data\Campaigns` subfolder. 

### Step 2: Country Validation

The tracker scans all installed campaigns and attempts to detect the correct country for each.  A validation GUI appears where you can:

- ✅ Confirm automatically detected countries
- ✏️ Correct any misidentified campaigns
- 🚫 Exclude WW1 (Flying Circus) campaigns

This is important because promotions and awards are nation-specific.

### WW1 (Flying Circus) Detection

If the tracker detects Flying Circus campaigns, you can - or better should - mark them as **WW1 (ignore)** in this screen so they are excluded from tracking.

### Step 3: Ready to Track

After setup, the tracker: 
1. Decodes your current campaign save file
2. Generates initial events (existing promotions/awards)
3. Starts monitoring for changes

---

## 🪖 WW1 Detection & Exclusion

Flying Circus (WW1) campaigns are detected and excluded by default because the tracker only includes WWII ranks, awards, and debriefing logic.

**Detection signals include:**
- Mission dates in the 1914–1918 range
- WW1 aircraft keywords in campaign data
- “Flying Circus”/WW1 keywords in campaign descriptions

**How exclusion works:**
- Excluded campaigns are skipped during decoding and event generation.
- The exclusion reason is stored in `campaign_mission_dates.json` so the tracker consistently ignores them.
- You can review or change exclusions by re-running setup (delete `campaign_mission_dates.json`) and using the **WW1 (ignore)** checkbox in the country validation GUI.

---

## ⚙️ How It Works

### Monitoring Loop

```
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
│                          ↓                              │
│   5. Parse mission log for debriefing                   │
│                          ↓                              │
│   6. Show popups for new events                         │
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

## 🎖️ Promotions & Awards System

### How Promotions Work

Promotions are based on **accumulated score** across all completed missions (the score value comes from the campaignsstates.txt and is calculated by IL-2 BoS internal rules):

```
Score Earned = Mission Score × Rank Scaling Factor
```

**Rank Scaling Factor** adjusts requirements based on campaign length (can be editited in `campaign_progress_config.yaml`) :
"1-10":    1.00   # Short campaigns (stock campaigns)
"11-20":   1.15   # Medium-short campaigns  
"21-30":   1.30   # Medium campaigns
"31-40":   1.50   # Medium-long campaigns
"41-50":   1.75   # Long campaigns
"51-70":   2.00   # Very long campaigns
"71+":     2.50   # Epic campaigns (70+ missions)

This prevents rapid promotions in long campaigns while ensuring fair progression in short ones.

### How Awards Work

Awards are granted based on various criteria defined in `campaign_progress_config.yaml` and are derived from the career mode in IL-2 BoS.
All conditions for awards are `OR` conditions:

| Criteria Type | Example |
|---------------|---------|
| **Cumulative Kills** | 8 air combat score → Iron Cross 1st Class |
| **Single Mission** | 7 kills in one sortie → Medal of Honor |
| **Missions Completed** | 15 missions → Order of the Red Star |
| **Wounded in Action** | Pilot damage > 20% → Wound Badge |
| **Random + Threshold** | High kills + luck factor → Rare decorations |

Some awards have **prerequisites** (e.g., must have Iron Cross 2nd Class before 1st Class) and **mutual exclusivity** (e.g., cannot earn both wound stripe variants on same mission).

### Starting Rank Offset

Some campaigns can start with higher ranks.  This is configurable per-campaign in `campaign_mission_dates.json`:

```json
"kerch": {
  "country": "Germany",
  "starting_rank_offset": 2, --> change this number (default = 0, starting at the lowest rank)
  "missions": { ...  }
}
```

---

## 📊 Mission Debriefings

### Data Source

Debriefing data is extracted from IL-2's **mission log files** (`.mlg` files):

```
Location: [IL-2 Directory]\data\FlightLogs\[mission].mlg
```

These binary files contain detailed records of everything that happened during the mission. 
These binary files are "translated" by `mlg2txt.exe into` a *.txt file and is then further processed.

### What's Tracked

| Category | Details |
|----------|---------|
| **Flight Time** | Takeoff to landing duration |
| **Kills** | Air, ground, and naval targets with timestamps |
| **Damage Taken** | Hits received, from whom, damage percentage |
| **Pilot Status** | Healthy, wounded, killed, captured |
| **Status** | Landed, Landed (wounded), Hard Landing, Hard Landing (wounded), Bailout, Bailout (wounded), KIA/MIA |

### Debriefing Output

Each mission generates detailed output in two formats:

1. **In-Game (Flight Log)** - Chronological list of events written to the campaign's `info.locale=eng.txt`
2. **PDF Report** - Detailed kill breakdown by category matching the in-game results screen

---

## 💾 Backup & Restore System

### When Backups Are Created

Backups are **only** created when you remove incomplete missions via the Mission Cleanup tool.  They are **not** created automatically after every mission.

This ensures you can restore your campaign to the state **before** you removed any missions.

## 🧹 Mission Cleanup

### What is takeoffStatus?

IL-2 tracks mission completion with a `takeoffStatus` flag:

| Value | Meaning |
|-------|---------|
| `takeoffStatus=1` | Mission started but not completed properly |
| `takeoffStatus=2` | Mission completed successfully |

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

```
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


### Restore GUI

When the tracker starts and backups are available, a restore GUI may appear:

```
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
│  │ 2024-01-14 20:45:11  │                  │ ✗ No    | │
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

```
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


## 📁 File Reference

### Configuration Files

| File | Purpose | User Editable |
|------|---------|---------------|
| `campaign_progress_config.yaml` | Ranks, awards, criteria, and settings | ✅ Yes |
| `campaign_mission_dates.json` | Campaign metadata, mission dates, countries | ⚠️ Careful |

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
|------|---------|----------|
| `campaigns_decoded.json` | Decoded campaign save data | Tracker folder |
| `campaign_popups_seen.json` | Tracks shown popups per campaign | Tracker folder |
| `campaign_events.json` | Generated events (promotions/awards) | Tracker folder |
| `campaign_completion_state.json` | Tracks mission completion between runs | Tracker folder |

### Backup Files

| File | Purpose | Location |
|------|---------|----------|
| `campaignsstates_[timestamp].backup` | Campaign save backup | IL-2 usersave folder |
| `popups_[timestamp].backup` | Popup state backup | IL-2 usersave folder |
| `campaignsstates_hash_index.json` | Backup index with hashes | IL-2 usersave folder |

### Output Files

| File | Purpose | Location |
|------|---------|----------|
| `[Campaign]_Report.pdf` | Career PDF report | `reports/` subfolder |

---

## 🔧 Troubleshooting

### Tracker Won't Start

| Problem | Solution |
|---------|----------|
| Missing `campaign_progress_config.yaml` | Ensure file is in same folder as EXE |
| Antivirus blocking | Add exception for tracker folder |
| Missing Visual C++ Runtime | Install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

### No Campaigns Detected

| Problem | Solution |
|---------|----------|
| Wrong folder selected | Re-run setup (delete `campaign_mission_dates.json`) |
| No missions flown yet | Start a campaign in IL-2, fly at least one mission |
| Permission issues | Run tracker as Administrator |

### Popups Not Appearing

| Problem | Solution |
|---------|----------|
| IL-2 not running | Popups only show while IL-2 is active |
| Already seen | Check `campaign_popups_seen.json` |
| Popups disabled | Check `enable_popups:  true` in config |

### PDF Generation Fails

| Problem | Solution |
|---------|----------|
| Missing dependencies | Ensure all required DLLs are present |
| PDF locked | Close the PDF if open in a viewer |
| Path too long | Move tracker to shorter path |

### Events Not Appearing In-Game

| Problem | Solution |
|---------|----------|
| IL-2 caches description | Restart IL-2 to see updated campaign description |
| Events written to wrong file | Check campaign country assignment |

---

## ❓ FAQ

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

*Happy flying!  ✈️🎖️*
