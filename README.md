# IL-2 Campaign Progress Tracker

A comprehensive tracking tool for IL-2 Sturmovik Great Battles career campaigns.  Automatically monitors your campaign progress, calculates promotions and awards based on historical criteria, generates detailed mission debriefings, and creates PDF reports of your pilot's career.

![Version](https://img.shields.io/badge/version-1.7-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-IL--2%20Great%20Battles-orange)

---

## 📋 Table of Contents

- [Features](#-features)
- [Supported Nations](#-supported-nations)
- [Installation](#-installation)
- [First Run Setup](#-first-run-setup)
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

---

## 🌍 Supported Nations

The tracker includes historically accurate ranks and awards for: 

| Nation | Ranks | Awards |
|--------|-------|--------|
| 🇩🇪 **Germany** | Unteroffizier → Generalfeldmarschall | Iron Cross, Knight's Cross, etc. |
| 🇷🇺 **Soviet Union** | Сержант → Генерал-лейтенант | Order of the Red Banner, Hero of the Soviet Union, etc. |
| 🇺🇸 **USA** | Flight Officer → Major General | Distinguished Flying Cross, Medal of Honor, etc.  |
| 🇬🇧 **Britain** | Pilot Officer → Air Vice Marshal | Distinguished Flying Cross, Victoria Cross, etc. |

> **Note:** Soviet ranks automatically switch between early (pre-1943) and late (post-January 6, 1943) insignia based on mission dates.

---

## 📥 Installation

1. **Download** the latest release (`IL2_Campaign_Tracker. zip`)
2. **Extract** to a folder of your choice (e.g., `C:\IL2_Tracker`)
3. **Run** `IL2_Campaign_Tracker.exe`

### Required Files

Ensure these files are in the same folder as the executable:

```
IL2_Campaign_Tracker/
├── IL2_Campaign_Tracker.exe        # Main executable
├── campaign_progress_config.yaml   # Ranks & awards configuration
└── (other files created automatically on first run)
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
- 🚫 Exclude campaigns (e.g., WWI Flying Circus campaigns)

This is important because promotions and awards are nation-specific.

### Step 3: Ready to Track

After setup, the tracker: 
1. Decodes your current campaign save file
2. Generates initial events (existing promotions/awards)
3. Starts monitoring for changes

---

## ⚙️ How It Works

### Monitoring Loop

```
┌─────────────────────────────────────────────────────────┐
│                    TRACKER RUNNING                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   1. Watch campaignsstates.txt for changes               │
│                          ↓                               │
│   2.  Detect file modification (mission completed)        │
│                          ↓                               │
│   3. Decode campaign save file                           │
│                          ↓                               │
│   4. Calculate new promotions/awards                     │
│                          ↓                               │
│   5. Parse mission log for debriefing                    │
│                          ↓                               │
│   6. Show popups for new events                          │
│                          ↓                               │
│   7. Update campaign info file                           │
│                          ↓                               │
│   8. Generate PDF report                                 │
│                          ↓                               │
│   9. Return to monitoring                                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Real-time Popups

When you earn a promotion or award, a popup notification appears on screen:

- 🎖️ Shows the rank insignia or medal image
- 📅 Displays the date earned
- ⏱️ Auto-dismisses after 5 seconds (click to dismiss immediately)

> **Note:** Popups only appear while IL-2 is running to avoid interruptions during other activities.

---

## 🎖️ Promotions & Awards System

### How Promotions Work

Promotions are based on **accumulated score** across all completed missions:

```
Score Earned = Mission Score × Rank Scaling Factor
```

**Rank Scaling Factor** adjusts requirements based on campaign length:
- Short campaigns (1-10 missions): 1.0x (normal)
- Medium campaigns (11-30 missions): 1.5x (higher requirements)
- Long campaigns (31+ missions): 2.0x (highest requirements)

This prevents rapid promotions in long campaigns while ensuring fair progression in short ones.

### How Awards Work

Awards are granted based on various criteria defined in `campaign_progress_config.yaml`:

| Criteria Type | Example |
|---------------|---------|
| **Cumulative Kills** | 10+ air victories → Iron Cross 2nd Class |
| **Single Mission** | 5 kills in one sortie → Knight's Cross |
| **Flight Time** | 50+ hours → Long Service Medal |
| **Missions Completed** | 30 missions → Campaign Medal |
| **Wounded in Action** | Pilot damage > 20% → Wound Badge |
| **Random + Threshold** | High kills + luck factor → Rare decorations |

Some awards have **prerequisites** (e.g., must have Iron Cross 2nd Class before 1st Class) and **mutual exclusivity** (e.g., cannot earn both wound stripe variants on same mission).

### Starting Rank Offset

Some campaigns start with higher ranks.  This is configured per-campaign in `campaign_mission_dates.json`:

```json
"kerch": {
  "country": "Germany",
  "starting_rank_offset": 2,
  "missions": { ...  }
}
```

---

## 📊 Mission Debriefings

### Data Source

Debriefing data is extracted from IL-2's **mission log files** (`.mlg` files):

```
Location: [IL-2 Directory]\data\mlg\[username]\[mission]. mlg
```

These binary files contain detailed records of everything that happened during the mission. 

### What's Tracked

| Category | Details |
|----------|---------|
| **Flight Time** | Takeoff to landing duration |
| **Kills** | Air, ground, and naval targets with timestamps |
| **Damage Taken** | Hits received, from whom, damage percentage |
| **Pilot Status** | Healthy, wounded, killed, captured |
| **Aircraft Status** | Landed safely, crash landed, destroyed |
| **Ammunition** | Rounds fired, bombs dropped, rockets launched |

### Debriefing Output

Each mission generates detailed output in two formats:

1. **In-Game (Flight Log)** - Chronological list of events written to the campaign's `info.locale=eng. txt`
2. **PDF Report** - Detailed kill breakdown by category matching the in-game results screen

---

## 💾 Backup & Restore System

### When Backups Are Created

Backups are **only** created when you remove incomplete missions via the Mission Cleanup tool.  They are **not** created automatically after every mission.

This ensures you can restore your campaign to the state **before** you removed any missions.

### What is takeoffStatus?

IL-2 tracks mission completion with a `takeoffStatus` flag:

| Value | Meaning |
|-------|---------|
| `takeoffStatus=1` | Mission started but not completed properly |
| `takeoffStatus=2` | Mission completed successfully |

### What Triggers the Cleanup Tool

The Mission Cleanup GUI appears when missions with `takeoffStatus=1` are detected. This status indicates something went wrong: 

| Situation | Result |
|-----------|--------|
| Mission objective not completed | `takeoffStatus=1` |
| Pilot bailed out | `takeoffStatus=1` |
| Pilot killed in action (KIA) | `takeoffStatus=1` |
| Pilot missing in action (MIA) | `takeoffStatus=1` |
| IL-2 crashed during mission | `takeoffStatus=1` |
| Force quit (Alt+F4, Task Manager) | `takeoffStatus=1` |

> **Note:** There may be other situations that result in `takeoffStatus=1`. The common factor is that the mission was not completed successfully.

### Backup Location

```
[IL-2 Directory]\data\swf\il2\usersave\[username]\campaign\

Files Created (when removing missions):
├── campaignsstates_20240115_143022.backup     # Save file backup
├── popups_20240115_143022.backup               # Popup state backup
└── campaignsstates_hash_index. json             # Backup index
```

### What's Backed Up

| File | Content |
|------|---------|
| `campaignsstates_*. backup` | Complete campaign save state before mission removal |
| `popups_*.backup` | Popup state backup (prevents duplicate popups after restore) |
| `campaignsstates_hash_index.json` | Index linking file hashes to backup timestamps |

### Restore GUI

When the tracker starts and backups are available, a restore GUI may appear:

```
┌─────────────────────────────────────────────────────────┐
│           🔄 Restore Campaign Backup                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Select a backup to restore:                              │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Date & Time          │ Status           │ Popups   │ │
│  ├──────────────────────┼──────────────────┼──────────┤ │
│  │ 2024-01-15 14:30:22  │ ✅ Currently Active │ ✓ Yes  │ │
│  │ 2024-01-15 12:15:03  │                  │ ✓ Yes    │ │
│  │ 2024-01-14 20:45:11  │                  │ ✗ No     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  [🔄 Restore Selected]  [▶ Continue]  [✕ Exit]          │
│                                                          │
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
   - Deletes current `campaignsstates. txt`
   - Renames backup copy to `campaignsstates.txt`
   - Restarts to process the restored state
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
3. **Popup state cleared** - Associated events removed from `campaign_popups_seen. json`
4. **Ready to replay** - You can fly the mission again

### What Happens When You Keep a Mission

If you click "Keep All" or don't select a mission: 
- No backup is created
- No changes are made
- The mission remains in your save file
- Cleanup GUI will appear again next time (for remaining incomplete missions)

---

## 📁 File Reference

### Configuration Files

| File | Purpose | User Editable |
|------|---------|---------------|
| `campaign_progress_config. yaml` | Ranks, awards, criteria, and settings | ✅ Yes |
| `campaign_mission_dates.json` | Campaign metadata, mission dates, countries | ⚠️ Careful |

### Configuration Details

#### campaign_progress_config. yaml

This is the main configuration file containing:

```yaml
# Rank definitions per nation
ranks: 
  Germany:
    - name: "Unteroffizier"
      score_threshold: 0
      image:  "ranks/germany/unteroffizier.png"
    - name: "Feldwebel"
      score_threshold: 500
      image: "ranks/germany/feldwebel.png"
    # ... more ranks

# Award definitions per nation
awards: 
  Germany:
    - name: "Iron Cross 2nd Class"
      criteria:
        type: "cumulative_kills"
        threshold: 10
      image: "awards/germany/ek2.png"
    # ... more awards

# General settings
settings:
  enable_popups: true
  popup_duration: 5
  generate_pdf:  true
```

#### campaign_mission_dates.json

Auto-generated during first run, contains:

```json
{
  "game_directory": "C:\\Games\\IL-2 Sturmovik",
  "kerch": {
    "country": "Germany",
    "starting_rank_offset":  0,
    "excluded":  false,
    "missions": {
      "0": "1943-11-01",
      "1":  "1943-11-03",
      "2": "1943-11-05"
    }
  }
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
| `[Campaign]_Report. pdf` | Career PDF report | `reports/` subfolder |

---

## 🔧 Troubleshooting

### Tracker Won't Start

| Problem | Solution |
|---------|----------|
| Missing `campaign_progress_config.yaml` | Ensure file is in same folder as EXE |
| Antivirus blocking | Add exception for tracker folder |
| Missing Visual C++ Runtime | Install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist. x64. exe) |

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

**A:** Flying Circus campaigns can be excluded during first-run setup. The tracker is designed for WWII campaigns and does not include WWI-era ranks or awards.

---

## 📜 License

This project is provided as-is for personal use with IL-2 Sturmovik Great Battles. 

---

## 🙏 Acknowledgments

- **1C Game Studios / 777 Studios** - For creating IL-2 Great Battles
- **The IL-2 Community** - For inspiration and feedback

---

*Happy flying!  ✈️🎖️*