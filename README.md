# IL-2 Campaign Tracker

A comprehensive campaign progress tracker for IL-2 Sturmovik: Great Battles that automatically monitors your campaigns, tracks achievements, generates detailed mission debriefings, and exports professional PDF reports.

![IL-2 Campaign Tracker](https://img.shields.io/badge/IL--2-Campaign%20Tracker-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## ✨ Features

### 📊 **Career Progression Tracking**
- **Automatic Rank Promotions**: Tracks your progress through military ranks with intelligent scaling for campaign length
- **Award System**: Monitors and awards medals, crosses, and decorations based on your achievements
- **Country Support**: Full support for Germany, Soviet Union, Britain, and USA with historically accurate awards
- **Smart Calculation**: Dynamically adjusts promotion requirements based on campaign duration

### 🎯 **Mission Debriefings**
- **Detailed Flight Logs**: Complete timeline of every mission with altitude, time, and event data
- **Kill Attribution**: Intelligent kill tracking with direct and indirect (80% damage rule) attribution
- **Damage Tracking**: Separate aircraft and pilot damage tracking, aggregated per minute for clarity
- **Landing Analysis**: Four-criteria system to detect hard landings vs. safe landings
- **Combat Statistics**: Air, ground, and naval kills with comprehensive breakdowns

### 📄 **Professional PDF Reports**
- **One PDF per Campaign**: Automatically generated reports with complete mission history
- **Embedded Images**: All medals, ranks, and awards displayed with proper rotation
- **Clean Layout**: Professional formatting with proper page breaks and alignment
- **Historical Accuracy**: Uses actual mission dates and campaign names from game files

### 🔄 **Live Monitoring**
- **Automatic Detection**: Monitors IL-2 game process and campaign file changes
- **Real-time Updates**: Processes new missions immediately after completion
- **Mission Replay Support**: Automatically uses the latest attempt when missions are re-flown
- **Smart Caching**: Efficient processing with intelligent file management

### 🎨 **In-Game Display**
- **Career Screen Integration**: Events appear directly in IL-2's campaign description
- **Image Display**: Medals, ranks, and awards shown with original game graphics
- **Chronological Order**: All achievements displayed in proper sequence

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- IL-2 Sturmovik: Great Battles (any version)
- Windows OS

### Required Python Packages
```bash
pip install pillow pyyaml psutil pdfkit
```

### Optional: wkhtmltopdf (for PDF export)
Download and install from: https://wkhtmltopdf.org/downloads.html

Or the tracker will guide you through installation on first run.

### Setup
1. Clone this repository:
```bash
git clone https://github.com/yourusername/il2-campaign-tracker.git
cd il2-campaign-tracker
```

2. Run the initial setup:
```bash
python il2_campaign_tracker.py
```

3. Select your IL-2 installation directory when prompted

## 📖 Usage

### First Time Setup
1. Run `python il2_campaign_tracker.py`
2. Point the tracker to your IL-2 installation directory
3. The tracker will scan your existing campaigns and validate country assignments

### Automatic Monitoring
The tracker runs in the background and automatically:
- Detects when you start IL-2
- Monitors campaign progress
- Generates debriefings after each mission
- Updates career events (promotions, awards)
- Exports PDF reports

### Manual Operation
You can also run individual components:

**Extract mission dates:**
```bash
python step1_extract_mission_dates.py
```

**Generate career events:**
```bash
python step3_generate_events.py
```

**Process mission logs:**
```bash
python step4_process_mission_logs.py
```

## 📂 File Structure

```
IL2_CampaignTracker/
├── il2_campaign_tracker.py          # Main GUI application
├── monitor_campaigns.py             # Background monitoring service
├── step1_extract_mission_dates.py   # Mission date extraction
├── step3_generate_events.py         # Career event generation
├── step4_process_mission_logs.py    # Mission log processing
├── il2_mission_debrief.py           # Debriefing parser
├── decode_campaing_usersave1.py     # Save file decoder
├── country_validator_gui.py         # Country validation GUI
├── mlg2txt.py                       # Mission log converter
├── campaign_progress_config.yaml    # Awards & ranks configuration
├── object_categories.yaml           # Aircraft/vehicle classifications
├── stock_campaigns.yaml             # Known campaign definitions
├── IL2_CampaignTracker.spec         # SPEC file for building an EXE
├── build_exe.bat                    # BAT file for creating an EXE
└── reports/                         # Generated PDF reports
```

## ⚙️ Configuration

### Campaign Progress Config (`campaign_progress_config.yaml`)
Customize:
- Rank progression requirements
- Award conditions and prerequisites
- Scaling factors for different campaign lengths
- Country-specific settings

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
- Separate early (collar tabs) and late (shoulder boards) periods
- And more..

### Britain
- Distinguished Flying Cross (DFC)
- Distinguished Flying Medal (DFM)
- Distinguished Service Order (DSO)
- Air Force Cross (AFC)
- And more..
  
### USA
- Distinguished Flying Cross
- Air Medal
- Silver Star
- Distinguished Service Cross
- Purple Heart
- And more..

## 🔧 Advanced Features

### Rank Scaling
Automatically adjusts promotion requirements based on campaign length:
- Short campaigns (1-10 missions): 1.0x
- Medium campaigns (11-30 missions): 1.15-1.30x
- Long campaigns (31-50 missions): 1.5-1.75x
- Epic campaigns (70+ missions): 2.5x

### Kill Attribution System
- **Direct kills**: You destroyed the target
- **Indirect kills**: You dealt 80%+ damage before target was destroyed by someone else
- **Shared kills**: Proper credit distribution in multi-player scenarios

### Landing Detection
Four-criteria system:
1. Altitude < 200m
2. Speed < 180 km/h (adjustable)
3. No damage in previous 30 seconds
4. Engine state considered

### DDS Image Support
Automatically converts IL-2's DDS texture files to PNG for PDF embedding.

### Image Rotation for PDFs
Properly displays rank insignia:
- German: All ranks rotated 90° counter-clockwise
- British: Selected officer ranks rotated
- American: All ranks except First Sergeant rotated
- Soviet: Late-period (1943+) ranks rotated

## 🐛 Troubleshooting

### No images in PDF
- Ensure Pillow is installed: `pip install pillow`
- Check that `data/swf/CampaignRanksAwards/` exists in IL-2 installation

### No mission debriefings
- Verify FlightLogs are enabled in IL-2 settings
- Check `data/FlightLogs/` directory exists and has .mlg files

### Campaign country detection issues
- Use the Country Validator GUI to manually assign countries
- Add your custom campaigns to `stock_campaigns.yaml`

### PDF export fails
- Install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
- Ensure it's added to system PATH

## 📝 Known Limitations

- Flying Circus (WWI) support: Not currently implemented (no test data available)
- Multiplayer: Optimized for single-player career campaigns
- Language: Currently supports English localization only

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Flying Circus / WWI support
- Additional language localizations
- New award systems for modded campaigns
- Enhanced statistics and analytics
- Web-based dashboard

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

## 🔄 Version History

### v1.5 (Current)
- PDF export with embedded images
- Image rotation for rank insignia
- Mission replay support (always uses latest attempt)
- Enhanced layout and formatting
- Country validation GUI
- Comprehensive debriefing system

### v1.0
- Initial release
- Basic event tracking
- Career progression monitoring

---

**Happy Flying! 🛩️**
