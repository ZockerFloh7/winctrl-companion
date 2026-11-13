"""Tests run against the installed executor; no real desktop/system actions."""
import ctypes
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import executor
import winctrl_extensions as ext


def block(t, value=None, **fields):
    if value is not None:
        fields['VALUE'] = value
    return {'type': t, 'fields': fields}


def chain(*items):
    for a, b in zip(items, items[1:]):
        a['next'] = {'block': b}
    return items[0]


def inp(b, key, child):
    b.setdefault('inputs', {})[key] = {'block': child}
    return b


def plan(b):
    return {'id': 'test', 'name': 'Mock-Test', 'timeout_minutes': 1,
            'blockly': {'blocks': {'blocks': [b]}}}


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.gui = types.ModuleType('pyautogui')
        for name in ('press', 'hotkey', 'write', 'moveTo', 'dragTo', 'doubleClick', 'click', 'scroll'):
            setattr(self.gui, name, Mock())
        self.window = Mock()
        self.window.isMinimized = False
        self.gui.getWindowsWithTitle = Mock(return_value=[self.window])
        self.clip = types.ModuleType('pyperclip')
        self.clip.copy = Mock()
        self.clip.paste = Mock(return_value='Grüße äöü')
        self.ps = types.ModuleType('psutil')
        self.ps.NoSuchProcess = type('NoSuchProcess', (Exception,), {})
        self.ps.AccessDenied = type('AccessDenied', (Exception,), {})
        self.ps.process_iter = Mock(return_value=[types.SimpleNamespace(info={'name': 'notepad.exe'})])
        self.com = types.ModuleType('comtypes')
        self.com.CoInitialize = Mock()
        self.com.CoUninitialize = Mock()
        self.volume = Mock()
        self.caw = types.ModuleType('pycaw.pycaw')
        self.caw.AudioUtilities = types.SimpleNamespace(GetSpeakers=Mock(return_value=types.SimpleNamespace(EndpointVolume=self.volume)))
        self.modules = patch.dict(sys.modules, {'pyautogui': self.gui, 'pyperclip': self.clip,
            'psutil': self.ps, 'comtypes': self.com, 'pycaw': types.ModuleType('pycaw'), 'pycaw.pycaw': self.caw})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def run_plan(self, b, settings=None):
        return executor.execute_plan(plan(b), settings or {'action_timeout_minutes': 1},
                                     lambda level, text: self.logs.append((level, text)))

    def test_start_and_return_unicode(self):
        result = self.run_plan(chain(block('winctrl_when'), block('winctrl_return', 'Grüße äöü')))
        self.assertEqual(result, 'Grüße äöü')

    def test_empty_return(self):
        self.assertEqual(self.run_plan(block('winctrl_return', '')), '')

    def test_return_expression(self):
        b = inp(block('winctrl_return_value'), 'TEXT', block('text', TEXT='Hallo'))
        self.assertEqual(self.run_plan(b), 'Hallo')

    def test_log(self):
        self.run_plan(block('winctrl_log', 'Hallo', LEVEL='WARNING'))
        self.assertIn(('WARNING', 'Hallo'), self.logs)

    def test_value_log(self):
        self.run_plan(inp(block('winctrl_log_value'), 'TEXT', block('text', TEXT='Wert')))
        self.assertIn(('INFO', 'Wert'), self.logs)

    def test_program(self):
        with patch('executor.shutil.which', return_value='notepad.exe'), patch('executor.subprocess.Popen') as popen:
            popen.return_value.pid = 123
            self.run_plan(block('winctrl_start_app', 'notepad.exe'))
            popen.assert_called_once_with(['notepad.exe'], shell=False)

    def test_program_error(self):
        with patch('executor.shutil.which', return_value=None), patch('executor.os.path.isfile', return_value=False), patch('executor.subprocess.Popen', side_effect=FileNotFoundError('fehlt')):
            with self.assertRaisesRegex(RuntimeError, 'Programmstart abgelehnt'):
                self.run_plan(block('winctrl_start_app', 'missing.exe'))

    def test_url(self):
        with patch('executor.webbrowser.open', return_value=True) as browser:
            self.run_plan(block('winctrl_open_url', 'https://example.invalid'))
            browser.assert_called_once()
        with self.assertRaises(ValueError):
            self.run_plan(block('winctrl_open_url', 'file:///secret'))

    def test_key(self):
        self.run_plan(block('winctrl_press_key', 'enter'))
        self.gui.press.assert_called_with('enter')

    def test_hotkey(self):
        self.run_plan(block('winctrl_hotkey', 'ctrl+s'))
        self.gui.hotkey.assert_called_with('ctrl', 's')

    def test_text(self):
        self.run_plan(block('winctrl_type_text', 'Hallo'))
        self.gui.write.assert_called_with('Hallo')

    def test_paste(self):
        self.run_plan(block('winctrl_paste_text', 'Grüße'))
        self.clip.copy.assert_called_with('Grüße')
        self.gui.hotkey.assert_called_with('ctrl', 'v')

    def test_mouse_move(self):
        self.run_plan(block('winctrl_mouse_move', '50,60'))
        self.gui.moveTo.assert_called_with(50, 60)

    def test_mouse_drag(self):
        self.run_plan(block('winctrl_mouse_drag', '50,60'))
        self.gui.dragTo.assert_called_with(50, 60, duration=0.5)

    def test_mouse_buttons(self):
        for button in ('left', 'right', 'middle'):
            self.run_plan(block('winctrl_mouse_click', button))
            self.gui.click.assert_called_with(button=button)
        self.run_plan(block('winctrl_mouse_click', 'double'))
        self.gui.doubleClick.assert_called_once()

    def test_double_click_block(self):
        self.run_plan(block('winctrl_double_click'))
        self.gui.doubleClick.assert_called_once_with(interval=0.1)

    def test_scroll(self):
        self.run_plan(block('winctrl_scroll', '-3'))
        self.gui.scroll.assert_called_with(-3)

    def test_media(self):
        for key, expected in executor.MEDIA.items():
            self.run_plan(block('winctrl_media', key))
            self.gui.press.assert_called_with(expected)

    def test_media_separate(self):
        self.run_plan(block('winctrl_media_next'))
        self.gui.press.assert_called_with('nexttrack')
        self.run_plan(block('winctrl_media_previous'))
        self.gui.press.assert_called_with('prevtrack')

    def test_volume(self):
        self.run_plan(block('winctrl_volume', '35'))
        self.volume.SetMasterVolumeLevelScalar.assert_called_with(0.35, None)
        self.com.CoUninitialize.assert_called_once()

    def test_volume_invalid(self):
        for value in ('-1', '101', 'nan'):
            with self.assertRaises(ValueError):
                self.run_plan(block('winctrl_volume', value))

    def test_mute(self):
        self.run_plan(block('winctrl_mute', 'on'))
        self.volume.SetMute.assert_called_with(True, None)
        self.run_plan(block('winctrl_mute', 'off'))
        self.volume.SetMute.assert_called_with(False, None)

    def test_window_actions(self):
        for name, method in [('close', 'close'), ('minimize', 'minimize'), ('maximize', 'maximize'), ('focus', 'activate')]:
            self.run_plan(block('winctrl_' + name + '_window', 'Editor'))
            getattr(self.window, method).assert_called_once()

    def test_window_missing(self):
        self.gui.getWindowsWithTitle.return_value = []
        with self.assertRaisesRegex(ValueError, 'Fenster nicht gefunden: Editor'):
            self.run_plan(block('winctrl_close_window', 'Editor'))

    def test_wait_window_found(self):
        self.run_plan(block('winctrl_wait_window', 'Editor', SECONDS=10))

    def test_wait_window_timeout(self):
        self.gui.getWindowsWithTitle.return_value = []
        with self.assertRaisesRegex(TimeoutError, 'Fenster nicht gefunden nach 0 Sekunden: Editor'):
            self.run_plan(block('winctrl_wait_window', 'Editor', SECONDS=0))

    def test_window_exists_value(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        self.assertTrue(r.value(block('winctrl_window_exists', 'Editor')))

    def test_file_exists_value(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        with patch('executor.os.path.exists', return_value=True):
            self.assertTrue(r.value(block('winctrl_file_exists', 'test')))

    def test_clipboard_value(self):
        b = inp(block('winctrl_return_value'), 'TEXT', block('winctrl_clipboard'))
        self.assertEqual(self.run_plan(b), 'Grüße äöü')

    def test_process_value(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        self.assertTrue(r.value(block('winctrl_process_running', 'NOTEPAD.EXE')))
        self.assertFalse(r.value(block('winctrl_process_running', 'missing.exe')))

    def test_process_branches(self):
        for name, expected in [('notepad.exe', 'yes'), ('missing.exe', 'no')]:
            b = block('winctrl_if_process', name)
            inp(b, 'DO', block('winctrl_return', 'yes'))
            inp(b, 'ELSE', block('winctrl_return', 'no'))
            self.assertEqual(self.run_plan(b), expected)

    def test_repeat(self):
        b = inp(block('controls_repeat_ext'), 'TIMES', block('math_number', NUM=3))
        inp(b, 'DO', block('winctrl_log', 'x'))
        self.run_plan(b)
        self.assertEqual(self.logs.count(('INFO', 'x')), 3)

    def test_loop_break(self):
        body = chain(block('winctrl_log', 'x'), block('controls_flow_statements', FLOW='BREAK'), block('winctrl_log', 'unreachable'))
        self.run_plan(inp(block('winctrl_loop'), 'DO', body))
        self.assertEqual(self.logs.count(('INFO', 'x')), 1)
        self.assertNotIn(('INFO', 'unreachable'), self.logs)

    def test_continue(self):
        body = chain(block('controls_flow_statements', FLOW='CONTINUE'), block('winctrl_log', 'unreachable'))
        b = inp(block('controls_repeat_ext'), 'TIMES', block('math_number', NUM=3))
        self.run_plan(inp(b, 'DO', body))
        self.assertNotIn(('INFO', 'unreachable'), self.logs)

    def test_nested_break(self):
        inner = inp(block('winctrl_loop'), 'DO', block('controls_flow_statements', FLOW='BREAK'))
        outer = inp(block('controls_repeat_ext'), 'TIMES', block('math_number', NUM=2))
        inp(outer, 'DO', chain(inner, block('winctrl_log', 'outer')))
        self.run_plan(outer)
        self.assertEqual(self.logs.count(('INFO', 'outer')), 2)

    def test_break_outside(self):
        with self.assertRaisesRegex(ValueError, 'nur innerhalb'):
            self.run_plan(block('controls_flow_statements', FLOW='BREAK'))

    def test_wait_invalid(self):
        self.run_plan(block('winctrl_wait', '0'))
        with self.assertRaises(ValueError):
            self.run_plan(block('winctrl_wait', '-1'))

    def test_timeout(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        r.deadline = 0
        with self.assertRaises(TimeoutError):
            r.check()

    def test_shutdown_blocked(self):
        with self.assertRaisesRegex(ValueError, 'nicht freigegeben'):
            self.run_plan(block('winctrl_shutdown_pc'))

    def test_shutdown_mock(self):
        with patch('executor.subprocess.run') as run:
            self.run_plan(block('winctrl_shutdown_pc'), {'allow_dangerous_actions': True})
            run.assert_called_once_with(['shutdown', '/s', '/t', '10'], check=True, timeout=5)

    def test_lock_mock(self):
        win = types.SimpleNamespace(user32=types.SimpleNamespace(LockWorkStation=Mock(return_value=1)))
        with patch.object(ctypes, 'windll', win, create=True):
            self.run_plan(block('winctrl_lock_pc'))
            win.user32.LockWorkStation.assert_called_once()

    def test_variables_and_arithmetic(self):
        assign = inp(block('variables_set', VAR='x'), 'VALUE', block('math_number', NUM=2))
        add = inp(block('math_change', VAR='x'), 'DELTA', block('math_number', NUM=3))
        ret = inp(block('winctrl_return_value'), 'TEXT', block('variables_get', VAR='x'))
        self.assertEqual(float(self.run_plan(chain(assign, add, ret))), 5)

    def test_if(self):
        b = inp(block('controls_if'), 'IF0', block('logic_boolean', BOOL='TRUE'))
        inp(b, 'DO0', block('winctrl_return', 'yes'))
        self.assertEqual(self.run_plan(b), 'yes')

    def test_disabled(self):
        b = block('winctrl_return', 'bad'); b['disabled'] = True
        self.assertEqual(self.run_plan(b), '')

    def test_reject_disconnected(self):
        a = plan(block('winctrl_when'))
        a['blockly']['blocks']['blocks'].append(block('winctrl_log', 'extra'))
        with self.assertRaises(ValueError):
            executor.execute_plan(a, {})

    def test_while_until(self):
        for mode, op in [('WHILE', 'LT'), ('UNTIL', 'GTE')]:
            assign = inp(block('variables_set', VAR='x'), 'VALUE', block('math_number', NUM=0))
            condition = inp(block('logic_compare', OP=op), 'A', block('variables_get', VAR='x'))
            inp(condition, 'B', block('math_number', NUM=3))
            loop = inp(block('controls_whileUntil', MODE=mode), 'BOOL', condition)
            inp(loop, 'DO', inp(block('math_change', VAR='x'), 'DELTA', block('math_number', NUM=1)))
            ret = inp(block('winctrl_return_value'), 'TEXT', block('variables_get', VAR='x'))
            self.assertEqual(float(self.run_plan(chain(assign, loop, ret))), 3)

    def test_logic_expressions(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        a = inp(block('logic_operation', OP='AND'), 'A', block('logic_boolean', BOOL='TRUE'))
        inp(a, 'B', block('logic_boolean', BOOL='FALSE'))
        self.assertFalse(r.value(a))
        self.assertTrue(r.value(inp(block('logic_negate'), 'BOOL', a)))
        for op, expected in [('EQ', False), ('NEQ', True), ('LT', True), ('LTE', True), ('GT', False), ('GTE', False)]:
            expression = inp(block('logic_compare', OP=op), 'A', block('math_number', NUM=2))
            inp(expression, 'B', block('math_number', NUM=3))
            self.assertEqual(r.value(expression), expected)

    def test_arithmetic_expressions(self):
        r = executor.Runner(plan(block('winctrl_when')), {}, lambda *args: None)
        for op, expected in [('ADD', 5), ('MINUS', -1), ('MULTIPLY', 6), ('DIVIDE', 2/3), ('POWER', 8)]:
            expression = inp(block('math_arithmetic', OP=op), 'A', block('math_number', NUM=2))
            inp(expression, 'B', block('math_number', NUM=3))
            self.assertAlmostEqual(r.value(expression), expected)

    def test_focus_restores_minimized(self):
        self.window.isMinimized = True
        self.run_plan(block('winctrl_focus_window', 'Editor'))
        self.window.restore.assert_called_once()
        self.window.activate.assert_called_once()

    def test_unknown_block(self):
        with self.assertRaises(ValueError):
            self.run_plan(block('winctrl_unknown'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
