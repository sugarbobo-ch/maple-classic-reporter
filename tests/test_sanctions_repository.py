"""Unit tests for SanctionRepository persistence, cache schema, and history evaluation."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from maple_reporter.sanctions.models import (
    BulletinDetail,
    DateCacheEntry,
    SanctionCache,
    SanctionEntry,
)
from maple_reporter.sanctions.repository import SANCTION_PARSER_REVISION, SanctionRepository
from maple_reporter.sanctions.parser import parse_sanction_html_table


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

    def test_old_parser_cache_is_refetched_without_losing_history(self):
        self.test_load_and_save_cache()
        record = self.repo.add_history_entry({'suspect_id': 'TestID', 'status': '成功'})
        self.repo.db.set_meta('parser_revision', '')
        loaded = self.repo.load_cache()
        self.assertFalse(loaded.bulletins)
        self.assertFalse(loaded.dates)
        self.assertFalse(loaded.last_complete_sync_at)
        self.assertEqual(self.repo.load_history()[0]['record_id'], record['record_id'])
        self.assertFalse(self.repo.load_cache().bulletins)

    def test_old_json_parser_cache_is_not_seeded(self):
        self.test_load_and_save_cache()
        data = json.loads(self.cache_path.read_text(encoding='utf-8'))
        data.pop('parser_revision')
        self.repo.db.reset_all_cache()
        self.cache_path.write_text(json.dumps(data), encoding='utf-8')
        self.assertFalse(self.repo.load_cache().bulletins)
        self.assertFalse(self.repo.db.load_all_bulletins())

    def test_development_reset_writes_parser_revision(self):
        self.test_load_and_save_cache()
        self.repo.reset_cache_for_development()
        data = json.loads(self.cache_path.read_text(encoding='utf-8'))
        self.assertEqual(data['parser_revision'], SANCTION_PARSER_REVISION)
        self.assertEqual(self.repo.db.get_meta('parser_revision'), SANCTION_PARSER_REVISION)
        self.assertFalse(self.repo.load_cache().bulletins)

    def test_resync_repairs_existing_incorrect_status_and_result(self):
        self.test_load_and_save_cache()
        self.repo.save_history([
            {'record_id': 'missed', 'time': '2026-09-06', 'suspect_id': 'TestID',
             'ban_status': 'unbanned', 'note': 'keep evidence'},
            {'record_id': 'wrong-result', 'time': '2026-09-06', 'suspect_id': 'sample1',
             'ban_status': 'banned', 'ban_result': 'T***ID', 'ban_bulletin_id': 100},
        ])
        self.repo.db.set_meta('parser_revision', '')
        cache = self.repo.load_cache()
        # Cache invalidation preserves history until corrected announcements arrive.
        self.assertEqual(self.repo.load_history()[0]['ban_status'], 'unbanned')
        entries = parse_sanction_html_table(
            '<p>已執行「永久鎖定」處分。</p>'
            '<table><tr><td colspan="6">角色名稱</td></tr>'
            '<tr><td>sample1</td><td>T***ID</td><td>sample3</td>'
            '<td>sample4</td><td>sample5</td><td>sample6</td></tr></table>'
        )
        cache.bulletins['100'] = BulletinDetail(
            100, '2026-09-07', '制裁公告', 'https://example.com/100', '', tuple(entries),
        )
        # Positive corrections can already be applied during a partial sync.
        summary, records = self.repo.commit_sync_progress(cache, is_complete=False)
        self.assertEqual(summary.newly_banned_count, 1)
        self.assertTrue(all(record['ban_status'] == 'banned' for record in records))
        self.assertTrue(all(record['ban_result'] == '永久鎖定' for record in records))
        self.assertEqual(records[0]['note'], 'keep evidence')
        persisted = self.repo.load_history()
        self.assertEqual(persisted[0]['ban_masked_name'], 'T***ID')
        self.assertEqual(persisted[1]['ban_result'], '永久鎖定')

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
        self.assertTrue(all(item["submission_state"] == "submitted" for item in loaded))

    def test_sqlite_history_schema_migrates_draft_columns(self):
        legacy_db = Path(self.temp_dir.name) / "legacy.db"
        with sqlite3.connect(legacy_db) as connection:
            connection.execute(
                """
                CREATE TABLE reports (
                    record_id TEXT PRIMARY KEY, time TEXT, suspect_id TEXT,
                    server TEXT, map TEXT, url TEXT, status TEXT, note TEXT,
                    ban_status TEXT, ban_date TEXT, ban_announcement_url TEXT,
                    ban_bulletin_id INTEGER, ban_result TEXT,
                    ban_masked_name TEXT, ban_checked_at TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO reports (record_id, time, suspect_id, status) VALUES (?, ?, ?, ?)",
                ("legacy-1", "2026-08-16 12:00:00", "Player1", "成功"),
            )

        migrated_repo = SanctionRepository(
            cache_path=Path(self.temp_dir.name) / "legacy-cache.json",
            history_path=Path(self.temp_dir.name) / "legacy-history.json",
            db_path=legacy_db,
        )
        loaded = migrated_repo.load_history()

        self.assertEqual(loaded[0]["submission_state"], "submitted")
        self.assertEqual(loaded[0]["media_path"], "")

    def test_draft_round_trip_and_in_place_submission_update(self):
        draft = self.repo.add_history_entry(
            {
                "time": "2026-08-16 12:00:00",
                "submission_state": "draft",
                "media_path": "C:/evidence.mp4",
                "media_type": "video",
                "status": "尚未送出",
            }
        )

        updated = self.repo.update_history_entry(
            draft["record_id"],
            {
                "submission_state": "submitted",
                "suspect_id": "Player1",
                "map": "墮落城市",
                "status": "成功",
            },
            evaluate=True,
        )

        loaded = self.repo.load_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(updated["record_id"], draft["record_id"])
        self.assertEqual(loaded[0]["submission_state"], "submitted")
        self.assertEqual(loaded[0]["suspect_id"], "Player1")

    def test_sanction_sync_skips_drafts(self):
        self.repo.save_history(
            [
                {
                    "record_id": "draft-1",
                    "time": "2026-08-16 10:00:00",
                    "suspect_id": "DraftPlayer",
                    "submission_state": "draft",
                    "ban_status": "pending",
                },
                {
                    "record_id": "submitted-1",
                    "time": "2026-08-16 11:00:00",
                    "suspect_id": "SubmittedPlayer",
                    "submission_state": "submitted",
                    "ban_status": "pending",
                },
            ]
        )

        summary, records = self.repo.commit_sync_progress(SanctionCache(), is_complete=True)

        self.assertEqual(summary.checked_record_count, 1)
        self.assertEqual(records[0]["ban_status"], "pending")
        self.assertEqual(records[1]["ban_status"], "unbanned")

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
