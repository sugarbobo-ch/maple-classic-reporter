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
from maple_reporter.evidence.lifecycle import parse_drive_file_id
from maple_reporter.sanctions.models import (
    SUBMISSION_AWAITING_MANUAL,
    SUBMISSION_DRAFT,
    SUBMISSION_SUBMITTED,
    SUBMISSION_STATES,
    get_submission_state,
    normalize_submission_state,
)

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
            "submission_state": SUBMISSION_DRAFT,
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
        submission_state: str,
    ) -> dict[str, Any] | None:
        normalized_state = normalize_submission_state(submission_state)
        if submission_state not in SUBMISSION_STATES:
            raise ValueError(f"Unsupported submission state: {submission_state}")
        submitted = normalized_state == SUBMISSION_SUBMITTED
        provider = str(form_data.get("evidence_provider") or "").strip().lower()
        if not provider:
            destination = str(form_data.get("upload_destination") or "").strip().lower()
            provider = destination if destination in {"gdrive", "discord"} else "none"
        remote_id = str(form_data.get("remote_evidence_id") or "").strip()
        if provider == "gdrive" and not remote_id:
            remote_id = parse_drive_file_id(evidence_url)
        payload = {
            "suspect_id": form_data.get("suspect_id", ""),
            "server": form_data.get("server_name") or form_data.get("server", "雪吉拉"),
            "map": form_data.get("map_name", ""),
            "map_name": form_data.get("map_name", ""),
            "url": evidence_url,
            "status": status,
            "note": form_data.get("note", "") if note is None else note,
            "submission_state": normalized_state,
            "submission_mode": form_data.get("submission_mode", "automatic"),
            "media_path": file_path,
            "media_type": form_data.get("media_type", ""),
            "evidence_provider": provider,
            "remote_evidence_id": remote_id,
            "remote_evidence_state": "available" if provider == "gdrive" and remote_id else "",
        }
        record_id = str(form_data.get("record_id", "") or "").strip()
        repo = getattr(self, "sanction_repo", None)
        if record_id:
            if repo is None:
                return None
            return repo.update_history_entry(
                record_id, payload, evaluate=submitted
            )
        if normalized_state == SUBMISSION_DRAFT:
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
        if dest == "none":
            message = "目前是只試用模式，不會上傳證據。請先在設定中選擇 Google Drive 或 Discord。"
            self._emit_submission_status("uploading", message, "error")
            return {"status": "error", "message": message}
        if form_data.get("record_id"):
            self._persist_submission_history(
                form_data,
                file_path=file_path,
                evidence_url=evidence_url,
                status="尚未送出",
                submission_state=SUBMISSION_DRAFT,
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
                form_data["evidence_provider"] = "gdrive"
                form_data["remote_evidence_id"] = parse_drive_file_id(evidence_url)
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
                form_data["evidence_provider"] = "discord"
                form_data["remote_evidence_id"] = ""

        submission_mode = str(
            form_data.get("submission_mode")
            or self.config.get("report_submission_mode", "automatic")
        ).strip().lower()
        if submission_mode not in {"manual", "automatic"}:
            submission_mode = "automatic"
        form_data["submission_mode"] = submission_mode

        if submission_mode == "manual":
            record = self._persist_submission_history(
                form_data,
                file_path=file_path,
                evidence_url=evidence_url,
                status="待手動檢舉",
                submission_state=SUBMISSION_AWAITING_MANUAL,
            )
            if record is None:
                message = "無法建立待手動檢舉紀錄，請稍後再試。"
                self._emit_submission_status("uploading", message, "error")
                return {"status": "error", "message": message}
            message = "證據已上傳，請依序填寫官方檢舉表單。"
            self._emit_submission_status("manual_ready", message, "success")
            return {
                "status": "manual_ready",
                "message": message,
                "evidence_url": evidence_url,
                "record_id": record.get("record_id", ""),
                "record": record,
            }

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
                submission_state=SUBMISSION_SUBMITTED,
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
            submission_state=SUBMISSION_SUBMITTED if ok else SUBMISSION_DRAFT,
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

    def confirm_manual_report(self, record_id: str) -> dict[str, Any]:
        """Confirm a user-completed manual report and apply safe evidence cleanup."""
        normalized_id = str(record_id or "").strip()
        if not normalized_id:
            return {"status": "error", "message": "找不到待確認的檢舉紀錄。"}

        record = next(
            (
                item
                for item in self.sanction_repo.load_history()
                if item.get("record_id") == normalized_id
            ),
            None,
        )
        if record is None or get_submission_state(record) != SUBMISSION_AWAITING_MANUAL:
            return {"status": "error", "message": "這筆紀錄已完成或無法繼續確認。"}

        updated = self.sanction_repo.update_history_entry(
            normalized_id,
            {
                "submission_state": SUBMISSION_SUBMITTED,
                "submission_mode": "manual",
                "status": "成功",
            },
            evaluate=True,
        )
        if updated is None:
            return {"status": "error", "message": "無法更新檢舉紀錄，請稍後再試。"}

        deleted = False
        file_path = str(updated.get("media_path") or "")
        if bool(self.config.get("auto_delete_after_upload", False)):
            mod = _bridge_mod()
            if file_path and mod.is_owned_recording_path(file_path):
                try:
                    os.remove(file_path)
                    deleted = True
                    LOGGER.info("Auto-deleted confirmed manual evidence: %s", file_path)
                except FileNotFoundError:
                    pass
                except OSError as err:
                    LOGGER.warning("Failed to auto-delete manual evidence: %s", err)

        return {
            "status": "success",
            "message": "已記錄為完成檢舉。",
            "record": updated,
            "deleted": deleted,
        }
