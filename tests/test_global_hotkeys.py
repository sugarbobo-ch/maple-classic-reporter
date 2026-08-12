import ctypes
import os
import unittest
from unittest.mock import Mock

from PySide6.QtCore import QCoreApplication

from maple_reporter.gui.main_window import MainWindow
from maple_reporter.platform.global_hotkeys import (
    ACTION_RECORD_VIDEO,
    ACTION_SAVE_REPLAY,
    DEFAULT_RECORD_VIDEO_HOTKEY,
    DEFAULT_RECORD_VIDEO_KEY,
    DEFAULT_SAVE_REPLAY_HOTKEY,
    DEFAULT_SAVE_REPLAY_KEY,
    HOTKEY_IDS,
    HOTKEY_KEY_OPTIONS,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    WM_HOTKEY,
    GlobalHotkeyManager,
    HotkeyParseError,
    fixed_hotkey_for_key,
    hotkey_key_from_shortcut,
    parse_hotkey,
)


class TestHotkeyParsing(unittest.TestCase):
    def test_default_hotkeys_use_f9_and_f10(self):
        self.assertEqual(DEFAULT_SAVE_REPLAY_KEY, "F9")
        self.assertEqual(DEFAULT_RECORD_VIDEO_KEY, "F10")
        self.assertEqual(DEFAULT_SAVE_REPLAY_HOTKEY, "Ctrl+Shift+F9")
        self.assertEqual(DEFAULT_RECORD_VIDEO_HOTKEY, "Ctrl+Shift+F10")

    def test_parse_hotkey_returns_canonical_win32_values(self):
        parsed = parse_hotkey("shift+control+f9")

        self.assertEqual(parsed.shortcut, "Ctrl+Shift+F9")
        self.assertEqual(parsed.virtual_key, 0x78)
        self.assertEqual(
            parsed.modifiers,
            MOD_CONTROL | MOD_SHIFT,
        )

    def test_parse_hotkey_accepts_alt_and_letter(self):
        parsed = parse_hotkey("Alt+R")

        self.assertEqual(parsed.shortcut, "Alt+R")
        self.assertEqual(parsed.virtual_key, ord("R"))
        self.assertEqual(parsed.modifiers, MOD_ALT)

    def test_parse_hotkey_requires_modifier_and_rejects_f12(self):
        with self.assertRaises(HotkeyParseError):
            parse_hotkey("F9")
        with self.assertRaises(HotkeyParseError):
            parse_hotkey("Ctrl+F12")

    def test_fixed_modifier_helpers_keep_ctrl_shift_and_change_one_key(self):
        self.assertEqual(fixed_hotkey_for_key("F10"), "Ctrl+Shift+F10")
        self.assertEqual(hotkey_key_from_shortcut("Alt+R", "F9"), "R")
        self.assertEqual(hotkey_key_from_shortcut("not-a-shortcut", "F9"), "F9")
        self.assertIn("F9", HOTKEY_KEY_OPTIONS)


class TestReplayHotkeyDispatch(unittest.TestCase):
    def _window_stub(self, *, replay_running: bool, replay_workflow_active=False):
        window = Mock()
        window._closing = False
        window._replay_save_workflow_active = replay_workflow_active
        window.replay_controller.is_running = replay_running
        return window

    def test_f9_starts_buffer_when_buffer_is_not_running(self):
        window = self._window_stub(replay_running=False)

        MainWindow.handle_save_replay_hotkey(window)

        window.toggle_replay_buffer.assert_called_once_with(from_hotkey=True)
        window.save_replay_segment.assert_not_called()

    def test_f9_saves_when_buffer_is_running(self):
        window = self._window_stub(replay_running=True)

        MainWindow.handle_save_replay_hotkey(window)

        window.save_replay_segment.assert_called_once_with(from_hotkey=True)
        window.toggle_replay_buffer.assert_not_called()

    def test_duplicate_f9_is_ignored_while_replay_preview_is_processing(self):
        window = self._window_stub(
            replay_running=True,
            replay_workflow_active=True,
        )

        MainWindow.handle_save_replay_hotkey(window)

        window.save_replay_segment.assert_not_called()
        window.toggle_replay_buffer.assert_not_called()

    def test_successful_f9_save_locks_until_preview_finishes(self):
        window = self._window_stub(replay_running=True)
        window.replay_controller.save.return_value = True

        MainWindow.save_replay_segment(window, from_hotkey=True)

        self.assertTrue(window._replay_save_workflow_active)
        window.replay_controller.save.assert_called_once_with()


