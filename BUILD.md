# Building IL-2 Campaign Tracker

This guide covers building a standalone executable from the Python source code.

## Important Note

**To BUILD the EXE:** You need Python 3.8+ and all dependencies installed.

**To RUN the EXE:** End users do NOT need Python - the EXE is standalone.

## Prerequisites

### Required Software (For Building)
- **Python 3.8 or higher** - Required to run PyInstaller
- **PyInstaller 5.0 or higher** - Packages Python code into EXE
- **All project dependencies** - Must be installed in your Python environment

### Install Dependencies
```bash
pip install -r requirements.txt
pip install pyinstaller
```

**Clarification:**
- **Developers/Builders:** Need Python to create the EXE
- **End Users:** Don't need Python to run the EXE you distribute

## Build Methods

### Method 1: Automated Build Script (Recommended)

The easiest way to build is using the provided batch script:

```bash
build_exe.bat
```

**What it does:**
1. Checks for PyInstaller installation
2. Verifies all dependencies
3. Runs PyInstaller with the spec file
4. Copies configuration files to dist/
5. Bundles wkhtmltopdf if available
6. Creates a ready-to-distribute package

**Output location:**
```
dist/IL2_CampaignTracker/
```

### Method 2: Manual PyInstaller

If you prefer manual control:

```bash
pyinstaller IL2_CampaignTracker_WITH_WKHTML.spec
```

Then manually copy these files to `dist/IL2_CampaignTracker/`:
- `campaign_progress_config.yaml`
- `object_categories.yaml`
- `stock_campaigns.yaml`

### Method 3: Custom Build

For advanced users who want to modify the build:

1. Edit `IL2_CampaignTracker_WITH_WKHTML.spec`
2. Modify paths, exclusions, or bundled files
3. Run: `pyinstaller IL2_CampaignTracker_WITH_WKHTML.spec`

## Understanding the Spec File

The spec file (`IL2_CampaignTracker_WITH_WKHTML.spec`) contains:

### Analysis Section
```python
a = Analysis(
    ['il2_campaign_tracker.py'],  # Entry point
    pathex=[],
    binaries=binaries,            # wkhtmltopdf and DLLs
    datas=datas,                  # YAML configs
    hiddenimports=[...],          # Required imports
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],         # Excluded modules
    noarchive=False,
)
```

### Key Components

**Entry Point:**
- `il2_campaign_tracker.py` - Main GUI application

**Bundled Data Files:**
- `campaign_progress_config.yaml` - Awards and ranks
- `object_categories.yaml` - Aircraft classifications
- `stock_campaigns.yaml` - Known campaigns

**Bundled Binaries:**
- `wkhtmltopdf.exe` - PDF generation (if found)
- `wkhtmltox.dll` - Required DLL (if found)

**Hidden Imports:**
All Python modules that PyInstaller might miss:
- `decode_campaing_usersave1`
- `step1_extract_mission_dates`
- `step3_generate_events`
- `step4_process_mission_logs`
- `il2_mission_debrief`
- `monitor_campaigns`
- `country_validator_gui`
- `mlg2txt`

**Excluded Modules:**
- `tkinter` - Not used, saves space

## Build Configuration

### Including wkhtmltopdf

The spec file automatically searches for wkhtmltopdf in:
- `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`
- `C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe`

If found, it's bundled into the executable. If not, users will be prompted to install it separately.

### One-File vs One-Folder

Current configuration: **One-Folder**
- Creates `dist/IL2_CampaignTracker/` directory
- Faster startup time
- Easier to debug
- Users can modify YAML configs

To switch to **One-File** (single EXE):

Edit spec file:
```python
exe = EXE(
    # ... existing parameters ...
    onefile=True,  # Change to True
)
```

**Trade-offs:**
- One-File: Single EXE, slower startup, harder to modify configs
- One-Folder: Multiple files, faster startup, easier config access

## Build Output

After successful build:

```
dist/
└── IL2_CampaignTracker/
    ├── IL2_CampaignTracker.exe          # Main executable
    ├── _internal/                       # PyInstaller runtime files
    │   ├── Python DLLs
    │   ├── Libraries
    │   └── Dependencies
    ├── campaign_progress_config.yaml
    ├── object_categories.yaml
    ├── stock_campaigns.yaml
    └── wkhtmltopdf.exe                  # If bundled
```

**Important:** The `_internal/` directory must stay with the EXE!

## Testing the Build

### Basic Test
1. Navigate to `dist/IL2_CampaignTracker/`
2. Double-click `IL2_CampaignTracker.exe`
3. GUI should open without errors

### Full Test
1. Run the EXE
2. Select IL-2 installation directory
3. Validate a campaign
4. Start monitoring
5. Generate a PDF report
6. Check that all features work

