import os
import sys
import tempfile
import threading
import time
import unittest
import gc
import tracemalloc
import weakref
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath("src"))

from maple_reporter.recorder.replay_buffer import (
    BufferedFrame,
    ReplayBufferRecorder,
    RollingAudioRecorder,
    REPLAY_KEYFRAME_MAX_COUNT,
    _build_replay_keyframe_indices,
    _build_replay_keyframe_times,
    _clip_monitor_to_virtual_screen,
    capture_monitor_frame,
    get_audio_output_devices,
)
from maple_reporter.recorder.window_recorder import merge_audio_into_mp4


def jpeg_frame(value: int) -> bytes:
    image = np.full((120, 160, 3), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("Could not create test JPEG")
    return encoded.tobytes()


class TestReplayBuffer(unittest.TestCase):
    def test_replay_keyframes_sample_the_event_tail_more_densely(self):
        times = _build_replay_keyframe_times(30.0)
        tail_start = 30.0 - 5.0
        regular_times = [value for value in times if value < tail_start]
        tail_times = [value for value in times if value >= tail_start]

        self.assertLessEqual(len(times), REPLAY_KEYFRAME_MAX_COUNT)
        self.assertEqual(regular_times[:3], [0.0, 2.0, 4.0])
        self.assertEqual(tail_times[0], tail_start)
        self.assertAlmostEqual(tail_times[1] - tail_times[0], 0.5)
        self.assertAlmostEqual(tail_times[-1], 30.0)

        indices = _build_replay_keyframe_indices(30.0, fps=20, output_count=601)
        self.assertEqual(len(indices), len(times))

    def test_audio_device_list_keeps_working_when_one_endpoint_breaks(self):
        class BrokenSpeaker:
            id = "broken-id"

            @property
            def name(self):
                raise OSError("endpoint disconnected")

        soundcard = SimpleNamespace(
            all_speakers=lambda: [
                BrokenSpeaker(),
                SimpleNamespace(id="working-id", name="Bluetooth headphones"),
            ]
        )
        with patch.dict(sys.modules, {"soundcard": soundcard}):
            devices = get_audio_output_devices()

        self.assertEqual(devices, [("working-id", "Bluetooth headphones")])

    def test_audio_source_is_reported_only_after_loopback_opens(self):
        sources = []
        audio = RollingAudioRecorder(buffer_seconds=30)

        class RecorderContext:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        speaker = SimpleNamespace(id="device-id", name="Selected headphones")
        soundcard = SimpleNamespace(
            all_speakers=lambda: [speaker],
            default_speaker=lambda: speaker,
            get_microphone=lambda *_args, **_kwargs: SimpleNamespace(
                recorder=lambda **_kwargs: RecorderContext()
            ),
        )

        def source_opened(name):
            sources.append(name)
            audio._stop_event.set()

        audio.source_callback = source_opened
        with patch.dict(sys.modules, {"soundcard": soundcard}):
            audio.run()

        self.assertEqual(sources, ["Selected headphones"])

    def test_two_simulated_hours_keep_frame_memory_and_append_time_bounded(self):
        recorder = ReplayBufferRecorder()
        recorder._running = True
        recorder._buffer_seconds = 30
        fps = 30
        batch_size = 20_000

        tracemalloc.start()
        try:
            for index in range(batch_size):
                recorder._append_frame(index / fps, bytes([index % 251]) * 1024)
            gc.collect()
            memory_after_warmup = tracemalloc.get_traced_memory()[0]

            first_start = time.perf_counter()
            for index in range(batch_size, batch_size * 2):
                recorder._append_frame(index / fps, bytes([index % 251]) * 1024)
            first_batch_time = time.perf_counter() - first_start

            final_start_index = (2 * 60 * 60 * fps) - batch_size
            last_start = time.perf_counter()
            for index in range(final_start_index, final_start_index + batch_size):
                recorder._append_frame(index / fps, bytes([index % 251]) * 1024)
            last_batch_time = time.perf_counter() - last_start
            gc.collect()
            final_memory = tracemalloc.get_traced_memory()[0]
        finally:
            tracemalloc.stop()

        self.assertLessEqual(len(recorder._frames), (30 * fps) + 2)
        self.assertLessEqual(recorder._buffered_duration_locked(), 30.0)
        self.assertLess(final_memory - memory_after_warmup, 256 * 1024)
        self.assertLess(last_batch_time, (first_batch_time * 2.5) + 0.05)

    def test_audio_ring_discards_chunks_older_than_the_sliding_window(self):
        audio = RollingAudioRecorder(buffer_seconds=30, sample_rate=10)
        for index in range(36_000):
            audio._append_chunk(index / 10, np.full((1, 2), index, dtype=np.float32))

        self.assertLessEqual(len(audio._chunks), 312)
        oldest_start, _ = audio._chunks[0]
        newest_start, _ = audio._chunks[-1]
        self.assertLessEqual(newest_start - oldest_start, 31.1)

    def test_repeated_start_stop_does_not_leave_capture_threads_or_frames(self):
        recorder = ReplayBufferRecorder()

        def idle_capture_loop():
            recorder._stop_event.wait(timeout=1.0)

        with patch(
            "maple_reporter.recorder.replay_buffer.find_window_bounds",
            return_value=(0, 0, 320, 240),
        ), patch.object(recorder, "_capture_loop", side_effect=idle_capture_loop):
            for _ in range(25):
                self.assertTrue(recorder.start("game", record_audio=False))
                recorder._frames.append(BufferedFrame(time.monotonic(), b"frame"))
                recorder.stop()
                self.assertFalse(recorder._capture_thread.is_alive())
                self.assertEqual(len(recorder._frames), 0)

    def test_repeated_saved_snapshots_release_evicted_frame_objects(self):
        recorder = ReplayBufferRecorder()
        recorder._running = True
        recorder._buffer_seconds = 30
        references = []

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = str(Path(temporary_dir) / "replay.mp4")
            Path(output).touch()
            recorder._encode_video = lambda _frames: (output, [])

            for cycle in range(50):
                first = BufferedFrame(float(cycle * 2), b"first")
                second = BufferedFrame(float(cycle * 2 + 1), b"second")
                references.extend((weakref.ref(first), weakref.ref(second)))
                recorder._frames = deque((first, second))
                self.assertTrue(recorder.save_replay())
                recorder._save_thread.join(timeout=2.0)
                self.assertFalse(recorder.is_saving)
                recorder._frames.clear()

            del first, second
            gc.collect()

        self.assertEqual(sum(reference() is not None for reference in references), 0)

    def test_saved_callback_runs_from_worker_without_a_qt_event_loop(self):
        """The default pywebview UI has no Qt loop to drain queued signals."""
        saved = []
        recorder = ReplayBufferRecorder(
            replay_saved_callback=lambda file_path, keyframes: saved.append(
                (file_path, keyframes)
            )
        )
        recorder._running = True
        recorder._frames = deque(
            [BufferedFrame(1.0, b"first"), BufferedFrame(2.0, b"second")]
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = str(Path(temporary_dir) / "replay.mp4")

            def encode(_frames):
                Path(output).touch()
                return output, [Image.new("RGB", (2, 2))]

            with patch.object(recorder, "_encode_video", side_effect=encode):
                self.assertTrue(recorder.save_replay())
                recorder._save_thread.join(timeout=2.0)

            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0][0], output)
            self.assertEqual(len(saved[0][1]), 1)

    def test_capture_bounds_are_clipped_to_the_virtual_desktop(self):
        clipped = _clip_monitor_to_virtual_screen(
            {"left": -2100, "top": -20, "width": 900, "height": 700},
            {"left": -1920, "top": 0, "width": 3840, "height": 1080},
        )
        self.assertEqual(
            clipped,
            {"left": -1920, "top": 0, "width": 720, "height": 680},
        )

    def test_pillow_capture_is_used_when_windows_bitblt_fails(self):
        screen = MagicMock()
        screen.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        screen.grab.side_effect = RuntimeError(
            "Windows graphics function failed (no error provided): BitBlt"
        )
        fallback_image = Image.new("RGB", (20, 10), color=(10, 20, 30))

        with patch(
            "maple_reporter.recorder.replay_buffer.ImageGrab.grab",
            return_value=fallback_image,
        ) as fallback:
            frame, used_fallback = capture_monitor_frame(
                screen,
                {"left": 100, "top": 200, "width": 20, "height": 10},
            )

        self.assertTrue(used_fallback)
        self.assertEqual(frame.shape, (10, 20, 3))
        self.assertEqual(frame[0, 0].tolist(), [30, 20, 10])
        fallback.assert_called_once_with(
            bbox=(100, 200, 120, 210), all_screens=True
        )

    def test_snapshot_encodes_real_time_duration_and_keyframes(self):
        recorder = ReplayBufferRecorder()
        recorder._fps = 5
        frames = [BufferedFrame(index / 5, jpeg_frame(index * 10)) for index in range(11)]

        with tempfile.TemporaryDirectory() as temporary_dir, patch(
            "maple_reporter.recorder.replay_buffer.get_recordings_dir",
            return_value=Path(temporary_dir),
        ):
            file_path, keyframes = recorder._encode_video(frames)
            capture = cv2.VideoCapture(file_path)
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = capture.get(cv2.CAP_PROP_FPS)
            capture.release()

            self.assertEqual(frame_count, 11)
            self.assertAlmostEqual(frame_count / fps, 2.2, delta=0.25)
            # A short replay is entirely inside the event tail, so screenshots
            # are sampled every 0.5 seconds instead of every 2 seconds.
            self.assertEqual(len(keyframes), 5)

    def test_replay_video_can_be_remuxed_with_an_aac_audio_track(self):
        recorder = ReplayBufferRecorder()
        recorder._fps = 10
        frames = [
            BufferedFrame(index / 10, jpeg_frame(index * 5))
            for index in range(31)
        ]
        sample_rate = 44100
        samples = np.arange(int(3.1 * sample_rate), dtype=np.float32)
        tone = 0.2 * np.sin(2 * np.pi * 440 * samples / sample_rate)
        audio_data = np.column_stack((tone, tone)).astype(np.float32)

        with tempfile.TemporaryDirectory() as temporary_dir, patch(
            "maple_reporter.recorder.replay_buffer.get_recordings_dir",
            return_value=Path(temporary_dir),
        ):
            file_path, _keyframes = recorder._encode_video(frames)
            self.assertTrue(
                merge_audio_into_mp4(file_path, audio_data, sample_rate)
            )
            container = __import__("av").open(file_path)
            try:
                self.assertEqual(len(container.streams.video), 1)
                self.assertEqual(len(container.streams.audio), 1)
                self.assertEqual(container.streams.audio[0].codec_context.name, "aac")
            finally:
                container.close()

    def test_only_one_snapshot_can_be_saved_at_a_time(self):
        recorder = ReplayBufferRecorder()
        recorder._running = True
        recorder._buffer_seconds = 30
        recorder._frames = deque(
            [BufferedFrame(1.0, b"a"), BufferedFrame(2.0, b"b")]
        )
        release_encode = threading.Event()

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = str(Path(temporary_dir) / "replay.mp4")

            def delayed_encode(_frames):
                release_encode.wait(timeout=2.0)
                Path(output).touch()
                return output, []

            with patch.object(recorder, "_encode_video", side_effect=delayed_encode):
                self.assertTrue(recorder.save_replay())
                self.assertFalse(recorder.save_replay())
                release_encode.set()
                recorder._save_thread.join(timeout=2.0)

        self.assertFalse(recorder.is_saving)


if __name__ == "__main__":
    unittest.main()
