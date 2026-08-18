"""PyWebView Application Launcher for Maple Classic Reporter."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import webview
from maple_reporter import __version__
from maple_reporter.gui.native_window import (
    _window_handle,
    install_native_resize_support,
    set_window_identity,
)
from maple_reporter.gui.pywebview_bridge import PyWebViewBridge
from maple_reporter.utils.config import get_user_app_data_dir, load_config

LOGGER = logging.getLogger(__name__)
APP_TITLE = f"新楓之谷：經典版《自動外掛檢舉工具》｜v{__version__}"
APP_USER_MODEL_ID = "MapleClassicReporter"
DEFAULT_WINDOW_SIZE = (1040, 860)
MIN_WINDOW_SIZE = (880, 620)


def is_dev_server_running(host: str = "127.0.0.1", port: int = 5173) -> bool:
    """Quickly check if Vite dev server is running on localhost:5173 (<0.1s)."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.1):
            return True
    except OSError:
        return False


def get_web_index_path() -> str:
    """Resolve local path or URL to index.html for PyWebView."""
    # Check if dev server override is active
    if os.environ.get("MAPLE_REPORTER_DEV") == "1":
        return "http://localhost:5173"

    # PyInstaller frozen path
    if getattr(sys, "frozen", False):
        bundle_dist = Path(sys._MEIPASS) / "web" / "dist" / "index.html"
        if bundle_dist.is_file():
            return bundle_dist.as_uri()

    # If Vite dev server is actively running during development, connect for HMR
    if is_dev_server_running():
        return "http://localhost:5173"

    # Source checkout path
    repo_root = Path(__file__).resolve().parents[3]
    local_dist = repo_root / "web" / "dist" / "index.html"
    if local_dist.is_file():
        return local_dist.as_uri()

    # Fallback to dev server
    return "http://localhost:5173"


def get_webview_icon_path() -> str | None:
    """Resolve the project's Windows icon for the native PyWebView window."""
    if getattr(sys, "frozen", False):
        icon_path = Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icon.ico"
    else:
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.ico"

    return str(icon_path) if icon_path.is_file() else None


def set_windows_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """Give Windows a stable taskbar identity instead of grouping as Python."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
        shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        return shell32.SetCurrentProcessExplicitAppUserModelID(app_id) == 0
    except (AttributeError, OSError, TypeError, ValueError):
        LOGGER.debug("Failed to set Windows AppUserModelID", exc_info=True)
        return False


def enable_per_monitor_v2_dpi_awareness() -> bool:
    """Explicitly enable Per-Monitor V2 DPI awareness for the Windows process."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return True
        # Fallback: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = -3
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-3)):
            return True
    except Exception:
        pass
    return False


def run_webview_app() -> None:
    """Launch the PyWebView window with React frontend UI."""
    enable_per_monitor_v2_dpi_awareness()
    set_windows_app_user_model_id()

    cfg = load_config()
    is_dev = bool(cfg.get("dev_mode", False)) or os.environ.get("MAPLE_REPORTER_DEBUG") == "1"

    # Setup file and stdout logging
    log_dir = get_user_app_data_dir() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "reporter.log"
        logging.basicConfig(
            level=logging.DEBUG if is_dev else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(str(log_file), encoding="utf-8", mode="a"),
                logging.StreamHandler(sys.stdout),
            ],
            force=True,
        )
    except Exception as err:
        logging.basicConfig(
            level=logging.DEBUG if is_dev else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,
        )
        LOGGER.warning("Could not initialize file logger: %s", err)

    bridge = PyWebViewBridge()

    url = get_web_index_path()
    LOGGER.info("Starting PyWebView GUI loading from: %s (dev_mode=%s)", url, is_dev)

    window = webview.create_window(
        title=APP_TITLE,
        url=url,
        js_api=bridge,
        width=DEFAULT_WINDOW_SIZE[0],
        height=DEFAULT_WINDOW_SIZE[1],
        min_size=MIN_WINDOW_SIZE,
        background_color="#F9F0E7",
        resizable=True,
        frameless=True,
        easy_drag=False,
    )

    def on_window_ready() -> None:
        hwnd = _window_handle(window)
        if not install_native_resize_support(window):
            LOGGER.warning("Native window resize support could not be installed")
        if not set_window_identity(hwnd or 0, APP_TITLE, get_webview_icon_path()):
            LOGGER.debug("Native window identity could not be applied")

    window.events.shown += on_window_ready
    window.events.loaded += on_window_ready
    window.events.maximized += bridge.handle_window_maximized
    window.events.restored += bridge.handle_window_restored
    bridge.set_window(window)
    window.events.closed += bridge.shutdown
    webview.start(
        debug=is_dev,
        icon=get_webview_icon_path(),
    )


__all__ = [
    "APP_TITLE",
    "APP_USER_MODEL_ID",
    "DEFAULT_WINDOW_SIZE",
    "MIN_WINDOW_SIZE",
    "get_web_index_path",
    "get_webview_icon_path",
    "set_windows_app_user_model_id",
    "run_webview_app",
]
