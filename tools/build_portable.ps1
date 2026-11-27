$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$version = & .\.venv\Scripts\python.exe -c "from blackout_tracker.version import VERSION; print(VERSION)"
if ($LASTEXITCODE -ne 0) { throw 'Cannot read application version' }
# Build a clean portable payload separately; never package or delete the user's data folder.
$stage = 'build\portable-staging'
$assetArgs = @()
foreach ($file in @('app-icon.ico', 'app-icon.png', 'checkmark.svg')) {
    $assetArgs += @('--add-data', "${projectRoot}\assets\${file}:assets")
}
$assetArgs += @('--add-data', "${projectRoot}\assets\audio\registry.json:assets/audio")
foreach ($language in @('ua', 'en', 'de')) {
    $assetArgs += @('--add-data', "${projectRoot}\assets\audio\${language}:assets/audio/${language}")
}
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --distpath $stage --specpath build --name BlackoutTracker --icon "${projectRoot}\assets\app-icon.ico" --collect-data tzdata @assetArgs main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$payload = Join-Path $stage 'BlackoutTracker'
Rename-Item -LiteralPath (Join-Path $payload 'BlackoutTracker.exe') -NewName 'Blackout tracker.exe'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --distpath 'build\updater-dist' --workpath 'build\updater-work' --specpath build --name Updater tools/portable_updater.py
if ($LASTEXITCODE -ne 0) { throw 'Updater build failed' }
Copy-Item -LiteralPath 'build\updater-dist\Updater.exe' -Destination (Join-Path $payload 'Updater.exe')
Copy-Item -LiteralPath 'README.txt' -Destination (Join-Path $payload 'README.txt')
& .\.venv\Scripts\python.exe tools/collect_licenses.py (Join-Path $payload 'licenses')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
Set-Content -LiteralPath (Join-Path $payload 'portable.flag') -Value 'portable'
New-Item -ItemType Directory -Force -Path 'dist' | Out-Null
Compress-Archive -Path $payload -DestinationPath "dist\BlackoutTracker-$version-win-x64.zip" -Force
# Refresh the immediately runnable folder, keeping its data/ preferences and cache.
$destination = Join-Path $projectRoot 'dist\BlackoutTracker'
$executable = Join-Path $destination 'Blackout tracker.exe'
$oldExecutable = Join-Path $destination 'BlackoutTracker.exe'
$running = Get-Process -Name 'BlackoutTracker','Blackout tracker' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $executable -or $_.Path -eq $oldExecutable }
if ($running) {
    Write-Warning 'Portable ZIP is ready. Close BlackoutTracker before refreshing dist\BlackoutTracker; existing files and data were preserved.'
} else {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Get-ChildItem -LiteralPath $payload -Force | Copy-Item -Destination $destination -Recurse -Force
    # Remove only the three retired sounds from an existing portable installation.
    $resolvedDestination = [IO.Path]::GetFullPath($destination)
    foreach ($legacyName in @('siren.wav', 'blackout_in_5.wav', 'blackout_in_10.wav')) {
        $legacySound = [IO.Path]::GetFullPath((Join-Path $destination "_internal\assets\$legacyName"))
        if (-not $legacySound.StartsWith($resolvedDestination + '\')) { throw 'Unsafe legacy sound path' }
        if (Test-Path -LiteralPath $legacySound) { Remove-Item -LiteralPath $legacySound -Force }
    }
    if (Test-Path -LiteralPath $oldExecutable) { Remove-Item -LiteralPath $oldExecutable -Force }
}
