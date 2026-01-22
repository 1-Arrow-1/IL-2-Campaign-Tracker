@echo off
REM Build IL-2 Campaign Tracker as EXE
REM 
REM Prerequisites:
REM   pip install pyinstaller pyyaml psutil

setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "PYTHONHASHSEED=0"
set "PYINSTALLER_OPTS=--noconfirm --clean"

echo ====================================================================
echo IL-2 CAMPAIGN TRACKER - BUILD SCRIPT
echo ====================================================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo ERROR: PyInstaller not installed!
    echo.
    echo Please run: pip install pyinstaller
    echo.
    pause
    exit /b 1
)

REM Detect wkhtmltopdf (optional)
if exist "%ProgramFiles%\wkhtmltopdf\bin\wkhtmltopdf.exe" (
    set "WKHTMLTOPDF_PATH=%ProgramFiles%\wkhtmltopdf\bin\wkhtmltopdf.exe"
) else if exist "%ProgramFiles(x86)%\wkhtmltopdf\bin\wkhtmltopdf.exe" (
    set "WKHTMLTOPDF_PATH=%ProgramFiles(x86)%\wkhtmltopdf\bin\wkhtmltopdf.exe"
) else (
    echo WARNING: wkhtmltopdf.exe not found; PDF export will be skipped.
)

