"""Google Drive, Discord, sanction sync, and system utility bridge mixin."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any
import webbrowser

from maple_reporter.reset import build_reset_helper_command

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


class IntegrationBridgeMixin:
    """Methods for external integrations (GDrive, Discord), sanction syncing, and OS utilities."""

    # --- Sanctions & History ---

    def start_sanction_sync(self, trigger: str = "manual") -> dict[str, Any]:
        """Start sanction synchronization worker."""
        trig = "startup" if trigger == "startup" else "manual"
        result = self.sanction_coordinator.start(trigger=trig)
        return result.to_dict()

    def get_sanction_sync_status(self) -> dict[str, Any]:
        """Return current sanction synchronization status."""
        return self.sanction_coordinator.get_status().to_dict()

    def get_history(self) -> list[dict[str, Any]]:
        """Return the latest history records."""
        records = self.sanction_repo.load_history()
        enriched: list[dict[str, Any]] = []
        for item in records:
            record = self.evidence_lifecycle.enrich_record(dict(item))
            media_path = str(record.get("media_path", "") or "")
            record["media_available"] = bool(media_path and os.path.isfile(media_path))
            enriched.append(record)
        return enriched

    def cleanup_history_evidence(
        self,
        record_ids: list[str],
        targets: list[str],
    ) -> dict[str, Any]:
        """Clean selected evidence while retaining the history records."""
        return self.evidence_lifecycle.cleanup_records(
            record_ids,
            targets,
        )

    def delete_history_entries(
        self,
        record_ids: list[str],
        cleanup_targets: list[str] | None = None,
    ) -> dict[str, Any]:
        """Delete selected history records after optional evidence cleanup."""
        return self.evidence_lifecycle.delete_records(
            record_ids,
            cleanup_targets or [],
        )

    def rebuild_sanction_cache_for_development(self) -> bool:
        """Reset sanction cache if developer mode is enabled."""
        if not self.config.get("dev_mode", False):
            return False
        return self.sanction_coordinator.rebuild_cache_for_development()

    def clear_history(self) -> bool:
        """Delete all locally persisted report history entries."""
        try:
            self.sanction_repo.clear_history()
            return True
        except OSError as err:
            LOGGER.warning("Failed to clear report history: %s", err)
            return False

    # --- Google Drive & Discord Integration ---

    def check_gdrive_auth(self) -> bool:
        """Check if Google Drive is authorized."""
        return self.drive_mgr.is_authenticated()

    def authenticate_gdrive(self) -> dict[str, Any]:
        """Trigger interactive Google Drive OAuth login in default browser."""
        ok, msg = self.drive_mgr.authenticate_interactive()
        is_auth = self.drive_mgr.is_authenticated()
        return {"success": ok, "message": msg, "is_authenticated": is_auth}

    def disconnect_gdrive(self) -> dict[str, Any]:
        """Revoke Google authorization and remove credentials from this device."""

        return self.drive_mgr.disconnect(revoke=True)

    def get_gdrive_folder_url(self, folder_name: str | None = None) -> str:
        """Return URL to the user's GDrive reports folder."""
        name = folder_name or self.config.get("gdrive_folder_name", "MapleClassic_Reports")
        if self.drive_mgr.is_authenticated():
            url = self.drive_mgr.get_folder_url(name)
            if url:
                return url
        return "https://drive.google.com/drive/my-drive"

    def test_discord_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Test sending a test message to the Discord Webhook URL."""
        if not webhook_url:
            return {"success": False, "message": "請先輸入 Discord 頻道連結"}
        mod = _bridge_mod()
        if not mod.is_valid_discord_webhook_url(webhook_url):
            return {"success": False, "message": "請輸入有效的 Discord HTTPS 頻道連結"}
        try:
            import requests

            res = requests.post(
                webhook_url,
                json={"content": " Maple Classic Reporter: Discord 頻道連結測試成功！"},
                timeout=8,
            )
            if res.status_code in (200, 204):
                return {"success": True, "message": "Discord 頻道連結測試成功！"}
            return {"success": False, "message": f"Discord 頻道連結回傳錯誤碼: {res.status_code}"}
        except Exception as err:
            return {"success": False, "message": f"連線失敗: {str(err)}"}

    # --- System & Utilities ---

    def open_external_url(self, url: str) -> bool:
        """Open URL in system default browser."""
        from maple_reporter.utils.urls import is_safe_https_url

        if not is_safe_https_url(url):
            LOGGER.warning("Blocked unsafe external URL: %r", url)
            return False
        return bool(_bridge_mod().webbrowser.open(url))

    def open_file_location(self, file_path: str) -> None:
        """Open File Explorer highlighting the specified file."""
        if file_path and os.path.exists(file_path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(file_path)])

    def open_media_file(self, file_path: str) -> None:
        """Open image or video in system default viewer."""
        if file_path and os.path.exists(file_path):
            os.startfile(os.path.normpath(file_path))

    def open_app_data_folder(self) -> None:
        """Open the local AppData folder in Explorer."""
        folder = _bridge_mod().get_user_app_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["explorer", str(folder)])

    def open_log_file(self) -> bool:
        """Open the reporter.log file in default text editor."""
        log_file = _bridge_mod().get_user_app_data_dir() / "logs" / "reporter.log"
        if not log_file.exists():
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text("", encoding="utf-8")
        try:
            if os.name == "nt":
                os.startfile(str(log_file))
            else:
                subprocess.Popen(["notepad", str(log_file)])
            return True
        except Exception as err:
            LOGGER.warning("Failed to open log file: %s", err)
            return False

    def open_log_folder(self) -> None:
        """Open the logs folder in File Explorer."""
        folder = _bridge_mod().get_user_app_data_dir() / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["explorer", str(folder)])

    def reset_all_user_data(self) -> dict[str, Any]:
        """Schedule a safe out-of-process reset after this application exits."""

        if getattr(self, "_recording_active", False):
            return {
                "success": False,
                "accepted": False,
                "message": "錄影仍在進行，請先停止錄影再刪除資料。",
            }
        if getattr(self, "_replay_state", "idle") not in {"idle", "stopped"}:
            return {
                "success": False,
                "accepted": False,
                "message": "循環錄影仍在進行，請先停止後再刪除資料。",
            }
        submission_lock = getattr(self, "_submission_lock", None)
        if submission_lock is not None and submission_lock.locked():
            return {
                "success": False,
                "accepted": False,
                "message": "檢舉資料仍在處理，請完成後再刪除資料。",
            }

        update_service = getattr(self, "update_service", None)
        update_state = update_service.status().get("state") if update_service else "idle"
        if update_state in {"checking", "downloading", "waiting_for_idle", "applying"}:
            return {
                "success": False,
                "accepted": False,
                "message": "應用程式更新仍在進行，請完成或取消更新後再刪除資料。",
            }

        try:
            command = build_reset_helper_command(os.getpid())
            subprocess.Popen(
                command,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
            )
        except (OSError, ValueError) as error:
            LOGGER.warning("Failed to start user-data reset helper (%s)", type(error).__name__)
            return {
                "success": False,
                "accepted": False,
                "message": "無法啟動資料清除程序，請關閉程式後再試。",
            }

        def close_window() -> None:
            try:
                if getattr(self, "_window", None):
                    self._window.destroy()
            except Exception as error:
                LOGGER.warning("Failed to close app for user-data reset (%s)", type(error).__name__)

        threading.Timer(0.5, close_window).start()
        return {
            "success": True,
            "accepted": True,
            "message": "程式即將關閉並刪除所有本機資料。",
        }
