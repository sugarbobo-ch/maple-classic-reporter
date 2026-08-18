"""Bounded replay buffer for saving the most recent gameplay on demand."""

from __future__ import annotations

import io
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Deque, Mapping, Optional

import av
import cv2
import mss
import numpy as np
from PIL import Image, ImageGrab
from PySide6.QtCore import QObject, Signal

from maple_reporter.recorder.audio_capture import (
    DEFAULT_SAMPLE_RATE,
    LoopbackAudioRecorder,
    get_audio_output_devices,
    has_audio_signal,
    merge_audio_into_mp4,
)
from maple_reporter.recorder.window_recorder import find_window_bounds
from maple_reporter.utils.config import get_recordings_dir


LOGGER = logging.getLogger(__name__)


# Replay videos keep their configured FPS. These intervals only control the
# representative screenshots sent to OCR and the preview modal. The tail is
# sampled more densely because the user usually presses "save" immediately
# after spotting a suspected player, just like a dashcam event buffer.
REPLAY_KEYFRAME_BASE_INTERVAL_SECONDS = 2.0
REPLAY_KEYFRAME_TAIL_WINDOW_SECONDS = 5.0
REPLAY_KEYFRAME_TAIL_INTERVAL_SECONDS = 0.5
REPLAY_KEYFRAME_MAX_COUNT = 40


@dataclass(frozen=True)
class BufferedFrame:
    captured_at: float
    jpeg_data: bytes


class ReplayCaptureError(RuntimeError):
    """Raised after both Windows capture paths fail for one frame."""


class ReplayState(str, Enum):
    """Lifecycle states shared by the recorder and its UI."""

    IDLE = "idle"
    WARMING = "warming"
    READY = "ready"
    SAVING = "saving"
    STOPPING = "stopping"
    ERROR = "error"


def _build_replay_keyframe_times(duration: float) -> list[float]:
    """Return representative screenshot times with a denser event tail."""

    duration = max(0.0, float(duration))
    if duration <= 0.0:
        return [0.0]

    tail_start = max(0.0, duration - REPLAY_KEYFRAME_TAIL_WINDOW_SECONDS)
    times: list[float] = []

    current = 0.0
    while current < tail_start - 1e-9:
        times.append(round(current, 6))
        current += REPLAY_KEYFRAME_BASE_INTERVAL_SECONDS

    current = tail_start
    while current <= duration + 1e-9:
        times.append(round(min(current, duration), 6))
        current += REPLAY_KEYFRAME_TAIL_INTERVAL_SECONDS

    if not times or times[-1] < duration - 1e-9:
        times.append(round(duration, 6))

    # Keep the event tail intact if a future buffer setting exceeds the normal
    # 60-second UI limit. Thin only the older, lower-priority samples.
    if len(times) > REPLAY_KEYFRAME_MAX_COUNT:
        tail_times = [time for time in times if time >= tail_start - 1e-9]
        regular_times = [time for time in times if time < tail_start - 1e-9]
        available_regular = REPLAY_KEYFRAME_MAX_COUNT - len(tail_times)
        if available_regular <= 0:
            times = tail_times[-REPLAY_KEYFRAME_MAX_COUNT:]
        elif len(regular_times) > available_regular:
            if available_regular == 1:
                regular_times = [regular_times[0]]
            else:
                indexes = np.linspace(
                    0,
                    len(regular_times) - 1,
                    num=available_regular,
                    dtype=int,
                )
                regular_times = [regular_times[int(index)] for index in indexes]
            times = regular_times + tail_times

    return times


def _build_replay_keyframe_indices(
    duration: float,
    fps: int,
    output_count: int,
) -> set[int]:
    """Map screenshot times to unique encoded-video frame indexes."""

    if output_count <= 0:
        return set()
    safe_fps = max(1, int(fps))
    max_index = output_count - 1
    return {
        min(max_index, max(0, int(round(timestamp * safe_fps))))
        for timestamp in _build_replay_keyframe_times(duration)
    }


def _clip_monitor_to_virtual_screen(
    monitor: dict[str, int], virtual_screen: Mapping[str, int]
) -> dict[str, int]:
    left = max(monitor["left"], int(virtual_screen["left"]))
    top = max(monitor["top"], int(virtual_screen["top"]))
    right = min(
        monitor["left"] + monitor["width"],
        int(virtual_screen["left"]) + int(virtual_screen["width"]),
    )
    bottom = min(
        monitor["top"] + monitor["height"],
        int(virtual_screen["top"]) + int(virtual_screen["height"]),
    )
    if right <= left or bottom <= top:
        raise ReplayCaptureError("目標遊戲視窗目前不在可擷取的螢幕範圍內。")
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}


