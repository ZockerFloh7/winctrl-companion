"""Additional Windows actions. Imported by executor after its original definitions."""
import math
import os
import time

class LoopFlow(Exception):
    def __init__(self, mode):
        self.mode = mode


def process_running(name):
    import psutil
    wanted = str(name).strip().casefold()
    if not wanted:
        raise ValueError("Bitte einen Prozessnamen angeben, zum Beispiel notepad.exe.")
    for proc in psutil.process_iter(["name"], ad_value=None):
        try:
            if (proc.info.get("name") or "").casefold() == wanted:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def windows(title):
    import pyautogui
    if not str(title).strip():
        raise ValueError("Bitte einen Fenstertitel angeben.")
    return pyautogui.getWindowsWithTitle(str(title))


def audio(value=None, mute=None):
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers()
        if device is None:
            raise RuntimeError("Kein Standard-Audioausgabegerät gefunden.")
        volume = device.EndpointVolume
        if value is not None:
            level = float(value)
            if not math.isfinite(level) or not 0 <= level <= 100:
                raise ValueError("Lautstärke muss zwischen 0 und 100 Prozent liegen.")
            volume.SetMasterVolumeLevelScalar(level / 100, None)
        if mute is not None:
            volume.SetMute(bool(mute), None)
    finally:
        comtypes.CoUninitialize()


def extend_runner(Base):
    class ExtendedRunner(Base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.loop_depth = 0

        def value(self, b):
            if b and b.get("type") == "winctrl_process_running":
                self.check()
                return process_running(self.field(b, "VALUE"))
            return super().value(b)

        def sequence(self, b):
            while b:
                self.check()
                if not b.get("disabled", False):
                    try:
                        self.statement(b)
                    except LoopFlow:
                        raise
                    except Exception as exc:
                        if not getattr(exc, "winctrl_context", False):
                            label = b.get("type", "Block")
                            self.emit("ERROR", f"{label}: {exc}")
                            try:
                                exc.winctrl_context = True
                            except Exception:
                                pass
                        raise
                b = b.get("next", {}).get("block")

        def statement(self, b):
            t = b["type"]
            if t == "controls_flow_statements":
                if not self.loop_depth:
                    raise ValueError("Schleifenabbruch ist nur innerhalb einer Schleife erlaubt.")
                mode = self.field(b, "FLOW", "BREAK")
                if mode not in ("BREAK", "CONTINUE"):
                    raise ValueError("Ungültige Schleifensteuerung.")
                raise LoopFlow(mode)
            if t == "winctrl_if_process":
                self.check()
                branch = "DO" if process_running(self.field(b, "VALUE")) else "ELSE"
                self.sequence(self.child(b, branch))
                return
            if t in ("controls_repeat_ext", "controls_whileUntil", "winctrl_loop"):
                remaining = max(0, int(self.value(self.child(b, "TIMES")) or 0)) if t == "controls_repeat_ext" else None
                self.loop_depth += 1
                try:
                    while True:
                        self.check()
                        if remaining is not None:
                            if remaining <= 0:
                                break
                            remaining -= 1
                        elif t == "controls_whileUntil":
                            until = self.field(b, "MODE", "WHILE") == "UNTIL"
                            if bool(self.value(self.child(b, "BOOL"))) == until:
                                break
                        try:
                            self.sequence(self.child(b, "DO"))
                        except LoopFlow as flow:
                            if flow.mode == "BREAK":
                                break
                        # Yield without disabling action timeout or Force-Stop.
                        self.wait(0.01)
                finally:
                    self.loop_depth -= 1
                return
            return super().statement(b)

        def perform(self, b):
            self.check()
            t = b["type"]
            value = self.field(b, "VALUE")
            if t == "winctrl_wait_window":
                seconds = float(self.field(b, "SECONDS", 10))
                if not math.isfinite(seconds) or seconds < 0:
                    raise ValueError("Fenster-Wartezeit muss eine endliche Zahl ab 0 sein.")
                end = time.monotonic() + seconds
                while True:
                    self.check()
                    if windows(value):
                        self.emit("INFO", f"Fenster gefunden: {value}")
                        return
                    if time.monotonic() >= end:
                        raise TimeoutError(f"Fenster nicht gefunden nach {seconds:g} Sekunden: {value}")
                    self.wait(min(0.1, max(0, end - time.monotonic())))
            elif t in ("winctrl_close_window", "winctrl_minimize_window", "winctrl_maximize_window", "winctrl_focus_window"):
                found = windows(value)
                if not found:
                    raise ValueError(f"Fenster nicht gefunden: {value}")
                if len(found) > 1:
                    self.emit("WARNING", f"{len(found)} passende Fenster; verwende das erste: {value}")
                window = found[0]
                if t == "winctrl_close_window":
                    window.close()
                elif t == "winctrl_minimize_window":
                    window.minimize()
                elif t == "winctrl_maximize_window":
                    window.maximize()
                else:
                    if window.isMinimized:
                        window.restore()
                    window.activate()
            elif t == "winctrl_double_click":
                import pyautogui
                pyautogui.doubleClick(interval=0.1)
            elif t == "winctrl_volume":
                audio(value=value)
            elif t == "winctrl_mute":
                audio(mute=str(value) == "on")
            elif t in ("winctrl_media_next", "winctrl_media_previous"):
                import pyautogui
                pyautogui.press("nexttrack" if t.endswith("next") else "prevtrack")
            else:
                return super().perform(b)
    return ExtendedRunner
