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
- `pillow` - Image processing (DDS to PNG conversion)
- `pyyaml` - Configuration parsing
- `psutil` - Process monitoring
- `pdfkit` - PDF generation
- `pyinstaller` - EXE builder

### Optional (but recommended): wkhtmltopdf
For PDF generation:
- Download: https://wkhtmltopdf.org/downloads.html
- Install to: `C:\Program Files\wkhtmltopdf\`
- Build script will automatically bundle it if found

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
  - `il2_tracker_launcher.py` (main entry point)
  - `monitor_campaigns.py` (background monitoring)
  - `step1_extract_mission_dates.py` (mission extraction + GUI)
  - `step3_generate_events.py` (rank/award calculation)
  - `decode_campaing_usersave1.py` (save file decoder)
  - `step4_process_mission_logs.py` (mission log parser)
  - `il2_mission_debrief.py` (debriefing generator)
  - `mlg2txt.py` (mission log converter)
  - `country_validator_gui.py` (country validation GUI)
  - `cleanup_failed_missions.py` (mission cleanup tool - NEW in v1.1)

**[3/5] Cleans Build Artifacts**
- Removes `build/` directory
- Removes `dist/` directory
- Removes old EXE

**[4/5] Runs PyInstaller**
- Executes: `pyinstaller IL2_CampaignTracker.spec`
- Uses spec file to bundle everything
- Takes 2-5 minutes depending on system

**[5/5] Creates Distribution Package**
- Creates distribution folder (e.g., `IL2_Campaign_Tracker_v1.1\`)
- Copies EXE from `dist/`
- Copies all configuration YAML files
- Copies `mlg2txt.exe` (required at runtime for log conversion)
- Generates `QUICK_START.txt` with usage instructions

### Build Output

```
dist\IL2_CampaignTracker\
├── IL2_CampaignTracker.exe          # Standalone executable (~40 MB)
├── campaign_progress_config.yaml    # Awards & ranks config
├── object_categories.yaml           # Aircraft classifications
├── stock_campaigns.yaml             # Known campaigns
├── weapons_mappings.yaml            # Weapon classifications (NEW in v1.1)
└── mlg2txt.exe                       # Mission log converter (if needed)
```

**This folder is ready for distribution!**

## The Spec File

`IL2_CampaignTracker.spec` defines the build:

### Entry Point
```python
['il2_tracker_launcher.py']  # Main unified launcher
```

### Hidden Imports
Modules PyInstaller might miss:
- `decode_campaing_usersave1` - Save file decoder
- `step1_extract_mission_dates` - Mission extraction
- `step3_generate_events` - Event generator
- `step4_process_mission_logs` - Log processor
- `il2_mission_debrief` - Debriefing parser
- `monitor_campaigns` - Background monitor
- `country_validator_gui` - Country validation
- `cleanup_failed_missions` - Mission cleanup (NEW)
- `mlg2txt` - Log converter

### Bundled Data
Configuration files (must be in same directory as EXE):
- `campaign_progress_config.yaml` - Ranks, awards, scaling factors
- `object_categories.yaml` - Aircraft/vehicle classifications
- `stock_campaigns.yaml` - Known campaign definitions
- `weapons_mappings.yaml` - Weapon type definitions

### One-File Build
```python
onefile=True  # Single ~40 MB executable
```

All dependencies are bundled into a single EXE file.

## Distribution

### What to Package

**Essential:**
1. The entire distribution folder (e.g., `IL2_Campaign_Tracker_v1.1\`)
2. `CampaignRanksAwards.zip` (from repository - medal/rank images)

### Distribution Structure
```
YourDistribution\
├── IL2_Campaign_Tracker_v1.1\
│   ├── IL2_CampaignTracker.exe
│   ├── campaign_progress_config.yaml
│   ├── object_categories.yaml
│   ├── stock_campaigns.yaml
│   ├── weapons_mappings.yaml
│   ├── mlg2txt.exe 
│   └── QUICK_START.txt
└── CampaignRanksAwards.zip
```

### User Instructions

**Installation Steps:**
1. Extract `CampaignRanksAwards.zip`
2. Copy `CampaignRanksAwards\` folder to: `<IL-2>\data\swf\`
3. Run `IL2_CampaignTracker.exe`
4. On first run:
   - Select IL-2 installation directory via GUI
   - Validate auto-detected country assignments
   - Review any unsuccessful missions (if applicable)

**Requirements:**
- IL-2 Sturmovik: Great Battles (any version)
- Windows OS
- NO Python needed by end users

### Creating a ZIP

```bash
# After successful build
cd dist
powershell Compress-Archive -Path IL2_CampaignTracker -DestinationPath IL2_Tracker_v1.1.zip
```

Or manually zip the `IL2_CampaignTracker\` folder.

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
- Common issues: mixed tabs/spaces, missing colons, incorrect indentation
- Test manually: `python -m py_compile filename.py`

### Missing Files

**Error:** `ERROR: filename.py not found!`

**Solution:**
- Ensure all required `.py` files are present in the project directory
- Check file names match exactly (case-sensitive)
- Required files listed in "What the Script Does" section

### Build Fails

**Error:** PyInstaller errors during build

**Solutions:**

1. **Clean and retry:**
   ```bash
   rmdir /s /q build dist
   build_exe.bat
   ```

2. **Update PyInstaller:**
   ```bash
   pip install --upgrade pyinstaller
   ```

3. **Reinstall dependencies:**
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

4. **Check for import errors:**
   - Review PyInstaller output for missing modules
   - Add missing modules to `hiddenimports` in spec file

### EXE Won't Start

**Solution:**

1. **Run from command line to see errors:**
   ```bash
   cd dist\IL2_CampaignTracker
   IL2_CampaignTracker.exe
   ```

2. **Common issues:**
   - YAML files missing from EXE directory
   - Antivirus blocking the executable
   - Missing Visual C++ Redistributables (install from Microsoft)

3. **Verify file structure:**
   ```
   IL2_CampaignTracker.exe
   campaign_progress_config.yaml  ✓
   object_categories.yaml         ✓
   stock_campaigns.yaml           ✓
   weapons_mappings.yaml          ✓
   ```

4. **Temporarily disable antivirus and retry**

### YAML Configuration Errors

**Error:** `FileNotFoundError: campaign_progress_config.yaml`

**Solution:**
- YAML files MUST be in the same directory as the EXE
- These files are NOT embedded in the EXE (intentionally - for user editing)
- Copy YAML files from source to EXE directory if missing

### Mission Cleanup GUI Not Showing

**Symptom:** Cleanup GUI doesn't appear on startup

**Solution:**
- Ensure `cleanup_failed_missions.py` is included in build
- Check that `campaigns_decoded.json` exists (created after first mission)
- GUI only shows if unsuccessful missions are found

### PDF Export Fails

**Error:** PDF generation errors or missing PDFs

**Solutions:**

1. **Install wkhtmltopdf:**
   - Download: https://wkhtmltopdf.org/downloads.html
   - Use default path: `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`

2. **For standalone EXE:**
   - Copy `wkhtmltopdf.exe` to same directory as tracker EXE
   - Or bundle during build (see Advanced Customization)

3. **Install pdfkit:**
   ```bash
   pip install pdfkit
   ```

4. **Check PDF output directory:**
   - Default: `<IL-2>\data\Campaigns\<CampaignName>\reports\`
   - Verify write permissions

### Size Issues

**Expected size:** ~40 MB for the EXE

**If larger:**
- Normal variation depending on Python version and dependencies
- 35-45 MB is typical range

**If smaller (<20 MB):**
- May indicate missing dependencies
- Run and test thoroughly

## Advanced Customization

### Modifying the Build

1. **Edit `IL2_CampaignTracker.spec`**

2. **Common changes:**
   - **Executable name:** Change `name='IL2_CampaignTracker'`
   - **Version info:** Add `version` parameter
   - **Bundled files:** Modify `datas` list
   - **Excluded modules:** Add to `excludes` list
   - **Custom icon:** Set `icon='path/to/icon.ico'`

3. **Rebuild:**
   ```bash
   build_exe.bat
   ```

### Adding Custom Icon

In `IL2_CampaignTracker.spec`:
```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    # ...
    icon='resources/icon.ico',  # Add this line
    # ...
)
```

Requires `.ico` file (Windows icon format).

### Bundling Additional Files

In `IL2_CampaignTracker.spec`:
```python
datas=[
    ('campaign_progress_config.yaml', '.'),
    ('object_categories.yaml', '.'),
    ('stock_campaigns.yaml', '.'),
    ('weapons_mappings.yaml', '.'),
    ('your_new_file.txt', '.'),  # Add your file here
],
```

### Optimizing Build Size

1. **Exclude unused modules:**
```python
excludes=['tkinter.test', 'unittest', 'pydoc']
```

2. **Use UPX compression** (optional):
```python
upx=True,
upx_exclude=[],
```

Note: UPX may trigger some antivirus software.

### Bundling wkhtmltopdf (for standalone PDF generation)

To include wkhtmltopdf in your EXE distribution:

1. **Install wkhtmltopdf:**
   - Download from: https://wkhtmltopdf.org/downloads.html
   - Note installation path (e.g., `C:\Program Files\wkhtmltopdf\bin\`)

2. **Modify spec file to bundle it:**
```python
# In IL2_CampaignTracker.spec
import os

