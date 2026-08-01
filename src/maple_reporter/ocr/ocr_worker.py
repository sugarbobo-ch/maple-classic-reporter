from PySide6.QtCore import QThread, Signal
from typing import List
from PIL import Image
from maple_reporter.ocr.win_ocr import (
    recognize_candidates_from_image_list,
    recognize_text_from_image,
    recognize_map_name_from_image_list,
    recognize_with_gemini_unified,
)

class OcrWorkerThread(QThread):
    """
    Background QThread for the default local OCR pass, without freezing PySide6.
    Cloud AI is deliberately invoked only by the separate manual review worker.
    """
    candidates_found = Signal(list)
    map_name_found = Signal(str)
    status_changed = Signal(str)

    def __init__(self, keyframes: List[Image.Image], api_key: str = "", whitelist: List[str] = None, parent=None):
        super().__init__(parent)
        self.keyframes = keyframes
        self.api_key = api_key
        self.whitelist = [w.strip() for w in whitelist if w.strip()] if whitelist else []

    def run(self):
        if not self.keyframes:
            self.status_changed.emit("沒有待辨識影格")
            return

        candidates = []
        seen = set()
        excluded = set(self.whitelist)

        # Local OCR is the fast default. AI review is explicit in the preview UI.
        self.status_changed.emit("RapidOCR 辨識地圖名稱中...")
        map_name = recognize_map_name_from_image_list(self.keyframes)
        if map_name:
            self.map_name_found.emit(map_name)

        # RapidOCR / WinSDK — local recognition
        self.status_changed.emit("RapidOCR 本地補充掃描中...")
        local_cands = recognize_candidates_from_image_list(self.keyframes, detected_map_name=map_name)
        for lc in local_cands:
            if lc not in seen and lc not in excluded:
                seen.add(lc)
                candidates.append(lc)

        self.candidates_found.emit(list(candidates))
        if candidates:
            self.status_changed.emit(f"辨識完成（共 {len(candidates)} 個候選 ID）")
        else:
            self.status_changed.emit("辨識完成，沒有自動偵測到 ID，可手動輸入。")


class AiReviewWorkerThread(QThread):
    """A single user-triggered Gemini review of one representative frame."""
    candidates_found = Signal(list)
    map_name_found = Signal(str)
    status_changed = Signal(str)

    def __init__(self, image: Image.Image, api_key: str, whitelist: List[str] = None, parent=None):
        super().__init__(parent)
        self.image = image
        self.api_key = api_key
        self.whitelist = set(whitelist or [])

    def run(self):
        if not self.api_key:
            self.status_changed.emit("尚未設定 Gemini API Key，無法進行 AI 複核。")
            return
        self.status_changed.emit("AI 正在複核目前畫面…")
        ids, map_name = recognize_with_gemini_unified(self.image, self.api_key)
        ids = [candidate for candidate in ids if candidate not in self.whitelist]
        if ids:
            self.candidates_found.emit(ids)
        if map_name:
            self.map_name_found.emit(map_name)
        self.status_changed.emit("AI 複核完成" if (ids or map_name) else "AI 未能取得可用結果")
