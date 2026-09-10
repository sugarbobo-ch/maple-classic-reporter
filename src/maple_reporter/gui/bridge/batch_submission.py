"""Durable, sequential reports sharing one evidence upload."""

from __future__ import annotations

import os
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from maple_reporter.sanctions.models import get_submission_state
from maple_reporter.sanctions.repository import HISTORY_LOCK, MAX_HISTORY_RECORDS

LOGGER = logging.getLogger(__name__)


class BatchSubmissionMixin:
    def _batch_records(self, batch_id: str) -> list[dict[str, Any]]:
        return sorted(
            [r for r in self.sanction_repo.load_history() if r.get("batch_id") == batch_id],
            key=lambda r: r.get("batch_order") or 0,
        )

    def _batch_result(self, batch_id, status="success", message="已儲存檢舉名單"):
        records = self._batch_records(batch_id)
        pending = next((r for r in records if get_submission_state(r) != "submitted"), None)
        return {"status": status, "message": message, "batch_id": batch_id,
                "records": records, "record": pending or (records[0] if records else None),
                "evidence_url": next((r.get("url") for r in records if r.get("url")), "")}

    def _prepare_batch(self, data: dict[str, Any]) -> dict[str, Any]:
        raw = data.get("suspects")
        if not isinstance(raw, list) or not raw:
            return {"status": "error", "message": "請至少加入一名角色。"}
        names = []
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("suspect_id"), str):
                return {"status": "error", "message": "角色名單格式不正確。"}
            if item.get("note_override") is not None and not isinstance(item["note_override"], str):
                return {"status": "error", "message": "個別檢舉說明格式不正確。"}
            name = item["suspect_id"].strip()
            if not name or re.search(r"[\s,，]", name):
                return {"status": "error", "message": "請使用空白或逗號分隔每個角色 ID。"}
            if name not in [i["suspect_id"] for i in names]:
                names.append({**item, "suspect_id": name})

        batch_id = str(data.get("batch_id") or "")
        existing = self._batch_records(batch_id) if batch_id else []
        if batch_id and not existing:
            return {"status": "error", "message": "找不到這批檢舉紀錄。"}
        if not batch_id and data.get("record_id"):
            source = next((r for r in self.sanction_repo.load_history()
                           if r["record_id"] == data["record_id"]), None)
            if not source or source.get("batch_id") or get_submission_state(source) != "draft":
                return {"status": "error", "message": "這筆紀錄無法轉為新的檢舉名單。"}
        history = self.sanction_repo.load_history()
        existing_ids = {str(record.get("record_id") or "") for record in existing}
        source_record_id = str(data.get("record_id") or "").strip() if not batch_id else ""
        retained_count = sum(
            1
            for record in history
            if str(record.get("record_id") or "") not in existing_ids
            and str(record.get("record_id") or "") != source_record_id
        )
        if retained_count + len(names) > MAX_HISTORY_RECORDS:
            return {
                "status": "error",
                "message": f"檢舉紀錄最多保存 {MAX_HISTORY_RECORDS} 筆，請分批處理或先清理舊紀錄。",
            }

        # Once upload/submission starts, the durable list is authoritative.
        if existing and any(r.get("batch_phase") != "draft" for r in existing):
            return self._batch_result(batch_id)

        seed = existing[0] if existing else None
        saved = self._save_report_draft({**data, "suspect_id": names[0]["suspect_id"],
            "record_id": seed["record_id"] if seed else data.get("record_id")})
        if saved["status"] != "success":
            return saved
        seed = saved["record"]
        batch_id = batch_id or str(uuid.uuid4())
        by_name = {r["suspect_id"]: r for r in existing}
        map_value = str(data.get("map_name") or "").strip()
        records = []
        for order, item in enumerate(names):
            old = by_name.get(item["suspect_id"], {})
            override = item.get("note_override")
            records.append({
                **seed, "record_id": old.get("record_id") or (
                    seed["record_id"] if not existing and order == 0 else str(uuid.uuid4())),
                "time": old.get("time") or time.strftime("%Y-%m-%d %H:%M:%S"),
                "suspect_id": item["suspect_id"], "batch_id": batch_id, "batch_order": order,
                "batch_note": str(data.get("note") or ""), "note_override": override,
                "note": str(override if override is not None else data.get("note") or ""),
                "server": data.get("server_name") or data.get("server") or "雪吉拉",
                "map": map_value, "map_name": map_value,
                "submission_mode": data.get("submission_mode") or "automatic",
                "submission_state": "draft", "batch_phase": "draft", "status": "尚未送出",
            })
        with HISTORY_LOCK:
            history = self.sanction_repo.load_history()
            retained = [r for r in history if r.get("batch_id") != batch_id
                        and r["record_id"] != seed["record_id"]]
            self.sanction_repo.save_history(records + retained)
        return self._batch_result(batch_id)

    def save_report_batch(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._submission_lock.acquire(blocking=False):
            return {"status": "error", "message": "已有檢舉正在處理。"}
        try:
            return self._prepare_batch(data)
        finally:
            self._submission_lock.release()

    def _update_batch(self, batch_id, updates):
        with HISTORY_LOCK:
            records = self.sanction_repo.load_history()
            self.sanction_repo.save_history([
                {**r, **updates} if r.get("batch_id") == batch_id else r for r in records
            ])

    def _reset_pending_batch(self, batch_id: str) -> None:
        """Return records to an editable draft after a pre-submission failure."""

        for record in self._batch_records(batch_id):
            if get_submission_state(record) == "submitted":
                continue
            self.sanction_repo.update_history_entry(
                record["record_id"],
                {"batch_phase": "draft", "status": "尚未送出"},
            )

    def _publish_batch(self, batch_id, message, status="progress"):
        result = self._batch_result(batch_id)
        self._emit_event("SUBMISSION_STATUS", {
            "step": "batch", "status": status, "message": message,
            "batch_id": batch_id, "records": result["records"],
        })

    def submit_report_batch(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._submission_lock.acquire(blocking=False):
            return {"status": "error", "message": "已有檢舉正在處理。"}
        batch_id = ""
        try:
            prepared = self._prepare_batch(data)
            if prepared["status"] != "success":
                return prepared
            batch_id = prepared["batch_id"]
            self._active_batch_id = batch_id
            records = self._batch_records(batch_id)
            if any(r.get("batch_phase") in {"sending", "unknown"} for r in records):
                return self._batch_result(batch_id, "error", "有角色的送件結果待確認，請先確認完成或選擇重試。")
            if all(get_submission_state(r) == "submitted" for r in records):
                return self._batch_result(batch_id, message="這批檢舉已全部完成。")
            if not records[0].get("map"):
                return self._batch_result(batch_id, "error", "請填寫地圖名稱。")
            self._publish_batch(batch_id, "正在準備共用影片…")
            url = prepared.get("evidence_url") or ""
            first = records[0]
            common = {**data, "batch_id": batch_id, "file_path": first["media_path"],
                      "map_name": first["map"], "server": first["server"]}
            if not url:
                # Reuse upload adapters, but persist the shared URL before any official submission.
                uploaded = self._submit_report({**common, "_upload_only": True,
                    "suspect_id": first["suspect_id"], "note": first["note"],
                    "submission_mode": first["submission_mode"]})
                if uploaded["status"] != "success":
                    self._reset_pending_batch(batch_id)
                    self._publish_batch(batch_id, uploaded["message"], "error")
                    return self._batch_result(batch_id, "error", uploaded["message"])
                url = uploaded["evidence_url"]
            # Recover an upload interrupted between saving its first record and its siblings.
            source = next((r for r in self._batch_records(batch_id) if r.get("url")), None)
            if source is None:
                self._reset_pending_batch(batch_id)
                message = "共用影片連結尚未成功保存，請重新上傳後再試。"
                self._publish_batch(batch_id, message, "error")
                return self._batch_result(batch_id, "error", message)
            self._update_batch(batch_id, {"url": url,
                "evidence_provider": source.get("evidence_provider"),
                "remote_evidence_id": source.get("remote_evidence_id"),
                "remote_evidence_state": source.get("remote_evidence_state")})
            for record in self._batch_records(batch_id):
                if get_submission_state(record) != "submitted":
                    self.sanction_repo.update_history_entry(record["record_id"], {"batch_phase": "queued"})
            mode = first["submission_mode"]
            if mode == "manual":
                for record in self._batch_records(batch_id):
                    if get_submission_state(record) != "submitted":
                        self.sanction_repo.update_history_entry(record["record_id"], {
                            "submission_state": "awaiting_manual", "batch_phase": "manual",
                            "submission_mode": "manual", "status": "待手動檢舉"})
                return self._batch_result(batch_id, "manual_ready", "影片已上傳，請逐人填寫並確認完成。")
            for index, record in enumerate(self._batch_records(batch_id)):
                if get_submission_state(record) == "submitted":
                    continue
                self.sanction_repo.update_history_entry(record["record_id"],
                    {"batch_phase": "sending", "status": "結果待確認"})
                self._publish_batch(batch_id, f"正在檢舉 {record['suspect_id']}（{index + 1}/{len(records)}）")
                result = self._submit_report({**common, "evidence_url": url,
                    "record_id": record["record_id"], "suspect_id": record["suspect_id"],
                    "note": record["note"], "submission_mode": "automatic",
                    "evidence_provider": record.get("evidence_provider"),
                    "remote_evidence_id": record.get("remote_evidence_id")})
                if result["status"] != "success":
                    self.sanction_repo.update_history_entry(record["record_id"],
                        {"batch_phase": "unknown", "status": "結果待確認"})
                    self._publish_batch(batch_id, result["message"], "error")
                    return self._batch_result(batch_id, "error",
                        f"{record['suspect_id']} 送出未獲確認，已暫停。請確認結果後再繼續。")
                self.sanction_repo.update_history_entry(record["record_id"], {"batch_phase": "completed"})
                self._publish_batch(batch_id, f"已完成 {record['suspect_id']}（{index + 1}/{len(records)}）")
            self._cleanup_completed_batch(batch_id)
            return self._batch_result(batch_id, message="這批檢舉已全部完成。")
        except Exception:
            LOGGER.exception("Batch report processing interrupted")
            if batch_id:
                return self._batch_result(batch_id, "error", "處理中斷，已保留進度。請確認送件結果後繼續。")
            raise
        finally:
            self._active_batch_id = ""
            self._submission_lock.release()

    def resolve_report_result(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._submission_lock.acquire(blocking=False):
            return {"status": "error", "message": "請等待目前檢舉處理完成。"}
        try:
            record = next((r for r in self.sanction_repo.load_history()
                           if r["record_id"] == data.get("record_id")), None)
            if not record or not record.get("batch_id") or record.get("batch_phase") not in {"sending", "unknown"}:
                return {"status": "error", "message": "找不到待確認的紀錄。"}
            completed = data.get("completed") is True
            self.sanction_repo.update_history_entry(record["record_id"], {
                "batch_phase": "completed" if completed else "queued",
                "submission_state": "submitted" if completed else "draft",
                "status": "成功" if completed else "尚未送出",
            }, evaluate=completed)
            self._cleanup_completed_batch(record["batch_id"])
            self._publish_batch(record["batch_id"], "已更新送件結果。")
            return self._batch_result(record["batch_id"])
        finally:
            self._submission_lock.release()

    def _cleanup_completed_batch(self, batch_id):
        from maple_reporter.utils.config import is_owned_recording_path
        records = self._batch_records(batch_id)
        if not records or not all(get_submission_state(r) == "submitted" for r in records):
            return
        if not self.config.get("auto_delete_after_upload", False):
            return
        path = records[0].get("media_path")
        if path and is_owned_recording_path(path) and self._can_cleanup_shared_local(path):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError:
                return
            self._update_batch(
                batch_id,
                {
                    "media_path": "",
                    "local_evidence_cleaned_at": datetime.now(timezone.utc).isoformat(),
                },
            )

    def _can_cleanup_shared_local(self, path):
        if getattr(self, "sanction_repo", None) is None:
            return True
        return not any(
            r.get("media_path") and os.path.normcase(os.path.abspath(r["media_path"])) == os.path.normcase(os.path.abspath(path))
            and get_submission_state(r) != "submitted"
            for r in self.sanction_repo.load_history()
        )
