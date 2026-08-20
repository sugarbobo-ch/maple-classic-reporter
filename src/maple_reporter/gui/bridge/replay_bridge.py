"""Replay buffer recording and event callbacks bridge mixin."""

from __future__ import annotations

import logging
from typing import Any
from PIL import Image

LOGGER = logging.getLogger(__name__)


class ReplayBridgeMixin:
    """Methods for managing the background sliding replay buffer recorder."""

    def start_replay(
        self,
        window_title: str | None = None,
        fps: int | None = None,
        buffer_seconds: int | None = None,
        record_audio: bool | None = None,
        audio_device_id: str | None = None,
        audio_capture_mode: str | None = None,
    ) -> bool:
        """Start the background sliding replay buffer."""
        title = window_title or self.config.get("selected_window_title", "新楓之谷：經典版")
        rec_fps = fps or int(self.config.get("record_fps", 30))
        sec = buffer_seconds or int(self.config.get("replay_buffer_sec", 30))
        rec_audio = (
            record_audio
            if record_audio is not None
            else bool(self.config.get("record_audio", True))
        )
        mode = str(
            audio_capture_mode
            or self.config.get("audio_capture_mode", "system" if rec_audio else "off")
        ).casefold()
        if mode not in {"process", "system", "off"}:
            mode = "system" if rec_audio else "off"
        audio_dev = audio_device_id or self.config.get("audio_output_device_id") or None

        return self.replay_recorder.start(
            title,
            fps=rec_fps,
            buffer_seconds=sec,
            record_audio=rec_audio,
            audio_device_id=audio_dev,
            audio_capture_mode=mode,
        )

    def stop_replay(self) -> bool:
        """Stop background replay buffer."""
        self.replay_recorder.stop()
        return True

    def save_replay(self) -> bool:
        """Save the current buffer segment to mp4 file."""
        return self.replay_recorder.save_replay()

    def get_replay_status(self) -> dict[str, Any]:
        """Return current replay buffer state and duration."""
        return {
            "state": self._replay_state,
            "duration": self._replay_duration,
            "is_running": self.replay_recorder.is_running,
        }

    def _on_replay_state_changed(self, state: str, duration: float) -> None:
        self._replay_state = state
        self._replay_duration = duration
        self._emit_event(
            "REPLAY_STATE_CHANGED",
            {
                "state": state,
                "duration": duration,
                "total": int(self.config.get("replay_buffer_sec", 30)),
            },
        )

    def _on_replay_saved(self, file_path: str, keyframes: list[Image.Image]) -> None:
        LOGGER.info("Replay saved to %s (%d keyframes)", file_path, len(keyframes))
        self._emit_event("REPLAY_SAVED", {"file_path": file_path})
        try:
            ocr_res = self._perform_ocr(keyframes)
        except Exception as err:
            LOGGER.error("Failed to perform OCR on replay: %s", err)
            ocr_res = {
                "suspect_ids": [],
                "map_name": self.config.get("default_map", ""),
                "ocr_map_name": "",
                "map_name_source": "default",
            }
        self._emit_event(
            "OCR_RESULT",
            {
                "status": "success",
                "suspect_ids": ocr_res.get("suspect_ids", []),
                "map_name": ocr_res.get("map_name", ""),
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": "video",
            },
        )

    def _on_replay_error(self, message: str) -> None:
        LOGGER.warning("Replay error: %s", message)
        self._emit_event("REPLAY_ERROR", {"message": message})
