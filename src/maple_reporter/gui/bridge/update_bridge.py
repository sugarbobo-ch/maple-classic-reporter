"""PyWebView methods for the portable application updater."""

from __future__ import annotations

from typing import Any


class UpdateBridgeMixin:
    """Expose update discovery, download and restart actions to React."""

    def get_update_status(self) -> dict[str, Any]:
        return self.update_service.status()

    def check_for_updates(self, force: bool = False) -> bool:
        return self.update_service.start_check(force=bool(force))

    def start_update_download(self) -> bool:
        return self.update_service.start_download()

    def cancel_update_download(self) -> bool:
        return self.update_service.cancel_download()

    def restart_and_apply_update(self) -> bool:
        return self.update_service.restart_and_apply()

    def start_update_check(self) -> bool:
        """Start the non-blocking startup check after the window is attached."""

        return self.update_service.start_check(force=False)
