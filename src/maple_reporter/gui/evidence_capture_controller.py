"""Evidence capture and media decoding service used by MainWindow."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image

from maple_reporter.recorder.window_recorder import record_short_video
from maple_reporter.utils.config import get_recordings_dir


LOGGER = logging.getLogger(__name__)


class EvidenceCaptureController:
    def save_snippet(self, image: Image.Image) -> str:
        path = get_recordings_dir() / f"maple_evidence_{time.time_ns() // 1_000_000}.png"
        image.convert("RGB").save(path)
        return str(path)

    def record_video(
        self,
        window_title: str,
        *,
        duration_sec: int,
        fps: int,
        progress_callback: Optional[Callable[[float], None]],
        cancel_checker: Optional[Callable[[], bool]],
        record_audio: bool,
        audio_device_id: str | None,
    ):
        return record_short_video(
            window_title,
            duration_sec=duration_sec,
            fps=fps,
            progress_callback=progress_callback,
            cancel_checker=cancel_checker,
            record_audio=record_audio,
            audio_device_id=audio_device_id,
        )

    def load_keyframes(self, file_path: str) -> list[Image.Image]:
        """Decode representative frames from an imported image or video."""

        if not os.path.exists(file_path):
            return []
        extension = Path(file_path).suffix.lower()
        if extension not in {".mp4", ".mkv", ".avi", ".mov"}:
            try:
                return [Image.open(file_path)]
            except (OSError, ValueError) as error:
                LOGGER.warning("讀取匯入圖片失敗 (%s)", type(error).__name__)
                return []

        keyframes: list[Image.Image] = []
        capture = cv2.VideoCapture(file_path)
        try:
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = capture.get(cv2.CAP_PROP_FPS) or 20
            safe_fps = max(1.0, float(fps))
            duration = total_frames / safe_fps if total_frames > 0 else 0.0
            is_replay = "replay" in Path(file_path).name.lower()

            if total_frames > 0:
                if is_replay and duration >= 4.0:
                    tail_sec = min(5.0, duration * 0.6)
                    tail_start_frame = int(round((duration - tail_sec) * safe_fps))
                    head_indices = (
                        np.linspace(0, max(0, tail_start_frame - 1), num=4, dtype=int)
                        if tail_start_frame > 0
                        else []
                    )
                    tail_indices = np.linspace(
                        tail_start_frame, total_frames - 1, num=8, dtype=int
                    )
                    target_indices = sorted(
                        list(set(list(head_indices) + list(tail_indices)))
                    )
                else:
                    target_count = min(12, total_frames)
                    target_indices = np.linspace(
                        0, total_frames - 1, num=target_count, dtype=int
                    )

                for idx in target_indices:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        keyframes.append(
                            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        )
            else:
                step = max(1, int(safe_fps * 1.5))
                frame_index = 0
                while capture.isOpened() and len(keyframes) < 12:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    if frame_index % step == 0:
                        keyframes.append(
                            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        )
                    frame_index += 1
        finally:
            capture.release()
        return keyframes


__all__ = ["EvidenceCaptureController"]
