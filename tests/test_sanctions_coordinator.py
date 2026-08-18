"""Unit tests for SanctionSyncCoordinator."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from maple_reporter.sanctions.coordinator import SanctionSyncCoordinator
from maple_reporter.sanctions.matcher import TAIPEI_TZ
from maple_reporter.sanctions.models import (
    BulletinDetail,
    BulletinHeader,
    DateCacheEntry,
    SanctionCache,
    SanctionEntry,
)
from maple_reporter.sanctions.repository import SanctionRepository


class TestSanctionSyncCoordinator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name) / "sanction_cache.json"
        self.history_path = Path(self.temp_dir.name) / "history.json"
        self.repo = SanctionRepository(
            cache_path=self.cache_path,
            history_path=self.history_path,
        )
        self.mock_api_client = MagicMock()
        self.emitted_events: list[tuple[str, dict]] = []

        def capture_event(event_type, data):
            self.emitted_events.append((event_type, data))

        self.coordinator = SanctionSyncCoordinator(
            repository=self.repo,
            api_client=self.mock_api_client,
            event_emitter=capture_event,
        )

    def tearDown(self):
        self.coordinator.cancel(timeout=1.0)
        self.temp_dir.cleanup()

    @patch("maple_reporter.sanctions.coordinator.load_config", return_value={"auto_check_sanction_status": False})
    def test_startup_disabled_in_config(self, _mock_cfg):
        res = self.coordinator.start(trigger="startup")
        self.assertFalse(res.started)
        self.assertEqual(res.reason, "disabled")

    @patch("maple_reporter.sanctions.coordinator.load_config", return_value={"auto_check_sanction_status": True})
    def test_startup_no_history(self, _mock_cfg):
        # Empty history
        self.repo.save_history([])
        res = self.coordinator.start(trigger="startup")
        self.assertFalse(res.started)
        self.assertEqual(res.reason, "no_history")

    @patch("maple_reporter.sanctions.coordinator.load_config", return_value={"auto_check_sanction_status": True})
    def test_startup_fresh_within_6_hours(self, _mock_cfg):
        # Populate history
        self.repo.save_history([{"time": "2026-08-16", "suspect_id": "P1"}])
        # Populate fresh cache (1 hour ago)
        one_hour_ago = (datetime.now(TAIPEI_TZ) - timedelta(hours=1)).isoformat()
        self.repo.save_cache(SanctionCache(schema_version=1, last_complete_sync_at=one_hour_ago))

        res = self.coordinator.start(trigger="startup")
        self.assertFalse(res.started)
        self.assertEqual(res.reason, "fresh")

        # Manual trigger ignores 6-hour restriction
        self.mock_api_client.fetch_bulletin_list.return_value = []
        res_manual = self.coordinator.start(trigger="manual")
        self.assertTrue(res_manual.started)
        self.coordinator.cancel()

    def test_single_flight_blocks_concurrent_workers(self):
        def mock_list(p, cancel):
            cancel.wait(0.2)
            return []

        self.mock_api_client.fetch_bulletin_list.side_effect = mock_list
        res1 = self.coordinator.start(trigger="manual")
        self.assertTrue(res1.started)

        res2 = self.coordinator.start(trigger="manual")
        self.assertFalse(res2.started)
        self.assertEqual(res2.reason, "already_running")
        self.coordinator.cancel()

    def test_finalized_dates_skip_detail_fetching(self):
        # Pre-seed finalized date (2026-08-10)
        cached_bulletin = BulletinDetail(
            bid=82410,
            publication_date="2026-08-10",
            title="0810制裁公告",
            url="http://example.com/82410",
            fetched_at="2026-08-10T12:00:00+08:00",
            entries=(SanctionEntry("雲**間", "永久鎖定"),),
        )
        cache = SanctionCache(
            schema_version=1,
            bootstrap_start_date="2026-08-01",
            dates={
                "2026-08-10": DateCacheEntry(
                    state="finalized",
                    last_success_at="2026-08-10T12:00:00+08:00",
                    bulletin_ids=[82410],
                )
            },
            bulletins={"82410": cached_bulletin},
        )
        self.repo.save_cache(cache)
        self.repo.save_history([{"time": "2026-08-09", "suspect_id": "雲端之間", "ban_status": "pending"}])

        # Return bulletin list containing 82410 (finalized) on page 1 and empty on page 2
        self.mock_api_client.fetch_bulletin_list.side_effect = lambda page, cancel: [
            BulletinHeader(
                bid=82410,
                title="0810制裁公告",
                publication_date="2026-08-10",
                url="http://example.com/82410",
            )
        ] if page == 1 else []

        res = self.coordinator.start(trigger="manual")
        self.assertTrue(res.started)
        self.coordinator._worker_thread.join(timeout=2.0)

        # fetch_bulletin_detail should NOT have been called for the finalized bulletin!
        self.mock_api_client.fetch_bulletin_detail.assert_not_called()

        # Check emitted completion event
        event_types = [e[0] for e in self.emitted_events]
        self.assertIn("SANCTION_SYNC_STARTED", event_types)
        self.assertIn("SANCTION_SYNC_COMPLETED", event_types)


if __name__ == "__main__":
    unittest.main()
