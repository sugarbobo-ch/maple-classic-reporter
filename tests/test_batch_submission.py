"""Batch integration tests use real SQLite history and mocked external services."""
from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest

from maple_reporter.gui.bridge.submission_bridge import SubmissionBridgeMixin
from maple_reporter.sanctions.repository import SanctionRepository
from maple_reporter.evidence.lifecycle import EvidenceLifecycleManager


@pytest.fixture
def batch(tmp_path, monkeypatch):
    bridge = SubmissionBridgeMixin()
    bridge._submission_lock = threading.Lock()
    bridge.config = {"upload_destination": "gdrive", "auto_delete_after_upload": True}
    bridge.sanction_repo = SanctionRepository(cache_path=tmp_path / "cache.json",
        history_path=tmp_path / "history.json", db_path=tmp_path / "history.db")
    bridge.drive_mgr = MagicMock()
    bridge.drive_mgr.upload_file_and_make_public.return_value = (True, "https://drive.google.com/file/d/shared/view")
    bridge.drive_mgr.trash_file.return_value = (True, "trashed")
    bridge._emit_event = MagicMock()
    bridge._emit_submission_status = MagicMock()
    monkeypatch.setattr("maple_reporter.gui.pywebview_bridge.is_owned_recording_path", lambda p: True)
    monkeypatch.setattr("maple_reporter.utils.config.is_owned_recording_path", lambda p: True)
    monkeypatch.setattr("maple_reporter.evidence.lifecycle.is_owned_recording_path", lambda p: True)
    send = MagicMock(return_value=(True, "成功"))
    monkeypatch.setattr("maple_reporter.gui.pywebview_bridge.submit_gamania_report", send)
    video = tmp_path / "evidence.mp4"
    video.write_bytes(b"test evidence")
    data = {"file_path": str(video), "server": "雪吉拉", "map_name": "弓箭手村",
        "note": "共用說明", "submission_mode": "automatic", "media_type": "video",
        "suspects": [{"suspect_id": "甲"}, {"suspect_id": "乙", "note_override": "乙的說明"}, {"suspect_id": "丙"}]}
    return bridge, data, send, video


def test_upload_once_separate_records_and_cleanup_after_last(batch):
    bridge, data, send, video = batch
    send.side_effect = lambda **kwargs: (video.exists(), "成功")
    result = bridge.submit_report_batch(data)
    assert result["status"] == "success"
    assert bridge.drive_mgr.upload_file_and_make_public.call_count == 1
    assert [c.kwargs["suspect_id"] for c in send.call_args_list] == ["甲", "乙", "丙"]
    assert [c.kwargs["note"] for c in send.call_args_list] == ["共用說明", "乙的說明", "共用說明"]
    assert len({r["record_id"] for r in result["records"]}) == 3
    assert all(r["submission_state"] == "submitted" for r in result["records"])
    assert not video.exists()
    assert all(record["media_path"] == "" for record in bridge.sanction_repo.load_history())


def test_second_failure_pauses_and_resume_never_repeats_success(batch):
    bridge, data, send, video = batch
    send.side_effect = [(True, "成功"), (False, "timeout")]
    result = bridge.submit_report_batch(data)
    assert result["status"] == "error"
    assert send.call_count == 2
    assert video.exists()
    assert result["records"][1]["batch_phase"] == "unknown"
    data["batch_id"] = result["batch_id"]
    assert bridge.submit_report_batch(data)["status"] == "error"
    assert send.call_count == 2
    bridge.resolve_report_result({"record_id": result["records"][1]["record_id"], "completed": False})
    send.side_effect = None
    result = bridge.submit_report_batch(data)
    assert result["status"] == "success"
    assert [c.kwargs["suspect_id"] for c in send.call_args_list] == ["甲", "乙", "乙", "丙"]
    assert bridge.drive_mgr.upload_file_and_make_public.call_count == 1


def test_manual_confirmation_preserves_video_and_advances(batch):
    bridge, data, send, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    assert result["status"] == "manual_ready"
    send.assert_not_called()
    for index, row in enumerate(result["records"]):
        confirmed = bridge.confirm_manual_report(row["record_id"])
        assert confirmed["status"] == "success"
        assert video.exists() == (index < 2)
        assert bool(confirmed["next_record"]) == (index < 2)
    assert bridge.drive_mgr.upload_file_and_make_public.call_count == 1


def test_draft_roundtrip_and_edit_preserves_overrides(batch):
    bridge, data, send, video = batch
    result = bridge.save_report_batch(data)
    ids = [r["record_id"] for r in result["records"]]
    data["batch_id"] = result["batch_id"]
    data["note"] = "新共用說明"
    result = bridge.save_report_batch(data)
    assert [r["record_id"] for r in result["records"]] == ids
    assert [r["note"] for r in result["records"]] == ["新共用說明", "乙的說明", "新共用說明"]
    reloaded = SanctionRepository(cache_path=video.parent / "cache.json",
        history_path=video.parent / "history.json", db_path=video.parent / "history.db")
    assert len(reloaded.load_history()) == 3
    assert all(r["batch_id"] == data["batch_id"] for r in reloaded.load_history())
    send.assert_not_called()
    bridge.drive_mgr.upload_file_and_make_public.assert_not_called()


