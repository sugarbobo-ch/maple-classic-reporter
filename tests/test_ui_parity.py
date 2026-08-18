import json
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from PySide6.QtCore import QCoreApplication

from maple_reporter.gui import history_controller as history_module
from maple_reporter.gui import pywebview_bridge as bridge_module
from maple_reporter.gui import settings_controller as settings_module
from maple_reporter.gui.evidence_capture_controller import EvidenceCaptureController
from maple_reporter.gui.history_controller import HistoryController
from maple_reporter.gui.replay_controller import ReplayController
from maple_reporter.gui.settings_controller import SettingsController
from maple_reporter.gui.submission_controller import SubmitThread
from maple_reporter.gui.pywebview_bridge import PyWebViewBridge
from maple_reporter.gui.quick_links_controller import QuickLinksController
from maple_reporter.ocr import ocr_worker as ocr_worker_module
from maple_reporter.ocr.ocr_worker import OcrWorkerThread


TEST_CONFIG_FILE = Path(__file__).parent / "fixtures" / "config.json"
_QT_APP = None


def _ensure_qt_app():
    global _QT_APP
    _QT_APP = QCoreApplication.instance() or QCoreApplication([])
    return _QT_APP


class _TextField:
    def __init__(self, value):
        self.value = value

    def text(self):
        return self.value

    def currentText(self):
        return self.value


class _DataField(_TextField):
    def currentData(self):
        return self.value


class _BoolField:
    def __init__(self, value):
        self.value = value

    def isChecked(self):
        return self.value


class _NumberField:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


def _legacy_settings_window():
    return SimpleNamespace(
        combo_server=_TextField("Gamania"),
        txt_map=_TextField("Test Map"),
        txt_note=_TextField("Test note"),
        combo_windows=_TextField("MapleStory Classic"),
        spin_duration=_NumberField(4),
        combo_fps=_DataField(24),
        spin_countdown=_NumberField(0),
        spin_replay_seconds=_NumberField(30),
        txt_gdrive_folder=_TextField("MapleClassic_Reports"),
        txt_discord_webhook=_TextField(""),
        combo_upload_destination=_DataField("gdrive"),
        txt_whitelist=_TextField("known-player, suspect-42"),
        chk_auto_delete=_BoolField(False),
        chk_record_audio=_BoolField(False),
        chk_form_submit_headless=_BoolField(False),
        chk_dev_mode=_BoolField(True),
        chk_ocr_id=_BoolField(True),
        chk_ocr_map=_BoolField(False),
        combo_audio_output=_DataField("loopback"),
        chk_global_hotkeys=_BoolField(True),
        combo_save_replay_hotkey_key=_DataField("F9"),
        combo_record_video_hotkey_key=_DataField("F10"),
    )


class _TableItem:
    def __init__(self, value):
        self.value = value

    def text(self):
        return self.value


class _HistoryTable:
    def __init__(self, value):
        self.value = value

    def item(self, _row, _column):
        return _TableItem(self.value)


