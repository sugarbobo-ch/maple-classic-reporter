"""Controller facade for replay buffering lifecycle operations."""

from __future__ import annotations

from PySide6.QtCore import QObject

from maple_reporter.recorder.replay_buffer import ReplayBufferRecorder


class ReplayController(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorder = ReplayBufferRecorder(self)

    @property
    def is_running(self) -> bool:
        return self.recorder.is_running

    def start(
        self,
        window_title: str,
        *,
        fps: int,
        buffer_seconds: int,
        record_audio: bool,
        audio_device_id: str | None,
    ) -> bool:
        return self.recorder.start(
            window_title,
            fps=fps,
            buffer_seconds=buffer_seconds,
            record_audio=record_audio,
            audio_device_id=audio_device_id,
        )

    def stop(self) -> None:
        self.recorder.stop()

    def save(self) -> bool:
        return self.recorder.save_replay()


__all__ = ["ReplayController"]
