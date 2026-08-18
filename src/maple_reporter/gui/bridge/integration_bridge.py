"""Google Drive, Discord, sanction sync, and system utility bridge mixin."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any
import webbrowser

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
        return self.sanction_repo.load_history()

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
            return {"success": False, "message": "請先輸入 Webhook URL"}
        mod = _bridge_mod()
        if not mod.is_valid_discord_webhook_url(webhook_url):
            return {"success": False, "message": "請輸入有效的 Discord HTTPS Webhook URL"}
        try:
            import requests

            res = requests.post(
                webhook_url,
                json={"content": " Maple Classic Reporter: Webhook 連線測試成功！"},
                timeout=8,
            )
            if res.status_code in (200, 204):
                return {"success": True, "message": "Discord Webhook 測試連線成功！"}
            return {"success": False, "message": f"Webhook 回傳錯誤碼: {res.status_code}"}
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
