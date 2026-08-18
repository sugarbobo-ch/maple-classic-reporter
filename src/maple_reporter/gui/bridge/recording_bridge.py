"""Screenshot capture and video recording bridge mixin."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

LOGGER = logging.getLogger(__name__)


def _bridge_mod():
    import maple_reporter.gui.pywebview_bridge as bridge_mod

    return bridge_mod


class RecordingBridgeMixin:
    """Methods for taking screenshots and executing video recordings of the game window."""

    def capture_screenshot(self, mode: str = "window") -> dict[str, Any]:
        """Capture screenshot from the selected target game window and perform OCR."""
        mod = _bridge_mod()
        win_title = self.config.get("selected_window_title", "新楓之谷：經典版")
        try:
            if mod.is_window_minimized(win_title):
                return {
                    "status": "error",
                    "message": "目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再進行截圖。",
                }

            mod.focus_window(win_title)
            mod.time.sleep(0.15)
            bounds = mod.find_window_bounds(win_title)
            if not bounds:
                raise RuntimeError("找不到選取的遊戲視窗，請重新整理視窗清單。")

            img, file_path = mod.capture_window_screenshot(win_title)
            if img is None or not file_path:
                img, file_path = mod.record_capture_screenshot(bounds)

            ocr_res = self._perform_ocr([img])

            return {
                "status": "success",
                "suspect_ids": ocr_res["suspect_ids"],
                "map_name": ocr_res["map_name"],
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": "image",
            }
        except Exception as err:
            mod.LOGGER.error("Screenshot capture failed: %s", err)
            return {
                "status": "error",
                "message": f"截圖失敗: {str(err)}",
                "suspect_ids": [],
                "map_name": "",
                "media_path": "",
                "media_type": "image",
            }

    def start_recording(
        self,
        duration_sec: int | None = None,
        fps: int | None = None,
        countdown_sec: int | None = None,
        record_audio: bool | None = None,
        audio_device_id: str | None = None,
    ) -> bool:
        """Start a short video recording in a background thread with real-time events."""
        mod = _bridge_mod()
        if self._recording_active or (self._recording_thread and self._recording_thread.is_alive()):
            # Wait briefly if previous thread is finishing cleanup
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=0.5)
            if self._recording_active:
                LOGGER.warning("start_recording rejected: previous recording still active.")
                return False

        duration = duration_sec or int(self.config.get("record_duration_sec", 8))
        rec_fps = fps or int(self.config.get("record_fps", 30))
        countdown = (
            countdown_sec
            if countdown_sec is not None
            else int(self.config.get("record_countdown_sec", 0))
        )
        rec_audio = (
            record_audio
            if record_audio is not None
            else bool(self.config.get("record_audio", True))
        )
        audio_dev = audio_device_id or self.config.get("audio_output_device_id") or None
        win_title = self.config.get("selected_window_title", "新楓之谷：經典版")

        # Reject if target window is minimized
        if mod.is_window_minimized(win_title):
            LOGGER.warning("start_recording rejected: target window '%s' is minimized.", win_title)
            self._emit_event(
                "RECORDING_ERROR",
                {"message": "目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再開始錄影。"},
            )
            raise RuntimeError("目標遊戲視窗處於最小化狀態，請先展開遊戲視窗後再開始錄影。")

        mod.focus_window(win_title)

        self._recording_active = True
        self._cancel_requested = False

        def _worker():
            try:
                mod.focus_window(win_title)
                # Countdown phase
                if countdown > 0:
                    for remaining in range(countdown, 0, -1):
                        if self._cancel_requested:
                            self._emit_event("RECORDING_CANCELED")
                            return
                        percent = int((remaining / countdown) * 100)
                        self._emit_event(
                            "RECORDING_COUNTDOWN",
                            {"remaining": remaining, "percent": percent, "total": countdown},
                        )
                        mod.time.sleep(1.0)

                if self._cancel_requested:
                    self._emit_event("RECORDING_CANCELED")
                    return

                self._emit_event(
                    "RECORDING_PROGRESS",
                    {"elapsed": 0, "total": duration, "percent": 0, "fraction": 0.0},
                )

                last_progress_time = 0.0

                def _progress_cb(val: float):
                    nonlocal last_progress_time
                    now = time.monotonic()
                    if now - last_progress_time < 0.04 and val < 0.99:
                        return
                    last_progress_time = now
                    frac = max(0.0, min(1.0, float(val)))
                    elapsed = min(duration, int(frac * duration))
                    percent = int(frac * 100)
                    self._emit_event(
                        "RECORDING_PROGRESS",
                        {"elapsed": elapsed, "total": duration, "percent": percent, "fraction": frac},
                    )

                file_path, keyframes = mod.record_short_video(
                    win_title,
                    duration_sec=duration,
                    fps=rec_fps,
                    progress_callback=_progress_cb,
                    cancel_checker=lambda: self._cancel_requested,
                    record_audio=rec_audio,
                    audio_device_id=audio_dev,
                )

                if self._cancel_requested or not file_path:
                    if self._cancel_requested:
                        self._emit_event("RECORDING_CANCELED")
                    else:
                        self._emit_event("RECORDING_ERROR", {"message": "無法擷取目標遊戲視窗，請確認遊戲未關閉"})
                    return

                # Emit final 100% progress so the circle fills completely
                self._emit_event(
                    "RECORDING_PROGRESS",
                    {"elapsed": duration, "total": duration, "percent": 100, "fraction": 1.0},
                )
                mod.time.sleep(0.15)

                self._emit_event("RECORDING_FINISHED", {"file_path": file_path})
                ocr_res = self._perform_ocr(keyframes)

                self._emit_event(
                    "OCR_RESULT",
                    {
                        "status": "success",
                        "suspect_ids": ocr_res["suspect_ids"],
                        "map_name": ocr_res["map_name"],
                        "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                        "map_name_source": ocr_res.get("map_name_source", "default"),
                        "media_path": file_path,
                        "media_type": "video",
                    },
                )
            except Exception as err:
                LOGGER.error("Recording worker exception: %s", err)
                self._emit_event("RECORDING_ERROR", {"message": str(err)})
            finally:
                self._recording_active = False
                self._cancel_requested = False

        self._recording_thread = threading.Thread(target=_worker, daemon=True)
        self._recording_thread.start()
        return True

    def cancel_recording(self) -> bool:
        """Request cancellation of active recording and wait for cleanup."""
        if not self._recording_active and (
            not self._recording_thread or not self._recording_thread.is_alive()
        ):
            return True
        self._cancel_requested = True
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=1.5)
        self._recording_active = False
        self._cancel_requested = False
        return True