def capture_monitor_frame(
    screen,
    monitor: dict[str, int],
) -> tuple[np.ndarray, bool]:
    """Capture BGR pixels, falling back when MSS/GDI BitBlt is unavailable."""

    clipped = _clip_monitor_to_virtual_screen(monitor, screen.monitors[0])
    try:
        raw = np.asarray(screen.grab(clipped))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR), False
    except Exception as error:
        LOGGER.debug("MSS 畫面擷取失敗，改用 Pillow (%s)", type(error).__name__)
        try:
            left, top = clipped["left"], clipped["top"]
            image = ImageGrab.grab(
                bbox=(left, top, left + clipped["width"], top + clipped["height"]),
                all_screens=True,
            ).convert("RGB")
            return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), True
        except Exception as fallback_error:
            raise ReplayCaptureError("Windows 畫面擷取暫時失敗。") from fallback_error


# Backward-compatible name used by older callers and tests. The implementation
# now lives in audio_capture.py and is shared with short recordings.
RollingAudioRecorder = LoopbackAudioRecorder


_WORKING_H264_ENCODER_CACHE: Optional[tuple[str, dict[str, str]]] = None


def _get_working_h264_encoder(fps: int = 30) -> tuple[str, dict[str, str]]:
    global _WORKING_H264_ENCODER_CACHE
    if _WORKING_H264_ENCODER_CACHE is not None:
        return _WORKING_H264_ENCODER_CACHE

    candidates = [
        ("h264_nvenc", {"preset": "p1", "tune": "ull"}),
        ("h264_qsv", {}),
        ("h264_amf", {}),
        ("libx264", {"crf": "23", "preset": "ultrafast"}),
        ("h264", {"crf": "23", "preset": "ultrafast"}),
    ]
    for codec, options in candidates:
        if codec not in getattr(av, "codecs_available", set()):
            continue
        try:
            buf = io.BytesIO()
            test_container = av.open(buf, mode="w", format="mp4")
            test_stream = test_container.add_stream(codec, rate=fps)
            test_stream.width = 64
            test_stream.height = 64
            test_stream.pix_fmt = "yuv420p"
            if options:
                test_stream.options = options
            test_stream.codec_context.open()
            test_container.close()
            _WORKING_H264_ENCODER_CACHE = (codec, options)
            LOGGER.info("Selected H.264 encoder: %s", codec)
            return _WORKING_H264_ENCODER_CACHE
        except Exception as error:
            LOGGER.debug("Encoder candidate %s not supported (%s)", codec, error)
            continue

    _WORKING_H264_ENCODER_CACHE = ("h264", {"preset": "ultrafast"})
    return _WORKING_H264_ENCODER_CACHE


def _create_optimized_h264_stream(container, width: int, height: int, fps: int):
    """Create H.264 video stream using probed working encoder with CPU fallback."""
    codec, options = _get_working_h264_encoder(fps)
    stream = container.add_stream(codec, rate=fps)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    if options:
        stream.options = options
    return stream


