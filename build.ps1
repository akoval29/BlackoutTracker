$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --name BlackoutTracker --collect-data tzdata app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Copy-Item -LiteralPath 'README.txt' -Destination 'dist\BlackoutTracker\README.txt'
& .\.venv\Scripts\python.exe bundle_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
# The flag is present in the ZIP, but excluded from installer payload.
Set-Content -LiteralPath 'dist\BlackoutTracker\portable.flag' -Value 'portable'
Compress-Archive -Path 'dist\BlackoutTracker' -DestinationPath 'dist\BlackoutTracker-0.2-win-x64.zip' -Force
if (Test-Path '.tools\InnoSetup\ISCC.exe') {
    & '.\.tools\InnoSetup\ISCC.exe' /Q installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
}
