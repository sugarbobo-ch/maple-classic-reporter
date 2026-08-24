"""Safe helper for deleting per-user application data after the app exits."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import sys
import time

from maple_reporter.utils.config import get_user_app_data_dir


RESET_ARGUMENT = "--reset-user-data-after-pid"
RESET_DIRECTORY_NAME = "MapleClassicReporter"


def build_reset_helper_command(pid: int) -> list[str]:
    """Build the detached command that will delete data after ``pid`` exits."""

    if getattr(sys, "frozen", False):
        return [sys.executable, RESET_ARGUMENT, str(pid)]
    return [sys.executable, "-m", "maple_reporter.main", RESET_ARGUMENT, str(pid)]


def validate_user_data_root(
    target: Path,
    *,
    local_app_data_root: Path | None = None,
) -> Path:
    """Return a validated app-data path and reject broad or redirected targets."""

    candidate = Path(target)
    if not str(candidate).strip() or candidate.is_symlink():
        raise ValueError("使用者資料路徑無效。")

    local_root = local_app_data_root
    if local_root is None:
        raw_root = os.environ.get("LOCALAPPDATA", "").strip()
        if not raw_root:
            raise ValueError("找不到 Windows 使用者資料目錄。")
        local_root = Path(raw_root)

    resolved_root = Path(local_root).resolve(strict=False)
    resolved_target = candidate.resolve(strict=False)
    expected = resolved_root / RESET_DIRECTORY_NAME
    if (
        candidate.name != RESET_DIRECTORY_NAME
        or candidate.parent.resolve(strict=False) != resolved_root
        or resolved_target != expected
        or resolved_target.parent != resolved_root
    ):
        raise ValueError("拒絕刪除非本程式擁有的資料目錄。")
    if resolved_target == Path(resolved_target.anchor) or resolved_target == resolved_root:
        raise ValueError("拒絕刪除過大的資料範圍。")
    return resolved_target


def wait_for_process_exit(pid: int, *, timeout: float = 30.0) -> bool:
    """Wait for a process without terminating it."""

    if pid <= 0 or pid == os.getpid():
        return False
    if os.name == "nt":
        synchronize = 0x00100000
        wait_object_0 = 0
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return True
        try:
            result = kernel32.WaitForSingleObject(handle, max(0, int(timeout * 1000)))
            return result == wait_object_0
        finally:
            kernel32.CloseHandle(handle)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.1)
    return False


def delete_user_data(
    target: Path,
    *,
    local_app_data_root: Path | None = None,
    attempts: int = 5,
    retry_delay: float = 0.2,
) -> None:
    """Delete the exact application-owned user-data directory with short retries."""

    validated = validate_user_data_root(
        target,
        local_app_data_root=local_app_data_root,
    )
    if not validated.exists():
        return

    last_error: OSError | None = None
    for attempt in range(max(1, attempts)):
        try:
            shutil.rmtree(validated)
            return
        except OSError as error:
            last_error = error
            if attempt + 1 < max(1, attempts):
                time.sleep(retry_delay * (attempt + 1))
    if last_error is not None:
        raise last_error


def show_reset_error(message: str) -> None:
    """Show a native failure message because the React window is already closed."""

    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "無法刪除所有本機資料",
            0x10,
        )
        return
    print(message, file=sys.stderr)


def run_reset_helper(pid: int) -> int:
    """Wait for the main process, delete its user data, and exit without relaunching."""

    target = get_user_app_data_dir()
    if not wait_for_process_exit(pid):
        show_reset_error("程式尚未完全關閉，因此沒有刪除任何資料。請重新開機後手動刪除：\n" + str(target))
        return 1
    try:
        delete_user_data(target)
    except (OSError, ValueError) as error:
        show_reset_error(
            "部分本機資料無法刪除。請重新開機後手動刪除：\n"
            f"{target}\n\n錯誤類型：{type(error).__name__}"
        )
        return 1
    return 0


__all__ = [
    "RESET_ARGUMENT",
    "build_reset_helper_command",
    "delete_user_data",
    "run_reset_helper",
    "validate_user_data_root",
    "wait_for_process_exit",
]
