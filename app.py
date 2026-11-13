import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

from flask import Flask, jsonify, render_template, request, send_file
from waitress import create_server

import storage as store
import autostart
from executor import execute_plan
import network_policy
# WINCTRL_FEATURE_UPDATE
# WINCTRL_UI_V2

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
ADMIN_KEY = secrets.token_urlsafe(32)

jobs = {}
jobs_lock = threading.RLock()
active_process = None
active_process_lock = threading.RLock()
active_job_id = None

recent = deque(maxlen=500)
log_lock = threading.Lock()


class MemoryLog(logging.Handler):
    def emit(self, record):
        with log_lock:
            recent.appendleft(self.format(record))


logdir = store.USER_BASE / "logs"
logdir.mkdir(exist_ok=True)
for handler in [
    RotatingFileHandler(logdir / "winctrl.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8"),
    MemoryLog(),
]:
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(handler)

logging.getLogger().setLevel(store.settings()["log_level"])


@app.before_request
def protect():
    if request.host not in ("127.0.0.1:5050", "localhost:5050"):
        return jsonify(error="Ungültiger Host"), 403
    if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
        request.headers.get("X-WinCtrl-Key", ""), ADMIN_KEY
    ):
        return jsonify(error="Seite neu laden: Sitzungsschlüssel fehlt"), 403


@app.errorhandler(Exception)
def error(error):
    from werkzeug.exceptions import HTTPException

    code = (
        error.code
        if isinstance(error, HTTPException)
        else 400
        if isinstance(error, (ValueError, KeyError, TypeError))
        else 500
    )
    logging.exception("Anfrage fehlgeschlagen")
    return jsonify(error=str(error)), code


def find(action_id):
    from werkzeug.exceptions import NotFound

    a = next((x for x in store.actions() if x["id"] == action_id), None)
    if not a:
        raise NotFound("Aktion nicht gefunden")
    return a


def validate(a, others):
    import re

    a["name"] = str(a.get("name", "")).strip()
    a["trigger"] = str(a.get("trigger", "")).strip()
    if not a["name"]:
        raise ValueError("Name darf nicht leer sein")

    # If trigger is empty or doesn't start with '/', normalize or validate
    if not a["trigger"]:
        raise ValueError("Trigger darf nicht leer sein (z.B. /netflix)")
    if not a["trigger"].startswith("/"):
        a["trigger"] = "/" + a["trigger"]

    if not re.fullmatch(r"/[A-Za-z0-9_/-]+", a["trigger"]):
        raise ValueError("Trigger muss mit / beginnen und darf nur Buchstaben, Ziffern, Unterstrich und Bindestrich enthalten (z.B. /netflix)")
    if any(x["id"] != a["id"] and x.get("trigger") == a["trigger"] for x in others):
        raise ValueError("Trigger schon vergeben")
    if not isinstance(a.get("enabled"), bool):
        raise ValueError("Aktiv muss ein boolescher Wert sein")
    if not isinstance(a.get("blockly"), dict):
        raise ValueError("Ungültiger Workspace")

    category = str(a.get("category", "")).strip()
    a["category"] = category if category in {"", "blue", "green", "yellow", "orange", "red", "purple"} else ""
    a.pop("tags", None)
    if a["trigger"] == "/ping":
        raise ValueError("/ping ist für die Verbindungsprüfung reserviert.")
    raw_to = a.get("timeout_minutes")
    if raw_to is None or str(raw_to).strip() == "":
        a["timeout_minutes"] = None
    else:
        try:
            val = int(raw_to)
            a["timeout_minutes"] = max(1, min(120, val))
        except Exception:
            a["timeout_minutes"] = 1


@app.get("/")
def home():
    return render_template("index.html", admin_key=ADMIN_KEY)


@app.get("/settings")
def settings_page():
    return render_template("settings.html", admin_key=ADMIN_KEY)


@app.get("/editor/<action_id>")
def editor(action_id):
    return render_template("editor.html", admin_key=ADMIN_KEY, action=find(action_id))


@app.get("/api/actions")
def actions():
    return jsonify(store.actions())


