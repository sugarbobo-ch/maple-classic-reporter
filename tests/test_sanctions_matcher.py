"""Unit tests for sanction mask matching and history evaluation."""

import unittest
import unicodedata

from maple_reporter.sanctions.matcher import (
    find_matching_bulletin,
    match_masked_name,
    parse_taiwan_date,
)
from maple_reporter.sanctions.models import BulletinDetail, SanctionEntry


class TestSanctionMatcher(unittest.TestCase):
    def test_masked_name_exact_wildcard_matching(self):
        # 雲**間
        self.assertTrue(match_masked_name("雲端之間", "雲**間"))
        self.assertFalse(match_masked_name("雲間", "雲**間"))
        self.assertFalse(match_masked_name("雲端測試間", "雲**間"))

        # A**z (case sensitivity & numbers)
        self.assertTrue(match_masked_name("Ab1z", "A**z"))
        self.assertFalse(match_masked_name("ab1z", "A**z"))
        self.assertFalse(match_masked_name("Ab12z", "A**z"))

    def test_unicode_nfc_normalization(self):
        # Character with combining diacritics
        decomposed = "e\u0301"  # é decomposed (NFD)
        composed = "\u00e9"  # é precomposed (NFC)
        self.assertTrue(match_masked_name(decomposed + "test", composed + "t*st"))
        self.assertTrue(match_masked_name(composed + "test", decomposed + "t*st"))

    def test_parse_taiwan_date(self):
        self.assertEqual(
            parse_taiwan_date("2026-08-16 21:30:15"), "2026-08-16"
        )
        self.assertEqual(
            parse_taiwan_date("2026/08/17 09:00:00"), "2026-08-17"
        )
        self.assertEqual(
            parse_taiwan_date("2026-08-15T08:00:00+08:00"), "2026-08-15"
        )
        self.assertIsNone(parse_taiwan_date("invalid-date-format"))
        self.assertIsNone(parse_taiwan_date(""))

    def test_find_matching_bulletin_date_threshold_and_tie_breaking(self):
        b1 = BulletinDetail(
            bid=82420,
            publication_date="2026-08-14",
            title="0814制裁公告",
            url="http://example.com/82420",
            fetched_at="2026-08-14T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定"),),
        )
        b2 = BulletinDetail(
            bid=82425,
            publication_date="2026-08-16",
            title="0816制裁公告-1",
            url="http://example.com/82425",
            fetched_at="2026-08-16T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定"),),
        )
        b3 = BulletinDetail(
            bid=82430,
            publication_date="2026-08-16",
            title="0816制裁公告-2",
            url="http://example.com/82430",
            fetched_at="2026-08-16T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定(最新)"),),
        )

        bulletins = [b1, b2, b3]

        # Case 1: Report date is 2026-08-15. b1 (08-14) is ignored.
        # Between b2 (bid 82425) and b3 (bid 82430), same date 08-16 -> picks b3 because bid 82430 > 82425
        match = find_matching_bulletin("雲端之間", "2026-08-15", bulletins)
        self.assertIsNotNone(match)
        self.assertEqual(match.bulletin.bid, 82430)
        self.assertEqual(match.entry.result, "永久鎖定(最新)")

        # Case 2: Report date is 2026-08-17. All bulletins are prior to report date -> no match
        no_match = find_matching_bulletin("雲端之間", "2026-08-17", bulletins)
        self.assertIsNone(no_match)


if __name__ == "__main__":
    unittest.main()
