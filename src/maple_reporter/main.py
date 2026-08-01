import sys
import subprocess
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PySide6.QtCore import Qt
from maple_reporter.gui.main_window import MainWindow


def get_application_icon_path() -> Path:
    """Return the icon location for source runs and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "icon.png"
    return Path(__file__).resolve().parents[2] / "assets" / "icon.png"


def _ensure_playwright_chromium(app: QApplication) -> None:
    """
    Check whether Playwright's Chromium browser is available.
    If not (common in PyInstaller builds), run ``playwright install chromium``
    automatically so the form-filler works on first launch.

    In frozen (EXE) builds, the playwright ``driver/`` directory (node.exe +
    cli.js) is bundled inside ``_MEIPASS``. We use that driver to install the
    Chromium binary into the user's AppData on first run.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = p.chromium.executable_path
            if Path(exe).exists():
                return  # Already installed, nothing to do.
    except Exception:
        pass  # Not installed or path lookup failed — fall through to install.

    # Show a modal progress dialog while downloading.
    dlg = QProgressDialog(
        "首次啟動：正在安裝 Playwright 瀏覽器模組（約 150~400 MB）\n"
        "下載完成後視窗會自動關閉，請稍後…",
        None, 0, 0,
    )
    dlg.setWindowTitle("初始化")
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.setCancelButton(None)
    dlg.setMinimumWidth(480)
    dlg.show()
    app.processEvents()

    try:
        if getattr(sys, "frozen", False):
            # In a PyInstaller build, use the bundled node.exe + cli.js.
            meipass = Path(sys._MEIPASS)
            node_exe = meipass / "playwright" / "driver" / "node.exe"
            cli_js = meipass / "playwright" / "driver" / "package" / "cli.js"
            cmd = [str(node_exe), str(cli_js), "install", "chromium"]
        else:
            # In development, delegate to the Python package entry-point.
            cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as exc:
        dlg.close()
        QMessageBox.warning(
            None,
            "Playwright 安裝失敗",
            f"無法自動安裝 Playwright 瀏覽器模組：\n{exc}\n\n"
            "請手動執行：playwright install chromium\n"
            "自動填表功能將無法使用，其他功能不受影響。",
        )
        return

    dlg.close()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MapleStory Classic Auto Reporter")
    icon = QIcon(str(get_application_icon_path()))
    app.setWindowIcon(icon)

    # Ensure Playwright Chromium is installed (auto-downloads on first run).
    _ensure_playwright_chromium(app)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
