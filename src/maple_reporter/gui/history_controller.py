"""History persistence and table projection for the report history tab."""

from __future__ import annotations

import logging
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from maple_reporter.utils.config import add_history_entry, load_history
from maple_reporter.utils.urls import is_safe_https_url


LOGGER = logging.getLogger(__name__)


class HistoryController:
    def add(self, entry: dict) -> None:
        add_history_entry(entry)

    def refresh_table(self, table) -> None:
        history = load_history()
        table.setRowCount(len(history))
        for row, item in enumerate(history):
            table.setItem(row, 0, QTableWidgetItem(item.get("time", "")))
            table.setItem(row, 1, QTableWidgetItem(item.get("suspect_id", "")))
            table.setItem(row, 2, QTableWidgetItem(item.get("server", "")))
            table.setItem(row, 3, QTableWidgetItem(item.get("map", "")))

            url_text = item.get("url", "")
            url_item = QTableWidgetItem(url_text)
            if is_safe_https_url(url_text):
                url_item.setForeground(Qt.GlobalColor.blue)
                font = url_item.font()
                font.setUnderline(True)
                url_item.setFont(font)
                url_item.setToolTip("點擊前往開啟雲端事證網址")
            table.setItem(row, 4, url_item)
            table.setItem(row, 5, QTableWidgetItem(item.get("status", "")))

    def open_url_from_cell(self, table, row: int, column: int) -> bool:
        if column != 4:
            return False
        item = table.item(row, column)
        if not item:
            return False
        url = item.text().strip()
        if not is_safe_https_url(url):
            return False
        try:
            webbrowser.open(url)
        except OSError as error:
            LOGGER.warning("開啟歷史事證網址失敗 (%s)", type(error).__name__)
            return False
        return True


__all__ = ["HistoryController"]