@app.post("/api/actions")
def create():
    d = request.get_json() or {}
    with store.LOCK:
        all_actions = store.actions()
        raw_to = d.get("timeout_minutes")
        to_min = int(raw_to) if raw_to is not None and str(raw_to).strip() != "" else None
        a = dict(
            id=uuid.uuid4().hex,
            name=d.get("name", "Neue Aktion"),
            category=d.get("category", ""),
            trigger=d.get("trigger", ""),
            enabled=False,
            timeout_minutes=to_min,
            blockly=d.get("blockly", {"blocks": {"languageVersion": 0, "blocks": [{"type": "winctrl_when", "x": 50, "y": 50}]}}),
        )
        validate(a, all_actions)
        all_actions.append(a)
        store.write("actions.json", all_actions)
    logging.info("Neue Aktion erstellt: %s (%s)", a["name"], a["trigger"])
    return jsonify(a), 201


@app.put("/api/actions/<action_id>")
def update(action_id):
    d = request.get_json() or {}
    with store.LOCK:
        a = find(action_id)
        all_actions = store.actions()
        for k in ("name", "trigger", "enabled", "blockly", "category"):
            if k in d:
                a[k] = d[k]
        if "timeout_minutes" in d:
            raw_to = d["timeout_minutes"]
            a["timeout_minutes"] = int(raw_to) if raw_to is not None and str(raw_to).strip() != "" else None

        validate(a, all_actions)
        store.write("actions.json", [a if x["id"] == action_id else x for x in all_actions])
    logging.info("Aktion gespeichert: %s; trigger=%s; timeout=%s; aktiv=%s", a["name"], a["trigger"], a.get("timeout_minutes"), a["enabled"])
    return jsonify(ok=True)


@app.delete("/api/actions/<action_id>")
def delete(action_id):
    with store.LOCK:
        a = find(action_id)
        store.write("actions.json", [x for x in store.actions() if x["id"] != action_id])
    logging.info("Aktion gelöscht: %s", a["name"])
    return jsonify(ok=True)


@app.get("/api/actions/<action_id>/export")
def export(action_id):
    return send_file(
        io.BytesIO(json.dumps(find(action_id), ensure_ascii=False, indent=2).encode()),
        as_attachment=True,
        download_name="aktion.winaction.json",
        mimetype="application/json",
    )


@app.post("/api/actions/import")
def import_action():
    d = request.get_json() or {}
    with store.LOCK:
        all_actions = store.actions()
        raw_to = d.get("timeout_minutes")
        to_min = int(raw_to) if raw_to is not None and str(raw_to).strip() != "" else None

        imp_trigger = d.get("trigger", "").strip()
        if not imp_trigger or not imp_trigger.startswith("/"):
            imp_trigger = "/" + imp_trigger.lstrip("/") if imp_trigger else f"/import_{uuid.uuid4().hex[:6]}"

        # avoid collision on import
        base_trig = imp_trigger
        counter = 1
        while any(x.get("trigger") == imp_trigger for x in all_actions):
            imp_trigger = f"{base_trig}_{counter}"
            counter += 1

        a = dict(
            id=uuid.uuid4().hex,
            name=d.get("name", "Importierte Aktion"),
            category=d.get("category", ""),
            trigger=imp_trigger,
            enabled=False,
            timeout_minutes=to_min,
            blockly=d.get("blockly", d),
        )
        validate(a, all_actions)
        all_actions.append(a)
        store.write("actions.json", all_actions)
    return jsonify(ok=True)


def new_job(action, source):
    with jobs_lock:
        for key in list(jobs):
            if len(jobs) < 50:
                break
            if jobs[key]["state"] in ("done", "error", "stopped"):
                del jobs[key]
        jid = uuid.uuid4().hex
        jobs[jid] = dict(
            id=jid,
            action_id=action["id"],
            state="starting",
            error=None,
            return_value="",
            logs=deque(maxlen=1000),
            seq=0,
            started_at=None,
            finished_at=None,
        )
    return jid


def emit(jid, level, text):
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        level = "INFO"
    with jobs_lock:
        j = jobs[jid]
        j["seq"] += 1
        j["logs"].append(
            dict(
                seq=j["seq"],
                time=datetime.now().isoformat(timespec="milliseconds"),
                level=level,
                message=str(text),
            )
        )
    logging.log(getattr(logging, level), "[%s] %s", jid[:8], text)


def worker_output_lines(proc, output_path):
    if output_path is None:
        yield from proc.stdout
        return
    with open(output_path, "rb") as stream:
        pending = b""
        while True:
            chunk = stream.read(65536)
            if chunk:
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    yield line.decode("utf-8", errors="replace")
            elif proc.poll() is not None:
                # Process has exited: perform a final read after observing exit.
                pending += stream.read()
                if pending:
                    yield from pending.decode("utf-8", errors="replace").splitlines()
                break
            else:
                time.sleep(0.05)


