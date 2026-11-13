import os
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        plan = sys.argv[2]
        if len(sys.argv) == 5:
            sys.stdout = open(sys.argv[3], "w", encoding="utf-8", buffering=1)
            sys.stderr = open(sys.argv[4], "w", encoding="utf-8", buffering=1)
        sys.argv = [sys.argv[0], plan]
        from worker import main
        main()
    else:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinCtrl" / "logs"
        base.mkdir(parents=True, exist_ok=True)
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = open(base / "startup-error.log", "a", encoding="utf-8", buffering=1)
        try:
            from app import main
            main()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            raise SystemExit(1)
