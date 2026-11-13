import json
import os
import sys
import traceback
from datetime import datetime
from executor import execute_plan


def emit(level, text):
    payload = {
        "type": "log",
        "level": level,
        "time": datetime.now().isoformat(timespec="milliseconds"),
        "message": str(text),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: worker.py <plan_file.json>\n")
        sys.exit(1)

    plan_path = sys.argv[1]
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    action = data.get("action", {})
    settings = data.get("settings", {})
    source = data.get("source", "TEST")

    emit("INFO", f"{source} im Worker gestartet: {action.get('name', 'Unbenannt')}")
    try:
        ret_val = execute_plan(action, settings, emit)
        payload = {"type": "result", "return_value": str(ret_val if ret_val is not None else "")}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        emit("INFO", f"{source} erfolgreich abgeschlossen.")
        sys.exit(0)
    except Exception as e:
        emit("ERROR", f"Ausführungsfehler: {e}")
        sys.stdout.write(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
