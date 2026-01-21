# Building IL-2 Campaign Tracker

This guide covers running the tracker from Python and building Windows executables with the provided build script.

**To BUILD the EXE:** You need Python 3.8+ and all dependencies installed.

Use this if you want to run the tracker directly from source.

### Prerequisites
- **Python 3.8+**
- Optional: **wkhtmltopdf** for PDF exports

### Install Dependencies

```bash
pip install -r requirements.txt
```
The `requirements.txt` file includes the core runtime dependencies (Pillow, PyYAML, psutil, pdfkit, regex).

### Run the tracker
```bash
python il2_tracker_launcher.py
```

The launcher opens the GUI and starts the background monitoring flow. Make sure the `.yaml` config files remain in the same folder as the script.

### Optional: wkhtmltopdf
If you want PDF exports, install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html and ensure it is on your PATH (or installed at the default `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`).

---

## Build a Windows EXE (build_exe.bat + spec files)

The build process requires a Python environment, but the compiled executable is fully self-contained and does not depend on Python at runtime.

### Prerequisites
- **Python 3.8+**
- **PyInstaller**
- All dependencies from `requirements.txt`

```bash
pip install -r requirements.txt
```

### Build command
```bash
build_exe.bat
```

### What the build script does

**[1/5] Checks required files**
- `il2_tracker_launcher.py` (main entry point)
- `step1_extract_mission_dates.py`
- `decode_campaign_usersave1.py`
- `step3_generate_events.py`
- `monitor_campaigns.py`
- `step4_process_mission_logs.py`
- `cleanup_failed_missions.py`
- `mlg2txt.py`
- `popups_min.py`
- `campaign_reset_checker.py`
- `backup_restore_gui.py`
- `IBMPlexSans-Light.ttf`
- `utils/` (and `utils` modules)
- `campaign_progress_config.yaml`
- `object_categories.yaml`
- `stock_campaigns.yaml`
- `IL2_CampaignTracker.spec`
- `mlg2txt.spec`

**[2/5] Validates Python syntax**
- Runs `python -m py_compile` on the Python files listed above.

**[3/5] Cleans build artifacts**
- Removes `build/`, `dist/`, and any prior `.exe` files.

**[4/5] Builds EXEs**
- `pyinstaller IL2_CampaignTracker.spec`
- `pyinstaller mlg2txt.spec`

**[5/5] Creates distribution package**
- Creates `IL2_Campaign_Tracker_v2.0/`
- Copies `IL2_CampaignTracker_v2.0.exe` from `dist/`
- Copies `mlg2txt.exe` from `dist/`
- Copies YAML configuration files
- Writes `QUICK_START.txt`

### Build output
```
IL2_Campaign_Tracker_v2.0/
├── IL2_CampaignTracker_v2.0.exe
├── mlg2txt.exe
├── campaign_progress_config.yaml
├── object_categories.yaml
├── stock_campaigns.yaml
├── README.html
└── QUICK_START.txt
```

### Notes on the spec files
- `IL2_CampaignTracker.spec` bundles the tracker and its dependencies, includes `IBMPlexSans-Light.ttf`, `wkhtmltopdf.exe` 
- `mlg2txt.spec` builds a standalone CLI converter for `.mlg` files.

### Distribution reminders
- Include `CampaignRanksAwards.zip` alongside your distribution folder. Unzip and move to `<Path to Il-2 BG>\data\swf`
- End users do **not** need Python when using the EXE.

---

## Troubleshooting
### PyInstaller Not Found
```bash
pip install pyinstaller
```

### Syntax errors during validation
Run the failing file directly to see the issue:
```bash
python -m py_compile path\to\file.py
```

### Build fails
1. Clean and retry:
   ```bash
   rmdir /s /q build dist
   build_exe.bat
   ```

2. Upgrade PyInstaller:
   ```bash
   pip install --upgrade pyinstaller
   ```

### EXE won't start
1. Run from a terminal to see errors:
   ```bash
   cd IL2_Campaign_Tracker_v2.0
   IL2_CampaignTracker_v2.0.exe
   ```
2. Verify required YAML files are next to the EXE.

### PDF export fails
Install wkhtmltopdf and ensure the executable is available at:
`C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`   

---

**Recommendation:** Use `build_exe.bat` to ensure both `IL2_CampaignTracker_v2.0.exe` and `mlg2txt.exe` are built consistently.




 