### Command Line Test
```bash
cd dist/IL2_CampaignTracker
IL2_CampaignTracker.exe
```

Watch for error messages in the console.

## Distribution

### Creating a Release Package

**Option 1: ZIP Archive**
```bash
cd dist
zip -r IL2_CampaignTracker_v1.5.zip IL2_CampaignTracker/
```

**Option 2: Installer (Advanced)**
Use tools like:
- Inno Setup (Windows)
- NSIS
- WiX Toolset

### What to Include

**Essential:**
- `IL2_CampaignTracker.exe`
- `_internal/` directory (entire folder)
- `*.yaml` config files
- `README.md` (or README.txt)

**Optional:**
- `wkhtmltopdf.exe` (if bundled)
- License file
- Example screenshots
- User guide

### What NOT to Include

**Never distribute:**
- `build/` directory (build artifacts)
- `*.pyc` files (Python bytecode)
- `__pycache__/` directories
- User-specific files:
  - `campaignsstates.txt`
  - `campaigns_decoded.json`
  - `campaign_events.json`
  - `reports/*.pdf`

## Troubleshooting Build Issues

### PyInstaller Fails to Start

**Error:** `pyinstaller: command not found`

**Solution:**
```bash
pip install --upgrade pyinstaller
# or
python -m pip install pyinstaller
```

### Missing Module Errors

**Error:** `ModuleNotFoundError: No module named 'X'`

**Solution:**
Add to spec file's `hiddenimports`:
```python
hiddenimports=[
    'existing_imports',
    'X',  # Add missing module here
],
```

### DLL Load Failed

**Error:** `ImportError: DLL load failed`

**Solution:**
1. Install Visual C++ Redistributable
2. Ensure all Python packages are properly installed
3. Try rebuilding in a clean environment

### wkhtmltopdf Not Found

**Error:** PDF generation fails in built EXE

**Solution:**
1. Install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
2. Rebuild to include it in bundle
3. Or instruct users to install separately

### EXE Too Large

**Current size:** ~150-200 MB (includes wkhtmltopdf)

**To reduce:**
1. Exclude wkhtmltopdf (save ~50 MB)
2. Use UPX compression:
   ```python
   exe = EXE(
       # ...
       upx=True,
       upx_exclude=[],
   )
   ```
3. Exclude unused libraries in spec file

### Antivirus False Positives

PyInstaller executables may trigger antivirus warnings.

**Solutions:**
1. Submit to antivirus vendors as false positive
2. Code-sign the executable (requires certificate)
3. Distribute source code as alternative

## Advanced Customization

### Custom Icon

Add to spec file:
```python
exe = EXE(
    # ...
    icon='path/to/icon.ico',
)
```

### Version Information

Add to spec file:
```python
exe = EXE(
    # ...
    version='version_info.txt',  # Create this file
)
```

Example `version_info.txt`:
```
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 5, 0, 0),
    prodvers=(1, 5, 0, 0),
    # ...
  ),
  kids=[
    StringFileInfo([
      StringTable(u'040904B0', [
        StringStruct(u'CompanyName', u'Your Name'),
        StringStruct(u'FileDescription', u'IL-2 Campaign Tracker'),
        StringStruct(u'FileVersion', u'1.5.0.0'),
        StringStruct(u'ProductName', u'IL-2 Campaign Tracker'),
        StringStruct(u'ProductVersion', u'1.5.0.0'),
      ])
    ])
  ]
)
```

### Build for Different Python Versions

To ensure compatibility:
```bash
# Use a specific Python version
py -3.8 -m PyInstaller IL2_CampaignTracker_WITH_WKHTML.spec
```

### Clean Build

Remove old build artifacts:
```bash
rmdir /s /q build dist
pyinstaller IL2_CampaignTracker_WITH_WKHTML.spec
```

Or on Linux/Mac:
```bash
rm -rf build dist
pyinstaller IL2_CampaignTracker_WITH_WKHTML.spec
```

## Continuous Integration

### GitHub Actions Example

Create `.github/workflows/build.yml`:
```yaml
name: Build EXE

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pyinstaller
    - name: Build EXE
      run: pyinstaller IL2_CampaignTracker_WITH_WKHTML.spec
    - name: Upload artifact
      uses: actions/upload-artifact@v2
      with:
        name: IL2_CampaignTracker
        path: dist/IL2_CampaignTracker/
```

## Support

For build issues:
1. Check this guide
2. Review PyInstaller documentation: https://pyinstaller.org/
3. Open an issue on GitHub with:
   - Python version
   - PyInstaller version
   - Full error message
   - Build command used

---

**Happy Building! 🔨**