def test_interrupted_sending_requires_explicit_resolution(batch):
    bridge, data, send, _ = batch
    saved = bridge.save_report_batch(data)
    row = saved["records"][0]
    bridge.sanction_repo.update_history_entry(row["record_id"], {"batch_phase": "sending"})
    data["batch_id"] = saved["batch_id"]
    assert bridge.submit_report_batch(data)["status"] == "error"
    send.assert_not_called()
    bridge.resolve_report_result({"record_id": row["record_id"], "completed": True})
    assert bridge.submit_report_batch(data)["status"] == "success"
    assert [c.kwargs["suspect_id"] for c in send.call_args_list] == ["乙", "丙"]


def test_deleting_one_record_keeps_shared_evidence(batch):
    bridge, data, _, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    manager = EvidenceLifecycleManager(bridge.sanction_repo, bridge.drive_mgr)
    deleted = manager.delete_records([result["records"][0]["record_id"]], ["local", "google_drive"])
    assert deleted["success"]
    assert video.exists()
    bridge.drive_mgr.trash_file.assert_not_called()
    assert len(bridge.sanction_repo.load_history()) == 2


def test_upload_error_retains_every_record_and_does_not_send(batch):
    bridge, data, send, video = batch
    bridge.drive_mgr.upload_file_and_make_public.return_value = (False, "offline")
    result = bridge.submit_report_batch(data)
    assert result["status"] == "error"
    assert len(result["records"]) == 3
    assert video.exists()
    send.assert_not_called()


def test_upload_error_returns_batch_to_editable_draft(batch):
    bridge, data, send, _ = batch
    bridge.drive_mgr.upload_file_and_make_public.return_value = (False, "offline")
    result = bridge.submit_report_batch(data)
    assert result["status"] == "error"
    assert {record["batch_phase"] for record in result["records"]} == {"draft"}

    data["batch_id"] = result["batch_id"]
    data["suspects"] = [{"suspect_id": "修正後角色"}]
    saved = bridge.save_report_batch(data)
    assert saved["status"] == "success"
    assert [record["suspect_id"] for record in saved["records"]] == ["修正後角色"]
    send.assert_not_called()


def test_invalid_names_rejected_before_persistence(batch):
    bridge, data, send, _ = batch
    data["suspects"] = [{"suspect_id": "甲 乙"}]
    assert bridge.submit_report_batch(data)["status"] == "error"
    assert not bridge.sanction_repo.load_history()
    send.assert_not_called()


def test_more_than_history_capacity_is_rejected_without_partial_records(batch):
    bridge, data, send, video = batch
    data["suspects"] = [{"suspect_id": f"Player-{index}"} for index in range(201)]
    result = bridge.save_report_batch(data)
    assert result["status"] == "error"
    assert "200" in result["message"]
    assert bridge.sanction_repo.load_history() == []
    assert video.exists()
    send.assert_not_called()


def test_new_batch_cannot_evict_existing_history_at_capacity(batch):
    bridge, data, send, video = batch
    existing = [
        {
            "record_id": f"old-{index}",
            "suspect_id": f"Old-{index}",
            "submission_state": "submitted",
            "time": "2026-09-10 12:00:00",
        }
        for index in range(200)
    ]
    bridge.sanction_repo.save_history(existing)
    data["suspects"] = [{"suspect_id": "new-person"}]
    result = bridge.save_report_batch(data)
    assert result["status"] == "error"
    assert {record["record_id"] for record in bridge.sanction_repo.load_history()} == {
        f"old-{index}" for index in range(200)
    }
    assert video.exists()
    send.assert_not_called()


def test_whitespace_map_is_rejected_before_any_official_submission(batch):
    bridge, data, send, _ = batch
    data["map_name"] = "   "
    result = bridge.submit_report_batch(data)
    assert result["status"] == "error"
    assert send.call_count == 0


def test_cleanup_all_selected_shared_records_cleans_once(batch):
    bridge, data, send, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    manager = EvidenceLifecycleManager(bridge.sanction_repo, bridge.drive_mgr)
    cleaned = manager.cleanup_records(
        [record["record_id"] for record in result["records"]],
        ["local", "google_drive"],
    )
    assert cleaned["success"]
    assert len(cleaned["cleaned_record_ids"]) == 3
    assert not video.exists()
    assert bridge.drive_mgr.trash_file.call_count == 1
    records = bridge.sanction_repo.load_history()
    assert all(record["media_path"] == "" for record in records)


def test_cleanup_selected_subset_keeps_remote_reference_state_available(batch):
    bridge, data, send, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    manager = EvidenceLifecycleManager(bridge.sanction_repo, bridge.drive_mgr)
    selected = [record["record_id"] for record in result["records"][:2]]
    cleaned = manager.cleanup_records(selected, ["google_drive"])
    assert cleaned["success"]
    assert bridge.drive_mgr.trash_file.call_count == 0
    remaining = bridge.sanction_repo.load_history()
    assert all(record["remote_evidence_state"] != "trashed" for record in remaining)
    assert video.exists()


