"""Thread-safe persistence repository for sanction cache and report history."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from maple_reporter.sanctions.matcher import (
    TAIPEI_TZ,
    find_matching_bulletin,
    parse_taiwan_date,
)
from maple_reporter.sanctions.models import (
    BulletinDetail,
    DateCacheEntry,
    SanctionCache,
    SanctionSyncSummary,
)
from maple_reporter.utils.config import (
    CONFIG_DIR,
    HISTORY_FILE,
    LEGACY_HISTORY_FILE,
    _write_json_atomic,
    ensure_config_dir,
)

LOGGER = logging.getLogger(__name__)

# Process-wide lock for atomic history & sanction cache mutations
HISTORY_LOCK = threading.RLock()


def get_sanction_cache_path() -> Path:
    ensure_config_dir()
    return CONFIG_DIR / "sanction_cache.json"


def get_current_taipei_datetime() -> datetime:
    """Return current datetime in Asia/Taipei timezone."""
    return datetime.now(TAIPEI_TZ)


def get_mutable_dates() -> tuple[str, str]:
    """Return (today, yesterday) date strings in Asia/Taipei timezone."""
    now = get_current_taipei_datetime()
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return today_str, yesterday_str


from maple_reporter.sanctions.database import SanctionDatabase, get_default_db_path


class SanctionRepository:
    """Thread-safe repository managing SQLite database, sanction_cache.json, and history.json."""

    def __init__(
        self,
        cache_path: Path | None = None,
        history_path: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        self._cache_path = cache_path or get_sanction_cache_path()
        self._history_path = history_path or (
            HISTORY_FILE if HISTORY_FILE.exists() else LEGACY_HISTORY_FILE
        )
        self.db = SanctionDatabase(db_path=db_path)
        self._lock = HISTORY_LOCK

    # --- Sanction Cache IO ---

    def load_cache(self) -> SanctionCache:
        """Load sanction cache from SQLite/JSON. Returns fresh empty cache on corruption."""
        with self._lock:
            # 1. Try loading from SQLite database first
            db_bulletins = self.db.load_all_bulletins()
            db_dates = self.db.load_sync_dates()
            last_complete = self.db.get_meta("last_complete_sync_at")
            last_attempt = self.db.get_meta("last_attempt_at")
            bootstrap_start = self.db.get_meta("bootstrap_start_date")

            if db_bulletins or db_dates or last_complete:
                return SanctionCache(
                    schema_version=1,
                    bootstrap_start_date=bootstrap_start,
                    last_attempt_at=last_attempt,
                    last_complete_sync_at=last_complete,
                    dates=db_dates,
                    bulletins=db_bulletins,
                )

            # 2. Fallback to JSON file if DB is empty
            if not self._cache_path.exists():
                return SanctionCache()
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cache = SanctionCache.from_dict(data)
                # Seed SQLite DB from JSON
                self.save_cache(cache)
                return cache
            except Exception as error:
                LOGGER.warning("讀取制裁快取失敗，重置為預設狀態 (%s: %s)", type(error).__name__, error)
                return SanctionCache()

    def save_cache(self, cache: SanctionCache) -> None:
        """Save sanction cache atomically to both SQLite database and JSON."""
        with self._lock:
            # 1. Save to SQLite database
            for b in cache.bulletins.values():
                self.db.save_bulletin(b)
            self.db.save_sync_dates(cache.dates)
            self.db.set_meta("last_complete_sync_at", cache.last_complete_sync_at)
            self.db.set_meta("last_attempt_at", cache.last_attempt_at)
            self.db.set_meta("bootstrap_start_date", cache.bootstrap_start_date)

            # 2. Mirror to JSON file
            _write_json_atomic(self._cache_path, cache.to_dict())

    def reset_cache_for_development(self) -> None:
        """Reset sanction database and cache for development purposes."""
        with self._lock:
            self.db.reset_all_cache()
            _write_json_atomic(self._cache_path, SanctionCache().to_dict())

    # --- History IO & Record ID Migration ---

    def load_history(self) -> list[dict[str, Any]]:
        """Load history records with process lock from DB/JSON."""
        with self._lock:
            # 1. Try loading from SQLite database
            db_reports = self.db.load_reports()
            if db_reports:
                return db_reports

            # 2. Fallback to JSON
            target_path = self._history_path if self._history_path.exists() else HISTORY_FILE
            if not target_path.exists():
                return []
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    raw_history = json.load(f)
                if not isinstance(raw_history, list):
                    return []
            except Exception as error:
                LOGGER.warning("讀取歷史紀錄失敗 (%s)", type(error).__name__)
                return []

            # Migrate missing record_ids
            records: list[dict[str, Any]] = []
            for item in raw_history:
                if not isinstance(item, dict):
                    continue
                record = dict(item)
                if not record.get("record_id"):
                    record["record_id"] = str(uuid.uuid4())
                records.append(record)

            self.save_history(records)
            return records

    def save_history(self, records: list[dict[str, Any]]) -> None:
        """Atomically persist history records to both SQLite database and JSON files."""
        with self._lock:
            clean_records = []
            for r in records[:200]:
                record = dict(r)
                if not record.get("record_id"):
                    record["record_id"] = str(uuid.uuid4())
                clean_records.append(record)

            # 1. Save to SQLite database
            self.db.save_reports(clean_records)

            # 2. Mirror to JSON files
            target_path = self._history_path if self._history_path else HISTORY_FILE
            _write_json_atomic(target_path, clean_records)

    def add_history_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Insert new history entry at index 0 after evaluating against local cache."""
        with self._lock:
            cache = self.load_cache()
            records = self.load_history()

            record = dict(entry)
            if not record.get("record_id"):
                record["record_id"] = str(uuid.uuid4())

            # Evaluate against current cache
            evaluated = self._evaluate_single_record(record, cache)
            records.insert(0, evaluated)
            self.save_history(records)
            return evaluated

    def clear_history(self) -> None:
        """Clear history records while preserving sanction cache."""
        with self._lock:
            self.db.clear_reports()
            target_path = self._history_path if self._history_path else HISTORY_FILE
            _write_json_atomic(target_path, [])

    # --- Cache Update Logic ---

    def update_date_and_bulletins(
        self,
        date_str: str,
        bulletins_for_date: list[BulletinDetail],
    ) -> None:
        """Store fetched bulletins for a specific date and update date state."""
        self.update_dates_batch({date_str: bulletins_for_date})

    def update_dates_batch(
        self,
        date_to_bulletins: dict[str, list[BulletinDetail]],
    ) -> None:
        """Atomically update multiple dates and their bulletins."""
        with self._lock:
            cache = self.load_cache()
            today_str, yesterday_str = get_mutable_dates()
            now_iso = get_current_taipei_datetime().isoformat()

            for date_str, bulletins_for_date in date_to_bulletins.items():
                date_state = "mutable" if date_str in (today_str, yesterday_str) else "finalized"
                bulletin_ids: list[int] = []
                for b in bulletins_for_date:
                    bulletin_ids.append(b.bid)
                    cache.bulletins[str(b.bid)] = b

                cache.dates[date_str] = DateCacheEntry(
                    state=date_state,
                    last_success_at=now_iso,
                    bulletin_ids=bulletin_ids,
                )

            self.save_cache(cache)

    def commit_sync_progress(
        self,
        cache: SanctionCache,
        is_complete: bool,
        failed_requests_count: int = 0,
    ) -> tuple[SanctionSyncSummary, list[dict[str, Any]]]:
        """Commit sync results to history and cache.
        
        - If complete: updates all records (banned, unbanned, pending), updates last_complete_sync_at.
        - If partial: only applies new banned hits, leaves unbanned/pending untouched.
        """
        with self._lock:
            now_iso = get_current_taipei_datetime().isoformat()
            cache.last_attempt_at = now_iso
            if is_complete:
                cache.last_complete_sync_at = now_iso

            # Finalize date states for older dates
            today_str, yesterday_str = get_mutable_dates()
            for d_str, date_entry in cache.dates.items():
                if d_str not in (today_str, yesterday_str):
                    date_entry.state = "finalized"

            self.save_cache(cache)

            # Apply to history
            records = self.load_history()
            all_bulletins = list(cache.bulletins.values())

            newly_banned = 0
            changed_to_unbanned = 0
            unchanged = 0
            indeterminate = 0
            checked_count = 0

            updated_records: list[dict[str, Any]] = []

            for record in records:
                checked_count += 1
                suspect_id = str(record.get("suspect_id") or record.get("id") or "").strip()
                raw_time = str(record.get("timestamp") or record.get("time") or "")
                report_date = parse_taiwan_date(raw_time)

                if not suspect_id or not report_date:
                    indeterminate += 1
                    updated_records.append(record)
                    continue

                prev_status = record.get("ban_status")
                match = find_matching_bulletin(suspect_id, report_date, all_bulletins)

                if match is not None:
                    # Positive match
                    new_record = dict(record)
                    new_record["ban_status"] = "banned"
                    new_record["ban_date"] = match.bulletin.publication_date
                    new_record["ban_announcement_url"] = match.bulletin.url
                    new_record["ban_bulletin_id"] = match.bulletin.bid
                    new_record["ban_result"] = match.entry.result
                    new_record["ban_masked_name"] = match.entry.masked_name
                    new_record["ban_checked_at"] = now_iso

                    if prev_status != "banned":
                        newly_banned += 1
                    else:
                        unchanged += 1
                    updated_records.append(new_record)
                elif is_complete:
                    # Complete sync and no match -> mark unbanned
                    new_record = dict(record)
                    new_record["ban_status"] = "unbanned"
                    new_record.pop("ban_date", None)
                    new_record.pop("ban_announcement_url", None)
                    new_record.pop("ban_bulletin_id", None)
                    new_record.pop("ban_result", None)
                    new_record.pop("ban_masked_name", None)
                    new_record["ban_checked_at"] = now_iso

                    if prev_status != "unbanned":
                        changed_to_unbanned += 1
                    else:
                        unchanged += 1
                    updated_records.append(new_record)
                else:
                    # Partial sync and no match -> preserve original status
                    unchanged += 1
                    updated_records.append(record)

            self.save_history(updated_records)

            summary = SanctionSyncSummary(
                completed=is_complete,
                bulletin_count=len(cache.bulletins),
                checked_record_count=checked_count,
                newly_banned_count=newly_banned,
                changed_to_unbanned_count=changed_to_unbanned,
                unchanged_count=unchanged,
                indeterminate_count=indeterminate,
                failed_request_count=failed_requests_count,
                last_complete_sync_at=cache.last_complete_sync_at or None,
            )
            return summary, updated_records

    def _evaluate_single_record(
        self,
        record: dict[str, Any],
        cache: SanctionCache,
    ) -> dict[str, Any]:
        """Evaluate a single history record against the cache."""
        suspect_id = str(record.get("suspect_id") or record.get("id") or "").strip()
        raw_time = str(record.get("timestamp") or record.get("time") or "")
        report_date = parse_taiwan_date(raw_time)

        if not suspect_id or not report_date:
            record["ban_status"] = record.get("ban_status", "pending")
            return record

        all_bulletins = list(cache.bulletins.values())
        match = find_matching_bulletin(suspect_id, report_date, all_bulletins)

        now_iso = get_current_taipei_datetime().isoformat()
        if match is not None:
            record["ban_status"] = "banned"
            record["ban_date"] = match.bulletin.publication_date
            record["ban_announcement_url"] = match.bulletin.url
            record["ban_bulletin_id"] = match.bulletin.bid
            record["ban_result"] = match.entry.result
            record["ban_masked_name"] = match.entry.masked_name
            record["ban_checked_at"] = now_iso
            return record

        # Check if cache has complete coverage from report_date up to last_complete_sync_at
        if cache.last_complete_sync_at:
            last_complete_date = parse_taiwan_date(cache.last_complete_sync_at)
            if last_complete_date and report_date <= last_complete_date:
                # Cache has verified coverage
                record["ban_status"] = "unbanned"
                record["ban_checked_at"] = now_iso
                return record

        record["ban_status"] = record.get("ban_status", "pending")
        return record