echo [1/5] Checking required files...
if not exist "il2_tracker_launcher.py" (
    echo ERROR: il2_tracker_launcher.py not found!
    pause
    exit /b 1
)
if not exist "step1_extract_mission_dates.py" (
    echo ERROR: step1_extract_mission_dates.py not found!
    pause
    exit /b 1
)
if not exist "decode_campaign_usersave1.py" (
    echo ERROR: decode_campaing_usersave1.py not found!
    pause
    exit /b 1
)
if not exist "step3_generate_events.py" (
    echo ERROR: step3_generate_events.py not found!
    pause
    exit /b 1
)
if not exist "monitor_campaigns.py" (
    echo ERROR: monitor_campaigns.py not found!
    pause
    exit /b 1
)
if not exist "step4_process_mission_logs.py" (
    echo ERROR: step4_process_mission_logs.py not found!
    pause
    exit /b 1
)
if not exist "campaign_progress_config.yaml" (
    echo ERROR: campaign_progress_config.yaml not found!
    pause
    exit /b 1
)
if not exist "object_categories.yaml" (
    echo ERROR: object_categories.yaml not found!
    pause
    exit /b 1
)
if not exist "stock_campaigns.yaml" (
    echo ERROR: stock_campaigns.yaml not found!
    pause
    exit /b 1
)
if not exist "cleanup_failed_missions.py" (
    echo ERROR: cleanup_failed_missions.py not found!
    pause
    exit /b 1
)
if not exist "mlg2txt.py" (
    echo ERROR: mlg2txt.py not found!
    pause
    exit /b 1
)
if not exist "IL2_CampaignTracker.spec" (
    echo ERROR: IL2_CampaignTracker.spec not found!
    pause
    exit /b 1
)
if not exist "campaign_service_record\campaign_service_record.spec" (
    echo ERROR: campaign_service_record\campaign_service_record.spec not found!
    pause
    exit /b 1
)
if not exist "mlg2txt.spec" (
    echo ERROR: mlg2txt.spec not found!
    pause
    exit /b 1
)
if not exist "popups_min.py" (
    echo ERROR: popups_min.py!
    pause
    exit /b 1
)
if not exist "campaign_reset_checker.py" (
    echo ERROR: campaign_reset_checker.py!
    pause
    exit /b 1
)
if not exist "backup_restore_gui.py" (
    echo ERROR: backup_restore_gui.py!
    pause
    exit /b 1
)
if not exist "IBMPlexSans-Light.ttf" (
    echo ERROR: IBMPlexSans-Light.ttf!
    pause
    exit /b 1
)
if not exist "utils" (
    echo ERROR: utils folder not found!
    pause
    exit /b 1
)
if not exist "utils\__init__.py" (
    echo ERROR: utils\__init__.py not found!
    pause
    exit /b 1
)
if not exist "utils\formatting.py" (
    echo ERROR: utils\formatting.py not found!
    pause
    exit /b 1
)
if not exist "utils\info_locale.py" (
    echo ERROR: utils\info_locale.py not found!
    pause
    exit /b 1
)
if not exist "utils\pathing.py" (
    echo ERROR: utils\pathing.py not found!
    pause
    exit /b 1
)
if not exist "utils\il2_paths.py" (
    echo ERROR: utils\il2_paths.py not found!
    pause
    exit /b 1
)
if not exist "utils\combat_results_html.py" (
    echo ERROR: utils\combat_results_html.py not found!
    pause
    exit /b 1
)
if not exist "utils\combat_results.py" (
    echo ERROR: utils\combat_results.py not found!
    pause
    exit /b 1
)
if not exist "utils\filesystem.py" (
    echo ERROR: utils\filesystem.py not found!
    pause
    exit /b 1
)
if not exist "utils\popup_state.py" (
    echo ERROR: utils\popup_state.py not found!
    pause
    exit /b 1
)
if not exist "utils\process.py" (
    echo ERROR: utils\process.py not found!
    pause
    exit /b 1
)
if not exist "utils\sorting.py" (
    echo ERROR: utils\sorting.py not found!
    pause
    exit /b 1
)
if not exist "utils\logging.py" (
    echo ERROR: utils\logging.py not found!
    pause
    exit /b 1
)
if not exist "utils\rank_scaling.py" (
    echo ERROR: utils\rank_scaling.py not found!
    pause
    exit /b 1
)
if not exist "sync_campaign_mission_states.py" (
    echo ERROR: sync_campaign_mission_states.py not found!
    pause
    exit /b 1
)
if not exist "locales" (
    echo ERROR: locales folder not found!
    pause
    exit /b 1
)
if not exist "locales\en.json" (
    echo ERROR: locales\en.json not found!
    pause
    exit /b 1
)
if not exist "locales\de.json" (
    echo ERROR: locales\de.json not found!
    pause
    exit /b 1
)
if not exist "CampaignRanksAwards.zip" (
    echo ERROR: CampaignRanksAwards.zip not found!
    pause
    exit /b 1
)
if not exist "cleanup_tracker_content.py" (
    echo ERROR: cleanup_tracker_content.py not found!
    pause
    exit /b 1
)
if not exist "cleanup_tracker_content.spec" (
    echo ERROR: cleanup_tracker_content.spec not found!
    pause
    exit /b 1
)
echo OK
echo.

echo [2/5] Validating Python syntax...
setlocal enabledelayedexpansion

for %%F in (
		"il2_tracker_launcher.py"
		"step1_extract_mission_dates.py"
		"monitor_campaigns.py"
		"step3_generate_events.py"
		"decode_campaign_usersave1.py"
		"step4_process_mission_logs.py"
		"il2_mission_debrief.py"
		"mlg2txt.py"
		"country_validator_gui.py"
		"cleanup_failed_missions.py"
		"popups_min.py"
		"campaign_reset_checker.py"
		"backup_restore_gui.py"
		"sync_campaign_mission_states.py"
        "cleanup_tracker_content.py"
		"utils\__init__.py"
		"utils\formatting.py"
		"utils\info_locale.py"
		"utils\pathing.py"
		"utils\il2_paths.py"
		"utils\sorting.py"
		"utils\process.py"
		"utils\popup_state.py"
		"utils\combat_results_html.py"
        "utils\combat_results.py"
		"utils\filesystem.py"
		"utils\logging.py"
        "utils\rank_scaling.py"
        "campaign_service_record\utils\i18n.py"
        "utils\locale_config.py"
) do (
    if exist %%F (
        echo Testing %%F ...
        python -m py_compile %%F
        if errorlevel 1 (
            echo ---------------------------------------------------------
            echo ERROR: Syntax / Indentation problem in %%F
            echo Build aborted!
            echo ---------------------------------------------------------
            pause
            exit /b 1
        ) else (
            echo ✓ %%F OK
        )
    ) else (
        echo WARNING: File %%F not found!
    )
)

