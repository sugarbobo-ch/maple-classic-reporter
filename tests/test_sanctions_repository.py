"""Unit tests for SanctionRepository persistence, cache schema, and history evaluation."""

import json
import tempfile
import unittest
from pathlib import Path

from maple_reporter.sanctions.models import (
    BulletinDetail,
    DateCacheEntry,
    SanctionCache,
    SanctionEntry,
)
from maple_reporter.sanctions.repository import SanctionRepository


class TestSanctionRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.cache_path = Path(self.temp_dir.name) / "sanction_cache.json"
        self.history_path = Path(self.temp_dir.name) / "history.json"
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.repo = SanctionRepository(
            cache_path=self.cache_path,
            history_path=self.history_path,
            db_path=self.db_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_and_save_cache(self):
        cache = SanctionCache(
            schema_version=1,
            bootstrap_start_date="2026-07-19",
            last_complete_sync_at="2026-08-17T12:00:00+08:00",
            dates={
                "2026-08-17": DateCacheEntry(
                    state="mutable",
                    last_success_at="2026-08-17T12:00:00+08:00",
                    bulletin_ids=[82430],
                )
            },
            bulletins={
                "82430": BulletinDetail(
                    bid=82430,
                    publication_date="2026-08-17",
                    title="0817公告",
                    url="http://example.com/82430",
                    fetched_at="2026-08-17T12:00:00+08:00",
                    entries=(SanctionEntry("雲**間", "永久鎖定"),),
                )
            },
        )
        self.repo.save_cache(cache)

        loaded = self.repo.load_cache()
        self.assertEqual(loaded.schema_version, 1)
        self.assertEqual(loaded.bootstrap_start_date, "2026-07-19")
        self.assertIn("2026-08-17", loaded.dates)
        self.assertEqual(loaded.dates["2026-08-17"].bulletin_ids, [82430])
        self.assertIn("82430", loaded.bulletins)
        self.assertEqual(loaded.bulletins["82430"].entries[0].masked_name, "雲**間")

    def test_corrupted_cache_fallback(self):
        self.cache_path.write_text("invalid json contents", encoding="utf-8")
        loaded = self.repo.load_cache()
        self.assertEqual(loaded.schema_version, 1)
        self.assertEqual(len(loaded.bulletins), 0)

    def test_history_record_id_migration(self):
        legacy_data = [
            {"time": "2026-08-16 12:00:00", "suspect_id": "Player1", "status": "成功"},
            {"time": "2026-08-16 13:00:00", "suspect_id": "Player2", "status": "成功"},
        ]
        self.history_path.write_text(json.dumps(legacy_data), encoding="utf-8")

        loaded = self.repo.load_history()
        self.assertEqual(len(loaded), 2)
        self.assertTrue(bool(loaded[0].get("record_id")))
        self.assertTrue(bool(loaded[1].get("record_id")))
        self.assertNotEqual(loaded[0]["record_id"], loaded[1]["record_id"])

    def test_add_history_entry_evaluates_against_cache(self):
        # Setup cache with a banned entry
        b = BulletinDetail(
            bid=82430,
            publication_date="2026-08-17",
            title="0817公告",
            url="http://example.com/82430",
            fetched_at="2026-08-17T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定"),),
        )
        cache = SanctionCache(
            schema_version=1,
            last_complete_sync_at="2026-08-17T12:00:00+08:00",
            bulletins={"82430": b},
        )
        self.repo.save_cache(cache)

        # 1. Matching suspect -> banned
        entry1 = self.repo.add_history_entry(
            {"time": "2026-08-16 10:00:00", "suspect_id": "雲端之間"}
        )
        self.assertEqual(entry1["ban_status"], "banned")
        self.assertEqual(entry1["ban_result"], "永久鎖定")
        self.assertEqual(entry1["ban_date"], "2026-08-17")

        # 2. Non-matching suspect with covered report date -> unbanned
        entry2 = self.repo.add_history_entry(
            {"time": "2026-08-16 11:00:00", "suspect_id": "普通玩家"}
        )
        self.assertEqual(entry2["ban_status"], "unbanned")

    def test_commit_sync_progress_partial_vs_complete(self):
        b = BulletinDetail(
            bid=82430,
            publication_date="2026-08-17",
            title="0817公告",
            url="http://example.com/82430",
            fetched_at="2026-08-17T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定"),),
        )
        cache = SanctionCache(
            schema_version=1,
            bulletins={"82430": b},
        )

        history = [
            {"record_id": "1", "time": "2026-08-16 10:00:00", "suspect_id": "雲端之間", "ban_status": "pending"},
            {"record_id": "2", "time": "2026-08-16 11:00:00", "suspect_id": "普通玩家", "ban_status": "pending"},
        ]
        self.repo.save_history(history)

        # Partial sync commit: only applies banned hit; does not turn non-matching to unbanned
        summary_partial, recs_partial = self.repo.commit_sync_progress(
            cache=cache, is_complete=False, failed_requests_count=1
        )
        self.assertFalse(summary_partial.completed)
        self.assertEqual(summary_partial.newly_banned_count, 1)
        self.assertEqual(recs_partial[0]["ban_status"], "banned")
        self.assertEqual(recs_partial[1]["ban_status"], "pending")

        # Complete sync commit: now updates non-matching to unbanned
        summary_complete, recs_complete = self.repo.commit_sync_progress(
            cache=cache, is_complete=True, failed_requests_count=0
        )
        self.assertTrue(summary_complete.completed)
        self.assertEqual(summary_complete.changed_to_unbanned_count, 1)
        self.assertEqual(recs_complete[0]["ban_status"], "banned")
        self.assertEqual(recs_complete[1]["ban_status"], "unbanned")

    def test_clear_history_preserves_sanction_cache(self):
        cache = SanctionCache(
            schema_version=1,
            last_complete_sync_at="2026-08-17T12:00:00+08:00",
        )
        self.repo.save_cache(cache)
        self.repo.save_history([{"record_id": "1", "time": "2026-08-16", "suspect_id": "P1"}])

        self.repo.clear_history()

        self.assertEqual(len(self.repo.load_history()), 0)
        loaded_cache = self.repo.load_cache()
        self.assertEqual(loaded_cache.last_complete_sync_at, "2026-08-17T12:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
