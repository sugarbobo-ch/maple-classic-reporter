import unittest
import os
import sys
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

if __name__ == "__main__":
    unittest.main()
