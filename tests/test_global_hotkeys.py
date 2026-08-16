import ctypes
import os
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox

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
    def test_manual_repeat_marks_active_workflow_as_cancelling(self):
        window = Mock()
        window._video_workflow_active = True
        window._video_cancel_requested = False

        self.assertTrue(MainWindow.cancel_video_recording(window))

        self.assertTrue(window._video_cancel_requested)
        window._set_video_cancelling.assert_called_once_with()

    def test_repeated_manual_or_global_trigger_requests_cancellation(self):
        window = Mock()
        window._video_workflow_active = True

        MainWindow.trigger_video_report(window)
        MainWindow.trigger_video_report(window, from_hotkey=True)

        self.assertEqual(window.cancel_video_recording.call_count, 2)

    def test_recording_status_button_is_gray_and_enabled_while_active(self):
        window = Mock()

        MainWindow._set_recording_status(window, True)

        window.btn_recording_status.setText.assert_called_with("取消錄影")
        window.btn_recording_status.setEnabled.assert_called_with(True)
        active_style = window.btn_recording_status.setStyleSheet.call_args.args[0]
        self.assertIn("#757575", active_style)

        MainWindow._set_recording_status(window, False)

        window.btn_recording_status.setText.assert_called_with("未錄影")
        window.btn_recording_status.setEnabled.assert_called_with(False)

    def test_video_trigger_button_turns_gray_while_active(self):
        window = Mock()

        MainWindow._set_video_trigger_active(window, True)

        active_style = window.btn_trigger_video.setStyleSheet.call_args.args[0]
        self.assertIn("#757575", active_style)
        window.btn_trigger_video.setText.assert_called_with("取消錄影")

        MainWindow._set_video_trigger_active(window, False)

        inactive_style = window.btn_trigger_video.setStyleSheet.call_args.args[0]
        self.assertIn("#e65100", inactive_style)
        window.btn_trigger_video.setText.assert_called_with("錄製影片並辨識")

    def test_cancel_state_disables_both_cancel_controls_immediately(self):
        window = Mock()

        MainWindow._set_video_cancelling(window)

        window.btn_trigger_video.setText.assert_called_with("取消中…")
        window.btn_trigger_video.setEnabled.assert_called_with(False)
        window.btn_recording_status.setText.assert_called_with("取消中…")
        window.btn_recording_status.setEnabled.assert_called_with(False)

    def test_status_progress_updates_status_text_and_progress_bar(self):
        window = Mock()

        MainWindow._set_recording_progress(window, "錄影中 5 / 10 秒", 50)

        window.lbl_recording_progress.setText.assert_called_with("錄影中 5 / 10 秒")
        window.lbl_recording_progress.setAccessibleDescription.assert_called_with(
            "錄影中 5 / 10 秒"
        )
        window.progress_recording.setAccessibleDescription.assert_called_with(
            "錄影中 5 / 10 秒"
        )
        window.progress_recording.setToolTip.assert_called_with("錄影中 5 / 10 秒")
        window.progress_recording.setValue.assert_called_with(50)
        window.progress_recording.show.assert_called_once_with()

    def test_ocr_master_checkbox_reflects_child_selection(self):
        QApplication.instance() or QApplication([])
        window = Mock()
        window.chk_ocr_autofill = QCheckBox()
        window.chk_ocr_autofill.setTristate(True)
        window.chk_ocr_id = QCheckBox()
        window.chk_ocr_map = QCheckBox()

        window.chk_ocr_id.setChecked(True)
        window.chk_ocr_map.setChecked(True)
        MainWindow.sync_ocr_autofill_checkboxes(window)
        self.assertEqual(
            window.chk_ocr_autofill.checkState(), Qt.CheckState.Checked
        )

        window.chk_ocr_map.setChecked(False)
        MainWindow.sync_ocr_autofill_checkboxes(window)
        self.assertEqual(
            window.chk_ocr_autofill.checkState(), Qt.CheckState.PartiallyChecked
        )

        MainWindow._on_ocr_autofill_master_changed(
            window, Qt.CheckState.Unchecked
        )
        self.assertFalse(window.chk_ocr_id.isChecked())
        self.assertFalse(window.chk_ocr_map.isChecked())

    def test_video_report_updates_status_progress_without_a_dialog(self):
        window = Mock()
        window._hotkey_recording_active = False
        window._video_cancel_requested = False
        window.combo_windows.currentText.return_value = "game"
        window.spin_duration.value.return_value = 3
        window.combo_fps.currentData.return_value = 30
        window.spin_countdown.value.return_value = 0
        window.chk_record_audio.isChecked.return_value = False
        window.combo_audio_output.currentData.return_value = ""

        def record_video(*args, progress_callback, **kwargs):
            progress_callback(0.5)
            return None, []

        window.capture_controller.record_video.side_effect = record_video

        with patch("maple_reporter.gui.main_window.focus_window"):
            MainWindow._perform_video_report(window)

        window._set_recording_progress.assert_any_call("錄影中 2 / 3 秒", 50)


@unittest.skipUnless(os.name == "nt", "Win32 hotkey registration is Windows-only")
class TestGlobalHotkeyManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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
