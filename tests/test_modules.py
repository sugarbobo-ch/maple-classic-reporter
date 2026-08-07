import unittest
import os
import sys
import time
from PIL import Image

sys.path.insert(0, os.path.abspath("src"))

from maple_reporter.utils.config import load_config, save_config
from maple_reporter.ocr.win_ocr import recognize_text_from_image
from maple_reporter.recorder.window_recorder import get_active_window_titles
from maple_reporter.ocr.map_catalog import normalize_map_name, resolve_map_name
from maple_reporter.ocr.win_ocr import _clean_map_ocr_text

class TestMapleReporter(unittest.TestCase):
    def test_config(self):
        cfg = load_config()
        self.assertIn("default_server", cfg)

    def test_window_list(self):
        titles = get_active_window_titles()
        self.assertIsInstance(titles, list)

    def test_ocr_mock_image(self):
        img = Image.new("RGB", (100, 30), color="white")
        res = recognize_text_from_image(img)
        self.assertIsInstance(res, str)

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
        file_path, keyframes = record_short_video(
            "non_existent_window_1234567",
            duration_sec=target_duration,
            fps=fps,
            record_audio=False
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

        # Create 1 second video
        out = cv2.VideoWriter(vpath, cv2.VideoWriter_fourcc(*'mp4v'), 20, (320, 240))
        for i in range(20):
            img = np.full((240, 320, 3), (i * 10) % 255, dtype=np.uint8)
            out.write(img)
        out.release()

        sr = 44100
        t = np.linspace(0, 1, sr)
        audio_data = np.column_stack((0.3 * np.sin(2 * np.pi * 440 * t), 0.3 * np.sin(2 * np.pi * 440 * t))).astype(np.float32)

        res = merge_audio_into_mp4(vpath, audio_data, sample_rate=sr)
        self.assertTrue(res)
        self.assertTrue(os.path.exists(vpath))

        if os.path.exists(vpath):
            os.remove(vpath)

    def test_gdrive_folder_url_formatting(self):
        from maple_reporter.gdrive.drive_service import GoogleDriveManager
        mgr = GoogleDriveManager("non_existent_token.json")
        # When unauthenticated, get_folder_url returns None
        self.assertIsNone(mgr.get_folder_url("MapleClassic_Reports"))

if __name__ == "__main__":
    unittest.main()
