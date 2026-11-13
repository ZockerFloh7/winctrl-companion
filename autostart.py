import os
import subprocess
import sys
from pathlib import Path

SHORTCUT_NAME = "WinCtrl.lnk"


def get_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if p.exists():
            return p
    user = os.environ.get("USERPROFILE")
    if user:
        p = Path(user) / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        p.mkdir(parents=True, exist_ok=True)
        return p
    raise RuntimeError("Windows Startup-Verzeichnis konnte nicht ermittelt werden.")


def get_shortcut_path() -> Path:
    return get_startup_dir() / SHORTCUT_NAME


def is_autostart_enabled() -> bool:
    try:
        return get_shortcut_path().exists()
    except Exception:
        return False


def set_autostart(enabled: bool) -> bool:
    shortcut = get_shortcut_path()
    if not enabled:
        if shortcut.exists():
            shortcut.unlink()
        return False

    base_dir = Path(__file__).resolve().parent
    start_bat = base_dir / "start.bat"
    app_py = base_dir / "app.py"
    icon_path = base_dir / "tray.ico"

    venv_pythonw = base_dir / ".venv" / "Scripts" / "pythonw.exe"
    target_path = ""
    args = ""

    if getattr(sys, "frozen", False):
        target_path = str(Path(sys.executable).resolve())
        base_dir = Path(sys.executable).resolve().parent
        icon_path = Path(sys.executable).resolve()
    elif venv_pythonw.exists():
        target_path = str(venv_pythonw)
        args = f'"{app_py}"'
    else:
        target_path = str(start_bat)
        args = ""

    def ps_quote(value):
        return str(value).replace("'", "''")

    ps_cmd = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{ps_quote(shortcut)}'); "
        f"$s.TargetPath = '{ps_quote(target_path)}'; "
        f"$s.WorkingDirectory = '{ps_quote(base_dir)}'; "
    )
    if args:
        ps_cmd += f"$s.Arguments = '{ps_quote(args)}'; "
    if icon_path.exists():
        ps_cmd += f"$s.IconLocation = '{ps_quote(icon_path)},0'; "
    ps_cmd += "$s.Save()"

    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Autostart-Verknüpfung fehlgeschlagen: {res.stderr or res.stdout}")

    return shortcut.exists()
