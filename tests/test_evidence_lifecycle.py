from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, patch

from maple_reporter.evidence.lifecycle import EvidenceLifecycleManager, parse_drive_file_id


class EvidenceLifecycleTests(TestCase):
    def test_parses_common_google_drive_links(self):
        self.assertEqual(
            parse_drive_file_id("https://drive.google.com/file/d/file-123/view?usp=sharing"),
            "file-123",
        )
        self.assertEqual(
            parse_drive_file_id("https://drive.google.com/open?id=file_456"),
            "file_456",
        )
        self.assertEqual(parse_drive_file_id("https://example.com/evidence"), "")

    def test_enriches_legacy_drive_and_discord_records(self):
        manager = EvidenceLifecycleManager(repository=MagicMock(), drive_manager=MagicMock())

        drive = manager.enrich_record(
            {"record_id": "drive-1", "url": "https://drive.google.com/file/d/file-123/view"}
        )
        discord = manager.enrich_record(
            {"record_id": "discord-1", "url": "https://cdn.discordapp.com/attachments/1/2/file.mp4"}
        )

        self.assertEqual(drive["evidence_provider"], "gdrive")
        self.assertEqual(drive["remote_evidence_id"], "file-123")
        self.assertEqual(drive["remote_evidence_state"], "available")
        self.assertEqual(discord["evidence_provider"], "discord")
        self.assertEqual(discord["remote_evidence_state"], "unmanaged")

    def test_drive_failure_stops_before_local_cleanup(self):
        drive = MagicMock()
        drive.trash_file.return_value = (False, "權限不足")
        manager = EvidenceLifecycleManager(repository=MagicMock(), drive_manager=drive)
        record = {
            "record_id": "record-1",
            "url": "https://drive.google.com/file/d/file-123/view",
            "media_path": "C:/recordings/maple_evidence_1.mp4",
        }

        with patch("maple_reporter.evidence.lifecycle.is_owned_recording_path", return_value=True), patch(
            "maple_reporter.evidence.lifecycle.os.path.isfile", return_value=True
        ), patch("maple_reporter.evidence.lifecycle.Path.unlink") as unlink:
            result = manager.cleanup_record(record, {"google_drive", "local"})

        self.assertFalse(result["success"])
        self.assertEqual(result["results"]["google_drive"]["message"], "權限不足")
        unlink.assert_not_called()

    def test_successful_local_cleanup_clears_media_path(self):
        manager = EvidenceLifecycleManager(repository=MagicMock(), drive_manager=MagicMock())
        record = {
            "record_id": "record-1",
            "media_path": "C:/recordings/maple_evidence_1.mp4",
        }

        with patch("maple_reporter.evidence.lifecycle.is_owned_recording_path", return_value=True), patch(
            "maple_reporter.evidence.lifecycle.os.path.isfile", return_value=True
        ), patch("maple_reporter.evidence.lifecycle.os.path.exists", return_value=True), patch(
            "maple_reporter.evidence.lifecycle.Path.unlink"
        ) as unlink:
            result = manager.cleanup_record(record, {"local"})

        self.assertTrue(result["success"])
        self.assertEqual(result["record"]["media_path"], "")
        unlink.assert_called_once()
