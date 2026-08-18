"""Unit tests for PyWebViewBridge sanction APIs and event handling."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from maple_reporter.gui.pywebview_bridge import PyWebViewBridge
from maple_reporter.sanctions.repository import SanctionRepository


class TestPyWebViewBridgeSanctions(unittest.TestCase):
    def setUp(self):
        self._load_config_patch = patch(
            "maple_reporter.gui.pywebview_bridge.load_config",
            return_value={"auto_check_sanction_status": True, "dev_mode": False},
        )
        self._media_server_patch = patch("maple_reporter.gui.pywebview_bridge.LocalMediaServer")
        self._hotkey_patch = patch("maple_reporter.gui.pywebview_bridge.BackgroundHotkeyListener")
        self._drive_patch = patch("maple_reporter.gui.pywebview_bridge.GoogleDriveManager")
        self._replay_patch = patch("maple_reporter.gui.pywebview_bridge.ReplayBufferRecorder")

        self._load_config_patch.start()
        media = self._media_server_patch.start()
        self._hotkey_patch.start()
        drive = self._drive_patch.start()
        replay = self._replay_patch.start()

        media.return_value.start.return_value = 0
        drive.return_value.is_authenticated.return_value = False
        replay.return_value.is_running = False

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
        self._replay_patch.stop()
        self._drive_patch.stop()
        self._hotkey_patch.stop()
        self._media_server_patch.stop()
        self._load_config_patch.stop()

    def test_start_sanction_sync_delegates_to_coordinator(self):
        with patch.object(self.bridge.sanction_coordinator, "start") as mock_start:
            mock_start.return_value.to_dict.return_value = {"started": True, "status": {"running": True}}
            res = self.bridge.start_sanction_sync(trigger="startup")
            mock_start.assert_called_once_with(trigger="startup")
            self.assertTrue(res["started"])

    def test_get_sanction_sync_status(self):
        with patch.object(self.bridge.sanction_coordinator, "get_status") as mock_status:
            mock_status.return_value.to_dict.return_value = {"running": False}
            res = self.bridge.get_sanction_sync_status()
            mock_status.assert_called_once()
            self.assertFalse(res["running"])

    def test_get_history_delegates_to_repository(self):
        with patch.object(self.bridge.sanction_repo, "load_history") as mock_history:
            mock_history.return_value = [{"record_id": "uuid-1", "suspect_id": "Player1"}]
            res = self.bridge.get_history()
            mock_history.assert_called_once()
            self.assertEqual(len(res), 1)

    def test_rebuild_sanction_cache_for_development_requires_dev_mode(self):
        # dev_mode is False
        self.bridge.config["dev_mode"] = False
        self.assertFalse(self.bridge.rebuild_sanction_cache_for_development())

        # dev_mode is True
        self.bridge.config["dev_mode"] = True
        with patch.object(self.bridge.sanction_coordinator, "rebuild_cache_for_development", return_value=True) as mock_rebuild:
            self.assertTrue(self.bridge.rebuild_sanction_cache_for_development())
            mock_rebuild.assert_called_once()


if __name__ == "__main__":
    unittest.main()
