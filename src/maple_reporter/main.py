import sys
from PySide6.QtWidgets import QApplication
from maple_reporter.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MapleStory Classic Auto Reporter")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