class TestUiParity(unittest.TestCase):
    """Drive both legacy entry points through the same backend operations."""

    def _config(self):
        return json.loads(TEST_CONFIG_FILE.read_text(encoding="utf-8"))

    def test_settings_toggle_has_the_same_backend_value(self):
        config = self._config()
        legacy_window = _legacy_settings_window()
        legacy_result = SettingsController(dict(config)).collect_from_window(legacy_window)

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = dict(config)
        with (
            patch.object(bridge_module, "load_config", return_value=dict(config)),
            patch.object(bridge_module, "save_config"),
            patch.object(bridge, "_init_hotkeys"),
        ):
            self.assertTrue(bridge.save_config_key("ocr_autofill_map", False))

        self.assertFalse(legacy_result["ocr_autofill_map"])
        self.assertEqual(bridge.config["ocr_autofill_map"], legacy_result["ocr_autofill_map"])

    def test_legacy_settings_reload_after_persistence_failure(self):
        controller = SettingsController({"ocr_autofill_map": False})
        backend_config = {"ocr_autofill_map": True, "dev_mode": False}
        with (
            patch.object(settings_module, "save_config", side_effect=OSError("disk full")),
            patch.object(settings_module, "load_config", return_value=backend_config),
        ):
            self.assertFalse(controller.save_model())

        self.assertEqual(controller.config, backend_config)

    def test_submission_settings_have_the_same_backend_value(self):
        config = self._config()
        legacy_result = SettingsController(dict(config)).collect_from_window(
            _legacy_settings_window()
        )

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = dict(config)
        with (
            patch.object(bridge_module, "load_config", return_value=dict(config)),
            patch.object(bridge_module, "save_config"),
            patch.object(bridge, "_init_hotkeys"),
        ):
            self.assertTrue(
                bridge.save_config_all(
                    {
                        "form_submit_headless": False,
                        "dev_mode": True,
                    }
                )
            )

        self.assertFalse(legacy_result["form_submit_headless"])
        self.assertTrue(legacy_result["dev_mode"])
        self.assertEqual(
            bridge.config["form_submit_headless"], legacy_result["form_submit_headless"]
        )
        self.assertEqual(bridge.config["dev_mode"], legacy_result["dev_mode"])

    def test_ocr_id_map_and_whitelist_have_the_same_result(self):
        _ensure_qt_app()
        image = Image.new("RGB", (32, 32), color="white")
        config = self._config()
        config.update(
            {
                "ocr_autofill_id": True,
                "ocr_autofill_map": True,
                "whitelist": ["known-player"],
                "default_map": "Fallback Map",
            }
        )

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = config
        with (
            patch.object(PyWebViewBridge, "_emit_event"),
            patch.object(
                bridge_module,
                "recognize_map_name_from_image_list",
                return_value="Test Map",
            ),
            patch.object(
                bridge_module,
                "recognize_candidates_from_image_list",
                return_value=["known-player", "suspect-42"],
            ),
        ):
            web_result = bridge._perform_ocr([image])

        old_map = []
        old_candidates = []
        worker = OcrWorkerThread(
            [image],
            whitelist=["known-player"],
            recognize_id=True,
            recognize_map=True,
        )
        worker.map_name_found.connect(old_map.append)
        worker.candidates_found.connect(old_candidates.append)
        with (
            patch.object(ocr_worker_module, "recognize_map_name_from_image_list", return_value="Test Map"),
            patch.object(
                ocr_worker_module,
                "recognize_candidates_from_image_list",
                return_value=["known-player", "suspect-42"],
            ),
        ):
            worker.run()

        self.assertEqual(web_result["map_name"], old_map[-1])
        self.assertEqual(web_result["suspect_ids"], old_candidates[-1])

    def test_recording_parameters_have_the_same_backend_shape(self):
        config = self._config()
        config["selected_window_title"] = "MapleStory Classic"
        keyframes = [Image.new("RGB", (16, 16), color="black")]

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = config
        bridge._recording_active = False
        bridge._cancel_requested = False
        bridge._recording_thread = None
        bridge._submission_lock = threading.Lock()
        with (
            patch.object(bridge_module, "focus_window"),
            patch.object(bridge_module, "record_short_video", return_value=("evidence.mp4", keyframes)) as web_record,
            patch.object(PyWebViewBridge, "_emit_event"),
            patch.object(PyWebViewBridge, "_perform_ocr", return_value={"suspect_ids": [], "map_name": "Test Map"}),
        ):
            self.assertTrue(
                bridge.start_recording(
                    duration_sec=4,
                    fps=24,
                    countdown_sec=0,
                    record_audio=False,
                    audio_device_id="loopback",
                )
            )
            bridge._recording_thread.join(timeout=2)

        capture = EvidenceCaptureController()
        with patch.object(
            # The legacy controller and the bridge both call the same recorder seam.
            __import__(
                "maple_reporter.gui.evidence_capture_controller",
                fromlist=["record_short_video"],
            ),
            "record_short_video",
            return_value=("evidence.mp4", keyframes),
        ) as old_record:
            capture.record_video(
                "MapleStory Classic",
                duration_sec=4,
                fps=24,
                progress_callback=None,
                cancel_checker=None,
                record_audio=False,
                audio_device_id="loopback",
            )

        def signature(call):
            args, kwargs = call
            return (
                args[0],
                kwargs["duration_sec"],
                kwargs["fps"],
                kwargs["record_audio"],
                kwargs["audio_device_id"],
            )

        self.assertEqual(signature(web_record.call_args), signature(old_record.call_args))

    def test_replay_start_and_stop_have_the_same_backend_shape(self):
        _ensure_qt_app()
        config = self._config()
        bridge_recorder = MagicMock()
        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = config
        bridge.replay_recorder = bridge_recorder

        bridge.start_replay(
            "MapleStory Classic",
            fps=30,
            buffer_seconds=30,
            record_audio=False,
            audio_device_id="loopback",
        )
        bridge.stop_replay()

        with patch("maple_reporter.gui.replay_controller.ReplayBufferRecorder") as recorder_class:
            legacy_controller = ReplayController()
            legacy_controller.start(
                "MapleStory Classic",
                fps=30,
                buffer_seconds=30,
                record_audio=False,
                audio_device_id="loopback",
            )
            legacy_controller.stop()
            legacy_recorder = recorder_class.return_value

        self.assertEqual(bridge_recorder.start.call_args, legacy_recorder.start.call_args)
        self.assertEqual(bridge_recorder.stop.call_count, legacy_recorder.stop.call_count)

    def test_submission_payload_and_headless_mode_have_the_same_shape(self):
        _ensure_qt_app()
        config = self._config()
        config["auto_delete_after_upload"] = False
        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = config
        bridge._submission_lock = threading.Lock()
        form_data = {
            "suspect_id": "suspect-42",
            "server": "Gamania",
            "map_name": "Test Map",
            "note": "Test note",
            "evidence_url": "https://drive.google.com/file/d/test/view",
            "form_submit_headless": True,
            "dev_mode": False,
        }

        with (
            patch.object(bridge_module, "submit_gamania_report", return_value=(True, "submitted")) as web_submit,
            patch.object(bridge_module, "add_history_entry"),
            patch.object(PyWebViewBridge, "_emit_submission_status"),
        ):
            web_result = bridge.submit_report(dict(form_data))

        legacy_data = {
            **form_data,
            "server_name": form_data["server"],
        }
        with patch(
            "maple_reporter.gui.submission_controller.submit_gamania_report",
            return_value=(True, "submitted"),
        ) as old_submit:
            thread = SubmitThread(legacy_data)
            thread.run()

        self.assertEqual(web_result["status"], "success")
        self.assertEqual(web_submit.call_args.kwargs, old_submit.call_args.kwargs)

    def test_dev_mode_skips_real_form_submission_on_both_entry_points(self):
        _ensure_qt_app()
        form_data = {
            "suspect_id": "suspect-42",
            "server_name": "Gamania",
            "map_name": "Test Map",
            "note": "Test note",
            "evidence_url": "https://drive.google.com/file/d/test/view",
            "dev_mode": True,
        }

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        bridge.config = self._config()
        bridge._submission_lock = threading.Lock()
        with (
            patch.object(bridge_module, "add_history_entry"),
            patch.object(bridge_module, "submit_gamania_report") as web_submit,
            patch.object(PyWebViewBridge, "_emit_submission_status"),
            patch.object(bridge, "open_external_url"),
        ):
            web_result = bridge.submit_report(dict(form_data))

        with patch(
            "maple_reporter.gui.submission_controller.submit_gamania_report"
        ) as old_submit:
            finished = []
            thread = SubmitThread(form_data)
            thread.finished_signal.connect(lambda ok, message, error: finished.append((ok, message, error)))
            thread.run()

        self.assertEqual(web_result["status"], "success")
        self.assertTrue(web_result["dev_mode"])
        self.assertEqual(finished[0][0], True)
        web_submit.assert_not_called()
        old_submit.assert_not_called()

    def test_history_copy_and_clear_have_the_same_backend_contract(self):
        safe_url = "https://drive.google.com/file/d/test/view"
        clipboard = MagicMock()
        legacy = HistoryController()

        with patch.object(history_module, "QApplication") as application:
            application.clipboard.return_value = clipboard
            self.assertTrue(legacy.copy_url_from_cell(_HistoryTable(safe_url), 0))
            clipboard.setText.assert_called_once_with(safe_url)
            self.assertFalse(
                legacy.copy_url_from_cell(_HistoryTable("javascript:alert(1)"), 0)
            )

        with patch.object(history_module, "clear_history") as clear_persisted:
            self.assertTrue(legacy.clear())
            clear_persisted.assert_called_once_with()

    def test_quick_links_support_the_same_crud_order_and_safe_open_contract(self):
        config = {
            "quick_links": [
                {
                    "id": "first",
                    "title": "First",
                    "url": "https://example.com/first",
                    "icon": "Globe",
                    "isDefault": True,
                },
                {
                    "id": "second",
                    "title": "Second",
                    "url": "https://example.com/second",
                    "icon": "Globe",
                    "isDefault": False,
                },
            ]
        }
        controller = QuickLinksController(config)

        with patch("maple_reporter.gui.quick_links_controller.save_config") as persist:
            self.assertTrue(controller.add("Custom", "example.com/custom"))
            self.assertEqual(config["quick_links"][-1]["url"], "https://example.com/custom")
            self.assertTrue(controller.update(2, "Updated", "https://example.com/updated"))
            self.assertTrue(controller.move(2, -1))
            self.assertEqual(config["quick_links"][1]["title"], "Updated")
            self.assertTrue(controller.remove(0))
            persist.assert_called()

        with patch(
            "maple_reporter.gui.quick_links_controller.webbrowser.open",
            return_value=True,
        ) as open_url:
            self.assertTrue(controller.open(0))
            self.assertFalse(controller.open_url("javascript:alert(1)"))
            open_url.assert_called_once_with(config["quick_links"][0]["url"])

    def test_history_url_opening_obeys_the_same_safe_https_boundary(self):
        safe_url = "https://drive.google.com/file/d/test/view"
        unsafe_url = "javascript:alert(1)"

        bridge = PyWebViewBridge.__new__(PyWebViewBridge)
        with patch.object(bridge_module.webbrowser, "open", return_value=True) as web_open:
            self.assertTrue(bridge.open_external_url(safe_url))
            self.assertFalse(bridge.open_external_url(unsafe_url))

        legacy = HistoryController()
        with patch("maple_reporter.gui.history_controller.webbrowser.open", return_value=True) as old_open:
            self.assertTrue(legacy.open_url_from_cell(_HistoryTable(safe_url), 0, 4))
            self.assertFalse(legacy.open_url_from_cell(_HistoryTable(unsafe_url), 0, 4))

        self.assertEqual(web_open.call_count, old_open.call_count)


if __name__ == "__main__":
    unittest.main()
