"""Shared Windows loopback audio capture and MP4 muxing helpers.

Both the short recorder and the replay buffer use this module so device
selection, bounded buffering, shutdown, and AAC muxing cannot drift apart.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from fractions import Fraction
from typing import Callable, Deque, Optional

import numpy as np


LOGGER = logging.getLogger(__name__)
DEFAULT_SAMPLE_RATE = 44_100
_SILENCE_THRESHOLD = 1e-5


class AudioCaptureError(RuntimeError):
    """Raised when a selected Windows playback endpoint cannot be opened."""


def _load_soundcard():
    try:
        import soundcard as soundcard_module
    except Exception as error:  # pragma: no cover - depends on the host image
        raise AudioCaptureError("系統聲音擷取元件無法載入。") from error
    return soundcard_module


def _resolve_speaker(soundcard_module, device_id: str | None = None):
    if device_id:
        for speaker in soundcard_module.all_speakers():
            try:
                if str(speaker.id) == str(device_id):
                    return speaker
            except Exception as error:
                LOGGER.debug("略過無法讀取的音訊端點 (%s)", type(error).__name__)
        raise AudioCaptureError("選取的音訊輸出裝置目前不可用，可能已中途斷線。")

    speaker = soundcard_module.default_speaker()
    if speaker is None:
        raise AudioCaptureError("Windows 沒有可用的預設音訊輸出裝置。")
    return speaker


def get_audio_output_devices() -> list[tuple[str, str]]:
    """Enumerate current Windows playback endpoints as ``(id, name)`` pairs."""

    try:
        soundcard_module = _load_soundcard()
        devices: list[tuple[str, str]] = []
        seen: set[str] = set()
        for speaker in soundcard_module.all_speakers():
            try:
                device_id = str(speaker.id).strip()
                device_name = str(speaker.name).strip()
                if not device_id or not device_name or device_id in seen:
                    continue
                seen.add(device_id)
                devices.append((device_id, device_name))
            except Exception as error:
                # A Bluetooth endpoint can disappear while it is being read.
                LOGGER.warning(
                    "略過無法讀取的音訊裝置 (%s)", type(error).__name__
                )
        return devices
    except AudioCaptureError:
        return []
    except Exception as error:
        LOGGER.warning("列舉音訊輸出裝置失敗 (%s)", type(error).__name__)
        return []


def get_default_audio_output_name() -> str:
    """Return the current default playback endpoint name."""

    try:
        speaker = _resolve_speaker(_load_soundcard())
        name = str(speaker.name).strip()
        return name or "Windows 預設裝置"
    except Exception as error:
        LOGGER.warning("讀取預設音訊裝置失敗 (%s)", type(error).__name__)
        return "Windows 預設裝置"


class LoopbackAudioRecorder(threading.Thread):
    """Capture a bounded WASAPI loopback window from one playback endpoint."""

    def __init__(
        self,
        buffer_seconds: float,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        device_id: str | None = None,
        error_callback: Optional[Callable[[str], None]] = None,
        source_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True)
        self.buffer_seconds = max(1.0, float(buffer_seconds))
        self.sample_rate = max(8_000, int(sample_rate))
        self.device_id = str(device_id) if device_id else None
        self.error_callback = error_callback
        self.source_callback = source_callback
        self._chunks: Deque[tuple[float, np.ndarray]] = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._error_message: str | None = None
        self._opened = threading.Event()

    @property
    def opened(self) -> bool:
        return self._opened.is_set()

    @property
    def error_message(self) -> str | None:
        return self._error_message

    def run(self) -> None:
        try:
            soundcard_module = _load_soundcard()
            speaker = _resolve_speaker(soundcard_module, self.device_id)
            microphone = soundcard_module.get_microphone(
                speaker.id, include_loopback=True
            )
            with microphone.recorder(samplerate=self.sample_rate) as recorder:
                self._opened.set()
                if self.source_callback:
                    try:
                        self.source_callback(str(speaker.name))
                    except Exception as error:
                        LOGGER.debug(
                            "音訊來源通知失敗 (%s)", type(error).__name__
                        )

                while not self._stop_event.is_set():
                    try:
                        data = recorder.record(
                            numframes=int(self.sample_rate * 0.1)
                        )
                    except Exception as error:
                        raise AudioCaptureError(
                            "選取的音訊輸出裝置在錄製途中失效。"
                        ) from error

                    if data is None or len(data) == 0:
                        # Bluetooth devices may return empty buffers while they
                        # wake up. Keep the capture alive and let the save path
                        # decide whether the requested window had usable audio.
                        continue
                    array = np.asarray(data, dtype=np.float32)
                    if array.ndim == 1:
                        array = array[:, None]
                    if array.ndim != 2 or array.shape[1] == 0:
                        LOGGER.debug("忽略格式不符的音訊緩衝")
                        continue
                    array = np.ascontiguousarray(np.nan_to_num(array))
                    chunk_end = time.monotonic()
                    chunk_start = chunk_end - (len(array) / self.sample_rate)
                    self._append_chunk(chunk_start, array)
        except AudioCaptureError as error:
            self._report_error(str(error))
        except Exception as error:  # pragma: no cover - host API dependent
            LOGGER.warning("WASAPI loopback 錄製失敗 (%s)", type(error).__name__)
            self._report_error("系統聲音錄製失敗，請重新選擇音訊輸出來源。")

    def _report_error(self, message: str) -> None:
        self._error_message = message
        if self.error_callback:
            try:
                self.error_callback(message)
            except Exception as error:
                LOGGER.debug("音訊錯誤通知失敗 (%s)", type(error).__name__)

    def _append_chunk(self, chunk_start: float, data: np.ndarray) -> None:
        chunk_end = chunk_start + (len(data) / self.sample_rate)
        with self._lock:
            self._chunks.append((chunk_start, data.copy()))
            cutoff = chunk_end - self.buffer_seconds - 1.0
            while self._chunks:
                start, chunk = self._chunks[0]
                if start + (len(chunk) / self.sample_rate) >= cutoff:
                    break
                self._chunks.popleft()

    def snapshot(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> np.ndarray | None:
        """Copy samples overlapping the requested monotonic-time window."""

        with self._lock:
            chunks = list(self._chunks)
        if not chunks:
            return None

        if start_time is None:
            start_time = chunks[0][0]
        if end_time is None:
            last_start, last_data = chunks[-1]
            end_time = last_start + len(last_data) / self.sample_rate

        selected: list[np.ndarray] = []
        for chunk_start, data in chunks:
            chunk_end = chunk_start + (len(data) / self.sample_rate)
            overlap_start = max(start_time, chunk_start)
            overlap_end = min(end_time, chunk_end)
            if overlap_end <= overlap_start:
                continue
            first = max(
                0, int(round((overlap_start - chunk_start) * self.sample_rate))
            )
            last = min(
                len(data), int(round((overlap_end - chunk_start) * self.sample_rate))
            )
            if last > first:
                selected.append(data[first:last].copy())

        if not selected:
            return None
        return np.vstack(selected)

    def stop(self, *, clear: bool = True) -> None:
        self._stop_event.set()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=2.0)
        if self.is_alive():
            LOGGER.warning("音訊錄製執行緒在停止期限內仍未結束")
        if clear:
            with self._lock:
                self._chunks.clear()

    def stop_and_get_data(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> np.ndarray | None:
        data = self.snapshot(start_time, end_time)
        self.stop(clear=True)
        return data


def has_audio_signal(audio_data: np.ndarray | None) -> bool:
    """Return whether a captured window contains more than digital silence."""

    if audio_data is None or len(audio_data) == 0:
        return False
    try:
        return bool(np.max(np.abs(audio_data)) >= _SILENCE_THRESHOLD)
    except (TypeError, ValueError):
        return False


def merge_audio_into_mp4(
    video_path: str | os.PathLike[str],
    audio_data: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> bool:
    """Remux an existing H.264 MP4 with a new AAC audio track.

    The video packets are copied without re-encoding. The temporary output is
    created beside the source and atomically replaces it only after both tracks
    have been flushed successfully.
    """

    source_path = Path(video_path)
    if audio_data is None or not source_path.is_file():
        return False

    array = np.asarray(audio_data, dtype=np.float32)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or len(array) == 0 or array.shape[1] == 0:
        return False
    array = np.ascontiguousarray(np.nan_to_num(array, copy=False))
    if array.shape[1] > 2:
        array = np.ascontiguousarray(array[:, :2])

    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{source_path.stem}.audio-", suffix=".mp4", dir=source_path.parent
    )
    os.close(temp_fd)
    temp_path = Path(temp_name)
    input_container = None
    output_container = None
    try:
        import av

        input_container = av.open(str(source_path), mode="r")
        if not input_container.streams.video:
            return False
        input_video = input_container.streams.video[0]
        output_container = av.open(str(temp_path), mode="w")
        source_rate = input_video.average_rate or input_video.base_rate or 20
        output_video = output_container.add_stream("h264", rate=source_rate)
        output_video.width = int(input_video.width)
        output_video.height = int(input_video.height)
        output_video.pix_fmt = "yuv420p"
        output_video.options = {"crf": "23", "preset": "veryfast"}
        channels = int(array.shape[1])
        layout = "stereo" if channels == 2 else "mono"
        # Add every output stream before the first packet writes the MP4
        # header; PyAV cannot assign a time base to a stream added afterwards.
        output_audio = output_container.add_stream("aac", rate=int(sample_rate))
        output_audio.layout = layout

        # Re-encode decoded frames with a fresh zero-based timeline. Some MP4
        # sources have a non-zero start timestamp; packet remuxing those into a
        # newly-created container makes PyAV reject the output as "zero time".
        frame_index = 0
        for decoded_frame in input_container.decode(input_video):
            video_frame = decoded_frame.reformat(
                width=output_video.width,
                height=output_video.height,
                format="yuv420p",
            )
            video_frame.pts = frame_index
            video_frame.time_base = Fraction(1, int(round(float(source_rate))))
            frame_index += 1
            for packet in output_video.encode(video_frame):
                output_container.mux(packet)
        for packet in output_video.encode():
            output_container.mux(packet)
        input_container.close()
        input_container = None

        samples_per_frame = 1024
        interleaved = np.ascontiguousarray(array.T, dtype=np.float32)
        for offset in range(0, interleaved.shape[1], samples_per_frame):
            chunk = interleaved[:, offset : offset + samples_per_frame]
            if chunk.shape[1] < samples_per_frame:
                padding = np.zeros(
                    (channels, samples_per_frame - chunk.shape[1]), dtype=np.float32
                )
                chunk = np.hstack((chunk, padding))
            frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout=layout)
            frame.rate = int(sample_rate)
            # Let the AAC encoder assign a valid stream time base. Manually
            # assigning timestamps before the output header is written can
            # produce PyAV's "Cannot rebase to zero time" error.
            frame.pts = None
            for packet in output_audio.encode(frame):
                if output_audio.time_base is None:
                    output_audio.time_base = packet.time_base
                packet.stream = output_audio
                output_container.mux(packet)

        for packet in output_audio.encode():
            if output_audio.time_base is None:
                output_audio.time_base = packet.time_base
            packet.stream = output_audio
            output_container.mux(packet)
        output_container.close()
        output_container = None

        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            return False
        os.replace(temp_path, source_path)
        return True
    except Exception as error:  # pragma: no cover - codec availability varies
        LOGGER.warning(
            "MP4 audio mux failed (%s: %s)",
            source_path.name,
            type(error).__name__,
        )
        return False
    finally:
        if input_container is not None:
            try:
                input_container.close()
            except Exception as error:
                LOGGER.debug("關閉輸入影音容器失敗 (%s)", type(error).__name__)
        if output_container is not None:
            try:
                output_container.close()
            except Exception as error:
                LOGGER.debug("關閉輸出影音容器失敗 (%s)", type(error).__name__)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as error:
            LOGGER.warning("清理暫存影音檔失敗 (%s: %s)", temp_path.name, type(error).__name__)


__all__ = [
    "AudioCaptureError",
    "DEFAULT_SAMPLE_RATE",
    "LoopbackAudioRecorder",
    "get_audio_output_devices",
    "get_default_audio_output_name",
    "has_audio_signal",
    "merge_audio_into_mp4",
]
