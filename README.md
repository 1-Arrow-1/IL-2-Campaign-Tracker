# IL-2 Campaign Tracker

A comprehensive campaign progress tracker for IL-2 Sturmovik: Great Battles that automatically monitors your **Campaign mode** (not Career mode), tracks achievements, calculates ranks and awards, and displays them directly in-game.

![IL-2 Campaign Tracker](https://img.shields.io/badge/IL--2-Campaign%20Tracker-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## ✨ Features

### 📊 **Campaign Progression Tracking**
- **Automatic Rank Promotions**: Tracks your progress through military ranks with intelligent scaling for campaign length
- **Award System**: Monitors and awards medals, crosses, and decorations based on your achievements
- **Country Support**: Full support for Germany, Soviet Union, Britain, and USA with historically accurate awards
- **Smart Calculation**: Dynamically adjusts promotion requirements based on campaign duration (short vs. long campaigns)
- **Dynamic Campaign Detection**: Automatically detects new campaigns and missions added to your IL-2 installation

### 🎯 **Mission Debriefings**
- **Detailed Flight Logs**: Complete timeline of every mission with altitude, time, and event data
- **Kill Attribution**: Intelligent kill tracking with direct and indirect (80% damage rule) attribution
- **Damage Tracking**: Separate aircraft and pilot damage tracking, aggregated per minute for clarity
- **Landing Analysis**: Four-criteria system to detect hard landings vs. safe landings
- **Combat Statistics**: Air, ground, and naval kills with comprehensive breakdowns

### 🔄 **Live Monitoring**
- **Automatic Detection**: Monitors IL-2 game process and campaign save file changes
- **Real-time Updates**: Processes new missions immediately after completion
- **Mission Replay Support**: Automatically detects when missions are re-flown
- **Smart Caching**: Efficient processing with intelligent file management
- **Campaign Detection**: Automatically detects new/removed campaigns and missions

### 🧹 **Mission Cleanup Tool**
- **Failed Mission Detection**: Automatically finds unsuccessful last missions (`takeOffStatus = 1`)
- **Selective Deletion**: GUI lets you choose which missions to delete for replay
- **Don't Ask Again**: Per-mission ignore flags prevent repeated prompts
- **Automatic Backups**: Creates timestamped backups before any deletion (keeps last 10)
- **Smart Filtering**: Only shows missions that need attention

### 🎨 **In-Game Display**
- **Campaign Screen Integration**: Events appear directly in IL-2's campaign `.info` files
- **Image Display**: Medals, ranks, and awards shown with original game graphics
- **Chronological Order**: All achievements displayed in proper sequence
- **Mission Dates**: Real historical dates extracted from mission files

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- IL-2 Sturmovik: Great Battles (any version)
- Windows OS

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `pillow` - Image processing (DDS to PNG conversion)
- `pyyaml` - Configuration file parsing
- `psutil` - Process monitoring

### Step 2: Download Campaign Ranks & Awards Images

**IMPORTANT:** The tracker requires medal and rank images to display in-game.

1. Download `CampaignRanksAwards.zip` from this repository
2. Extract the ZIP file
3. Copy the `CampaignRanksAwards` folder to: `<IL-2 Installation>\data\swf\`

**Final structure:**
```
<IL-2 Installation>\
└── data\
    └── swf\
        └── CampaignRanksAwards\
            ├── Germany\
            │   ├── unteroffizier.png
            │   ├── feldwebel.png
            │   └── ...
            ├── Britain\
            ├── US\
            └── USSR\
                ├── early\
                └── late\
```

### Step 3: Clone and Run

1. Clone this repository:
```bash
git clone https://github.com/yourusername/il2-campaign-tracker.git
cd il2-campaign-tracker
```

2. Run the tracker:
```bash
python il2_tracker_launcher.py
```

3. On first run:
   - Select your IL-2 installation directory via GUI
   - Review and validate auto-detected country assignments
   - If you have unsuccessful missions, choose whether to delete or ignore them

---

## 🔨 Building Standalone EXE

**Note:** Pre-built EXE files are NOT provided in releases. You must build your own executable.

### Why Build Your Own?

Building allows you to:
- Customize the configuration
- Verify the source code
- Ensure compatibility with your Python environment
- Include the exact versions of dependencies you want

### Build Requirements

**To BUILD the EXE, you need:**
- Python 3.8 or higher installed
- PyInstaller: `pip install pyinstaller`
- All dependencies: `pip install -r requirements.txt`

**To RUN the built EXE:**
- End users do NOT need Python
- The EXE is standalone

### Build Instructions

**Simply run the build script:**
```bash
build_exe.bat
```

**What the script does:**
1. Checks for PyInstaller and all dependencies
2. Validates all Python files (syntax check)
3. Cleans old build artifacts
4. Runs PyInstaller with the spec file
5. Creates output folder with:
   - `IL2_CampaignTracker.exe`
   - Configuration files (YAML)
   - Required scripts (mlg2txt.py)

**Output location:**
```
dist\IL2_CampaignTracker\
├── IL2_CampaignTracker.exe          # Standalone executable (~40 MB)
├── campaign_progress_config.yaml    # Awards & ranks config
├── object_categories.yaml           # Aircraft classifications
├── stock_campaigns.yaml             # Known campaigns
├── weapons_mappings.yaml            # Weapon classifications
└── mlg2txt.py                       # Mission log converter (if needed)
```

### Distribution

To share the tracker with others:

1. Build the EXE using `build_exe.bat`
2. Copy the entire output folder
3. Include `CampaignRanksAwards.zip` in your distribution
4. Provide instructions to copy `CampaignRanksAwards\` to IL-2's `data\swf\` folder

**No Python required for end users!**

### Build Troubleshooting

**PyInstaller not found:**
```bash
pip install pyinstaller
```

**Missing dependencies:**
```bash
pip install -r requirements.txt
```

**Build fails:**
- Check that all `.py` files exist in the project directory
- Verify Python syntax: `python -m py_compile filename.py`
- Review error messages in the console

**EXE won't start:**
- Run from command line to see error messages
- Ensure all YAML files are present in same directory as EXE
- Check antivirus isn't blocking the executable

## 📖 Usage

### First Time Setup
1. Run `python il2_tracker_launcher.py` (or `IL2_CampaignTracker.exe` if you built it)
2. **GUI Folder Selection**: Browse and select your IL-2 installation directory
3. **Mission Date Extraction**: The tracker automatically scans all campaigns and extracts mission dates
4. **Country Validation**: GUI appears showing auto-detected countries - verify or manually adjust
5. **Mission Cleanup Check** (if applicable): GUI shows any unsuccessful missions you can delete or ignore
6. **Initial Processing**: Decodes your save file and generates initial events
7. **Monitoring Starts**: Tracker runs in background, checking every 10 seconds

### Automatic Monitoring
The tracker runs in the background and automatically:
- Detects when you start IL-2 (monitors `IL-2.exe` process)
- Watches `campaignsstates.txt` for changes (mission completions)
- Monitors `Campaigns` folder for new/removed campaigns
- Automatically decodes save file when changes detected
- Generates career events (ranks, awards) immediately
- Creates mission debriefings from `.mlg` log files
- Updates campaign `.info` files for in-game display
- Shows Country Validation GUI when new campaigns detected

### Failed Mission Management

When you have unsuccessful missions (`takeOffStatus = 1`), the tracker:
1. **Detects** the last mission of each campaign
2. **Shows GUI** with details (kills, flight time, mission number)
3. **Offers Options**:
   - Delete mission entry to replay
   - "Don't ask again" to ignore permanently
   - Cancel to keep as-is

**Don't Ask Again Feature:**
- Per-mission persistent ignore flags
- Stored in `cleanup_ignored_missions.json`
- Prevents repeated prompts on startup
- Can be manually edited to un-ignore missions

### Manual Operation
You can also run individual components:

**Extract mission dates:**
```bash
python step1_extract_mission_dates.py
```
- Opens GUI to select game directory
- Scans all campaigns in `data\Campaigns\`
- Auto-detects countries based on aircraft
- Creates `campaign_mission_dates.json`

**Decode save file:**
```bash
python decode_campaing_usersave1.py
```
- Reads `campaignsstates.txt` (binary format)
- Creates `campaigns_decoded.json` with statistics

**Generate career events:**
```bash
python step3_generate_events.py
```
- Reads decoded save data and mission dates
- Calculates ranks and awards
- Processes mission logs for debriefings
- Updates campaign `.info` files

**Process mission logs:**
```bash
python step4_process_mission_logs.py
```
- Parses `.mlg` binary files
- Extracts kills, damage, events
- Creates detailed timelines

**Country validation:**
```bash
python country_validator_gui.py
```
- Shows GUI with all campaigns
- Allows manual country assignment
- Updates `campaign_mission_dates.json`

**Mission cleanup:**
```bash
python cleanup_failed_missions.py
```
- Scans for unsuccessful missions
- Shows GUI with cleanup options
- Manages ignore list

## 📂 File Structure

```
IL2_CampaignTracker/
├── il2_tracker_launcher.py          # Main launcher (single EXE entry point)
├── monitor_campaigns.py             # Background monitoring service
├── step1_extract_mission_dates.py   # Mission date extraction + GUI
├── step3_generate_events.py         # Career event generation (ranks/awards)
├── step4_process_mission_logs.py    # Mission log processing (.mlg files)
├── il2_mission_debrief.py           # Debriefing parser
├── decode_campaing_usersave1.py     # Save file decoder
├── country_validator_gui.py         # Country validation GUI
├── cleanup_failed_missions.py       # Mission cleanup tool (NEW in v1.1)
├── mlg2txt.py                       # Mission log converter
├── campaign_progress_config.yaml    # Awards & ranks configuration
├── object_categories.yaml           # Aircraft/vehicle classifications
├── stock_campaigns.yaml             # Known campaign definitions
├── weapons_mappings.yaml            # Weapon classifications
├── IL2_CampaignTracker.spec         # PyInstaller build spec
├── build_exe.bat                    # Automated build script
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

### Generated Files

The tracker creates these files during operation:

```
campaign_mission_dates.json          # Mission dates and country assignments
campaigns_decoded.json               # Decoded save file data
campaignsstates.txt                  # Copy of IL-2 save file (local)
cleanup_ignored_missions.json        # "Don't ask again" ignore list
campaign_monitor.log                 # Monitoring activity log
```

## ⚙️ Configuration

### Campaign Progress Config (`campaign_progress_config.yaml`)
Customize:
- **Rank progression requirements** (base scores)
- **Award conditions** and prerequisites
- **Scaling factors** for different campaign lengths (1-10 missions: 1.0x, 70+ missions: 2.5x)
- **Country-specific settings** (Germany, Britain, USA, Soviet Union)

Example rank scaling:
```yaml
rank_scaling:
  enabled: true
  factors:
    "1-10":    1.00   # Short campaigns (stock campaigns)
    "11-20":   1.15   # Medium-short campaigns  
    "21-30":   1.30   # Medium campaigns
    "31-40":   1.50   # Medium-long campaigns
    "41-50":   1.75   # Long campaigns
    "51-70":   2.00   # Very long campaigns
    "71+":     2.50   # Epic campaigns
```

### Object Categories (`object_categories.yaml`)
Defines:
- Aircraft classifications (light/medium/heavy)
- Ground vehicle categories
- Naval vessel types
- Static object classifications

### Stock Campaigns (`stock_campaigns.yaml`)
Pre-configured:
- Official IL-2 campaign names and countries
- User can add custom campaigns
- Automatic country detection for known campaigns

### Weapons Mappings (`weapons_mappings.yaml`)
Defines:
- Weapon types and calibers
- Used for kill attribution and statistics

## 🎖️ Award System

### Germany
- Iron Cross 2nd/1st Class
- German Cross in Gold
- Knight's Cross of the Iron Cross
- Honor Goblet
- Front Flying Clasps (Bronze/Silver/Gold)
- Wound Badge (Black/Silver/Gold)
- And more...

### Soviet Union
- Order of the Red Banner
- Order of the Red Star
- Hero of the Soviet Union (Gold Star)
- Order of Lenin
- Medals for Bravery and Combat Merit
- Separate early (collar tabs, pre-1943) and late (shoulder boards, 1943+) periods

### Britain
- Distinguished Flying Cross (DFC)
- Distinguished Flying Medal (DFM)
- Distinguished Service Order (DSO)
- Air Force Cross (AFC)

### USA
- Distinguished Flying Cross
- Air Medal
- Silver Star
- Distinguished Service Cross
- Purple Heart

## 🔧 Advanced Features

### Rank Scaling
Automatically adjusts promotion requirements based on campaign length:
- Short campaigns (1-10 missions): 1.0x (stock campaigns)
- Medium campaigns (11-30 missions): 1.15-1.30x
- Long campaigns (31-50 missions): 1.5-1.75x
- Very long campaigns (51-70 missions): 2.0x
- Epic campaigns (70+ missions): 2.5x

This ensures meaningful progression regardless of campaign duration.

### Kill Attribution System
- **Direct kills**: You destroyed the target
- **Indirect kills**: You dealt 80%+ damage before target was destroyed by someone else
- **Shared kills**: Proper credit distribution in multi-player scenarios
- **Per-minute aggregation**: Damage events grouped by minute for cleaner debriefings

### Landing Detection
Four-criteria system:
1. Altitude < 200m
2. Speed < 180 km/h (configurable)
3. No damage in previous 30 seconds
4. Engine state considered

### Dynamic Campaign Management
- **Auto-detection**: Monitors `Campaigns` folder for changes
- **New campaigns**: Shows Country Validation GUI automatically
- **Removed campaigns/missions**: Automatically removes from JSON
- **Mission count updates**: Recalculates when missions deleted

### DDS Image Support
Automatically converts IL-2's DDS texture files to PNG for in-game display.

### Image Rotation
Properly displays rank insignia:
- German: All ranks rotated 90° counter-clockwise
- British: Selected officer ranks rotated
- American: All ranks except First Sergeant rotated
- Soviet: Late-period (1943+) ranks rotated

### Mission Replay Intelligence
- Automatically uses the **latest attempt** when missions are re-flown
- Compares timestamps to determine newest data
- Seamlessly updates statistics without manual intervention

## 🐛 Troubleshooting

### No images in-game
- Ensure `CampaignRanksAwards\` folder exists in `<IL-2>\data\swf\`
- Check that image files are PNG format (not DDS)
- Verify folder structure matches documentation

### No mission debriefings
- Verify FlightLogs are enabled in IL-2 settings: `Settings > Difficulty > Events File = All`
- Check `<IL-2>\data\FlightLogs\` directory exists and has `.mlg` files
- Mission logs are only created for missions you fly (not AI)

### Campaign country detection issues
- Use the Country Validator GUI to manually assign countries
- Add your custom campaigns to `stock_campaigns.yaml`
- Countries detected based on aircraft types in missions

### Tracker not detecting changes
- Ensure `campaignsstates.txt` path is correct
- Check `campaign_monitor.log` for errors
- Verify IL-2 is actually writing to save file (fly a test mission)

### "Don't ask again" not working
- Check `cleanup_ignored_missions.json` exists and is valid JSON
- Verify campaign name matches exactly (case-sensitive)
- Delete the JSON file to reset all ignore flags

### Mission cleanup not finding unsuccessful missions
- Ensure `campaigns_decoded.json` exists (run decoder first)
- Check that missions actually have `takeOffStatus = 1` (unsuccessful)
- Only the **last** mission of each campaign is checked

## 📝 Known Limitations

- **Campaign Mode Only**: This tracker is designed for Campaign mode, NOT Career mode
- **Flying Circus (WWI)**: WW1 campaigns can be excluded (option in Step 1)
- **Multiplayer**: Optimized for single-player campaigns
- **Language**: Currently supports English localization only
- **Windows Only**: Relies on Windows-specific paths and process monitoring

## 🔄 Version History

### v1.1 (Current)
- **NEW: Mission Cleanup Tool** - Detect and delete unsuccessful missions with GUI
- **NEW: "Don't Ask Again" Feature** - Per-mission ignore flags to prevent repeated prompts
- **FIX: Cleanup timing** - Now runs AFTER initial decoding (works on first start)
- **IMPROVED: Startup flow** - Better error handling and user feedback
- Automatic backup system (keeps last 10 backups)
- Enhanced monitoring with campaign folder change detection

### v1.0
- Initial release
- Automatic rank and award tracking
- Mission debriefing system
- In-game event display
- Country validation GUI
- Background monitoring
- Campaign detection

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Flying Circus / WWI campaign support
- Additional language localizations
- New award systems for modded campaigns
- Enhanced statistics and analytics
- Web-based dashboard
- Multi-platform support (Linux/Mac)

## 📜 License

This project is provided as-is for the IL-2 Sturmovik community. Not affiliated with 1C Game Studios or 777 Studios.

## 🙏 Acknowledgments

- IL-2 Sturmovik community for mission log format documentation
- 1C Game Studios for creating IL-2 Sturmovik: Great Battles
- Contributors and testers who helped refine the tracker

## 📧 Support

For bugs, feature requests, or questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review `campaign_monitor.log` for debugging

---

**Happy Flying! 🛩️**

**Note:** This tracker is for **Campaign mode**, not Career mode. Campaign mode uses scripted missions from the Campaigns folder, while Career mode is the dynamic career generator. Make sure you're playing Campaign mode to use this tracker!