def run_worker_process(jid, action, config, source):
    global active_process, active_job_id
    temp_file = None
    stderr_file = None
    worker_dir = None
    output_path = None
    error_path = None
    proc = None
    try:
        with jobs_lock:
            if jobs[jid]["state"] == "stopped":
                return
            jobs[jid].update(state="running", started_at=datetime.now().isoformat())
        emit(jid, "INFO", f"{source} gestartet: {action['name']}")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
            temp_file = tf.name
            json.dump({"action": action, "settings": config, "source": source}, tf, ensure_ascii=False)

        python_exe = sys.executable
        worker_script = str(store.BASE / "worker.py")

        # Bestehende Umgebung erhalten und Python-Worker auf UTF-8 setzen.
        worker_env = os.environ.copy()
        worker_env["PYTHONIOENCODING"] = "utf-8"
        worker_env["PYTHONUNBUFFERED"] = "1"

        worker_command = [python_exe, worker_script, temp_file]
        if getattr(sys, "frozen", False):
            worker_dir = tempfile.TemporaryDirectory(prefix="winctrl_worker_")
            output_path = os.path.join(worker_dir.name, "events.jsonl")
            error_path = os.path.join(worker_dir.name, "stderr.log")
            for path in (output_path, error_path):
                with open(path, "wb"):
                    pass
            worker_command = [python_exe, "--worker", temp_file, output_path, error_path]
        stderr_file = tempfile.TemporaryFile(mode="w+b")
        proc = subprocess.Popen(
            worker_command,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="strict",
            bufsize=1,
            env=worker_env,
        )

        with active_process_lock:
            active_process = proc
            active_job_id = jid
            with jobs_lock:
                stopped = jobs[jid]["state"] == "stopped"
            if stopped:
                proc.kill()

        for line in worker_output_lines(proc, output_path):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if msg.get("type") == "log":
                    emit(jid, msg.get("level", "INFO"), msg.get("message", ""))
                elif msg.get("type") == "error":
                    with jobs_lock:
                        jobs[jid]["state"] = "error"
                        jobs[jid]["error"] = str(msg.get("message", "Ausführung fehlgeschlagen"))
                elif msg.get("type") == "result":
                    ret = msg.get("return_value", "")
                    with jobs_lock:
                        jobs[jid]["return_value"] = str(ret)
                else:
                    emit(jid, "INFO", line)
            except Exception:
                emit(jid, "INFO", line)

        proc.wait()
        stderr_file.seek(0)
        stderr_out = stderr_file.read().decode("utf-8", errors="replace")
        if error_path:
            with open(error_path, "r", encoding="utf-8", errors="replace") as ef:
                stderr_out += ef.read()
        if stderr_out:
            for l in stderr_out.strip().splitlines():
                emit(jid, "DEBUG", f"[stderr] {l}")

        with jobs_lock:
            if jobs[jid]["state"] not in ("stopped", "error"):
                if proc.returncode == 0:
                    emit(jid, "INFO", f"{source} erfolgreich abgeschlossen")
                    jobs[jid]["state"] = "done"
                else:
                    err_msg = f"Worker mit Exit-Code {proc.returncode} beendet"
                    emit(jid, "ERROR", err_msg)
                    jobs[jid]["state"] = "error"
                    jobs[jid]["error"] = err_msg

    except Exception as e:
        emit(jid, "ERROR", str(e))
        logging.exception("Ausführung fehlgeschlagen")
        with jobs_lock:
            jobs[jid].update(state="error", error=str(e))
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdout:
                proc.stdout.close()
        if stderr_file is not None:
            stderr_file.close()
        if worker_dir is not None:
            try:
                worker_dir.cleanup()
            except OSError:
                logging.exception('Worker-Temporaerdateien konnten nicht entfernt werden')
        with active_process_lock:
            if active_job_id == jid:
                active_process = None
                active_job_id = None
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        with jobs_lock:
            jobs[jid]["finished_at"] = datetime.now().isoformat()


