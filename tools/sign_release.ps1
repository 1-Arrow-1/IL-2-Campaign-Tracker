[CmdletBinding()]
param(
    # Folder holding the release executables (the installer staging folder by default).
    [string]$Path = (Join-Path (Split-Path -Parent $PSScriptRoot) "IL2_Campaign_Tracker_v3_ML"),

    [string]$MetadataPath = $(if ($env:ARTIFACT_SIGNING_METADATA) {
        $env:ARTIFACT_SIGNING_METADATA
    } else {
        "C:\CodeSigning\metadata.json"
    }),

    # Also compile IL2_Campaign_Tracker.iss in $Path, signing Setup and its uninstaller.
    [switch]$Installer,

    # Re-sign files that already carry a valid signature from $Publisher.
    [switch]$Force,

    [string]$Publisher = "Alexander Bleiholder"
)

# Signs the tracker's own executables with Azure Artifact Signing via sign_artifact.ps1.
# Sign after copying fresh builds into the folder and before packaging the installer
# or an update zip: signing changes the bytes, so checksums must come from the signed files.
#
#   az login
#   .\tools\sign_release.ps1                 # sign the executables in the staging folder
#   .\tools\sign_release.ps1 -Installer      # ...and build the signed Setup.exe
#   .\tools\sign_release.ps1 -Path <folder>  # any other folder, e.g. a dist/ or a package

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Built from this repository (mlg2txt.exe from the bundled MIT-licensed source).
$OwnExecutables = @(
    "IL2_CampaignTracker_v3_ML.exe",
    "IL2_Tracker_Control_GUI.exe",
    "Campaign_Service_Record.exe",
    "Career_Service_Record.exe",
    "IL2_Settings_Manager.exe",
    "cleanup_tracker_content.exe",
    "mlg2txt.exe",
    "il2_debrief.exe"
)

# Shipped but not built here. A signature vouches for the exact bytes, so these are never signed.
$ThirdPartyExecutables = @(
    "unGTP-IL2.exe"
)

$signScript = Join-Path $PSScriptRoot "sign_artifact.ps1"
if (-not (Test-Path -LiteralPath $signScript -PathType Leaf)) {
    throw "Signing helper not found: $signScript"
}
if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    throw "Folder not found: $Path"
}
$Path = (Resolve-Path -LiteralPath $Path).Path

function Test-SignedByPublisher {
    param([string]$File)
    $signature = Get-AuthenticodeSignature -LiteralPath $File
    return $signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid -and
        $signature.SignerCertificate.Subject -like "CN=$Publisher,*"
}

Write-Host "Signing release executables in $Path" -ForegroundColor Cyan

$signed = @()
$skipped = @()
foreach ($name in $OwnExecutables) {
    $file = Join-Path $Path $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        continue
    }
    if (-not $Force -and (Test-SignedByPublisher -File $file)) {
        $skipped += $name
        Write-Host "  already signed: $name" -ForegroundColor DarkGray
        continue
    }
    & $signScript -File $file -MetadataPath $MetadataPath
    $signed += $name
}

if (-not $signed -and -not $skipped) {
    throw "None of the tracker's executables were found in $Path"
}

foreach ($exe in Get-ChildItem -LiteralPath $Path -Filter *.exe -File) {
    if ($ThirdPartyExecutables -contains $exe.Name) {
        Write-Host "  not signed (third party): $($exe.Name)" -ForegroundColor Yellow
    } elseif ($OwnExecutables -notcontains $exe.Name) {
        Write-Host "  not signed (not on the list in sign_release.ps1): $($exe.Name)" -ForegroundColor Yellow
    }
}

if ($Installer) {
    $iss = Join-Path $Path "IL2_Campaign_Tracker.iss"
    if (-not (Test-Path -LiteralPath $iss -PathType Leaf)) {
        throw "Installer script not found: $iss"
    }
    $iscc = $null
    $isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCommand) { $iscc = $isccCommand.Source }
    if (-not $iscc) {
        foreach ($candidate in @(
                (Join-Path ([Environment]::GetEnvironmentVariable("ProgramFiles(x86)")) "Inno Setup 6\ISCC.exe"),
                (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))) {
            if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                $iscc = $candidate
                break
            }
        }
    }
    if (-not $iscc) {
        throw "ISCC.exe was not found. Install Inno Setup 6."
    }

    Write-Host "Building signed installer from $iss" -ForegroundColor Cyan
    # Run the helper under this same PowerShell: under pwsh 7 a bare "powershell.exe"
    # starts Windows PowerShell 5.1, which fails to load 7's security module mid-compile.
    $psExe = (Get-Process -Id $PID).Path
    $innoSignCommand =
        'azureartifacts=$q' + $psExe + '$q -NoProfile -ExecutionPolicy Bypass -File $q' +
        $signScript + '$q -MetadataPath $q' + $MetadataPath + '$q -File $f'
    $outputDir = Join-Path $Path "Output"
    $before = Get-Date
    & $iscc "-dAZURE_SIGNING=1" "-s$innoSignCommand" $iss
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed (exit $LASTEXITCODE)"
    }
    $setup = Get-ChildItem -LiteralPath $outputDir -Filter *.exe -File |
        Where-Object { $_.LastWriteTime -ge $before } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $setup) {
        throw "No new installer found in $outputDir"
    }
    & $signScript -File $setup.FullName -VerifyOnly
    Write-Host "Signed installer: $($setup.FullName)" -ForegroundColor Green
}

Write-Host ("Done. Signed {0}, already signed {1}." -f $signed.Count, $skipped.Count) -ForegroundColor Green
