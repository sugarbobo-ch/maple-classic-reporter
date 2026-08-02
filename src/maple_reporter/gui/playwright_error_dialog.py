"""A copy-friendly error dialog for Playwright/Chromium setup failures."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from maple_reporter.automation.playwright_runtime import PlaywrightErrorDetails


class PlaywrightErrorDialog(QDialog):
    """Show the failure context, a selectable URL, and a copy-all action."""

    def __init__(self, details: PlaywrightErrorDetails, parent=None) -> None:
        super().__init__(parent)
        self.details = details
        self.setWindowTitle("Playwright Chrome 無法使用")
        self.setModal(True)
        self.resize(720, 560)
        self.setMinimumSize(580, 430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("找不到或無法啟動 Playwright 內建 Chrome。")
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(heading)

        explanation = QLabel(
            "請先複製完整資訊提供給維護者；你也可以開啟官方說明頁下載或重新安裝 Chromium。"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        fields = QFormLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(8)

        summary = QLabel(details.summary)
        summary.setWordWrap(True)
        fields.addRow("狀態", summary)

        self.url_link = QLabel(
            f'<a href="{escape(details.download_url)}">{escape(details.download_url)}</a>'
        )
        self.url_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.url_link.setOpenExternalLinks(True)
        self.url_link.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.url_link.setAccessibleName("開啟 Playwright Chromium 下載網址")
        self.url_link.setToolTip("點選開啟 Playwright Chromium 下載說明")
        self.url_link.setWordWrap(True)
        fields.addRow("下載網址", self.url_link)
        layout.addLayout(fields)

        self.details_edit = QPlainTextEdit()
        self.details_edit.setReadOnly(True)
        self.details_edit.setPlainText(details.as_text())
        self.details_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.details_edit.setAccessibleName("Playwright 錯誤完整資訊")
        self.details_edit.setToolTip("這裡包含所有錯誤欄位，可直接選取複製")
        layout.addWidget(self.details_edit, 1)

        self.feedback_label = QLabel()
        self.feedback_label.setAccessibleName("錯誤資訊操作狀態")
        self.feedback_label.setWordWrap(True)
        layout.addWidget(self.feedback_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.copy_button = QPushButton("複製全部資訊")
        self.copy_button.setToolTip("複製錯誤視窗中的所有欄位")
        self.copy_button.clicked.connect(self.copy_all)
        self.copy_button.setDefault(True)
        actions.addWidget(self.copy_button)

        self.open_button = QPushButton("開啟下載頁")
        self.open_button.setToolTip("在瀏覽器開啟 Playwright Chromium 下載說明")
        self.open_button.clicked.connect(self.open_download_page)
        actions.addWidget(self.open_button)
        actions.addStretch(1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        actions.addWidget(self.button_box)
        layout.addLayout(actions)

        self.copy_button.setFocus()

    def copy_all(self) -> None:
        QApplication.clipboard().setText(self.details.as_text())
        self.feedback_label.setText("已複製全部錯誤欄位。")

    def open_download_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.details.download_url))


def show_playwright_error_dialog(parent, error) -> int:
    dialog = PlaywrightErrorDialog(error.details, parent)
    return dialog.exec()