@app.post("/api/actions/<action_id>/test")
def test(action_id):
    global active_process, active_job_id
    a = find(action_id)
    d = request.get_json(silent=True) or {}
    if "blockly" in d:
        a["blockly"] = d["blockly"]
    if "timeout_minutes" in d:
        raw = d["timeout_minutes"]
        if raw is None or str(raw).strip() == "":
            a["timeout_minutes"] = None
        else:
            try:
                a["timeout_minutes"] = max(1, min(120, int(raw)))
            except Exception:
                a["timeout_minutes"] = 1

    with active_process_lock:
        if active_job_id is not None:
            return jsonify(error="Eine andere Aktion läuft bereits"), 409

        jid = new_job(a, "TEST")
        active_job_id = jid
        t = threading.Thread(target=run_worker_process, args=(jid, a, store.settings(), "TEST"), daemon=True)
        t.start()

    return jsonify(id=jid), 202


@app.post("/api/tests/<jid>/stop")
def stop_test(jid):
    global active_process, active_job_id
    with active_process_lock:
        if active_job_id == jid and active_process is not None and active_process.poll() is None:
            emit(jid, "WARNING", "Force-Stop (Beenden) durch Benutzer angefordert …")
            try:
                active_process.kill()
                emit(jid, "WARNING", "Prozess wurde hart beendet (SIGKILL/TerminateProcess).")
            except Exception as e:
                emit(jid, "ERROR", f"Fehler beim Beenden: {e}")

            with jobs_lock:
                if jid in jobs:
                    jobs[jid]["state"] = "stopped"
                    jobs[jid]["error"] = "Vom Benutzer abgebrochen"
            return jsonify(ok=True)

    with jobs_lock:
        if jid in jobs and jobs[jid]["state"] in ("starting", "running"):
            jobs[jid]["state"] = "stopped"
            jobs[jid]["error"] = "Abgebrochen"
            return jsonify(ok=True)

    return jsonify(error="Kein laufender Test mit dieser ID"), 404


@app.get("/api/tests/<jid>")
def status(jid):
    with jobs_lock:
        j = jobs.get(jid)
        if not j:
            return jsonify(error="Lauf nicht gefunden"), 404
        result = {k: v for k, v in j.items() if k != "logs"}
        result["logs"] = list(j["logs"])
        return jsonify(result)


@app.get("/api/logs")
def logs():
    with log_lock:
        return jsonify(list(recent))


@app.get("/api/autostart")
def get_autostart():
    return jsonify(enabled=autostart.is_autostart_enabled())


@app.post("/api/autostart")
def post_autostart():
    d = request.get_json() or {}
    desired = bool(d.get("enabled", False))
    res = autostart.set_autostart(desired)
    logging.info("Autostart gesetzt: %s", res)
    return jsonify(enabled=res)


class CommandServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global active_process, active_job_id
        try:
            c = self.server.config
            p = urlsplit(self.path)
            peer = self.client_address[0]
            try:
                permitted = network_policy.allowed(peer, c)
            except ValueError:
                permitted = False
            if not permitted:
                network_policy.observe(peer, False, False)
                return self.reply_json(403, {"status": 0, "status_text": "failed", "response": "IP nicht freigegeben", "error": "IP nicht freigegeben"})
            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else parse_qs(p.query).get("token", [""])[0]
            authenticated = bool(c.get("token")) and secrets.compare_digest(token, c["token"])
            network_policy.observe(peer, True, authenticated)
            if not authenticated:
                return self.reply_json(403, {"status": 0, "status_text": "failed", "response": "Unauthorized", "error": "Unauthorized"})
            if p.path == "/ping":
                return self.reply_json(200, {"service": "winctrl", "response": "pong", "status_text": "pong"})

            a = next((x for x in store.actions() if x.get("enabled") and x.get("trigger") and x["trigger"] == p.path), None)
            if not a:
                return self.reply_json(404, {"status": 0, "status_text": "failed", "response": "Unbekannte oder deaktivierte Aktion", "error": "Not Found"})

            with active_process_lock:
                if active_job_id is not None:
                    return self.reply_json(409, {"status": 1, "status_text": "running", "response": "Aktion läuft bereits", "error": "Conflict"})
                jid = new_job(a, "HTTP")
                active_job_id = jid

            run_worker_process(jid, a, c, "HTTP")
            with jobs_lock:
                j = jobs[jid]
                failed = j["state"] in ("error", "stopped")
                err_text = j["error"] or ""
                ret_val = j["return_value"]

            if failed:
                payload = {
                    "status": 0,
                    "status_text": "failed",
                    "response": err_text or "Ausführungsfehler",
                    "error": err_text
                }
                self.reply_json(500, payload)
            else:
                payload = {
                    "status": 2,
                    "status_text": "success",
                    "response": ret_val if ret_val else "OK",
                    "return_value": ret_val
                }
                self.reply_json(200, payload)

        except Exception as e:
            logging.exception("HTTP-Fehler")
            self.reply_json(500, {"status": 0, "status_text": "failed", "response": str(e), "error": str(e)})

    def reply_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass

    def log_message(self, *args):
        pass