class ReplayBufferRecorder(QObject):

    """Continuously capture a bounded JPEG ring and save one replay at a time."""

    state_changed = Signal(str, float)
    replay_saved = Signal(str, object)
    error_occurred = Signal(str)
    warning_occurred = Signal(str)
    audio_source_changed = Signal(str)

    def __init__(
        self,
        parent: Optional[QObject] = None,
        *,
        state_callback: Optional[Callable[[str, float], None]] = None,
        replay_saved_callback: Optional[
            Callable[[str, list[Image.Image]], None]
        ] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        warning_callback: Optional[Callable[[str], None]] = None,
        audio_source_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        # PyWebView has no Qt event loop, so cross-thread Qt signals are never
        # drained there. Plain callbacks keep that frontend informed while the
        # signals remain available to the native PySide frontend.
        self._state_callback = state_callback
        self._replay_saved_callback = replay_saved_callback
        self._error_callback = error_callback
        self._warning_callback = warning_callback
        self._audio_source_callback = audio_source_callback
        self._frames: Deque[BufferedFrame] = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._save_thread: Optional[threading.Thread] = None
        self._audio: Optional[LoopbackAudioRecorder] = None
        self._running = False
        self._saving = False
        self._state = ReplayState.IDLE
        self._fps = 20
        self._buffer_seconds = 30
        self._bounds: Optional[tuple[int, int, int, int]] = None

    @property
    def state(self) -> ReplayState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def is_saving(self) -> bool:
        with self._lock:
            return self._saving

    @property
    def buffer_seconds(self) -> int:
        with self._lock:
            return self._buffer_seconds

    def _emit_state(self, state: ReplayState, duration: float) -> None:
        safe_duration = max(0.0, float(duration))
        with self._lock:
            self._state = state
        self._invoke_callback(self._state_callback, state.value, safe_duration)
        self.state_changed.emit(state.value, safe_duration)

    @staticmethod
    def _invoke_callback(callback: Optional[Callable], *args) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception as error:
            LOGGER.warning("回放事件回呼執行失敗 (%s)", type(error).__name__)

    def _emit_error(self, message: str) -> None:
        self._invoke_callback(self._error_callback, message)
        self.error_occurred.emit(message)

    def _emit_warning(self, message: str) -> None:
        self._invoke_callback(self._warning_callback, message)
        self.warning_occurred.emit(message)

    def _emit_audio_source(self, source_name: str) -> None:
        self._invoke_callback(self._audio_source_callback, source_name)
        self.audio_source_changed.emit(source_name)

    def _emit_replay_saved(
        self, file_path: str, keyframes: list[Image.Image]
    ) -> None:
        self._invoke_callback(self._replay_saved_callback, file_path, keyframes)
        self.replay_saved.emit(file_path, keyframes)

    def start(
        self,
        window_title: str,
        fps: int = 20,
        buffer_seconds: int = 30,
        record_audio: bool = True,
        audio_device_id: Optional[str] = None,
    ) -> bool:
        bounds = find_window_bounds(window_title)
        if not bounds:
            self._emit_error("找不到目標遊戲視窗，請重新整理後再試一次。")
            return False

        left, top, width, height = bounds
        width -= width % 2
        height -= height % 2
        if width < 2 or height < 2:
            self._emit_error("目標遊戲視窗大小無法錄製。")
            return False

        if self._save_thread and self._save_thread.is_alive():
            self._emit_error("上一段回放仍在儲存中，請稍候再啟動。")
            return False

        with self._lock:
            if self._running:
                return False
            self._frames.clear()
            self._running = True
            self._saving = False
            self._fps = max(1, int(fps))
            self._buffer_seconds = max(3, int(buffer_seconds))
            self._bounds = (left, top, width, height)
            self._stop_event.clear()

        if record_audio:
            self._audio = RollingAudioRecorder(
                self._buffer_seconds,
                sample_rate=DEFAULT_SAMPLE_RATE,
                device_id=audio_device_id,
                error_callback=self._emit_warning,
                source_callback=self._emit_audio_source,
            )
            self._audio.start()
        else:
            self._audio = None

        self._window_title = window_title
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="maple-replay-capture",
            daemon=True,
        )
        self._capture_thread.start()
        self._emit_state(ReplayState.WARMING, 0.0)
        return True

    def stop(self) -> None:
        with self._lock:
            was_active = self._running or self._saving or self._state != ReplayState.IDLE
            self._running = False
            self._stop_event.set()
        if not was_active:
            return

        self._emit_state(ReplayState.STOPPING, 0.0)
        if (
            self._capture_thread
            and self._capture_thread is not threading.current_thread()
        ):
            self._capture_thread.join(timeout=3.0)
        if self._capture_thread and self._capture_thread.is_alive():
            LOGGER.warning("回放擷取執行緒在停止期限內仍未結束")

        audio = self._audio
        self._audio = None
        if audio:
            audio.stop()

        save_thread = self._save_thread
        if save_thread and save_thread is not threading.current_thread():
            save_thread.join(timeout=5.0)
        if save_thread and save_thread.is_alive():
            LOGGER.warning("回放儲存執行緒在停止期限內仍未結束")

        with self._lock:
            self._frames.clear()
            self._saving = False
        self._emit_state(ReplayState.IDLE, 0.0)

    def save_replay(self) -> bool:
        with self._lock:
            if not self._running or self._saving or len(self._frames) < 2:
                return False
            frames = list(self._frames)
            self._saving = True
            buffer_seconds = self._buffer_seconds

        start_time = max(frames[0].captured_at, frames[-1].captured_at - buffer_seconds)
        frames = [frame for frame in frames if frame.captured_at >= start_time]
        if len(frames) < 2:
            with self._lock:
                self._saving = False
            return False
        end_time = frames[-1].captured_at
        audio_data = self._audio.snapshot(start_time, end_time) if self._audio else None
        if self._audio and not has_audio_signal(audio_data):
            self._emit_warning(
                "這段緩衝沒有偵測到系統聲音。請確認遊戲正在播放聲音，"
                "並在重新啟動緩衝前選擇正確的音訊輸出來源。"
            )

        self._emit_state(ReplayState.SAVING, end_time - start_time)
        self._save_thread = threading.Thread(
            target=self._save_snapshot,
            args=(frames, audio_data),
            name="maple-replay-save",
            daemon=True,
        )
        self._save_thread.start()
        return True

    def _buffered_duration_locked(self) -> float:
        if len(self._frames) < 2:
            return 0.0
        return min(
            float(self._buffer_seconds),
            self._frames[-1].captured_at - self._frames[0].captured_at,
        )

    def _append_frame(self, captured_at: float, jpeg_data: bytes) -> tuple[float, bool]:
        with self._lock:
            if not self._running:
                return 0.0, self._saving
            self._frames.append(BufferedFrame(captured_at, jpeg_data))
            cutoff = captured_at - self._buffer_seconds
            while len(self._frames) > 1 and self._frames[1].captured_at < cutoff:
                self._frames.popleft()
            return self._buffered_duration_locked(), self._saving

    def _capture_loop(self) -> None:
        with self._lock:
            bounds = self._bounds
            fps = self._fps
            buffer_seconds = self._buffer_seconds
            window_title = getattr(self, "_window_title", "")
        if bounds is None:
            return

        left, top, width, height = bounds
        monitor = {"left": left, "top": top, "width": width, "height": height}
        interval = 1.0 / max(1, fps)
        next_capture = time.monotonic()
        last_status_emit = 0.0
        consecutive_failures = 0
        screen = None

        from maple_reporter.recorder.window_capture import UnifiedWindowCapture

        video_capture = UnifiedWindowCapture(fallback_callback=self._emit_warning)
        video_capture.start_stream(window_title, fps=fps)

        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                if now < next_capture:
                    self._stop_event.wait(next_capture - now)
                    continue
                next_capture = max(next_capture + interval, now)

                bgr, captured_at = video_capture.get_latest_frame()
                if bgr is None:
                    try:
                        if screen is None:
                            screen = mss.MSS()
                        bgr, used_fallback = capture_monitor_frame(screen, monitor)
                        captured_at = time.monotonic()
                        consecutive_failures = 0
                    except ReplayCaptureError as error:
                        consecutive_failures += 1
                        if consecutive_failures >= 10:
                            raise ReplayCaptureError(
                                "無法持續擷取遊戲畫面。請確認遊戲視窗未最小化，"
                                "且仍位於已連接的螢幕上，再重新啟動回放緩衝。"
                            ) from error
                        try:
                            if screen is not None:
                                screen.close()
                        except Exception as close_error:
                            LOGGER.debug(
                                "重建 MSS 前關閉擷取器失敗 (%s)",
                                type(close_error).__name__,
                            )
                        screen = mss.MSS()
                        next_capture = time.monotonic() + min(
                            1.0, consecutive_failures * 0.15
                        )
                        continue

                    if used_fallback:
                        try:
                            if screen is not None:
                                screen.close()
                        except Exception as close_error:
                            LOGGER.debug(
                                "切換 Pillow 擷取後關閉 MSS 失敗 (%s)",
                                type(close_error).__name__,
                            )
                        screen = mss.MSS()
                else:
                    consecutive_failures = 0

                if bgr.shape[1] != width or bgr.shape[0] != height:
                    bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA)
                ok, encoded = cv2.imencode(
                    ".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 75]
                )
                if not ok:
                    continue

                duration, saving = self._append_frame(captured_at, encoded.tobytes())
                if not self.is_running:
                    break

                if captured_at - last_status_emit >= 0.25:
                    state = ReplayState.SAVING if saving else (
                        ReplayState.READY
                        if duration >= buffer_seconds - interval * 2
                        else ReplayState.WARMING
                    )
                    self._emit_state(state, duration)
                    last_status_emit = captured_at
        except Exception as error:
            with self._lock:
                was_running = self._running
                self._running = False
                self._stop_event.set()
            if was_running:
                self._emit_state(ReplayState.ERROR, 0.0)
                self._emit_error(f"緩衝錄影已停止：{error}")
        finally:
            video_capture.stop_stream()
            if screen is not None:
                try:
                    screen.close()
                except Exception as error:
                    LOGGER.debug("關閉回放 MSS 失敗 (%s)", type(error).__name__)

    def _save_snapshot(
        self,
        frames: list[BufferedFrame],
        audio_data: Optional[np.ndarray],
    ) -> None:
        file_path = ""
        saved_payload = None
        try:
            file_path, keyframes = self._encode_video(frames)
            if has_audio_signal(audio_data) and not merge_audio_into_mp4(
                file_path, audio_data, sample_rate=DEFAULT_SAMPLE_RATE
            ):
                self._emit_warning(
                    "影片已儲存，但系統聲音無法合併到影片中。"
                )
            saved_payload = (file_path, keyframes)
        except Exception as error:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as cleanup_error:
                    LOGGER.warning(
                        "清理失敗的回放檔案失敗 (%s: %s)",
                        os.path.basename(file_path),
                        type(cleanup_error).__name__,
                    )
            self._emit_error(f"無法儲存最近的錄影片段：{error}")
        finally:
            with self._lock:
                self._saving = False
                duration = self._buffered_duration_locked()
                running = self._running
            state = (
                ReplayState.READY
                if running and duration >= self._buffer_seconds - (2 / self._fps)
                else ReplayState.WARMING
                if running
                else ReplayState.IDLE
            )
            self._emit_state(state, duration if running else 0.0)
        if saved_payload:
            self._emit_replay_saved(*saved_payload)

    def _encode_video(self, frames: list[BufferedFrame]) -> tuple[str, list[Image.Image]]:
        if not frames:
            raise RuntimeError("沒有可儲存的回放影格。")
        first_image = cv2.imdecode(
            np.frombuffer(frames[0].jpeg_data, np.uint8), cv2.IMREAD_COLOR
        )
        if first_image is None:
            raise RuntimeError("緩衝影格已損毀。")
        height, width = first_image.shape[:2]
        width -= width % 2
        height -= height % 2
        if width < 2 or height < 2:
            raise RuntimeError("緩衝影格尺寸無法編碼。")

        file_path = str(
            get_recordings_dir()
            / f"maple_evidence_replay_{time.time_ns() // 1_000_000}.mp4"
        )
        container = None
        try:
            container = av.open(file_path, mode="w")
            stream = _create_optimized_h264_stream(container, width=width, height=height, fps=self._fps)

            start_time = frames[0].captured_at
            duration = max(0.0, frames[-1].captured_at - start_time)
            output_count = max(1, int(round(duration * self._fps)) + 1)
            video_duration = max(0.0, (output_count - 1) / self._fps)
            keyframe_indexes = _build_replay_keyframe_indices(
                video_duration,
                self._fps,
                output_count,
            )
            source_index = 0
            keyframes: list[Image.Image] = []

            for output_index in range(output_count):
                target_time = start_time + (output_index / self._fps)
                while (
                    source_index + 1 < len(frames)
                    and frames[source_index + 1].captured_at <= target_time
                ):
                    source_index += 1
                image = cv2.imdecode(
                    np.frombuffer(frames[source_index].jpeg_data, np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if image is None:
                    continue
                image = image[:height, :width]
                if output_index in keyframe_indexes:
                    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    keyframes.append(Image.fromarray(rgb))
                video_frame = av.VideoFrame.from_ndarray(image, format="bgr24")
                for packet in stream.encode(video_frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            return file_path, keyframes
        except Exception:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as cleanup_error:
                LOGGER.debug(
                    "清理影片編碼暫存檔失敗 (%s)", type(cleanup_error).__name__
                )
            raise
        finally:
            if container is not None:
                try:
                    container.close()
                except Exception as error:
                    LOGGER.debug("關閉回放 PyAV 容器失敗 (%s)", type(error).__name__)


__all__ = [
    "BufferedFrame",
    "ReplayBufferRecorder",
    "ReplayCaptureError",
    "ReplayState",
    "RollingAudioRecorder",
    "REPLAY_KEYFRAME_BASE_INTERVAL_SECONDS",
    "REPLAY_KEYFRAME_TAIL_WINDOW_SECONDS",
    "REPLAY_KEYFRAME_TAIL_INTERVAL_SECONDS",
    "REPLAY_KEYFRAME_MAX_COUNT",
    "_build_replay_keyframe_times",
    "_build_replay_keyframe_indices",
    "capture_monitor_frame",
    "get_audio_output_devices",
    "get_default_audio_output_name",
    "merge_audio_into_mp4",
    "_clip_monitor_to_virtual_screen",
]
