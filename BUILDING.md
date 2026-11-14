# Windows-Build und Austausch von pystray

## Getestete Build-Umgebung

- Windows x64
- Python 3.13.14 x64
- Paketversionen: siehe requirements-build-lock.txt
- Build-Skript: build-exe.ps1

## Normaler Build aus einem frischen Projektordner

Python installieren und im Projektordner ausführen:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build-lock.txt
powershell -ExecutionPolicy Bypass -File .\build-exe.ps1
```

Das Ergebnis liegt unter dist\WinCtrl.exe.

Das Build-Skript lädt Abhängigkeiten aus dem Paketindex.
Ein vollständig offline arbeitender Build ist damit nicht zugesichert.

## pystray durch eine geänderte Version ersetzen

Die Anwendung verwendet pystray 0.19.5 unter LGPLv3.
Die dazugehörigen Quellen und die Lizenztexte werden dem Release beigelegt.

1. Die WinCtrl-Quellen des Release-Stands bereitstellen.
2. Die Build-Umgebung wie oben anlegen und die festgehaltenen Pakete installieren.
3. pystray-0.19.5-source.zip in einen separaten Ordner entpacken.
4. Die gewünschten Änderungen an den pystray-Quellen durchführen.
5. Die geänderte Bibliothek in die Build-Umgebung installieren:

```powershell
.\.build-venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation --force-reinstall "C:\PFAD\ZU\pystray-0.19.5"
```

6. Danach die EXE direkt neu bauen, ohne zuvor erneut pystray vom Paketindex zu installieren:

```powershell
.\.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --exclude-module mouseinfo --exclude-module pymsgbox --name WinCtrl --add-data "templates;templates" --add-data "static;static" --add-data "assets;assets" --collect-submodules pystray --collect-submodules pycaw --collect-submodules comtypes winctrl_launcher.py
```

Die geänderte Bibliothek muss mit den von WinCtrl verwendeten Schnittstellen
kompatibel sein. Ein erfolgreicher Build beliebiger Änderungen wird nicht
garantiert.

## Lizenzhinweise

Der eigene WinCtrl-Code steht unter MIT.
pystray unterliegt seinen eigenen Lizenzbedingungen.

Die Berechtigungen der LGPL werden durch die MIT-Lizenz des eigenen Codes
nicht eingeschränkt. Insbesondere wird Reverse Engineering zur Fehlersuche
an Änderungen der LGPL-Bibliothek nicht untersagt.

Die Lizenzsammlung enthält auch Hinweise für installierte Build-Werkzeuge.
Sie ist keine exakte Liste aller in der EXE enthaltenen Module.

## Tests nach einem Neubau

- Tray und Weboberfläche
- Blockly-Aktion mit Logs und Unicode-Rückgabewert
- Tastatur-, Maus- und Fensteraktionen
- Aktionsabbruch und Zeitlimit
- Einstellungen nach Neustart
- ioBroker-Verbindung
- Autostart