class TestVideoWorkflowCancellation(unittest.TestCase):
    def test_manual_repeat_cancels_active_progress_dialog(self):
        window = Mock()
        window._active_video_countdown = None
        window._active_video_progress = Mock()

        self.assertTrue(MainWindow.cancel_video_recording(window))

        window._active_video_progress.cancel.assert_called_once_with()

    def test_repeated_manual_or_global_trigger_requests_cancellation(self):
        window = Mock()
        window._video_workflow_active = True

        MainWindow.trigger_video_report(window)
        MainWindow.trigger_video_report(window, from_hotkey=True)

        self.assertEqual(window.cancel_video_recording.call_count, 2)


@unittest.skipUnless(os.name == "nt", "Win32 hotkey registration is Windows-only")
class TestGlobalHotkeyManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.manager = GlobalHotkeyManager()
        self.user32 = Mock()
        self.user32.RegisterHotKey.return_value = 1
        self.user32.UnregisterHotKey.return_value = 1
        self.manager._user32 = self.user32

    def tearDown(self):
        self.manager.shutdown()

    def test_registers_all_shortcuts_with_no_repeat(self):
        self.assertTrue(
            self.manager.configure(
                1234,
                enabled=True,
                bindings={
                    ACTION_SAVE_REPLAY: "Ctrl+Shift+F9",
                    ACTION_RECORD_VIDEO: "Ctrl+Shift+F10",
                },
            )
        )

        self.assertEqual(self.manager.active_bindings[ACTION_SAVE_REPLAY], "Ctrl+Shift+F9")
        self.assertEqual(self.user32.RegisterHotKey.call_count, 2)
        for call in self.user32.RegisterHotKey.call_args_list:
            self.assertTrue(call.args[2] & MOD_NOREPEAT)

    def test_wm_hotkey_emits_action(self):
        self.manager._registered[ACTION_SAVE_REPLAY] = HOTKEY_IDS[ACTION_SAVE_REPLAY]
        self.manager._active_bindings[ACTION_SAVE_REPLAY] = "Ctrl+Shift+F9"
        received = []
        self.manager.activated.connect(received.append)

        message = ctypes.wintypes.MSG()
        message.message = WM_HOTKEY
        message.wParam = HOTKEY_IDS[ACTION_SAVE_REPLAY]
        handled, _result = self.manager._handle_native_event(
            b"windows_dispatcher_MSG",
            ctypes.addressof(message),
        )

        self.assertTrue(handled)
        self.assertEqual(received, [ACTION_SAVE_REPLAY])

    def test_failed_reconfiguration_restores_previous_bindings(self):
        self.assertTrue(
            self.manager.configure(
                1234,
                enabled=True,
                bindings={
                    ACTION_SAVE_REPLAY: "Ctrl+Shift+F9",
                    ACTION_RECORD_VIDEO: "Ctrl+Shift+F10",
                },
            )
        )
        self.user32.RegisterHotKey.side_effect = [1, 0, 1, 1]

        self.assertFalse(
            self.manager.configure(
                1234,
                enabled=True,
                bindings={
                    ACTION_SAVE_REPLAY: "Ctrl+Alt+F9",
                    ACTION_RECORD_VIDEO: "Ctrl+Alt+F10",
                },
            )
        )
        self.assertEqual(
            self.manager.active_bindings,
            {
                ACTION_SAVE_REPLAY: "Ctrl+Shift+F9",
                ACTION_RECORD_VIDEO: "Ctrl+Shift+F10",
            },
        )
