import json
import os
import secrets
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent
USER_BASE = (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinCtrl"
             if getattr(__import__("sys"), "frozen", False) else BASE)
USER_BASE.mkdir(parents=True, exist_ok=True)
DATA = USER_BASE / "data"
DATA.mkdir(exist_ok=True)
LOCK = threading.RLock()


def read(name, default):
    with LOCK:
        p = DATA / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write(name, value):
    with LOCK:
        p = DATA / name
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)


def settings():
    with LOCK:
        defaults = dict(
            host="0.0.0.0",
            port=8085,
            token=secrets.token_urlsafe(32),
            log_level="INFO",
            allow_dangerous_actions=False,
            action_timeout_minutes=1,
            ip_whitelist_enabled=False,
            ip_whitelist=[],
        )
        if not (DATA / "settings.json").exists():
            write("settings.json", defaults)
        cur = read("settings.json", {})
        if "action_timeout_minutes" not in cur and "action_timeout_seconds" in cur:
            cur["action_timeout_minutes"] = max(1, int(round(float(cur["action_timeout_seconds"]) / 60.0)))
        elif "action_timeout_minutes" in cur:
            cur["action_timeout_minutes"] = max(1, int(round(float(cur["action_timeout_minutes"]))))
        return {**defaults, **cur}


def actions():
    return read("actions.json", [])