endlocal
echo.
echo ===============================================
echo   All files passed SYNTAX check successfully!
echo ===============================================
echo.

echo [3/5] Cleaning old build files...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "IL2_Campaign_Tracker_v2.0" rmdir /s /q IL2_Campaign_Tracker_v2.0
if exist "IL2_CampaignTracker.exe" del /q IL2_CampaignTracker.exe
if exist "mlg2txt.exe" del /q mlg2txt.exe
echo OK
echo.

echo [4/5] Building EXEs with PyInstaller...
echo This may take a few minutes...
echo.

REM Build main tracker EXE
echo Building IL2_CampaignTracker.exe...
pyinstaller %PYINSTALLER_OPTS% IL2_CampaignTracker.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for IL2_CampaignTracker.exe!
    echo Check the error messages above.
    pause
    exit /b 1
)
echo ✓ IL2_CampaignTracker.exe built successfully
echo.

REM Build mlg2txt EXE
echo Building mlg2txt.exe...
pyinstaller %PYINSTALLER_OPTS% mlg2txt.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for mlg2txt.exe!
    echo Check the error messages above.
    pause
    exit /b 1
)
echo ✓ mlg2txt.exe built successfully
echo.

REM Build cleanup_tracker_content helper EXE
echo Building cleanup_tracker_content.exe...
pyinstaller %PYINSTALLER_OPTS% cleanup_tracker_content.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for cleanup_tracker_content.exe!
    echo Check the error messages above.
    pause
    exit /b 1
)
echo ✓ cleanup_tracker_content.exe built successfully
echo.

REM Build Campaign Service Record EXE
echo Building Campaign_Service_Record.exe...
pyinstaller %PYINSTALLER_OPTS% campaign_service_record\campaign_service_record.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for Campaign_Service_Record.exe!
    echo Check the error messages above.
    pause
    exit /b 1
)
echo ✓ Campaign_Service_Record.exe built successfully
echo OK
echo.

echo [5/5] Creating distribution package...
if not exist "IL2_Campaign_Tracker_v2.0" mkdir "IL2_Campaign_Tracker_v2.0"

REM Copy main tracker bundle (onedir)
xcopy /E /I /Y "dist\IL2_CampaignTracker_v2.0" "IL2_Campaign_Tracker_v2.0\" >NUL
if errorlevel 2 (
    echo ERROR: Could not copy IL2_CampaignTracker bundle!
    pause
    exit /b 1
)

REM Copy mlg2txt EXE
copy "dist\mlg2txt.exe" "IL2_Campaign_Tracker_v2.0\" >NUL
if errorlevel 1 (
    echo ERROR: Could not copy mlg2txt.exe!
    pause
    exit /b 1
)
REM Copy cleanup_tracker_content EXE
copy "dist\cleanup_tracker_content.exe" "IL2_Campaign_Tracker_v2.0\" >NUL
if errorlevel 1 (
    echo ERROR: Could not copy cleanup_tracker_content.exe!
    pause
    exit /b 1
)

REM Copy Campaign Service Record bundle
if exist "dist\Campaign_Service_Record" (
    xcopy /E /I /Y "dist\Campaign_Service_Record" "IL2_Campaign_Tracker_v2.0\" >NUL
    if errorlevel 2 (
        echo ERROR: Could not copy Campaign_Service_Record bundle!
        pause
        exit /b 1
    )
)

