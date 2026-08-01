import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from maple_reporter.gui.main_window import MainWindow


def get_application_icon_path() -> Path:
    """Return the icon location for source runs and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "icon.png"
    return Path(__file__).resolve().parents[2] / "assets" / "icon.png"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MapleStory Classic Auto Reporter")
    icon = QIcon(str(get_application_icon_path()))
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
