<#
.SYNOPSIS
    Creates a minimal update zip from the assembled IL2_Campaign_Tracker_v3_ML distribution.
    Only includes files that change between versions (EXEs with new code, static web files, locales).
    Assumes IL2_Campaign_Tracker_v3_ML\ is already assembled by build_exe.bat.
#>

param(
    [string]$SrcDir = "IL2_Campaign_Tracker_v3_ML",
    [string]$VersionFile = "version.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SrcDir)) {
    Write-Error "Distribution directory not found: $SrcDir"
    exit 1
}
if (-not (Test-Path $VersionFile)) {
    Write-Error "Version file not found: $VersionFile"
    exit 1
}

$version = (Get-Content $VersionFile -Raw).Trim()
Write-Host "Creating update zip for version $version..."

# Write update manifest
$manifest = @{
    version     = $version
    description = "IL-2 Campaign Tracker v$version update"
    protected   = @("data", "story_data", "config.yaml", "settings.json")
} | ConvertTo-Json -Depth 3
$manifest | Set-Content "$SrcDir\update_manifest.json" -Encoding UTF8

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zipFile = "IL2_CampaignTracker_update_v$version.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile -Force }

$zip = [System.IO.Compression.ZipFile]::Open(
    (Join-Path (Get-Location) $zipFile),
    [System.IO.Compression.ZipArchiveMode]::Create
)

# EXEs rebuilt for this version (only include what actually changed)
$coreExes = @(
    "IL2_CampaignTracker_v3_ML.exe",
    "Campaign_Service_Record.exe",
    "Career_Service_Record.exe"
)

# Live files that are read from disk at runtime (not compiled into EXEs)
$liveFiles = @(
    "_internal\static\index.html",
    "_internal\static\js\api.js",
    "_internal\static\js\detail.js",
    "_internal\static\js\main.js",
    "_internal\static\js\landing.js",
    "_internal\static\js\i18n.js",
    "_internal\static\js\medal_showcase.js",
    "_internal\static\css\detail.css",
    "_internal\static\css\landing.css",
    "_internal\static\css\main.css",
    "version.txt",
    "update_manifest.json"
)

$totalBytes = 0

function Add-Entry {
    param($zip, $fullPath, $entryName)
    $script:totalBytes += (Get-Item $fullPath).Length
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $fullPath, $entryName,
        [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}

foreach ($rel in ($coreExes + $liveFiles)) {
    $full = Join-Path $SrcDir $rel
    if (Test-Path $full) {
        Add-Entry $zip $full $rel.Replace('\', '/')
    }
}

# All locale files
Get-ChildItem "$SrcDir\locales\*.json" | ForEach-Object {
    Add-Entry $zip $_.FullName "locales/$($_.Name)"
}

$zip.Dispose()

$sizeMB  = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
$rawMB   = [math]::Round($totalBytes / 1MB, 1)
Write-Host "Done: $zipFile  ($sizeMB MB compressed, $rawMB MB raw)"
