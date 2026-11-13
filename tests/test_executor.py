import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from executor import execute_plan


def a(block, timeout_minutes=None):
    return {
        "id": "x",
        "name": "Test",
        "timeout_minutes": timeout_minutes,
        "blockly": {"blocks": {"blocks": [block]}},
    }


class Tests(unittest.TestCase):
    def test_start_and_nested_program(self):
        block = {
            "type": "winctrl_when",
            "next": {
                "block": {
                    "type": "winctrl_start_app",
                    "fields": {"VALUE": "notepad.exe"},
                }
            },
        }
        logs = []
        with patch("executor.shutil.which", return_value=r"C:\Windows\notepad.exe"), patch("executor.subprocess.Popen") as p:
            p.return_value.pid = 123
            res = execute_plan(a(block), {"action_timeout_minutes": 1}, lambda level, text: logs.append(text))
            p.assert_called_once_with([r"C:\Windows\notepad.exe"], shell=False)
        self.assertTrue(any("PID=123" in s for s in logs))
        self.assertEqual(res, "")

    def test_return_block(self):
        block = {
            "type": "winctrl_when",
            "next": {
                "block": {
                    "type": "winctrl_return",
                    "fields": {"VALUE": "Fenster geöffnet"},
                }
            },
        }
        logs = []
        res = execute_plan(a(block), {"action_timeout_minutes": 1}, lambda level, text: logs.append(text))
        self.assertEqual(res, "Fenster geöffnet")

    def test_log_block(self):
        logs = []
        execute_plan(
            a({"type": "winctrl_log", "fields": {"LEVEL": "WARNING", "VALUE": "Hallo"}}),
            {"action_timeout_minutes": 1},
            lambda level, text: logs.append((level, text)),
        )
        self.assertIn(("WARNING", "Hallo"), logs)

    def test_repeat(self):
        logs = []
        b = {
            "type": "controls_repeat_ext",
            "inputs": {
                "TIMES": {"shadow": {"type": "math_number", "fields": {"NUM": 3}}},
                "DO": {"block": {"type": "winctrl_log", "fields": {"VALUE": "x"}}},
            },
        }
        execute_plan(a(b), {"action_timeout_minutes": 1}, lambda level, text: logs.append(text))
        self.assertEqual(logs.count("x"), 3)

    def test_start_failure_visible(self):
        with patch("executor.shutil.which", return_value=None), patch(
            "executor.subprocess.Popen", side_effect=FileNotFoundError("nicht gefunden")
        ):
            with self.assertRaisesRegex(RuntimeError, "Programmstart abgelehnt"):
                execute_plan(
                    a({"type": "winctrl_start_app", "fields": {"VALUE": "missing.exe"}}),
                    {"action_timeout_minutes": 1},
                )

    def test_shutdown_blocked(self):
        with self.assertRaisesRegex(ValueError, "nicht freigegeben"):
            execute_plan(a({"type": "winctrl_shutdown_pc"}), {"action_timeout_minutes": 1})


if __name__ == "__main__":
    unittest.main()
