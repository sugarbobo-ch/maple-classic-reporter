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
        audio_capture_mode: str | None = None,
    ):
        return record_short_video(
            window_title,
            duration_sec=duration_sec,
            fps=fps,
            progress_callback=progress_callback,
            cancel_checker=cancel_checker,
            record_audio=record_audio,
            audio_device_id=audio_device_id,
            audio_capture_mode=audio_capture_mode,
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

    def capture_video_frame(
        self, file_path: str, timestamp_sec: float
    ) -> Image.Image | None:
        """Decode one video frame at the requested playback timestamp."""

        if not file_path or not os.path.exists(file_path):
            return None

        capture = cv2.VideoCapture(file_path)
        try:
            if not capture.isOpened():
                return None

            fps = max(1.0, float(capture.get(cv2.CAP_PROP_FPS) or 20.0))
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            timestamp = max(0.0, float(timestamp_sec))
            if total_frames > 0:
                duration = max(0.0, (total_frames - 1) / fps)
                timestamp = min(timestamp, duration)

            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(round(timestamp * fps)))
                ok, frame = capture.read()
            if not ok or frame is None:
                return None

            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        except (OSError, TypeError, ValueError) as error:
            LOGGER.warning("讀取目前影片畫面失敗 (%s)", type(error).__name__)
            return None
        finally:
            capture.release()


__all__ = ["EvidenceCaptureController"]
