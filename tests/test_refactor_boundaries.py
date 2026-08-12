import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maple_reporter.automation.form_filler import (
    _submission_failure_reason,
    _wait_for_submission_confirmation,
)
from maple_reporter.gui.submission_controller import SubmissionController
from maple_reporter.ocr.candidate_ranker import (
    CandidateObservation,
    rank_candidate_observations,
)
from maple_reporter.recorder.replay_buffer import ReplayState
from maple_reporter.utils import config


class _Locator:
    def __init__(self, visible=False):
        self.first = self
        self._visible = visible

    def count(self):
        return 1

    def is_visible(self):
        return self._visible


class _Page:
    def __init__(self, url="", visible_selectors=None):
        self.url = url
        self.visible_selectors = set(visible_selectors or [])

    def locator(self, selector):
        return _Locator(selector in self.visible_selectors)

    def wait_for_timeout(self, _milliseconds):
        return None


class TestRefactorBoundaries(unittest.TestCase):
    def test_submission_success_accepts_confirmed_thankyou_redirect(self):
        page = _Page("https://forms.gamania.com/s/eLGg4?redirect=thankyou")
        self.assertTrue(_wait_for_submission_confirmation(page, timeout_ms=100))

    def test_submission_success_rejects_unverified_success_path(self):
        page = _Page("https://forms.gamania.com/s/eLGg4/success")
        self.assertFalse(_wait_for_submission_confirmation(page, timeout_ms=100))

    def test_preview_modal_starts_ocr_after_map_field_is_created(self):
        source = Path("src/maple_reporter/gui/preview_modal.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            source.index("self.map_input = QLineEdit"),
            source.index("self.ocr_thread.start()"),
        )
        self.assertLess(
            source.index("self.ocr_thread.finished.connect(self.on_ocr_finished)"),
            source.index("self.ocr_thread.start()"),
        )

    def test_local_evidence_picker_starts_at_recordings_dir(self):
        source = Path("src/maple_reporter/gui/main_window.py").read_text(
            encoding="utf-8"
        )
        dialog_call = source[source.index("def trigger_local_file_report"):]
        self.assertIn("str(get_recordings_dir())", dialog_call)

    def test_submission_success_rejects_unrelated_host_url(self):
        page = _Page("https://example.com/success")
        self.assertFalse(_wait_for_submission_confirmation(page, timeout_ms=100))

    def test_submission_failure_exposes_visible_validation_message(self):
        page = _Page(visible_selectors={'text="請確認必填欄位"'})
        self.assertEqual(
            _submission_failure_reason(page),
            "表單仍有必填欄位未完成",
        )

    def test_candidate_ranking_deduplicates_repeated_text_in_one_frame(self):
        ranked = rank_candidate_observations(
            [
                CandidateObservation("Noise", 0.99, 0),
                CandidateObservation("Noise", 0.98, 0),
                CandidateObservation("PlayerOne", 0.75, 0),
                CandidateObservation("PlayerOne", 0.80, 1),
                CandidateObservation("PlayerTwo", 0.95, 0),
            ]
        )
        self.assertEqual(ranked, ["PlayerOne", "Noise", "PlayerTwo"])

    def test_auto_delete_requires_upload_and_form_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recording_dir = Path(temp_dir) / "recordings"
            recording_dir.mkdir()
            recording = recording_dir / "maple_evidence_123.mp4"
            recording.write_bytes(b"evidence")
            base = {
                "file_path": str(recording),
                "file_origin": "generated",
                "upload_confirmed": False,
            }
            with patch.object(config, "RECORDINGS_DIR", recording_dir):
                self.assertFalse(SubmissionController.can_delete_evidence(base, True))
                base["upload_confirmed"] = True
                self.assertFalse(SubmissionController.can_delete_evidence(base, False))
                self.assertTrue(SubmissionController.can_delete_evidence(base, True))
                self.assertTrue(SubmissionController.delete_confirmed_evidence(base))
            self.assertFalse(recording.exists())

    def test_history_write_uses_unique_fsynced_temp_file_and_replaces_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            history_file = config_dir / "history.json"
            with patch.object(config, "CONFIG_DIR", config_dir), patch.object(
                config, "HISTORY_FILE", history_file
            ), patch.object(config, "RECORDINGS_DIR", root / "recordings"):
                config.add_history_entry({"status": "成功"})
                self.assertEqual(config.load_history()[0]["status"], "成功")
                self.assertEqual(list(config_dir.glob("*.tmp")), [])

    def test_replay_state_machine_names_are_explicit(self):
        self.assertEqual(
            [state.value for state in ReplayState],
            ["idle", "warming", "ready", "saving", "stopping", "error"],
        )


if __name__ == "__main__":
    unittest.main()