REM Copy Campaign Service Record bundle
if exist "dist\Campaign_Service_Record" (
    xcopy /E /I /Y "locales" "IL2_Campaign_Tracker_v2.0\locales\" >NUL
    if errorlevel 2 (
        echo ERROR: Could not copy Campaign_Service_Record bundle!
        pause
        exit /b 1
    )
)

REM Copy README if exists
if exist "README.html" copy "README.html" "IL2_Campaign_Tracker_v2.0\README.html" >NUL

REM Copy font if exists
if exist "IBMPlexSans-Light.ttf" copy "IBMPlexSans-Light.ttf" "IL2_Campaign_Tracker_v2.0\IBMPlexSans-Light.ttf" >NUL

REM Copy font if exists
if exist "NotoSansSC-VF.ttf" copy "NotoSansSC-VF.ttf" "IL2_Campaign_Tracker_v2.0\NotoSansSC-VF.ttf" >NUL

REM Copy iss file if exists
if exist "IL2_Campaign_Tracker.iss" copy "IL2_Campaign_Tracker.iss" "IL2_Campaign_Tracker_v2.0\IL2_Campaign_Tracker.iss" >NUL

REM Copy iss file if exists
if exist "*.yaml" copy "*.yaml" "IL2_Campaign_Tracker_v2.0\" >NUL

REM Unzip CampaignRanksAwards
@echo off
set SCRIPT_DIR=%~dp0
set TARGET_DIR=%SCRIPT_DIR%IL2_Campaign_Tracker_v2.0

powershell -NoProfile -Command ^
  "Expand-Archive -Path '%SCRIPT_DIR%CampaignRanksAwards.zip' -DestinationPath '%TARGET_DIR%' -Force -ErrorAction Stop"


REM Create quick start guide
echo IL-2 CAMPAIGN PROGRESS TRACKER v2.0 > "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo ================================================= >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo INSTALLATION >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo ------------ >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo 1. Download the latest release: IL2_Campaign_Tracker_v2.0.zip >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo 2. Extract the archive to a folder of your choice >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    (e.g. C:\IL2_Campaign_Tracker_v2.0) >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo 3. Copy the CampaignRanksAwards folder to: >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    ^<Path to IL-2 Great Battles^>\data\swf >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo 4. OPTIONAL: Extract Campaigns.gtp (standard IL-2 campaigns): >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    - Download unGTP-IL2 from: >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo      https://www.mediafire.com/file/caxpalaudz1hd47/unGTP-IL2.zip >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    - Place unGTP-IL2.exe into: >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo      ^<Path to IL-2^>\data >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    - Drag Campaigns.gtp onto unGTP-IL2.exe >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    - Ignore any error messages in the command window >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    After extraction, go to: >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    ^<Path to IL-2^>\data\(null)\campaigns >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    Copy the campaigns folder to: >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    ^<Path to IL-2^>\data\campaigns >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    IMPORTANT: Only campaigns located in >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    ^<Path to IL-2^>\data\campaigns >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo    can be monitored by the tracker. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo 5. Run IL2_Campaign_Tracker_v2.0.exe >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo. >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"
echo For detailed information, please refer to README.html >> "IL2_Campaign_Tracker_v2.0\QUICK_START.txt"

echo.
echo OK
echo.

echo ====================================================================
echo BUILD COMPLETE!
echo ====================================================================
echo.
echo Distribution package created in: IL2_Campaign_Tracker_v2.0\
echo.
echo Contents:
echo   - IL2_CampaignTracker_v2.0\IL2_CampaignTracker_v2.0.exe (bundle)
echo   - mlg2txt.exe (~8 MB)
echo   - Campaign_Service_Record\Campaign_Service_Record.exe (bundle)
echo   - Configuration files (*.yaml)
echo   - i18n translation files (locales\*.json)
echo   - Documentation (README.html, QUICK_START.txt)
echo   - CampaignRanksAwards (folder ~37 MB) 		
echo.
pause
