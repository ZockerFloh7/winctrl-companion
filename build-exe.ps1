$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m venv .build-venv
if ($LASTEXITCODE -ne 0) { throw 'Build-Umgebung konnte nicht erstellt werden.' }
$python = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
& $python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Installation der Build-Abhaengigkeiten fehlgeschlagen.' }
foreach ($folder in @('templates', 'static', 'assets')) {
    if (!(Test-Path $folder -PathType Container)) { throw "Ressourcenordner fehlt: $folder" }
}
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name WinCtrl --add-data 'templates;templates' --add-data 'static;static' --add-data 'assets;assets' --collect-submodules pystray --collect-submodules pycaw --collect-submodules comtypes winctrl_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'EXE-Build fehlgeschlagen.' }
Write-Host 'Test-Build erstellt: dist\WinCtrl.exe'
