# Building IL-2 Campaign Tracker

This guide covers building a standalone executable using the provided build script.

## Important Notes

**To BUILD the EXE:** You need Python 3.8+ and all dependencies installed.

**To RUN the EXE:** End users do NOT need Python - the EXE is standalone (~40 MB).

**Pre-built EXE:** NOT provided in GitHub releases. You must build your own.

## Prerequisites

### Required Software
- **Python 3.8 or higher**
- **PyInstaller 5.0 or higher**
- **All project dependencies**

### Install Dependencies
```bash
pip install -r requirements.txt
pip install pyinstaller
```

**Required packages:**
- `pillow` - Image processing
- `pyyaml` - Configuration parsing
- `psutil` - Process monitoring
- `pdfkit` - PDF generation
- `pyinstaller` - EXE builder

### Optional (but recommended): wkhtmltopdf
For PDF generation:
- Download: https://wkhtmltopdf.org/downloads.html
- Install to: `C:\Program Files\wkhtmltopdf\`
- Build script will automatically bundle it

## Build Instructions

### Simple Method: Run the Build Script

Execute:
```bash
build_exe.bat
```

### What the Script Does

**[1/5] Checks for PyInstaller**
- Verifies PyInstaller is installed
- Exits if missing

**[2/5] Validates Python Files**
- Syntax check on all `.py` files
- Does NOT execute code - only validates
- Files checked:
  - `il2_tracker_launcher.py`
  - `monitor_campaigns.py`
  - `step1_extract_mission_dates.py`
  - `step3_generate_events.py`
  - `decode_campaing_usersave1.py`
  - `step4_process_mission_logs.py`
  - `il2_mission_debrief.py`
  - `mlg2txt.py`
  - `country_validator_gui.py`

**[3/5] Cleans Build Artifacts**
- Removes `build/` directory
- Removes `dist/` directory
- Removes old EXE

**[4/5] Runs PyInstaller**
- Executes: `pyinstaller IL2_CampaignTracker.spec`
- Uses spec file to bundle everything
- Takes 2-5 minutes

**[5/5] Creates Distribution Package**
- Creates: `IL2_Campaign_Tracker_v1.5\` folder
- Copies EXE from `dist/`
- Copies configuration YAML files
- Copies `mlg2txt.py` (required at runtime)
- Generates `QUICK_START.txt`

### Build Output

```
IL2_Campaign_Tracker_v1.5\
├── IL2_CampaignTracker.exe          # Standalone executable (~40 MB)
├── campaign_progress_config.yaml    # Awards & ranks config
├── object_categories.yaml           # Aircraft classifications
├── stock_campaigns.yaml             # Known campaigns
├── mlg2txt.py                       # Mission log converter
├── QUICK_START.txt                  # User instructions
└── README.txt                       # Optional
```

**This folder is ready for distribution!**

## The Spec File

`IL2_CampaignTracker.spec` defines the build:

### Entry Point
```python
['il2_tracker_launcher.py']  # Main launch script
```

### Hidden Imports
Modules PyInstaller might miss:
- `decode_campaing_usersave1`
- `step1_extract_mission_dates`
- `step3_generate_events`
- `step4_process_mission_logs`
- `il2_mission_debrief`
- `monitor_campaigns`
- `country_validator_gui`
- `mlg2txt`

### Bundled Data
Configuration files:
- `campaign_progress_config.yaml`
- `object_categories.yaml`
- `stock_campaigns.yaml`

### One-File Build
```python
onefile=True  # Single 40 MB executable
```

## Distribution

### What to Package

**Essential:**
1. The entire `IL2_Campaign_Tracker_v1.5\` folder
2. `CampaignRanksAwards.zip` (from repository)

### Distribution Structure
```
YourDistribution\
├── IL2_Campaign_Tracker_v1.5\
│   ├── IL2_CampaignTracker.exe
│   ├── *.yaml configs
│   ├── mlg2txt.py
│   └── QUICK_START.txt
└── CampaignRanksAwards.zip
```

### User Instructions

**Installation Steps:**
1. Extract `CampaignRanksAwards.zip`
2. Copy `CampaignRanksAwards\` folder to: `<IL-2>\data\swf\`
3. Run `IL2_CampaignTracker.exe`
4. Select IL-2 installation when prompted

**Requirements:**
- IL-2 Sturmovik: Great Battles
- Windows OS
- NO Python needed

### Creating a ZIP

```bash
cd IL2_Campaign_Tracker_v1.5
# Optionally add CampaignRanksAwards.zip here
cd ..
powershell Compress-Archive -Path IL2_Campaign_Tracker_v1.5 -DestinationPath IL2_Tracker_v1.5.zip
```

## Troubleshooting

### PyInstaller Not Found

**Error:** `pyinstaller: command not found`

**Solution:**
```bash
pip install pyinstaller
```

### Syntax Errors

**Error:** `SyntaxError` or `IndentationError` during validation

**Solution:**
- Fix the reported Python file
- Common issues: mixed tabs/spaces, missing colons
- Test manually: `python -m py_compile filename.py`

### Missing Files

**Error:** `ERROR: filename.py not found!`

**Solution:**
- Ensure all required `.py` files are present
- Check file names match exactly

### Build Fails

**Error:** PyInstaller errors

**Solutions:**

1. Clean and retry:
   ```bash
   rmdir /s /q build dist
   build_exe.bat
   ```

2. Update PyInstaller:
   ```bash
   pip install --upgrade pyinstaller
   ```

3. Reinstall dependencies:
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

### EXE Won't Start

**Solution:**

1. Run from command line to see errors:
   ```bash
   cd IL2_Campaign_Tracker_v1.5
   IL2_CampaignTracker.exe
   ```

2. Check YAML files are present

3. Disable antivirus temporarily

4. Verify wkhtmltopdf was bundled

### wkhtmltopdf Not Bundled

**Symptom:** PDF generation fails

**Solution:**
1. Install: https://wkhtmltopdf.org/downloads.html
2. Use default path: `C:\Program Files\wkhtmltopdf\`
3. Rebuild

### Size Issues

**Expected size:** ~40 MB

## Advanced Customization

### Modifying the Build

1. Edit `IL2_CampaignTracker.spec`
2. Common changes:
   - Executable name
   - Bundled files
   - Excluded modules
   - Custom icon

3. Rebuild with:
   ```bash
   build_exe.bat
   ```

### Adding Custom Icon

In spec file:
```python
exe = EXE(
    # ...
    icon='path/to/icon.ico',
)
```

**Recommendation:** Use `build_exe.bat` - it's automated and reliable.

## Support

For build issues, open a GitHub issue with:
- Full error output
- Python version: `python --version`
- PyInstaller version: `pyinstaller --version`
- Operating system

---

**Happy Building! 🔨**
