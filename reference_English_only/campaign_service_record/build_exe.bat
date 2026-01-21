@echo off
REM ============================================================================
REM IL-2 Campaign Service Record - Build Script
REM
REM Builds standalone executable using PyInstaller
REM ============================================================================

echo ============================================================================
echo  IL-2 Campaign Service Record - Build Script
echo ============================================================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo ERROR: PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM Run PyInstaller
echo Building executable...
echo.
pyinstaller campaign_service_record.spec

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo  BUILD FAILED
    echo ============================================================================
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo  BUILD COMPLETE
echo ============================================================================
echo.
echo  Executable location: dist\Campaign_Service_Record\Campaign_Service_Record.exe
echo.
echo  You can now copy the entire Campaign_Service_Record folder to your
echo  IL-2 Campaign Tracker directory and run the executable.
echo.
echo ============================================================================
echo.

pause
