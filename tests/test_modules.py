import unittest
import os
import sys
import time
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, os.path.abspath("src"))

from maple_reporter.utils.config import load_config, save_config
from maple_reporter.ocr.win_ocr import (
    recognize_map_name_from_image_list,
    recognize_text_from_image,
)
from maple_reporter.recorder.window_recorder import get_active_window_titles
from maple_reporter.ocr.map_catalog import normalize_map_name, resolve_map_name
from maple_reporter.ocr.win_ocr import _clean_map_ocr_text

class TestMapleReporter(unittest.TestCase):
    def test_config(self):
        cfg = load_config()
        self.assertIn("default_server", cfg)
        self.assertNotIn("gemini_api_key", cfg)

    def test_window_list(self):
        titles = get_active_window_titles()
        self.assertIsInstance(titles, list)

    def test_ocr_mock_image(self):
        img = Image.new("RGB", (100, 30), color="white")
        res = recognize_text_from_image(img)
        self.assertIsInstance(res, str)

    def test_ocr_worker_releases_large_keyframes_after_use(self):
        from maple_reporter.ocr.ocr_worker import OcrWorkerThread

        frames = [Image.new("RGB", (320, 240), color="white") for _ in range(10)]
        worker = OcrWorkerThread(frames)
        self.assertEqual(len(worker.keyframes), 10)
        worker.release_keyframes()
        self.assertEqual(worker.keyframes, [])

    def test_ocr_worker_keeps_detected_map_for_preview_fallback(self):
        from maple_reporter.ocr.ocr_worker import OcrWorkerThread

        with patch(
            "maple_reporter.ocr.ocr_worker.recognize_map_name_from_image_list",
            return_value="童話村",
        ), patch(
            "maple_reporter.ocr.ocr_worker.recognize_candidates_from_image_list",
            return_value=[],
        ):
            worker = OcrWorkerThread([Image.new("RGB", (320, 240))])
            worker.run()

        self.assertEqual(worker.detected_map_name, "童話村")

    def test_map_name_catalog_normalizes_roman_numerals(self):
        self.assertEqual(normalize_map_name("海岸草叢Ⅰ"), normalize_map_name("海岸草叢I"))
        self.assertEqual(resolve_map_name("海岸草叢I"), "海岸草叢Ⅰ")

    def test_map_name_catalog_converts_simplified_ocr_text(self):
        self.assertEqual(resolve_map_name("弓箭手訓练场I"), "弓箭手訓練場Ⅰ")

    def test_map_name_catalog_rejects_unrelated_text(self):
        self.assertIsNone(resolve_map_name("這不是新楓之谷地圖"))
        self.assertIsNone(resolve_map_name("小地国"))

    def test_minimap_map_text_cleans_training_ground_and_roman_numeral(self):
        self.assertEqual(_clean_map_ocr_text("南部森林訓辣場！"), "南部森林訓練場Ⅰ")

    def test_minimap_map_name_accepts_a_single_detected_map_line(self):
        def bbox(y):
            return [[0, y], [80, y], [80, y + 8], [0, y + 8]]

        ocr_results = [
            (bbox(0), "小地圖", 0.99),
            (bbox(8), "弓箭手訓练场I", 0.92),
        ]
        with patch("maple_reporter.ocr.win_ocr.HAS_RAPID_OCR", True), patch(
            "maple_reporter.ocr.win_ocr.RAPID_OCR_ENGINE",
            return_value=(ocr_results, None),
        ):
            self.assertEqual(
                recognize_map_name_from_image_list([Image.new("RGB", (640, 480))]),
                "弓箭手訓練場Ⅰ",
            )

    def test_is_valid_suspect_id_accepts_names_containing_ch_or_lv(self):
        from maple_reporter.ocr.win_ocr import is_valid_suspect_id
        self.assertTrue(is_valid_suspect_id("Charles"))
        self.assertTrue(is_valid_suspect_id("Richard"))
        self.assertTrue(is_valid_suspect_id("Oliver"))
        self.assertTrue(is_valid_suspect_id("NewType"))
        self.assertFalse(is_valid_suspect_id("ch"))
        self.assertFalse(is_valid_suspect_id("lv"))
        self.assertFalse(is_valid_suspect_id("新楓之谷"))

    def test_record_short_video_cancel(self):
        from maple_reporter.recorder.window_recorder import record_short_video
        file_path, keyframes = record_short_video(
            "non_existent_window_1234567",
            duration_sec=3,
            fps=15,
            cancel_checker=lambda: True
        )
        self.assertIsNone(file_path)
        self.assertEqual(keyframes, [])

    def test_record_short_video_duration_and_speed(self):
        import cv2
        import time
        from maple_reporter.recorder.window_recorder import record_short_video

        target_duration = 2
        fps = 15
        start = time.time()
        with patch(
            "maple_reporter.recorder.window_recorder.find_window_bounds",
            return_value=(0, 0, 320, 240),
        ):
            file_path, keyframes = record_short_video(
                "test-window",
                duration_sec=target_duration,
                fps=fps,
                record_audio=False,
            )
        elapsed = time.time() - start
        self.assertIsNotNone(file_path)
        self.assertTrue(os.path.exists(file_path))

        cap = cv2.VideoCapture(file_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        recorded_video_duration = frame_count / video_fps
        # Verify video duration is close to actual elapsed real time (within 0.3s)
        self.assertAlmostEqual(recorded_video_duration, target_duration, delta=0.4)
        self.assertAlmostEqual(recorded_video_duration, elapsed, delta=0.4)

        if os.path.exists(file_path):
            os.remove(file_path)

    def test_auto_delete_config_and_recordings_cleanup(self):
        from maple_reporter.utils.config import load_config, get_recordings_dir
        cfg = load_config()
        self.assertIn("auto_delete_after_upload", cfg)
        self.assertIn("record_audio", cfg)

        rec_dir = get_recordings_dir()
        test_file = rec_dir / f"test_dummy_{int(time.time())}.txt"
        test_file.write_text("test")
        self.assertTrue(test_file.exists())

        # Cleanup dummy file
        test_file.unlink()
        self.assertFalse(test_file.exists())

    def test_audio_merge_helper(self):
        import cv2
        import numpy as np
        from maple_reporter.recorder.window_recorder import merge_audio_into_mp4
        from maple_reporter.utils.config import get_recordings_dir

        rec_dir = get_recordings_dir()
        vpath = str(rec_dir / f"test_v_merge_{int(time.time())}.mp4")

        # Create 1 second video using PyAV for cross-platform CI compatibility
        import av
        container = av.open(vpath, mode='w')
        stream = container.add_stream('h264', rate=20)
        stream.width = 320
        stream.height = 240
        stream.pix_fmt = 'yuv420p'

        for i in range(20):
            img = np.full((240, 320, 3), (i * 10) % 255, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(img, format='bgr24')
            frame = frame.reformat(format='yuv420p')
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()

        sr = 44100
        t = np.linspace(0, 1, sr)
        audio_data = np.column_stack((0.3 * np.sin(2 * np.pi * 440 * t), 0.3 * np.sin(2 * np.pi * 440 * t))).astype(np.float32)

        res = merge_audio_into_mp4(vpath, audio_data, sample_rate=sr)
        self.assertTrue(res)
        self.assertTrue(os.path.exists(vpath))

        if os.path.exists(vpath):
            os.remove(vpath)

    def test_version_string_matches_pyproject(self):
        import re
        from maple_reporter import __version__
        pyproject_path = os.path.abspath("pyproject.toml")
        if os.path.exists(pyproject_path):
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                self.assertEqual(__version__, match.group(1))

if __name__ == "__main__":
    unittest.main()
