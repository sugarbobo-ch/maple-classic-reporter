"""Runtime helpers for the bundled Playwright Chromium browser."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLAYWRIGHT_DOWNLOAD_URL = "https://playwright.dev/python/docs/browsers"
PLAYWRIGHT_INSTALL_COMMAND = "playwright install chromium"
BUNDLED_BROWSER_DIRECTORY_NAME = "ms-playwright"


def _value_or_placeholder(value: str) -> str:
    return value if value else "（未提供）"


@dataclass(frozen=True)
class PlaywrightErrorDetails:
    """User-facing and diagnostic fields for a Playwright failure."""

    summary: str
    technical_error: str
    executable_path: str = ""
    bundled_browser_dir: str = ""
    driver_path: str = ""
    download_url: str = PLAYWRIGHT_DOWNLOAD_URL
    install_command: str = PLAYWRIGHT_INSTALL_COMMAND

    def as_text(self) -> str:
        """Return every diagnostic field in a copy-friendly format."""
        fields = (
            ("元件", "Playwright Chromium"),
            ("狀態", self.summary),
            ("技術錯誤", self.technical_error),
            ("瀏覽器執行檔", self.executable_path),
            ("內建瀏覽器目錄", self.bundled_browser_dir),
            ("Playwright driver", self.driver_path),
            ("下載網址", self.download_url),
            ("安裝指令", self.install_command),
        )
        return "\n\n".join(
            f"{label}：\n{_value_or_placeholder(value)}" for label, value in fields
        )


class PlaywrightBrowserError(RuntimeError):
    """A recoverable error caused by a missing or unusable Chromium binary."""

    def __init__(
        self,
        summary: str,
        *,
        technical_error: str,
        executable_path: Path | str | None = None,
        bundled_browser_dir: Path | str | None = None,
        driver_path: Path | str | None = None,
    ) -> None:
        self.details = PlaywrightErrorDetails(
            summary=summary,
            technical_error=technical_error,
            executable_path=str(executable_path or ""),
            bundled_browser_dir=str(bundled_browser_dir or ""),
            driver_path=str(driver_path or ""),
        )
        super().__init__(summary)

    @classmethod
    def from_exception(
        cls,
        summary: str,
        error: BaseException,
        *,
        executable_path: Path | str | None = None,
        bundled_browser_dir: Path | str | None = None,
        driver_path: Path | str | None = None,
        extra_details: str = "",
    ) -> "PlaywrightBrowserError":
        technical_error = f"{type(error).__name__}: {error}"
        if extra_details:
            technical_error = f"{technical_error}\n\n{extra_details}"
        return cls(
            summary,
            technical_error=technical_error,
            executable_path=executable_path,
            bundled_browser_dir=bundled_browser_dir,
            driver_path=driver_path,
        )


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_frozen_root() -> Path | None:
    """Return PyInstaller's extracted resource directory when frozen."""
    if not is_frozen():
        return None
    return Path(
        getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)
    )


def get_bundled_browser_dir() -> Path | None:
    root = get_frozen_root()
    return root / BUNDLED_BROWSER_DIRECTORY_NAME if root else None


def get_bundled_driver_path() -> Path | None:
    root = get_frozen_root()
    return root / "playwright" / "driver" / "node.exe" if root else None


def _bundled_chromium_candidates() -> Iterable[Path]:
    browser_dir = get_bundled_browser_dir()
    if not browser_dir or not browser_dir.is_dir():
        return ()
    return sorted(browser_dir.glob("chromium-*/chrome-win*/chrome.exe"))


def _default_driver_path() -> Path | None:
    try:
        import playwright

        return Path(inspect.getfile(playwright)).parent / "driver" / "node.exe"
    except Exception:
        return None


def resolve_chromium_executable() -> Path:
    """Find the bundled Chromium first, then a normal Playwright install."""
    bundled_browser_dir = get_bundled_browser_dir()
    driver_path = get_bundled_driver_path() or _default_driver_path()

    for candidate in _bundled_chromium_candidates():
        if candidate.is_file():
            return candidate

    cached_executable: Path | None = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            cached_executable = Path(playwright.chromium.executable_path)
    except Exception as error:
        raise PlaywrightBrowserError.from_exception(
            "無法初始化 Playwright Chromium。",
            error,
            bundled_browser_dir=bundled_browser_dir,
            driver_path=driver_path,
        ) from error

    if cached_executable.is_file():
        return cached_executable

    searched = [str(path) for path in _bundled_chromium_candidates()]
    if cached_executable:
        searched.append(str(cached_executable))
    search_text = "\n".join(f"- {path}" for path in searched) or "- （沒有找到可檢查的路徑）"
    error = FileNotFoundError(
        "找不到可用的 chrome.exe。\n已檢查：\n" + search_text
    )
    raise PlaywrightBrowserError.from_exception(
        "找不到可用的 Playwright Chromium。",
        error,
        executable_path=cached_executable,
        bundled_browser_dir=bundled_browser_dir,
        driver_path=driver_path,
    ) from error


def make_launch_error(executable_path: Path, error: BaseException) -> PlaywrightBrowserError:
    """Wrap a browser launch exception with enough context for support."""
    return PlaywrightBrowserError.from_exception(
        "Playwright Chromium 啟動失敗。",
        error,
        executable_path=executable_path,
        bundled_browser_dir=get_bundled_browser_dir(),
        driver_path=get_bundled_driver_path() or _default_driver_path(),
    )