server = None
server_thread = None
server_lock = threading.RLock()


def bind(config):
    global server, server_thread
    s = CommandServer((config["host"], config["port"]), Handler)
    s.config = dict(config)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    server = s
    server_thread = t


def apply(config):
    global server
    if not isinstance(config.get("ip_whitelist_enabled", False), bool):
        raise ValueError("Whitelist-Aktivierung muss wahr oder falsch sein.")
    config["ip_whitelist"] = network_policy.normalize_entries(config.get("ip_whitelist", []))
    config["port"] = int(config["port"])
    config["action_timeout_minutes"] = max(1, int(round(float(config.get("action_timeout_minutes", 1)))))
    if config["host"] not in ("0.0.0.0", "127.0.0.1"):
        raise ValueError("Ungültige Bind-Adresse")
    if not 1 <= config["port"] <= 65535 or config["port"] == 5050:
        raise ValueError("Ungültiger Port")
    if not config["token"]:
        raise ValueError("Token darf nicht leer sein")
    if config["log_level"] not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ValueError("Ungültiger Log-Level")
    if not 1 <= config["action_timeout_minutes"] <= 120:
        raise ValueError("Standard-Timeout: 1 bis 120 Minuten")

    with server_lock:
        old = dict(server.config) if server else None
        if old != config:
            if server:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)
                server = None
            try:
                bind(config)
            except Exception:
                if old:
                    try:
                        bind(old)
                    except Exception:
                        logging.exception("Vorherige Bindung konnte nicht wiederhergestellt werden")
                raise
        store.write("settings.json", config)
        logging.getLogger().setLevel(config["log_level"])
        logging.info("Kommandoserver aktiv: %s:%s", config["host"], config["port"])


@app.get("/api/settings")
def get_settings():
    with server_lock:
        return jsonify(
            settings=store.settings(),
            running=bool(server),
            active={k: v for k, v in server.config.items() if k != "token"} if server else None,
            autostart=autostart.is_autostart_enabled(),
        )


@app.post("/api/settings")
def put_settings():
    c = store.settings()
    d = request.get_json() or {}
    for k in c:
        if k in d:
            c[k] = d[k]
    apply(c)
    return jsonify(ok=True)


def main():
    import pystray
    from PIL import Image, ImageDraw

    admin = create_server(app, host="127.0.0.1", port=5050, threads=6)
    threading.Thread(target=admin.run, daemon=True).start()
    try:
        apply(store.settings())
    except Exception:
        logging.exception("Kommandoserver nicht gestartet; Einstellungen öffnen")

    icon_path = store.BASE / "assets" / "tray.ico"

    if not icon_path.exists():
        logging.warning("Tray-Icon nicht gefunden: %s – verwende Fallback", icon_path)

    def home(icon=None, item=None):
        webbrowser.open("http://127.0.0.1:5050/")

    tray = pystray.Icon(
        "WinCtrl",
        Image.open(icon_path) if icon_path.exists() else Image.new("RGBA", (64, 64), (59, 130, 246, 255)),
        "WinCtrl",
        menu=pystray.Menu(
            pystray.MenuItem("Konfiguration öffnen", home, default=True),
            pystray.MenuItem("Einstellungen", lambda icon, item: webbrowser.open("http://127.0.0.1:5050/settings")),
            pystray.MenuItem("Beenden", lambda icon, item: icon.stop()),
        ),
    )
    
    try:
        home()
        tray.run()
    finally:
        with active_process_lock:
            if active_process and active_process.poll() is None:
                try:
                    active_process.kill()
                except Exception:
                    pass
        if server:
            server.shutdown()
            server.server_close()
        admin.close()
        logging.shutdown()



@app.get("/api/clients")
def api_clients():
    return jsonify(network_policy.clients())

if __name__ == "__main__":
    main()
