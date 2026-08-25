"""Safe, user-triggered evidence cleanup for report history records."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from maple_reporter.utils.config import is_owned_recording_path

_DRIVE_FILE_PATTERNS = (
    re.compile(r"/file/d/([A-Za-z0-9_-]+)"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]+)"),
)
_VALID_CLEANUP_TARGETS = frozenset({'local', 'google_drive'})


def parse_drive_file_id(url: str | None) -> str:
    """Extract a Google Drive file ID from common share URL shapes."""

    value = str(url or "").strip()
    if not value:
        return ""
    for pattern in _DRIVE_FILE_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceLifecycleManager:
    """Deep module for eligibility, cleanup ordering, and result normalization."""

    TARGET_LOCAL = "local"
    TARGET_GOOGLE_DRIVE = "google_drive"

    def __init__(self, repository: Any, drive_manager: Any) -> None:
        self.repository = repository
        self.drive_manager = drive_manager

    @staticmethod
    def _normalize_ids(values: Iterable[object]) -> list[str]:
        return list(
            dict.fromkeys(
                normalized
                for value in values
                if (normalized := str(value or '').strip())
            )
        )

    @staticmethod
    def _normalize_targets(values: Iterable[object]) -> set[str]:
        return {
            normalized
            for value in values
            if (normalized := str(value or '').strip())
        }

    def _load_records_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {
            str(item.get('record_id', '')): item
            for item in self.repository.load_history()
        }

    def enrich_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        url = str(enriched.get("url") or enriched.get("evidence_url") or "").strip()
        provider = str(enriched.get("evidence_provider") or "").strip().lower()
        remote_id = str(enriched.get("remote_evidence_id") or "").strip()

        if not provider:
            remote_id = remote_id or parse_drive_file_id(url)
            if remote_id:
                provider = "gdrive"
            elif "discord" in url.lower() or "discordapp.net" in url.lower():
                provider = "discord"
            elif url:
                provider = "external"
            else:
                provider = "none"

        if provider == "gdrive" and not remote_id:
            remote_id = parse_drive_file_id(url)

        state = str(enriched.get("remote_evidence_state") or "").strip().lower()
        if not state:
            if provider == "gdrive" and remote_id:
                state = "available"
            elif provider == "discord":
                state = "unmanaged"
            elif provider == "external":
                state = "unavailable"
            else:
                state = "unavailable"

        media_path = str(enriched.get("media_path") or "")
        enriched["evidence_provider"] = provider
        enriched["remote_evidence_id"] = remote_id
        enriched["remote_evidence_state"] = state
        enriched["media_cleanup_eligible"] = bool(
            media_path and os.path.isfile(media_path) and is_owned_recording_path(media_path)
        )
        if not enriched["media_cleanup_eligible"] and media_path and not os.path.exists(media_path):
            enriched.setdefault("local_evidence_cleaned_at", "")
        return enriched

    def cleanup_record(self, record: Mapping[str, Any], targets: Iterable[str]) -> dict[str, Any]:
        """Clean one record in remote-first order and return an updated record/result."""

        target_set = self._normalize_targets(targets)
        current = self.enrich_record(record)
        results: dict[str, dict[str, Any]] = {}

        if self.TARGET_GOOGLE_DRIVE in target_set:
            drive_result = self._cleanup_google_drive(current)
            results[self.TARGET_GOOGLE_DRIVE] = drive_result
            if not drive_result["success"]:
                current["remote_evidence_state"] = "error"
                current["remote_cleanup_error"] = drive_result["message"]
                return {"success": False, "record": current, "results": results}
            current.update(drive_result.get("record_updates", {}))

        if self.TARGET_LOCAL in target_set:
            local_result = self._cleanup_local(current)
            results[self.TARGET_LOCAL] = local_result
            if not local_result["success"]:
                return {"success": False, "record": current, "results": results}
            current.update(local_result.get("record_updates", {}))

        return {"success": True, "record": current, "results": results}

    def cleanup_records(
        self,
        record_ids: Iterable[str],
        targets: Iterable[str],
    ) -> dict[str, Any]:
        """Clean selected records while retaining their history entries."""

        ids = self._normalize_ids(record_ids)
        target_set = self._normalize_targets(targets)
        if not ids or not target_set or not target_set.issubset(_VALID_CLEANUP_TARGETS):
            return {"success": False, "message": "請選擇有效的紀錄與清理目標。", "results": []}

        records = self._load_records_by_id()
        results: list[dict[str, Any]] = []
        for record_id in ids:
            record = records.get(record_id)
            if record is None:
                results.append({"record_id": record_id, "success": False, "message": "找不到紀錄。"})
                continue
            result = self.cleanup_record(record, target_set)
            updated = result.get("record", record)
            if updated != record:
                self.repository.update_history_entry(record_id, updated)
            results.append({"record_id": record_id, **result})

        failed = [item["record_id"] for item in results if not item.get("success")]
        return {
            "success": not failed,
            "cleaned_record_ids": [item["record_id"] for item in results if item.get("success")],
            "failed_record_ids": failed,
            "results": results,
        }

    def delete_records(
        self,
        record_ids: Iterable[str],
        cleanup_targets: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Clean selected targets, then hard-delete records only after success."""

        ids = self._normalize_ids(record_ids)
        target_set = self._normalize_targets(cleanup_targets)
        if not ids or not target_set.issubset(_VALID_CLEANUP_TARGETS):
            return {"success": False, "message": "請選擇有效的紀錄。", "deleted_record_ids": [], "failed_record_ids": []}

        records = self._load_records_by_id()
        deleted_ids: list[str] = []
        failed: list[dict[str, Any]] = []
        for record_id in ids:
            record = records.get(record_id)
            if record is None:
                failed.append({"record_id": record_id, "message": "找不到紀錄。"})
                continue

            cleanup_result = (
                self.cleanup_record(record, target_set)
                if target_set
                else {"success": True, "record": record, "results": {}}
            )
            if not cleanup_result.get("success"):
                updated = cleanup_result.get("record", record)
                if updated != record:
                    self.repository.update_history_entry(record_id, updated)
                failed.append({
                    "record_id": record_id,
                    "message": next(
                        (
                            item.get("message", "清理證據失敗。")
                            for item in cleanup_result.get("results", {}).values()
                            if not item.get("success")
                        ),
                        "清理證據失敗。",
                    ),
                    "cleanup": cleanup_result,
                })
                continue

            if self.repository.delete_history_entries([record_id]):
                deleted_ids.append(record_id)
            else:
                failed.append({"record_id": record_id, "message": "無法刪除紀錄。"})

        return {
            "success": not failed,
            "deleted_record_ids": deleted_ids,
            "failed_record_ids": [item["record_id"] for item in failed],
            "failed": failed,
        }

    def _cleanup_google_drive(self, record: Mapping[str, Any]) -> dict[str, Any]:
        provider = str(record.get("evidence_provider") or "")
        file_id = str(record.get("remote_evidence_id") or "")
        state = str(record.get("remote_evidence_state") or "")
        if provider != "gdrive" or not file_id:
            # Non-Drive and legacy records have no managed remote object for
            # this adapter to remove; do not block a batch deletion on them.
            return {
                "success": True,
                "message": "沒有可由本工具處理的 Google Drive 檔案。",
                "record_updates": {},
            }
        if state == "trashed":
            return {"success": True, "message": "Google Drive 檔案已在垃圾桶。", "record_updates": {}}

        try:
            ok, message = self.drive_manager.trash_file(file_id)
        except Exception as error:  # pragma: no cover - defensive adapter boundary
            ok, message = False, str(error)
        if not ok:
            return {"success": False, "message": message or "無法將 Google Drive 檔案移至垃圾桶。"}
        return {
            "success": True,
            "message": "Google Drive 檔案已移至垃圾桶。",
            "record_updates": {
                "remote_evidence_state": "trashed",
                "remote_evidence_cleaned_at": _now_iso(),
                "remote_cleanup_error": "",
            },
        }

    def _cleanup_local(self, record: Mapping[str, Any]) -> dict[str, Any]:
        path = str(record.get("media_path") or "")
        if not path:
            return {"success": True, "message": "沒有本機證據。", "record_updates": {}}
        if not is_owned_recording_path(path):
            return {"success": False, "message": "這個檔案不是本工具管理的本機證據。"}
        if not os.path.exists(path):
            return {"success": True, "message": "本機證據已不存在。", "record_updates": {}}
        try:
            Path(path).unlink()
        except OSError as error:
            return {"success": False, "message": f"無法刪除本機證據：{error}"}
        return {
            "success": True,
            "message": "本機證據已刪除。",
            "record_updates": {"media_path": "", "local_evidence_cleaned_at": _now_iso()},
        }
