$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# Build a clean portable payload separately; never package or delete the user's data folder.
$stage = 'build\portable-staging'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --distpath $stage --specpath build --name BlackoutTracker --icon "${PSScriptRoot}\assets\app-icon.ico" --collect-data tzdata --add-data "${PSScriptRoot}\assets:assets" app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$payload = Join-Path $stage 'BlackoutTracker'
Copy-Item -LiteralPath 'README.txt' -Destination (Join-Path $payload 'README.txt')
& .\.venv\Scripts\python.exe bundle_licenses.py (Join-Path $payload 'licenses')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
Set-Content -LiteralPath (Join-Path $payload 'portable.flag') -Value 'portable'
New-Item -ItemType Directory -Force -Path 'dist' | Out-Null
Compress-Archive -Path $payload -DestinationPath 'dist\BlackoutTracker-0.12-win-x64.zip' -Force
# Refresh the immediately runnable folder, keeping its data/ preferences and cache.
$destination = Join-Path $PSScriptRoot 'dist\BlackoutTracker'
$executable = Join-Path $destination 'BlackoutTracker.exe'
$running = Get-Process -Name BlackoutTracker -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $executable }
if ($running) {
    Write-Warning 'Portable ZIP is ready. Close BlackoutTracker before refreshing dist\BlackoutTracker; existing files and data were preserved.'
} else {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Get-ChildItem -LiteralPath $payload -Force | Copy-Item -Destination $destination -Recurse -Force
}
