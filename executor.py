import ctypes
import logging
import os
import shutil
import subprocess
import time
import webbrowser

MEDIA = dict(
    play_pause="playpause",
    next="nexttrack",
    prev="prevtrack",
    stop="stop",
    volume_up="volumeup",
    volume_down="volumedown",
    mute="volumemute",
)


class Runner:
    def __init__(self, action, settings, emit):
        self.action = action
        self.settings = settings
        self.emit = emit
        self.variables = {}
        self.return_value = ""
        try:
            val = action.get("timeout_minutes")
            timeout_min = int(val) if val is not None and str(val).strip() != "" else int(settings.get("action_timeout_minutes", 1))
        except Exception:
            timeout_min = 1
        timeout_min = max(1, timeout_min)
        self.deadline = time.monotonic() + (timeout_min * 60.0)

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Aktionszeitlimit überschritten")

    def wait(self, seconds):
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("Negative Wartezeit")
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            time.sleep(min(0.05, max(0, end - time.monotonic())))
        self.check()

    @staticmethod
    def field(b, key, default=""):
        return b.get("fields", {}).get(key, default)

    @staticmethod
    def child(b, key):
        x = b.get("inputs", {}).get(key, {})
        return x.get("block") or x.get("shadow")

    def variable(self, b):
        x = self.field(b, "VAR")
        return x.get("id", x.get("name", "")) if isinstance(x, dict) else x

    def value(self, b):
        self.check()
        if not b:
            return None
        t = b["type"]
        f = lambda k, d="": self.field(b, k, d)
        v = lambda k: self.value(self.child(b, k))
        if t == "math_number":
            return float(f("NUM", 0))
        if t == "text":
            return f("TEXT")
        if t == "logic_boolean":
            return f("BOOL") == "TRUE"
        if t == "logic_null":
            return None
        if t == "variables_get":
            return self.variables.get(self.variable(b), 0)
        if t == "logic_negate":
            return not v("BOOL")
        if t == "logic_operation":
            return (bool(v("A")) and bool(v("B"))) if f("OP") == "AND" else (bool(v("A")) or bool(v("B")))
        if t == "logic_compare":
            a, c = v("A"), v("B")
            return {
                "EQ": lambda: a == c,
                "NEQ": lambda: a != c,
                "LT": lambda: a < c,
                "LTE": lambda: a <= c,
                "GT": lambda: a > c,
                "GTE": lambda: a >= c,
            }[f("OP", "EQ")]()
        if t == "math_arithmetic":
            a, c = v("A"), v("B")
            return {
                "ADD": lambda: a + c,
                "MINUS": lambda: a - c,
                "MULTIPLY": lambda: a * c,
                "DIVIDE": lambda: a / c,
                "POWER": lambda: a ** c,
            }[f("OP", "ADD")]()
        if t == "winctrl_file_exists":
            return os.path.exists(str(f("VALUE")))
        if t == "winctrl_window_exists":
            import pyautogui as p

            return bool(p.getWindowsWithTitle(str(f("VALUE"))))
        if t == "winctrl_clipboard":
            import pyperclip

            return pyperclip.paste()
        raise ValueError("Nicht unterstützter Wertblock: " + t)

    def sequence(self, b):
        while b:
            self.check()
            if not b.get("disabled", False):
                self.statement(b)
            b = b.get("next", {}).get("block")

    def statement(self, b):
        t = b["type"]
        if t == "winctrl_when":
            return
        if t == "controls_if":
            i = 0
            while "IF" + str(i) in b.get("inputs", {}):
                if self.value(self.child(b, "IF" + str(i))):
                    self.sequence(self.child(b, "DO" + str(i)))
                    return
                i += 1
            self.sequence(self.child(b, "ELSE"))
            return
        if t == "controls_repeat_ext":
            for _ in range(max(0, int(self.value(self.child(b, "TIMES")) or 0))):
                self.check()
                self.sequence(self.child(b, "DO"))
            return
        if t == "controls_whileUntil":
            until = self.field(b, "MODE", "WHILE") == "UNTIL"
            while bool(self.value(self.child(b, "BOOL"))) != until:
                self.check()
                self.sequence(self.child(b, "DO"))
            return
        if t == "variables_set":
            self.variables[self.variable(b)] = self.value(self.child(b, "VALUE"))
            return
        if t == "math_change":
            k = self.variable(b)
            self.variables[k] = self.variables.get(k, 0) + (self.value(self.child(b, "DELTA")) or 0)
            return
        self.perform(b)

    def perform(self, b):
        t, value = b["type"], self.field(b, "VALUE")
        self.emit("DEBUG", "Block erreicht: " + t)
        if t in ("winctrl_log", "winctrl_log_value"):
            child = self.child(b, "TEXT")
            self.emit(self.field(b, "LEVEL", "INFO"), str(self.value(child) if child else value))
        elif t in ("winctrl_return", "winctrl_return_value"):
            child = self.child(b, "TEXT")
            res = str(self.value(child) if child else value)
            self.return_value = res
            self.emit("INFO", "Rückgabewert gesetzt: " + repr(res))
        elif t == "winctrl_wait":
            self.wait(value)
        elif t == "winctrl_start_app":
            command = os.path.expandvars(str(value).strip())
            if not command:
                raise ValueError("Kein Programm angegeben")
            self.emit("INFO", "Programmblock erreicht: " + repr(command))
            executable = shutil.which(command.strip('"'))
            if not executable and command.lower() == "notepad.exe":
                candidate = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "notepad.exe")
                if os.path.isfile(candidate):
                    executable = candidate
            self.emit("INFO", "Programmpfad: " + str(executable or "Windows-Kommandozeile"))
            try:
                process = subprocess.Popen([executable] if executable else command, shell=False)
            except OSError as error:
                raise RuntimeError("Programmstart abgelehnt: " + str(error)) from error
            self.emit("INFO", "Windows akzeptiert Prozessstart; PID=" + str(process.pid) + " (kein Nachweis eines sichtbaren Fensters)")
        elif t == "winctrl_open_url":
            if not str(value).lower().startswith(("http://", "https://")):
                raise ValueError("Nur HTTP/HTTPS erlaubt")
            if not webbrowser.open(str(value)):
                raise RuntimeError("Browserstart fehlgeschlagen")
        elif t == "winctrl_lock_pc":
            if not ctypes.windll.user32.LockWorkStation():
                raise RuntimeError("Sperren fehlgeschlagen")
        elif t == "winctrl_shutdown_pc":
            if not self.settings.get("allow_dangerous_actions"):
                raise ValueError("Shutdown nicht freigegeben")
            subprocess.run(["shutdown", "/s", "/t", "10"], check=True, timeout=5)
        else:
            import pyautogui as p

            if t == "winctrl_press_key":
                p.press(str(value).strip().lower())
            elif t == "winctrl_hotkey":
                keys = [x.strip().lower() for x in str(value).split("+") if x.strip()]
                if not keys:
                    raise ValueError("Keine Taste angegeben")
                p.hotkey(*keys)
            elif t == "winctrl_type_text":
                p.write(str(value))
            elif t == "winctrl_paste_text":
                import pyperclip

                pyperclip.copy(str(value))
                self.wait(0.1)
                p.hotkey("ctrl", "v")
            elif t == "winctrl_media":
                p.press(MEDIA[value])
            elif t in ("winctrl_mouse_move", "winctrl_mouse_drag"):
                x, y = str(value).split(",")
                if t == "winctrl_mouse_move":
                    p.moveTo(int(x), int(y))
                else:
                    p.dragTo(int(x), int(y), duration=0.5)
            elif t == "winctrl_mouse_click":
                if value == "double":
                    p.doubleClick()
                elif value in ("left", "right", "middle"):
                    p.click(button=value)
                else:
                    raise ValueError("Unbekannte Maustaste")
            elif t == "winctrl_scroll":
                p.scroll(int(value))
            elif t == "winctrl_focus_window":
                windows = p.getWindowsWithTitle(str(value))
                if not windows:
                    raise ValueError("Fenster nicht gefunden")
                if windows[0].isMinimized:
                    windows[0].restore()
                windows[0].activate()
            else:
                raise ValueError("Nicht unterstützter Aktionsblock: " + t)


def execute_plan(action, settings, emit=None):
    if emit is None:
        emit = lambda level, text: logging.log(getattr(logging, level, logging.INFO), text)
    blocks = action.get("blockly", {}).get("blocks", {}).get("blocks", [])
    if len(blocks) != 1:
        raise ValueError("Genau eine verbundene Blockkette erforderlich; Startblock optional")
    runner = Runner(action, settings, emit)
    runner.sequence(blocks[0])
    runner.check()
    return runner.return_value


from winctrl_extensions import extend_runner
Runner = extend_runner(Runner)
