@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
python -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
if not errorlevel 1 goto python
py -3 -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
if not errorlevel 1 goto launcher
echo Python nicht gefunden. Bitte Python installieren und PATH aktivieren.
goto error
:python
python -m venv .venv
if errorlevel 1 goto error
goto install
:launcher
py -3 -m venv .venv
if errorlevel 1 goto error
:install
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe app.py
if errorlevel 1 goto error
exit /b 0
:error
pause
exit /b 1
