"""Report form submission pipeline, upload dispatcher and guard."""

from __future__ import annotations

from functools import wraps
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any
import uuid

from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


def _submission_guard(method):
    """Reject overlapping submissions before they can upload duplicate evidence."""

    @wraps(method)
    def guarded(self, form_data):
        if not self._submission_lock.acquire(blocking=False):
            message = "已有檢舉正在送出，請稍候完成後再試。"
            self._emit_submission_status("busy", message, "error")
            return {"status": "error", "message": message}
        try:
            return method(self, form_data)
        finally:
            self._submission_lock.release()

    return guarded


class SubmissionBridgeMixin:
    """Methods for uploading evidence and submitting official reports via Playwright or dev simulation."""

    def save_report_draft(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Persist evidence and form values without uploading or submitting them."""
        mod = _bridge_mod()
        raw_path = form_data.get("file_path") or form_data.get("media_path") or ""
        source_path = Path(os.fspath(raw_path)).expanduser() if raw_path else None
        if source_path is None or not source_path.is_file():
            return {
                "status": "error",
                "message": "找不到可儲存的證據檔案，請等待檔案建立完成後再試。",
            }

        try:
            if mod.is_owned_recording_path(source_path):
                stored_path = source_path.resolve()
            else:
                recordings_dir = mod.get_recordings_dir()
                suffix = source_path.suffix.lower()
                target_name = (
                    f"maple_evidence_draft_{time.time_ns()}_{uuid.uuid4().hex[:8]}{suffix}"
                )
                stored_path = recordings_dir / target_name
                shutil.copy2(source_path, stored_path)
        except OSError as error:
            LOGGER.warning("Failed to preserve draft evidence: %s", error)
            return {"status": "error", "message": "儲存證據檔案失敗，請確認磁碟空間後重試。"}

        media_type = form_data.get("media_type")
        if media_type not in {"video", "image"}:
            media_type = (
                "video"
                if stored_path.suffix.lower() in {".mp4", ".mkv", ".avi", ".mov"}
                else "image"
            )
        payload = {
            "suspect_id": str(form_data.get("suspect_id", "") or "").strip(),
            "server": str(form_data.get("server_name") or form_data.get("server") or ""),
            "map": str(form_data.get("map_name", "") or "").strip(),
            "map_name": str(form_data.get("map_name", "") or "").strip(),
            "url": "",
            "status": "尚未送出",
            "note": str(form_data.get("note", "") or "").strip(),
            "submission_state": "draft",
            "media_path": str(stored_path),
            "media_type": media_type,
            "ban_status": "pending",
        }
        record_id = str(form_data.get("record_id", "") or "").strip()
        if record_id:
            record = self.sanction_repo.update_history_entry(record_id, payload)
            if record is None:
                return {"status": "error", "message": "找不到要更新的未送出紀錄。"}
        else:
            record = self.sanction_repo.add_history_entry(
                {"time": time.strftime("%Y-%m-%d %H:%M:%S"), **payload}
            )
        return {
            "status": "success",
            "message": "已儲存至回報紀錄",
            "record": record,
        }

    def _persist_submission_history(
        self,
        form_data: dict[str, Any],
        *,
        file_path: str,
        evidence_url: str,
        status: str,
        note: str | None = None,
        submitted: bool,
    ) -> dict[str, Any] | None:
        payload = {
            "suspect_id": form_data.get("suspect_id", ""),
            "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
            "map": form_data.get("map_name", ""),
            "map_name": form_data.get("map_name", ""),
            "url": evidence_url,
            "status": status,
            "note": form_data.get("note", "") if note is None else note,
            "submission_state": "submitted" if submitted else "draft",
            "media_path": file_path,
            "media_type": form_data.get("media_type", ""),
        }
        record_id = str(form_data.get("record_id", "") or "").strip()
        repo = getattr(self, "sanction_repo", None)
        if record_id:
            if repo is None:
                return None
            return repo.update_history_entry(
                record_id, payload, evaluate=submitted
            )
        if not submitted:
            return None
        entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), **payload}
        if repo is not None:
            return repo.add_history_entry(entry)
        _bridge_mod().add_history_entry(entry)
        return entry

    @_submission_guard
    def submit_report(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Upload evidence to GDrive/Discord and submit report via Playwright."""
        mod = _bridge_mod()
        LOGGER.info("PyWebViewBridge: Submitting report form: %s", form_data)
        raw_file_path = form_data.get("file_path", "")
        file_path = (
            os.fspath(raw_file_path)
            if isinstance(raw_file_path, os.PathLike)
            else raw_file_path
            if isinstance(raw_file_path, str)
            else ""
        )
        dest = form_data.get("upload_destination") or self.config.get("upload_destination", "gdrive")
        evidence_url = form_data.get("evidence_url", "")
        if form_data.get("record_id"):
            self._persist_submission_history(
                form_data,
                file_path=file_path,
                evidence_url=evidence_url,
                status="尚未送出",
                submitted=False,
            )

        # 1. Upload evidence if URL not yet provided
        if not evidence_url:
            if not file_path:
                message = "找不到檢舉證據檔案，請重新選取或錄影後再試。"
                self._emit_submission_status("uploading", message, "error")
                return {"status": "error", "message": message}
            if not os.path.isfile(file_path):
                message = "檢舉證據檔案不存在或無法讀取，請重新選取後再試。"
                self._emit_submission_status("uploading", message, "error")
                return {"status": "error", "message": message}

            self._emit_submission_status("uploading", "正在上傳檢舉證據檔案...")
            if dest == "gdrive":
                folder_name = self.config.get("gdrive_folder_name", "MapleClassic_Reports")
                ok, res_url = self.drive_mgr.upload_file_and_make_public(file_path, folder_name)
                if not ok:
                    message = f"Google Drive 上傳失敗: {res_url}"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                evidence_url = res_url
            else:
                webhook_url = self.config.get("discord_webhook_url", "")
                if not webhook_url:
                    message = "尚未設定 Discord 頻道連結"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                if not mod.is_valid_discord_webhook_url(webhook_url):
                    message = "請先設定有效的 Discord 頻道連結網址"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                desc = f"檢舉證據 - 玩家: {form_data.get('suspect_id')}, 地圖: {form_data.get('map_name')}"
                ok, res_msg = mod.upload_evidence_to_discord(webhook_url, file_path, desc)
                if not ok:
                    message = f"Discord 上傳失敗: {res_msg}"
                    self._emit_submission_status("uploading", message, "error")
                    return {"status": "error", "message": message}
                evidence_url = res_msg

        # 2. Automated form submission via Playwright (or Dev Mode Dry-Run)
        dev_mode = form_data.get("dev_mode", self.config.get("dev_mode", False))
        if dev_mode:
            LOGGER.info("PyWebViewBridge: Developer mode enabled. Skipping actual Gamania submission.")
            self._emit_submission_status("dev_mode", "開發者模式：已略過實際提交")
            report_url = "https://forms.gamania.com/s/eLGg4"
            try:
                self.open_external_url(report_url)
            except Exception as e:
                LOGGER.warning("Could not open external url: %s", e)

            self._persist_submission_history(
                form_data,
                file_path=file_path,
                evidence_url=evidence_url,
                status="模擬成功",
                note=f"[開發者模式] {form_data.get('note', '')}".strip(),
                submitted=True,
            )

            success_message = "開發者模式：已模擬檢舉成功（未實際送出），已在系統瀏覽器開啟檢舉頁面"
            self._emit_submission_status("completed", success_message, "success")
            return {
                "status": "success",
                "message": success_message,
                "evidence_url": evidence_url,
                "dev_mode": True,
            }

        self._emit_submission_status("filling", "正在自動填寫並送出官方檢舉表單...")
        headless_submit = form_data.get(
            "form_submit_headless",
            self.config.get("form_submit_headless", True),
        )
        if headless_submit is None:
            headless_submit = True
        try:
            ok, msg = mod.submit_gamania_report(
                suspect_id=form_data.get("suspect_id", ""),
                server_name=form_data.get("server_name") or form_data.get("server", "雪吉拉"),
                map_name=form_data.get("map_name", ""),
                note=form_data.get("note", "自動打怪/外掛行為"),
                evidence_url=evidence_url,
                headless=bool(headless_submit),
            )
        except PlaywrightBrowserError as err:
            LOGGER.warning("Playwright submission error: %s", err)
            message = f"自動填寫表單錯誤: {err.details.summary}"
            self._emit_submission_status("filling", message, "error")
            return {"status": "error", "message": message}
        except Exception as err:
            LOGGER.error("Form filler unhandled error: %s", err)
            message = f"表單送出異常: {str(err)}"
            self._emit_submission_status("filling", message, "error")
            return {"status": "error", "message": message}

        # 3. Persist successful reports or keep the original draft available for retry.
        self._persist_submission_history(
            form_data,
            file_path=file_path,
            evidence_url=evidence_url,
            status="成功" if ok else "尚未送出",
            submitted=bool(ok),
        )

        # 4. Auto-delete local recording if enabled
        if ok and bool(self.config.get("auto_delete_after_upload", False)):
            if file_path and mod.is_owned_recording_path(file_path):
                try:
                    os.remove(file_path)
                    LOGGER.info("Auto-deleted confirmed evidence: %s", file_path)
                except OSError as err:
                    LOGGER.warning("Failed to auto-delete file: %s", err)

        self._emit_submission_status(
            "completed" if ok else "failed",
            msg,
            "success" if ok else "error",
        )
        return {
            "status": "success" if ok else "error",
            "message": msg,
            "evidence_url": evidence_url,
        }
