# WinCtrl Companion

Windows-Tray-Anwendung als Companion für den ioBroker-Adapter `winctrl`.

WinCtrl stellt einen HTTP-Kommandoserver bereit und führt konfigurierbare
Windows-Aktionen aus. Aktionen werden in einer lokalen Weboberfläche mit
Blockly zusammengestellt.

## Funktionen

- Tray-Menü zum Öffnen der Konfiguration und Beenden der Anwendung
- Lokale Weboberfläche mit Blockly-Editor
- HTTP-Kommandoserver mit Token-Authentifizierung
- Optionale IP-Whitelist
- Programme starten und Webseiten öffnen
- Tastatur-, Maus-, Fenster- und Medienaktionen
- Aktionen testen, Logs anzeigen und Rückgabewerte senden
- Aktionszeitlimit und manueller Abbruch des Aktions-Workers
- Optionaler Autostart bei der Windows-Anmeldung

## Windows-EXE verwenden

Sobald ein Release verfügbar ist:

1. `WinCtrl.exe` aus dem Bereich Releases herunterladen.
2. Die EXE an einem dauerhaften Speicherort ablegen.
3. Die Anwendung starten.
4. Die Konfiguration über das Tray-Menü öffnen.

Die EXE enthält die Python-Laufzeit. Eine separate Python-Installation ist
für den vorgesehenen EXE-Betrieb nicht erforderlich.

Die Verwaltung läuft lokal unter:

http://127.0.0.1:5050/

Der Blockly-Editor lädt derzeit Blockly-Dateien von einem externen CDN.
Die EXE ist deshalb keine vollständig offline verfügbare Anwendung.

## Verbindung mit ioBroker

Adapter-Repository:

https://github.com/ZockerFloh7/ioBroker.winctrl

In den Einstellungen des Companions werden Bind-Adresse, Port, Token und
optional die IP-Whitelist konfiguriert.

Der Standardport des Kommandoservers ist `8085`.
Im ioBroker-Adapter müssen die Windows-IP-Adresse, der konfigurierte Port
und derselbe Token eingetragen werden.

Beispiel einer authentifizierten Verbindungsprüfung in PowerShell:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8085/ping" `
  -Headers @{ Authorization = "Bearer DEIN_TOKEN" }
```

## Datenspeicherung

Die EXE speichert ihre Daten benutzerbezogen:

- Einstellungen und Aktionen: `%LOCALAPPDATA%\WinCtrl\data`
- Anwendungslogs: `%LOCALAPPDATA%\WinCtrl\logs`
- Startfehler: `%LOCALAPPDATA%\WinCtrl\logs\startup-error.log`

Im Python-Quellbetrieb werden `data` und `logs` im Projektordner verwendet.

Persönliche Einstellungen und Aktionen werden nicht in die EXE eingebaut.
Beim Wechsel vom Quellbetrieb zur EXE werden sie nicht automatisch übernommen.

## Autostart

Autostart lässt sich in den WinCtrl-Einstellungen aktivieren und deaktivieren.

Dabei wird eine Verknüpfung namens `WinCtrl.lnk` im Autostart-Ordner des
aktuellen Windows-Benutzers erstellt oder entfernt.

- Die EXE vor dem Aktivieren an ihrem dauerhaften Speicherort ablegen.
- Nach einem Umzug der EXE Autostart deaktivieren und erneut aktivieren.
- Beim Wechsel vom Python-Betrieb zur EXE die Verknüpfung ebenfalls erneuern.

Der Start erfolgt bei der Benutzeranmeldung, nicht als Windows-Dienst.

## Aus dem Quellcode starten

Eine geeignete Python-3-Installation wird benötigt.
Die tatsächlich unterstützten Python-Versionen sind noch nicht als
Versionsmatrix dokumentiert.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nicht gleichzeitig eine Python-Instanz und die EXE mit denselben Ports starten.

## Windows-EXE bauen

Auf Windows mit installiertem Python:

```powershell
powershell -ExecutionPolicy Bypass -File .\build-exe.ps1
```

Das Skript erstellt eine separate `.build-venv`, installiert Abhängigkeiten
und PyInstaller und erzeugt:

```text
dist\WinCtrl.exe
```

Der aktuelle Build verwendet `--onefile` und `--windowed`.
Der Launcher unterstützt einen separaten internen Worker-Modus.
Worker-Meldungen werden über temporäre Dateien übertragen.

Die Build-Abhängigkeiten sind derzeit nicht vollständig auf exakte
Versionen festgelegt.

## Tests

Die Python-Testdateien befinden sich unter `tests`.

Die automatisierten Executor-Tests ersetzen Desktop- und Systemaktionen
teilweise durch Mocks. Sie ersetzen keine manuellen Tests der Windows-EXE,
der ioBroker-Verbindung oder des Autostarts.

## Sicherheit und Einschränkungen

- WinCtrl kann Eingaben simulieren und Programme im Kontext des angemeldeten
  Benutzers ausführen.
- Den Kommandoserver nicht ungeschützt ins Internet veröffentlichen.
- Einen eigenen starken Token verwenden und nicht weitergeben.
- Die IP-Whitelist bei Bedarf auf die berechtigten Clients begrenzen.
- Der Kommandoserver verwendet in dieser Version HTTP, nicht HTTPS.
- Herunterfahren muss gesondert in den Einstellungen freigegeben werden.
- Ein manueller Abbruch beendet den Aktions-Worker. Bereits ausgeführte
  Aktionen werden nicht rückgängig gemacht.
- Persönliche Konfiguration, Tokens und Logs gehören nicht ins Repository.

## Projektstatus

Erster öffentlicher Release in Vorbereitung.
Ein erfolgreicher lokaler Funktionstest ist keine vollständige
Kompatibilitätsprüfung für alle Windows-Systeme.

## Lizenz

Der eigene Projektcode steht unter der MIT-Lizenz. Siehe `LICENSE`.

Verwendete Drittanbieter-Komponenten und Ressourcen unterliegen ihren
jeweiligen Lizenzen.
