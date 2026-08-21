"""Runtime hooks used by the main app during a post-update launch."""

from __future__ import annotations

import sys
from pathlib import Path

from maple_reporter.utils.config import get_user_app_data_dir


def update_token_from_argv(argv: list[str] | None = None) -> str | None:
    for value in argv or sys.argv:
        if value.startswith("--update-token="):
            token = value.split("=", 1)[1].strip()
            return token or None
    return None


def mark_post_update_success(argv: list[str] | None = None) -> bool:
    token = update_token_from_argv(argv)
    if not token:
        return False
    update_dir = get_user_app_data_dir() / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    marker = update_dir / f"success-{token}.json"
    marker.write_text('{"ok": true}\n', encoding="utf-8")
    return True


__all__ = ["mark_post_update_success", "update_token_from_argv"]
