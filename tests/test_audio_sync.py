import os
import sys
import tempfile
import unittest
from pathlib import Path

import av
import numpy as np


sys.path.insert(0, os.path.abspath("src"))

from maple_reporter.recorder.audio_capture import (
    LoopbackAudioRecorder,
    merge_audio_into_mp4,
)


class TestAudioVideoSync(unittest.TestCase):
    def test_snapshot_preserves_late_audio_start_on_video_timeline(self):
        recorder = LoopbackAudioRecorder(buffer_seconds=30, sample_rate=8_000)
        recorder._append_chunk(100.2, np.ones((6_400, 2), dtype=np.float32))

        snapshot = recorder.snapshot(start_time=100.0, end_time=101.0)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.shape, (8_000, 2))
        np.testing.assert_array_equal(snapshot[:1_600], np.zeros((1_600, 2)))
        np.testing.assert_array_equal(snapshot[1_600:], np.ones((6_400, 2)))

    def test_snapshot_preserves_internal_and_trailing_capture_gaps(self):
        recorder = LoopbackAudioRecorder(buffer_seconds=30, sample_rate=8_000)
        recorder._append_chunk(100.0, np.ones((2_400, 2), dtype=np.float32))
        recorder._append_chunk(100.5, np.full((2_400, 2), 2.0, dtype=np.float32))

        snapshot = recorder.snapshot(start_time=100.0, end_time=101.0)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.shape, (8_000, 2))
        np.testing.assert_array_equal(snapshot[:2_400], np.ones((2_400, 2)))
        np.testing.assert_array_equal(
            snapshot[2_400:4_000], np.zeros((1_600, 2))
        )
        np.testing.assert_array_equal(
            snapshot[4_000:6_400], np.full((2_400, 2), 2.0)
        )
        np.testing.assert_array_equal(snapshot[6_400:], np.zeros((1_600, 2)))

    def test_stop_waits_for_the_pending_capture_chunk_before_snapshot(self):
        recorder = LoopbackAudioRecorder(buffer_seconds=30, sample_rate=8_000)

        def finish_pending_chunk():
            recorder._stop_event.wait(timeout=1.0)
            recorder._append_chunk(
                100.0, np.ones((8_000, 2), dtype=np.float32)
            )

        recorder.run = finish_pending_chunk
        recorder.start()

        snapshot = recorder.stop_and_get_data(start_time=100.0, end_time=101.0)

        self.assertIsNotNone(snapshot)
        np.testing.assert_array_equal(snapshot, np.ones((8_000, 2)))

    def test_muxed_streams_keep_the_same_timeline_when_audio_starts_late(self):
        sample_rate = 44_100
        recorder = LoopbackAudioRecorder(
            buffer_seconds=30, sample_rate=sample_rate
        )
        recorder._append_chunk(
            100.2,
            np.ones((int(0.8 * sample_rate), 2), dtype=np.float32),
        )
        audio = recorder.snapshot(start_time=100.0, end_time=101.0)
        self.assertIsNotNone(audio)

        with tempfile.TemporaryDirectory() as temporary_dir:
            video_path = Path(temporary_dir) / "late-audio.mp4"
            with av.open(str(video_path), mode="w") as container:
                stream = container.add_stream("h264", rate=10)
                stream.width = 64
                stream.height = 64
                stream.pix_fmt = "yuv420p"
                for _ in range(10):
                    frame = av.VideoFrame.from_ndarray(
                        np.zeros((64, 64, 3), dtype=np.uint8), format="bgr24"
                    )
                    for packet in stream.encode(frame):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)

            self.assertTrue(
                merge_audio_into_mp4(video_path, audio, sample_rate=sample_rate)
            )
            with av.open(str(video_path)) as container:
                video_stream = container.streams.video[0]
                audio_stream = container.streams.audio[0]
                video_start = float(
                    (video_stream.start_time or 0) * video_stream.time_base
                )
                audio_start = float(
                    (audio_stream.start_time or 0) * audio_stream.time_base
                )
                video_duration = float(
                    video_stream.duration * video_stream.time_base
                )
                audio_duration = float(
                    audio_stream.duration * audio_stream.time_base
                )

            self.assertEqual(video_start, 0.0)
            self.assertEqual(audio_start, 0.0)
            self.assertAlmostEqual(audio_duration, video_duration, delta=0.05)

    def test_continuous_capture_preserves_waveform_smoothness_without_jitter_gaps(self):
        sample_rate = 48_000
        freq = 440.0
        total_samples = 48_000
        t = np.arange(total_samples) / sample_rate
        sine_wave = np.sin(2 * np.pi * freq * t, dtype=np.float32)[:, None]
        sine_wave = np.repeat(sine_wave, 2, axis=1)

        recorder = LoopbackAudioRecorder(buffer_seconds=30, sample_rate=sample_rate)

        # Simulate continuous stream recording chunks with thread scheduling jitter
        anchor = 100.0
        samples_recorded = 0
        chunk_size = 4_800
        for i in range(10):
            chunk_data = sine_wave[i * chunk_size : (i + 1) * chunk_size]
            # calculate start time using the continuous timeline formula
            chunk_start = anchor + (samples_recorded / sample_rate)
            samples_recorded += len(chunk_data)
            recorder._append_chunk(chunk_start, chunk_data)

        snapshot = recorder.snapshot(start_time=100.0, end_time=101.0)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.shape, (48_000, 2))

        # Check that there are no silence dropouts / zero runs created by jitter
        zero_runs = (snapshot[:, 0] == 0)
        self.assertLessEqual(np.sum(zero_runs), 2)  # only pure zero crossings of 440Hz sine

        # Check maximum differential: 440Hz sine max diff at 48kHz is ~0.0576
        diffs = np.abs(np.diff(snapshot[:, 0]))
        self.assertLess(np.max(diffs), 0.065)


if __name__ == "__main__":
    unittest.main()

