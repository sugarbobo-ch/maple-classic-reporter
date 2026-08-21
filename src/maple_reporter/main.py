import sys
import subprocess
import json
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QProgressDialog
from PySide6.QtCore import Qt
from maple_reporter.automation.playwright_runtime import (
    PlaywrightBrowserError,
    get_bundled_driver_path,
    get_frozen_root,
    is_frozen,
    resolve_chromium_executable,
)
from maple_reporter.gui.main_window import MainWindow
from maple_reporter.gui.playwright_error_dialog import show_playwright_error_dialog
from maple_reporter.update.updater import recover_interrupted_update
from maple_reporter.update.runtime import mark_post_update_success
from maple_reporter.utils.config import get_user_app_data_dir


def get_application_icon_path() -> Path:
    """Return the icon location for source runs and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "icon.png"
    return Path(__file__).resolve().parents[2] / "assets" / "icon.png"


def _playwright_install_command() -> list[str]:
    if is_frozen():
        frozen_root = get_frozen_root()
        node_exe = get_bundled_driver_path()
        cli_js = frozen_root / "playwright" / "driver" / "package" / "cli.js" if frozen_root else None
        if not node_exe or not cli_js or not node_exe.is_file() or not cli_js.is_file():
            missing = ", ".join(str(path) for path in (node_exe, cli_js) if path)
            raise PlaywrightBrowserError(
                "找不到內建的 Playwright driver。",
                technical_error=f"必要檔案不存在：{missing or '未找到 driver 路徑'}",
                driver_path=node_exe,
            )
        return [str(node_exe), str(cli_js), "install", "chromium"]
    return [sys.executable, "-m", "playwright", "install", "chromium"]


def _install_playwright_chromium(app: QApplication, previous_error: PlaywrightBrowserError) -> bool:
    """Try a user-cache install only when the bundled/cache browser is missing."""
    dialog = QProgressDialog(
        "找不到可用的 Chrome，正在嘗試下載 Playwright Chromium（約 400 MB）。\n"
        "下載完成後會自動重新檢查，請稍候…",
        None,
        0,
        0,
    )
    dialog.setWindowTitle("初始化 Playwright Chrome")
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setCancelButton(None)
    dialog.setMinimumWidth(520)
    dialog.show()
    app.processEvents()

    try:
        command = _playwright_install_command()
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = "\n".join(
            value.strip()
            for value in (completed.stdout, completed.stderr)
            if value and value.strip()
        )
        if completed.returncode != 0:
            raise PlaywrightBrowserError(
                "Playwright Chromium 下載失敗。",
                technical_error=(
                    f"首次檢查：\n{previous_error.details.as_text()}\n\n"
                    f"下載程式回傳碼：{completed.returncode}\n"
                    f"下載輸出：\n{output or '（沒有輸出）'}"
                ),
                executable_path=previous_error.details.executable_path,
                bundled_browser_dir=previous_error.details.bundled_browser_dir,
                driver_path=previous_error.details.driver_path,
            )
        resolve_chromium_executable()
        return True
    except PlaywrightBrowserError as error:
        dialog.close()
        show_playwright_error_dialog(None, error)
        return False
    except subprocess.TimeoutExpired as error:
        timeout_error = PlaywrightBrowserError.from_exception(
            "Playwright Chromium 下載逾時。",
            error,
            executable_path=previous_error.details.executable_path,
            bundled_browser_dir=previous_error.details.bundled_browser_dir,
            driver_path=previous_error.details.driver_path,
            extra_details=f"首次檢查：\n{previous_error.details.as_text()}",
        )
        dialog.close()
        show_playwright_error_dialog(None, timeout_error)
        return False
    except Exception as error:
        install_error = PlaywrightBrowserError.from_exception(
            "Playwright Chromium 初始化失敗。",
            error,
            executable_path=previous_error.details.executable_path,
            bundled_browser_dir=previous_error.details.bundled_browser_dir,
            driver_path=previous_error.details.driver_path,
            extra_details=f"首次檢查：\n{previous_error.details.as_text()}",
        )
        dialog.close()
        show_playwright_error_dialog(None, install_error)
        return False
    finally:
        dialog.close()


def _ensure_playwright_chromium(app: QApplication) -> bool:
    """
    Check the bundled/cache browser and use a user-cache install as fallback.
    """
    try:
        resolve_chromium_executable()
        return True
    except PlaywrightBrowserError as error:
        return _install_playwright_chromium(app, error)


def run_bundle_smoke_test() -> int:
    """Validate a frozen onedir bundle without opening the GUI or services."""
    if not is_frozen():
        print("Bundle smoke test requires a PyInstaller executable.", file=sys.stderr)
        return 2

    root = get_frozen_root()
    if root is None:
        print("PyInstaller resource root is unavailable.", file=sys.stderr)
        return 2

    required_files = {
        "React entrypoint": root / "web" / "dist" / "index.html",
        "application icon": root / "assets" / "icon.png",
        "PyInstaller icon": root / "assets" / "icon.ico",
        "Playwright driver": root / "playwright" / "driver" / "node.exe",
        "OAuth client": root / "google_oauth_client.json",
    }
    missing = [f"{label}: {path}" for label, path in required_files.items() if not path.is_file()]
    if missing:
        print("Bundle smoke test failed; missing files:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in missing), file=sys.stderr)
        return 1

    try:
        oauth_config = json.loads(required_files["OAuth client"].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Bundle smoke test failed; OAuth client is invalid: {error}", file=sys.stderr)
        return 1
    if not isinstance(oauth_config, dict) or not isinstance(oauth_config.get("installed"), dict):
        print("Bundle smoke test failed; OAuth client has no installed configuration.", file=sys.stderr)
        return 1

    try:
        chromium = resolve_chromium_executable()
    except Exception as error:
        print(f"Bundle smoke test failed; bundled Chromium is unavailable: {error}", file=sys.stderr)
        return 1
    if not chromium.is_file():
        print(f"Bundle smoke test failed; Chromium executable is missing: {chromium}", file=sys.stderr)
        return 1

    print(f"Bundle smoke test passed: {root}")
    print(f"Chromium: {chromium}")
    return 0


from maple_reporter.gui.webview_app import (
    enable_per_monitor_v2_dpi_awareness,
    run_webview_app,
    set_windows_app_user_model_id,
)


def main():
    if "--post-update" not in sys.argv:
        recover_interrupted_update(get_user_app_data_dir() / "updates")
    if "--smoke-test" in sys.argv:
        sys.exit(run_bundle_smoke_test())

    enable_per_monitor_v2_dpi_awareness()
    set_windows_app_user_model_id()
    if "--pyside" in sys.argv:
        app = QApplication(sys.argv)
        app.setApplicationName("MapleStory Classic Auto Reporter")
        icon = QIcon(str(get_application_icon_path()))
        app.setWindowIcon(icon)

        _ensure_playwright_chromium(app)

        window = MainWindow()
        window.setWindowIcon(icon)
        window.show()
        mark_post_update_success()

        sys.exit(app.exec())
    else:
        # Default: Run PyWebView + React GUI app
        run_webview_app()

if __name__ == "__main__":
    main()

