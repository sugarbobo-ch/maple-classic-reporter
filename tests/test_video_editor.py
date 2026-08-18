"""Tests for video editor and segment trimming."""

from __future__ import annotations

import os
import tempfile
import unittest
from PIL import Image
import av

from maple_reporter.recorder.video_editor import cut_video_segment, get_video_duration


def _create_sample_video(path: str, duration_sec: int = 5, fps: int = 20) -> None:
    """Helper to create a simple MP4 video file for testing."""
    with av.open(path, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width = 320
        stream.height = 240
        stream.pix_fmt = "yuv420p"

        total_frames = duration_sec * fps
        for i in range(total_frames):
            color = (int((i / total_frames) * 255), 100, 150)
            img = Image.new("RGB", (320, 240), color=color)
            frame = av.VideoFrame.from_image(img)
            frame.pts = i
            for packet in stream.encode(frame):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)


class TestVideoEditor(unittest.TestCase):
    def test_get_video_duration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "sample.mp4")
            _create_sample_video(video_path, duration_sec=4, fps=20)

            dur = get_video_duration(video_path)
            self.assertGreaterEqual(dur, 3.5)
            self.assertLessEqual(dur, 4.5)

    def test_cut_video_segment_middle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "input.mp4")
            output_path = os.path.join(tmp_dir, "output.mp4")

            # Create 6-second video
            _create_sample_video(input_path, duration_sec=6, fps=20)
            self.assertTrue(os.path.exists(input_path))

            # Cut out 2.0 to 4.0 (2 seconds removed)
            ok = cut_video_segment(input_path, cut_start_sec=2.0, cut_end_sec=4.0, output_path=output_path)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(output_path))

            # Result should be approximately 4 seconds
            new_dur = get_video_duration(output_path)
            self.assertGreaterEqual(new_dur, 3.5)
            self.assertLessEqual(new_dur, 4.5)


if __name__ == "__main__":
    unittest.main()
