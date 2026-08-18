"""Background form submission controller."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, QThread, Signal

from maple_reporter.automation.form_filler import submit_gamania_report
from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError
from maple_reporter.utils.config import is_owned_recording_path


LOGGER = logging.getLogger(__name__)


class SubmitThread(QThread):
    finished_signal = Signal(bool, str, object)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data

    def run(self) -> None:
        try:
            if self.data.get("dev_mode") is True:
                self.finished_signal.emit(
                    True,
                    "Developer mode: SurveyCake submission skipped.",
                    None,
                )
                return

            success, message = submit_gamania_report(
                suspect_id=self.data["suspect_id"],
                server_name=self.data["server_name"],
                map_name=self.data["map_name"],
                note=self.data["note"],
                evidence_url=self.data.get("evidence_url", ""),
                headless=bool(self.data.get("form_submit_headless", False)),
            )
        except PlaywrightBrowserError as error:
            self.finished_signal.emit(False, error.details.summary, error)
            return
        except Exception as error:  # pragma: no cover - worker boundary
            LOGGER.warning("背景表單送出執行緒失敗 (%s)", type(error).__name__)
            self.finished_signal.emit(
                False,
                "表單送出執行緒發生未預期錯誤，請稍後再試。",
                error,
            )
            return
        self.finished_signal.emit(success, message, None)


class SubmissionController(QObject):
    """Own the worker thread and enforce upload/form confirmation boundaries."""

    finished = Signal(bool, str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: SubmitThread | None = None

    def submit(self, data: dict) -> bool:
        if self._thread:
            try:
                if self._thread.isRunning():
                    return False
            except RuntimeError:
                # The QThread wrapper can outlive its C++ object after the
                # previous finished signal scheduled deleteLater().
                self._thread = None

        thread = SubmitThread(data, self)
        self._thread = thread
        thread.finished_signal.connect(
            lambda ok, message, error: self._on_finished(ok, message, error, data)
        )
        thread.finished.connect(lambda: self._clear_finished_thread(thread))
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def _clear_finished_thread(self, thread: SubmitThread) -> None:
        if self._thread is thread:
            self._thread = None

    def _on_finished(self, ok: bool, message: str, error, data: dict) -> None:
        data["form_confirmed"] = bool(ok)
        self.finished.emit(ok, message, error, data)

    @staticmethod
    def can_delete_evidence(data: dict, form_confirmed: bool) -> bool:
        """Only generated, uploaded, and explicitly confirmed evidence is deletable."""

        return bool(
            form_confirmed
            and data.get("upload_confirmed") is True
            and data.get("file_origin") == "generated"
            and data.get("file_path")
            and is_owned_recording_path(data["file_path"])
        )

    @staticmethod
    def delete_confirmed_evidence(data: dict) -> bool:
        path = data.get("file_path")
        if not path or not is_owned_recording_path(path):
            return False
        try:
            os.remove(path)
        except OSError as error:
            LOGGER.warning("刪除已確認事證失敗 (%s)", type(error).__name__)
            return False
        return True


__all__ = ["SubmitThread", "SubmissionController"]
