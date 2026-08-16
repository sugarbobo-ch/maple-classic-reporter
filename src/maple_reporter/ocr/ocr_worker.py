from PySide6.QtCore import QThread, Signal
from typing import List
from PIL import Image
from maple_reporter.ocr.win_ocr import (
    recognize_candidates_from_image_list,
    recognize_map_name_from_image_list,
)

class OcrWorkerThread(QThread):
    """
    Background QThread for the default local OCR pass, without freezing PySide6.
    """
    candidates_found = Signal(list)
    map_name_found = Signal(str)
    status_changed = Signal(str)

    def __init__(
        self,
        keyframes: List[Image.Image],
        whitelist: List[str] = None,
        parent=None,
        *,
        recognize_id: bool = True,
        recognize_map: bool = True,
    ):
        super().__init__(parent)
        self.keyframes = keyframes
        self.whitelist = [w.strip() for w in whitelist if w.strip()] if whitelist else []
        self.recognize_id = bool(recognize_id)
        self.recognize_map = bool(recognize_map)
        # Keep the value after the signal is emitted so the preview dialog can
        # recover a very fast result when the queued signal is delivered late.
        self.detected_map_name = ""

    def set_ocr_options(self, *, recognize_id: bool, recognize_map: bool):
        """Update the two optional OCR passes selected in the settings UI."""

        self.recognize_id = bool(recognize_id)
        self.recognize_map = bool(recognize_map)

    def run(self):
        if not self.keyframes:
            self.status_changed.emit("沒有待辨識影格")
            return

        candidates = []
        seen = set()
        excluded = set(self.whitelist)

        # Local OCR is the fast default. AI review is explicit in the preview UI.
        if self.recognize_map:
            self.status_changed.emit("RapidOCR 辨識地圖名稱中...")
            self.detected_map_name = recognize_map_name_from_image_list(self.keyframes)
            if self.detected_map_name:
                self.map_name_found.emit(self.detected_map_name)
        else:
            self.status_changed.emit("已略過地圖 OCR")

        if self.recognize_id:
            # RapidOCR / WinSDK — local recognition
            self.status_changed.emit("RapidOCR 本地補充掃描中...")
            local_cands = recognize_candidates_from_image_list(
                self.keyframes, detected_map_name=self.detected_map_name
            )
            for lc in local_cands:
                if lc not in seen and lc not in excluded:
                    seen.add(lc)
                    candidates.append(lc)

        self.candidates_found.emit(list(candidates))
        if not self.recognize_id and not self.recognize_map:
            self.status_changed.emit("已略過 ID 與地圖 OCR，可手動填寫。")
        elif not self.recognize_id:
            self.status_changed.emit("地圖辨識完成，已略過 ID OCR。")
        elif candidates:
            self.status_changed.emit(f"辨識完成（共 {len(candidates)} 個候選 ID）")
        else:
            self.status_changed.emit("辨識完成，沒有自動偵測到 ID，可手動輸入。")

    def release_keyframes(self):
        """Drop large PIL frame references after OCR consumers have their result."""
        self.keyframes.clear()