# Add wkhtmltopdf binary to bundle
wkhtmltopdf_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
if os.path.exists(wkhtmltopdf_path):
    a.binaries += [('wkhtmltopdf.exe', wkhtmltopdf_path, 'BINARY')]
```

3. **Rebuild:**
```bash
build_exe.bat
```

4. **Result:**
   - wkhtmltopdf.exe bundled in EXE
   - No separate installation needed by end users
   - PDF generation works out of the box

**Alternative (simpler):**
- Copy `wkhtmltopdf.exe` manually to distribution folder
- Users place it next to tracker EXE

## Testing the Build

### Basic Functionality Test

1. **First Run:**
   ```bash
   cd dist\IL2_CampaignTracker
   IL2_CampaignTracker.exe
   ```

2. **Test GUI:**
   - Folder selection dialog should appear
   - Select a valid IL-2 directory
   - Country validation should show

3. **Test Monitoring:**
   - Tracker should continue running
   - Check `campaign_monitor.log` is created
   - Press Ctrl+C to exit cleanly

4. **Test with Real Data:**
   - Copy a real `campaignsstates.txt` to tracker directory
   - Run tracker
   - Verify events are generated

### Distribution Test

1. Copy distribution folder to clean test environment
2. Run without Python installed
3. Verify all features work
4. Test with actual IL-2 installation

## Version Management

### Updating Version Number

When releasing a new version:

1. **Update version in code:**
   - `il2_tracker_launcher.py` - Update version string
   - `build_exe.bat` - Update folder name

2. **Update documentation:**
   - `README.md` - Version history section
   - `BUILD.md` - Version references
   - `QUICK_START.txt` template

3. **Rebuild:**
   ```bash
   build_exe.bat
   ```

4. **Test thoroughly before distribution**

## Continuous Integration (Optional)

For automated builds, you can integrate into CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Build EXE
  run: |
    pip install -r requirements.txt
    pip install pyinstaller
    python -m PyInstaller IL2_CampaignTracker.spec
```

## Support

For build issues, open a GitHub issue with:
- **Full error output** (copy entire console output)
- **Python version:** `python --version`
- **PyInstaller version:** `pyinstaller --version`
- **Operating system** and version
- **Steps to reproduce**

**Tip:** Run `build_exe.bat` from a command prompt (not double-click) to see full output.

---

## Quick Reference

**Build Command:**
```bash
build_exe.bat
```

**Clean Build:**
```bash
rmdir /s /q build dist
build_exe.bat
```

**Test Build:**
```bash
cd dist\IL2_CampaignTracker
IL2_CampaignTracker.exe
```

**Required Files:**
- All `.py` files listed in script
- All `.yaml` config files
- `IL2_CampaignTracker.spec`
- `build_exe.bat`

**Output:**
- `dist\IL2_CampaignTracker\` folder with EXE and configs

---

**Happy Building! 🔨**

**Recommendation:** Always use `build_exe.bat` for automated, reliable builds. Manual PyInstaller commands may miss dependencies.
