import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch
from PIL import Image

from maple_reporter.gui.pywebview_bridge import PyWebViewBridge
from maple_reporter.sanctions.repository import SanctionRepository

TEST_CONFIG_FILE = Path(__file__).parent / "fixtures" / "config.json"


def load_test_config():
    return json.loads(TEST_CONFIG_FILE.read_text(encoding="utf-8"))


class TestPyWebViewBridge(unittest.TestCase):
    def setUp(self):
        isolated_config = load_test_config()
        isolated_config["ocr_autofill_id"] = False
        isolated_config["ocr_autofill_map"] = False
        self._load_config_patch = patch(
            "maple_reporter.gui.pywebview_bridge.load_config",
            side_effect=lambda: dict(isolated_config),
        )
        self._save_config_patch = patch(
            "maple_reporter.gui.pywebview_bridge.save_config"
        )
        self._local_media_server_patch = patch(
            "maple_reporter.gui.pywebview_bridge.LocalMediaServer"
        )
        self._hotkey_listener_patch = patch(
            "maple_reporter.gui.pywebview_bridge.BackgroundHotkeyListener"
        )
        self._drive_manager_patch = patch(
            "maple_reporter.gui.pywebview_bridge.GoogleDriveManager"
        )
        self._replay_recorder_patch = patch(
            "maple_reporter.gui.pywebview_bridge.ReplayBufferRecorder"
        )
        self._load_config_patch.start()
        self._save_config_patch.start()
        media_server = self._local_media_server_patch.start()
        self._hotkey_listener_patch.start()
        drive_manager = self._drive_manager_patch.start()
        replay_recorder = self._replay_recorder_patch.start()
        self.replay_recorder_factory = replay_recorder
        media_server.return_value.start.return_value = 0
        drive_manager.return_value.is_authenticated.return_value = False
        replay_recorder.return_value.is_running = False

        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        temp_cache = Path(self.temp_dir.name) / "sanction_cache.json"
        temp_history = Path(self.temp_dir.name) / "history.json"
        temp_db = Path(self.temp_dir.name) / "test.db"
        self._repo_patch = patch(
            "maple_reporter.gui.pywebview_bridge.SanctionRepository",
            side_effect=lambda **kw: SanctionRepository(cache_path=temp_cache, history_path=temp_history, db_path=temp_db),
        )
        self._repo_patch.start()

        self.bridge = PyWebViewBridge()

    def tearDown(self):
        self.bridge.shutdown()
        self._repo_patch.stop()
        self.temp_dir.cleanup()
        self._replay_recorder_patch.stop()
        self._drive_manager_patch.stop()
        self._hotkey_listener_patch.stop()
        self._local_media_server_patch.stop()
        self._save_config_patch.stop()
        self._load_config_patch.stop()

    def test_get_initial_data(self):
        data = self.bridge.get_initial_data()
        self.assertIn("config", data)
        self.assertIn("windows", data)
        self.assertIn("audio_devices", data)
        self.assertIn("history", data)
        self.assertIn("gdrive_authenticated", data)
        self.assertIn("replay_state", data)
        self.assertIn("replay_duration", data)
        self.assertIn("sanction_sync_status", data)

    def test_clear_history_delegates_to_persistence(self):
        with patch.object(self.bridge.sanction_repo, "clear_history") as mock_clear:
            self.assertTrue(self.bridge.clear_history())
            mock_clear.assert_called_once_with()

    def test_save_config_key_and_all(self):
        ok = self.bridge.save_config_key("record_duration_sec", 10)
        self.assertTrue(ok)
        self.assertEqual(self.bridge.config.get("record_duration_sec"), 10)

        ok_all = self.bridge.save_config_all({"record_duration_sec": 8, "default_server": "雪吉拉"})
        self.assertTrue(ok_all)
        self.assertEqual(self.bridge.config.get("record_duration_sec"), 8)

    def test_ocr_autofill_map_switch_controls_capture_ocr(self):
        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = {
            "selected_window_title": "test-window",
            "default_map": "fallback-map",
            "ocr_autofill_id": False,
            "ocr_autofill_map": False,
            "whitelist": [],
        }
        screenshot = Image.new("RGB", (32, 32), color="white")

        with (
            patch.object(PyWebViewBridge, "_emit_event"),
            patch("maple_reporter.gui.pywebview_bridge.focus_window"),
            patch("maple_reporter.gui.pywebview_bridge.time.sleep"),
            patch(
                "maple_reporter.gui.pywebview_bridge.find_window_bounds",
                return_value=(0, 0, 32, 32),
            ),
            patch(
                "maple_reporter.gui.pywebview_bridge.record_capture_screenshot",
                return_value=(screenshot, "test.png"),
            ),
            patch(
                "maple_reporter.gui.pywebview_bridge.recognize_map_name_from_image_list",
                return_value="recognized-map",
            ) as recognize_map,
        ):
            disabled_result = bridge.capture_screenshot()
            self.assertEqual(disabled_result["map_name"], "fallback-map")
            self.assertEqual(disabled_result["ocr_map_name"], "")
            self.assertEqual(disabled_result["map_name_source"], "default")
            recognize_map.assert_not_called()

            bridge.config["ocr_autofill_map"] = True
            enabled_result = bridge.capture_screenshot()

        self.assertEqual(enabled_result["map_name"], "recognized-map")
        self.assertEqual(enabled_result["ocr_map_name"], "recognized-map")
        self.assertEqual(enabled_result["map_name_source"], "ocr")
        recognize_map.assert_called_once_with(
            [screenshot], on_progress=ANY, cancel_checker=ANY
        )

    def test_cancel_ocr_stops_the_current_pipeline(self):
        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = {
            "default_map": "fallback-map",
            "ocr_autofill_id": True,
            "ocr_autofill_map": True,
            "whitelist": [],
        }
        screenshot = Image.new("RGB", (32, 32), color="white")

        def cancel_during_map(*_args, **_kwargs):
            bridge.cancel_ocr()
            return "ignored-map"

        with (
            patch.object(PyWebViewBridge, "_emit_event"),
            patch(
                "maple_reporter.gui.pywebview_bridge.recognize_map_name_from_image_list",
                side_effect=cancel_during_map,
            ),
            patch(
                "maple_reporter.gui.pywebview_bridge.recognize_candidates_from_image_list"
            ) as recognize_candidates,
        ):
            result = bridge._perform_ocr([screenshot])

        self.assertTrue(result["cancelled"])
        recognize_candidates.assert_not_called()

    def test_high_resolution_ocr_keeps_all_representative_frames_and_candidates(self):
        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = {
            "default_map": "fallback-map",
            "ocr_autofill_id": True,
            "ocr_autofill_map": True,
            "whitelist": [],
        }
        high_resolution_frame = Image.new("RGB", (3840, 2036), color="black")

        with (
            patch.object(PyWebViewBridge, "_emit_event"),
            patch(
                "maple_reporter.gui.pywebview_bridge.recognize_map_name_from_image_list",
                return_value="",
            ),
            patch(
                "maple_reporter.gui.pywebview_bridge.recognize_candidates_from_image_list",
                return_value=["sample-player", "another-player"],
            ) as recognize_candidates,
        ):
            result = bridge._perform_ocr([high_resolution_frame] * 12)

        self.assertEqual(
            result["suspect_ids"], ["sample-player", "another-player"]
        )
        sampled_frames = recognize_candidates.call_args.args[0]
        self.assertEqual(len(sampled_frames), 12)

    def test_recognize_video_frame_uses_the_requested_paused_timestamp(self):
        frame = Image.new("RGB", (320, 180), color="black")
        ocr_result = {
            "status": "success",
            "suspect_ids": ["sample-player"],
            "map_name": "Test Map",
            "ocr_map_name": "Test Map",
            "map_name_source": "ocr",
        }

        with (
            patch("maple_reporter.gui.bridge.media_bridge.os.path.exists", return_value=True),
            patch.object(
                self.bridge.capture_controller,
                "capture_video_frame",
                return_value=frame,
            ) as capture_frame,
            patch.object(self.bridge, "_perform_ocr", return_value=ocr_result) as perform_ocr,
        ):
            result = self.bridge.recognize_video_frame("evidence.mp4", 4.25)

        capture_frame.assert_called_once_with("evidence.mp4", 4.25)
        perform_ocr.assert_called_once_with([frame])
        self.assertEqual(result["suspect_ids"], ["sample-player"])
        self.assertEqual(result["media_path"], "evidence.mp4")
        self.assertEqual(result["media_type"], "video")

    @patch("maple_reporter.gui.pywebview_bridge.save_config", side_effect=OSError("disk full"))
    def test_config_save_failure_does_not_mutate_bridge_state(self, _mock_save):
        original_config = dict(self.bridge.config)

        self.assertFalse(self.bridge.save_config_key("default_map", "不應寫入"))
        self.assertEqual(self.bridge.config, original_config)

        self.assertFalse(self.bridge.save_config_all({"default_map": "不應寫入"}))
        self.assertEqual(self.bridge.config, original_config)

    def test_get_windows_and_audio_devices(self):
        windows = self.bridge.get_windows()
        self.assertIsInstance(windows, list)

        devices = self.bridge.get_audio_devices()
        self.assertIsInstance(devices, list)
        self.assertTrue(len(devices) > 0)

    @patch("maple_reporter.gui.pywebview_bridge.save_config")
    @patch(
        "maple_reporter.gui.pywebview_bridge.get_active_windows",
        return_value=[
            {"title": "其他視窗", "width": 1280, "height": 720},
            {"title": "新楓之谷：測試分頁", "width": 1600, "height": 900},
            {"title": "新楓之谷：經典版", "width": 1366, "height": 768},
        ],
    )
    def test_get_windows_prioritizes_classic_title_and_real_dimensions(
        self, mock_windows, mock_save_config
    ):
        self.bridge.config["selected_window_title"] = "其他視窗"

        windows = self.bridge.get_windows()

        self.assertEqual(
            [window["title"] for window in windows],
            ["新楓之谷：經典版", "新楓之谷：測試分頁", "其他視窗"],
        )
        self.assertEqual(windows[0]["width"], 1366)
        self.assertEqual(windows[0]["height"], 768)
        self.assertEqual(self.bridge.config["selected_window_title"], "新楓之谷：經典版")
        mock_save_config.assert_called_once_with(self.bridge.config)

    @patch(
        "maple_reporter.gui.pywebview_bridge.read_system_clipboard_text",
        return_value="TestPlayer",
    )
    def test_get_clipboard_text_uses_native_clipboard(self, mock_read_clipboard):
        self.assertEqual(self.bridge.get_clipboard_text(), "TestPlayer")
        mock_read_clipboard.assert_called_once_with()

    @patch(
        "maple_reporter.gui.pywebview_bridge.write_system_clipboard_text",
        return_value=True,
    )
    def test_set_clipboard_text_uses_native_clipboard(self, mock_write_clipboard):
        self.assertTrue(self.bridge.set_clipboard_text("https://drive.google.com/test"))
        mock_write_clipboard.assert_called_once_with("https://drive.google.com/test")

    def test_window_controls_delegate_to_webview(self):
        window = MagicMock()
        self.bridge._window = window

        self.assertTrue(self.bridge.minimize_window())
        window.minimize.assert_called_once_with()

        self.assertTrue(self.bridge.toggle_window_maximized())
        window.maximize.assert_called_once_with()
        self.assertFalse(self.bridge.toggle_window_maximized())
        window.restore.assert_called_once_with()

        self.assertTrue(self.bridge.close_window())
        window.destroy.assert_called_once_with()

    @patch("maple_reporter.gui.pywebview_bridge.begin_native_resize", return_value=True)
    @patch("maple_reporter.gui.pywebview_bridge._window_handle", return_value=5678)
    def test_resize_window_uses_the_native_resize_helper(
        self, window_handle, native_resize
    ):
        self.bridge._window = MagicMock()

        with patch("maple_reporter.gui.pywebview_bridge.os.name", "nt"):
            self.assertTrue(self.bridge.resize_window("bottom-right"))

        window_handle.assert_called_once_with(self.bridge._window)
        native_resize.assert_called_once_with(5678, "bottom-right")

    @patch("maple_reporter.gui.pywebview_bridge.begin_native_resize", return_value=True)
    def test_resize_window_blocks_when_maximized(self, native_resize):
        self.bridge._window = MagicMock()
        self.bridge._window_maximized = True

        with patch("maple_reporter.gui.pywebview_bridge.os.name", "nt"):
            self.assertFalse(self.bridge.resize_window("bottom-right"))

        native_resize.assert_not_called()

    @patch("maple_reporter.gui.pywebview_bridge.prepare_native_drag", return_value=True)
    @patch("maple_reporter.gui.pywebview_bridge._window_handle", return_value=5678)
    def test_drag_window_passes_the_header_anchor_mode(
        self, window_handle, prepare_drag
    ):
        self.bridge._window = MagicMock()

        with patch("maple_reporter.gui.pywebview_bridge.os.name", "nt"):
            self.assertTrue(self.bridge.drag_window("right"))

        window_handle.assert_called_once_with(self.bridge._window)
        prepare_drag.assert_called_once_with(5678, "right")

    @patch("maple_reporter.gui.pywebview_bridge.move_window_by_drag_delta")
    @patch("maple_reporter.gui.pywebview_bridge._window_handle", return_value=5678)
    def test_pywebview_move_adapter_uses_deltas(self, window_handle, move_delta):
        window = MagicMock()
        self.bridge.set_window(window)

        window.move(3000, 800)  # Establish the first drag sample only.
        window.move(3012, 804)

        window_handle.assert_called_once_with(window)
        move_delta.assert_called_once_with(5678, 12.0, 4.0)

    @patch.object(PyWebViewBridge, "_emit_event")
    def test_native_window_state_events_sync_frontend_state(self, emit_event):
        self.bridge.handle_window_maximized()
        self.assertTrue(self.bridge._window_maximized)
        emit_event.assert_called_once_with("WINDOW_MAXIMIZED")

        emit_event.reset_mock()
        self.bridge.handle_window_restored()
        self.assertFalse(self.bridge._window_maximized)
        emit_event.assert_called_once_with("WINDOW_RESTORED")

    @patch("maple_reporter.gui.pywebview_bridge.record_capture_screenshot")
    @patch("maple_reporter.gui.pywebview_bridge.find_window_bounds")
    @patch("maple_reporter.gui.pywebview_bridge.focus_window")
    def test_capture_screenshot(self, mock_focus, mock_bounds, mock_capture):
        mock_bounds.return_value = (0, 0, 1920, 1080)
        dummy_img = Image.new("RGB", (100, 100), color="blue")
        mock_capture.return_value = (dummy_img, "test_path.png")

        res = self.bridge.capture_screenshot("window")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["media_path"], "test_path.png")
        self.assertEqual(res["media_type"], "image")

    @patch("maple_reporter.gui.pywebview_bridge.record_capture_screenshot")
    @patch("maple_reporter.gui.pywebview_bridge.find_window_bounds", return_value=None)
    @patch("maple_reporter.gui.pywebview_bridge.focus_window")
    @patch("maple_reporter.gui.pywebview_bridge.LOGGER")
    def test_capture_screenshot_fails_closed_when_target_window_is_missing(
        self, _mock_logger, mock_focus, mock_bounds, mock_capture
    ):
        result = self.bridge.capture_screenshot("window")

        self.assertEqual(result["status"], "error")
        mock_capture.assert_not_called()

    def test_replay_lifecycle(self):
        status = self.bridge.get_replay_status()
        self.assertIn("state", status)
        self.assertIn("duration", status)

        self.bridge.stop_replay()
        self.assertFalse(self.bridge.replay_recorder.is_running)

    def test_replay_recorder_uses_callbacks_in_pywebview_mode(self):
        kwargs = self.replay_recorder_factory.call_args.kwargs

        self.assertEqual(
            kwargs["state_callback"], self.bridge._on_replay_state_changed
        )
        self.assertEqual(
            kwargs["replay_saved_callback"], self.bridge._on_replay_saved
        )
        self.assertEqual(kwargs["error_callback"], self.bridge._on_replay_error)

    @patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report")
    def test_submit_report_direct(self, mock_submit):
        self.bridge.config["dev_mode"] = False
        mock_submit.return_value = (True, "送出成功")
        form_data = {
            "suspect_id": "TestPlayer",
            "server_name": "雪吉拉",
            "map_name": "墮落城市",
            "note": "測試檢舉",
            "evidence_url": "https://example.com/evidence.mp4",
            "dev_mode": False,
        }
        res = self.bridge.submit_report(form_data)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["message"], "送出成功")

    @patch("maple_reporter.gui.pywebview_bridge.add_history_entry")
    @patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report", return_value=(True, "送出成功"))
    def test_submit_report_uploads_the_current_edited_media_path(self, _mock_submit, _mock_history):
        self.bridge._window = MagicMock()
        self.bridge.config["upload_destination"] = "gdrive"

        with tempfile.TemporaryDirectory() as temp_dir:
            edited_path = Path(temp_dir) / "edited-evidence.mp4"
            edited_path.write_bytes(b"edited")
            with patch.object(
                self.bridge.drive_mgr,
                "upload_file_and_make_public",
                return_value=(True, "https://drive.google.com/file/d/edited/view"),
            ) as mock_upload:
                result = self.bridge.submit_report(
                    {
                        "file_path": str(edited_path),
                        "upload_destination": "gdrive",
                        "suspect_id": "EditedPlayer",
                        "server_name": "雪吉拉",
                        "map_name": "墮落城市",
                        "note": "剪輯後事證",
                    }
                )

        self.assertEqual(result["status"], "success")
        mock_upload.assert_called_once_with(str(edited_path), "MapleClassic_Reports")
        event_payloads = [call.args[0] for call in self.bridge._window.evaluate_js.call_args_list]
        self.assertTrue(any('"step": "uploading"' in payload for payload in event_payloads))
        self.assertTrue(any('"status": "success"' in payload for payload in event_payloads))

    def test_submit_report_rejects_missing_media_before_form_submission(self):
        self.bridge._window = MagicMock()
        with patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report") as mock_submit:
            result = self.bridge.submit_report(
                {
                    "file_path": "C:/does-not-exist/edited-evidence.mp4",
                    "upload_destination": "gdrive",
                }
            )

        self.assertEqual(result["status"], "error")
        self.assertIn("檢舉證據檔案", result["message"])
        mock_submit.assert_not_called()

    def test_submit_report_rejects_an_overlapping_submission(self):
        self.bridge._window = MagicMock()
        self.bridge._submission_lock.acquire()
        try:
            result = self.bridge.submit_report({"evidence_url": "https://example.com/evidence"})
        finally:
            self.bridge._submission_lock.release()

        self.assertEqual(result["status"], "error")
        self.assertIn("正在送出", result["message"])

    @patch("maple_reporter.gui.pywebview_bridge.PyWebViewBridge.open_external_url")
    def test_submit_report_dev_mode(self, mock_open_url):
        form_data = {
            "suspect_id": "TestPlayer",
            "server_name": "雪吉拉",
            "map_name": "墮落城市",
            "note": "測試檢舉",
            "evidence_url": "https://example.com/evidence.mp4",
            "dev_mode": True,
        }
        res = self.bridge.submit_report(form_data)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["dev_mode"])
        mock_open_url.assert_called_once_with("https://forms.gamania.com/s/eLGg4")

    @patch("requests.post")
    def test_discord_webhook_test(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_post.return_value = mock_resp

        webhook_url = "https://discord.com/api/webhooks/123456789012345678/token_value-1"
        res = self.bridge.test_discord_webhook(webhook_url)
        self.assertTrue(res["success"])

        res_empty = self.bridge.test_discord_webhook("")
        self.assertFalse(res_empty["success"])

    @patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report")
    def test_submit_report_direct(self, mock_submit):
        self.bridge.config["dev_mode"] = False
        mock_submit.return_value = (True, "送出成功")
        form_data = {
            "suspect_id": "TestPlayer",
            "server_name": "雪吉拉",
            "map_name": "墮落城市",
            "note": "測試檢舉",
            "evidence_url": "https://example.com/evidence.mp4",
            "dev_mode": False,
        }
        res = self.bridge.submit_report(form_data)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["message"], "送出成功")

    @patch("maple_reporter.gui.pywebview_bridge.add_history_entry")
    @patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report", return_value=(True, "送出成功"))
    def test_submit_report_uploads_the_current_edited_media_path(self, _mock_submit, _mock_history):
        self.bridge._window = MagicMock()
        self.bridge.config["upload_destination"] = "gdrive"

        with tempfile.TemporaryDirectory() as temp_dir:
            edited_path = Path(temp_dir) / "edited-evidence.mp4"
            edited_path.write_bytes(b"edited")
            with patch.object(
                self.bridge.drive_mgr,
                "upload_file_and_make_public",
                return_value=(True, "https://drive.google.com/file/d/edited/view"),
            ) as mock_upload:
                result = self.bridge.submit_report(
                    {
                        "file_path": str(edited_path),
                        "upload_destination": "gdrive",
                        "suspect_id": "EditedPlayer",
                        "server_name": "雪吉拉",
                        "map_name": "墮落城市",
                        "note": "剪輯後事證",
                    }
                )

        self.assertEqual(result["status"], "success")
        mock_upload.assert_called_once_with(str(edited_path), "MapleClassic_Reports")
        event_payloads = [call.args[0] for call in self.bridge._window.evaluate_js.call_args_list]
        self.assertTrue(any('"step": "uploading"' in payload for payload in event_payloads))
        self.assertTrue(any('"status": "success"' in payload for payload in event_payloads))

    def test_submit_report_rejects_missing_media_before_form_submission(self):
        self.bridge._window = MagicMock()
        with patch("maple_reporter.gui.pywebview_bridge.submit_gamania_report") as mock_submit:
            result = self.bridge.submit_report(
                {
                    "file_path": "C:/does-not-exist/edited-evidence.mp4",
                    "upload_destination": "gdrive",
                }
            )

        self.assertEqual(result["status"], "error")
        self.assertIn("檢舉證據檔案", result["message"])
        mock_submit.assert_not_called()

    def test_submit_report_rejects_an_overlapping_submission(self):
        self.bridge._window = MagicMock()
        self.bridge._submission_lock.acquire()
        try:
            result = self.bridge.submit_report({"evidence_url": "https://example.com/evidence"})
        finally:
            self.bridge._submission_lock.release()

        self.assertEqual(result["status"], "error")
        self.assertIn("正在送出", result["message"])

    @patch("maple_reporter.gui.pywebview_bridge.PyWebViewBridge.open_external_url")
    def test_submit_report_dev_mode(self, mock_open_url):
        form_data = {
            "suspect_id": "TestPlayer",
            "server_name": "雪吉拉",
            "map_name": "墮落城市",
            "note": "測試檢舉",
            "evidence_url": "https://example.com/evidence.mp4",
            "dev_mode": True,
        }
        res = self.bridge.submit_report(form_data)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["dev_mode"])
        mock_open_url.assert_called_once_with("https://forms.gamania.com/s/eLGg4")

    @patch("requests.post")
    def test_discord_webhook_test(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_post.return_value = mock_resp

        webhook_url = "https://discord.com/api/webhooks/123456789012345678/token_value-1"
        res = self.bridge.test_discord_webhook(webhook_url)
        self.assertTrue(res["success"])

        res_empty = self.bridge.test_discord_webhook("")
        self.assertFalse(res_empty["success"])

        res_invalid = self.bridge.test_discord_webhook("https://example.com/webhook")
        self.assertFalse(res_invalid["success"])
        mock_post.assert_called_once()

    @patch("maple_reporter.gui.pywebview_bridge.webbrowser.open", return_value=True)
    def test_open_external_url_allows_only_safe_https(self, mock_open):
        self.assertTrue(self.bridge.open_external_url("https://example.com/path"))
        self.assertFalse(self.bridge.open_external_url("file:///C:/Windows/System32/calc.exe"))
        self.assertFalse(self.bridge.open_external_url("javascript:alert(1)"))
        mock_open.assert_called_once_with("https://example.com/path")

    @patch("maple_reporter.gui.pywebview_bridge.get_active_windows")
    def test_get_initial_data_first_run_defaults(self, mock_get_windows):
        mock_get_windows.return_value = [
            {"title": "新楓之谷：經典版 (1920x1080)", "width": 1920, "height": 1080}
        ]
        self.bridge.config = {"has_initialized_defaults": False}
        with patch("maple_reporter.gui.pywebview_bridge.load_config", return_value=dict(self.bridge.config)):
            init_data = self.bridge.get_initial_data()
            cfg = init_data["config"]
            self.assertTrue(cfg.get("has_initialized_defaults"))
            self.assertEqual(cfg.get("recording_preset"), "balanced")
            self.assertEqual(cfg.get("selected_window_title"), "新楓之谷：經典版 (1920x1080)")


if __name__ == "__main__":
    unittest.main()