def test_missing_saved_upload_url_returns_explicit_batch_error(batch):
    bridge, data, send, _ = batch
    original_update = bridge._update_batch
    bridge._update_batch = lambda batch_id, updates: None
    result = bridge.submit_report_batch(data)
    assert result["status"] == "error"
    assert "連結" in result["message"]
    bridge._update_batch = original_update
    send.assert_not_called()


def test_resume_uses_saved_url_even_if_local_video_is_missing(batch):
    bridge, data, send, video = batch
    send.side_effect = [(True, "成功"), (False, "timeout")]
    result = bridge.submit_report_batch(data)
    data["batch_id"] = result["batch_id"]
    bridge.resolve_report_result({"record_id": result["records"][1]["record_id"], "completed": False})
    video.unlink()
    send.side_effect = None
    assert bridge.submit_report_batch(data)["status"] == "success"
    assert bridge.drive_mgr.upload_file_and_make_public.call_count == 1


def test_overlapping_requests_do_not_mutate_history_or_upload(batch):
    bridge, data, send, _ = batch
    bridge._submission_lock.acquire()
    try:
        assert bridge.submit_report_batch(data)["status"] == "error"
        assert bridge.save_report_batch(data)["status"] == "error"
        assert bridge.save_report_draft(data)["status"] == "error"
        assert not bridge.sanction_repo.load_history()
        bridge.drive_mgr.upload_file_and_make_public.assert_not_called()
        send.assert_not_called()
    finally:
        bridge._submission_lock.release()


def test_sqlite_migration_preserves_legacy_completed_record(tmp_path):
    import sqlite3
    from maple_reporter.sanctions.database import SanctionDatabase
    path = tmp_path / "legacy.db"
    original = SanctionDatabase(path)
    original.insert_or_update_report({"record_id": "legacy", "suspect_id": "舊角色"})
    with sqlite3.connect(path) as conn:
        for column in ("batch_id", "batch_order", "batch_note", "note_override", "batch_phase"):
            conn.execute(f"ALTER TABLE reports DROP COLUMN {column}")
    migrated = SanctionDatabase(path)
    row = migrated.load_reports()[0]
    assert row["record_id"] == "legacy"
    assert row["suspect_id"] == "舊角色"
    assert row["submission_state"] == "submitted"
    assert row["batch_id"] is None


def test_deleting_all_selected_records_does_not_partially_delete_on_shared_cleanup_failure(batch, monkeypatch):
    bridge, data, _, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    ids = [record["record_id"] for record in result["records"]]
    manager = EvidenceLifecycleManager(bridge.sanction_repo, bridge.drive_mgr)

    monkeypatch.setattr(
        "maple_reporter.evidence.lifecycle.Path.unlink",
        MagicMock(side_effect=OSError("file is locked")),
    )
    deleted = manager.delete_records(ids, ["local", "google_drive"])

    assert deleted["deleted_record_ids"] == []
    assert set(deleted["failed_record_ids"]) == set(ids)
    assert {record["record_id"] for record in bridge.sanction_repo.load_history()} == set(ids)
    assert video.exists()


def test_deleting_all_selected_records_batches_history_write(batch):
    bridge, data, _, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    ids = [record["record_id"] for record in result["records"]]
    delete_history_entries = MagicMock(wraps=bridge.sanction_repo.delete_history_entries)
    bridge.sanction_repo.delete_history_entries = delete_history_entries
    manager = EvidenceLifecycleManager(bridge.sanction_repo, bridge.drive_mgr)

    deleted = manager.delete_records(ids, ["local", "google_drive"])

    assert deleted["success"]
    assert delete_history_entries.call_count == 1
    assert delete_history_entries.call_args.args[0] == ids
    assert not video.exists()


def test_saving_an_uploaded_record_as_draft_preserves_its_evidence_url(batch):
    bridge, data, _, video = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    uploaded = result["records"][0]

    saved = bridge.save_report_draft(
        {
            "record_id": uploaded["record_id"],
            "file_path": str(video),
            "media_type": "video",
            "suspect_id": uploaded["suspect_id"],
            "server": uploaded["server"],
            "map_name": uploaded.get("map_name") or uploaded["map"],
            "note": uploaded["note"],
        }
    )

    assert saved["status"] == "success"
    assert saved["record"]["url"] == uploaded["url"]


def test_manual_batch_confirmation_updates_history_once(batch):
    bridge, data, _, _ = batch
    data["submission_mode"] = "manual"
    result = bridge.submit_report_batch(data)
    update_history_entry = MagicMock(wraps=bridge.sanction_repo.update_history_entry)
    bridge.sanction_repo.update_history_entry = update_history_entry

    confirmed = bridge.confirm_manual_report(result["records"][0]["record_id"])

    assert confirmed["status"] == "success"
    assert update_history_entry.call_count == 1
    assert update_history_entry.call_args.args[1]["batch_phase"] == "completed"
