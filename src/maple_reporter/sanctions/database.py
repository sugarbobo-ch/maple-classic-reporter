"""SQLite persistence database for sanction bulletins, parsed suspect entries, and report history."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

from maple_reporter.sanctions.models import (
    BulletinDetail,
    DateCacheEntry,
    SanctionCache,
    SanctionEntry,
)
from maple_reporter.utils.config import CONFIG_DIR, ensure_config_dir

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


def get_default_db_path() -> Path:
    ensure_config_dir()
    return CONFIG_DIR / "reporter.db"


class SanctionDatabase:
    """Thread-safe SQLite database manager for sanctions and report history."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _execute(self, callback: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=15.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            try:
                with conn:
                    return callback(conn)
            finally:
                conn.close()

    def _init_db(self) -> None:
        def _init(conn: sqlite3.Connection) -> None:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS reports (
                    record_id TEXT PRIMARY KEY,
                    time TEXT,
                    suspect_id TEXT,
                    server TEXT,
                    map TEXT,
                    url TEXT,
                    status TEXT,
                    note TEXT,
                    ban_status TEXT,
                    ban_date TEXT,
                    ban_announcement_url TEXT,
                    ban_bulletin_id INTEGER,
                    ban_result TEXT,
                    ban_masked_name TEXT,
                    ban_checked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS bulletins (
                    bid INTEGER PRIMARY KEY,
                    publication_date TEXT,
                    title TEXT,
                    url TEXT,
                    fetched_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sanction_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bid INTEGER,
                    masked_name TEXT,
                    result TEXT,
                    FOREIGN KEY (bid) REFERENCES bulletins(bid) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_entries_bid ON sanction_entries(bid);
                CREATE INDEX IF NOT EXISTS idx_entries_masked ON sanction_entries(masked_name);

                CREATE TABLE IF NOT EXISTS sync_dates (
                    date TEXT PRIMARY KEY,
                    state TEXT,
                    last_success_at TEXT,
                    bulletin_ids TEXT
                );

                CREATE TABLE IF NOT EXISTS sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

        self._execute(_init)

    # --- Reports Operations ---

    def load_reports(self) -> list[dict[str, Any]]:
        def _load(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute("SELECT * FROM reports ORDER BY rowid ASC;").fetchall()
            return [dict(r) for r in rows]

        return self._execute(_load)

    def save_reports(self, reports: list[dict[str, Any]]) -> None:
        def _save(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM reports;")
            insert_sql = """
                INSERT INTO reports (
                    record_id, time, suspect_id, server, map, url, status, note,
                    ban_status, ban_date, ban_announcement_url, ban_bulletin_id,
                    ban_result, ban_masked_name, ban_checked_at
                ) VALUES (
                    :record_id, :time, :suspect_id, :server, :map, :url, :status, :note,
                    :ban_status, :ban_date, :ban_announcement_url, :ban_bulletin_id,
                    :ban_result, :ban_masked_name, :ban_checked_at
                );
            """
            for r in reports:
                params = {
                    "record_id": r.get("record_id", ""),
                    "time": r.get("time") or r.get("timestamp", ""),
                    "suspect_id": r.get("suspect_id") or r.get("id", ""),
                    "server": r.get("server", ""),
                    "map": r.get("map") or r.get("map_name", ""),
                    "url": r.get("url") or r.get("evidence_url", ""),
                    "status": r.get("status") or r.get("upload_status", ""),
                    "note": r.get("note", ""),
                    "ban_status": r.get("ban_status", "pending"),
                    "ban_date": r.get("ban_date"),
                    "ban_announcement_url": r.get("ban_announcement_url"),
                    "ban_bulletin_id": r.get("ban_bulletin_id"),
                    "ban_result": r.get("ban_result"),
                    "ban_masked_name": r.get("ban_masked_name"),
                    "ban_checked_at": r.get("ban_checked_at"),
                }
                conn.execute(insert_sql, params)

        self._execute(_save)

    def insert_or_update_report(self, r: dict[str, Any]) -> None:
        def _upsert(conn: sqlite3.Connection) -> None:
            params = {
                "record_id": r.get("record_id", ""),
                "time": r.get("time") or r.get("timestamp", ""),
                "suspect_id": r.get("suspect_id") or r.get("id", ""),
                "server": r.get("server", ""),
                "map": r.get("map") or r.get("map_name", ""),
                "url": r.get("url") or r.get("evidence_url", ""),
                "status": r.get("status") or r.get("upload_status", ""),
                "note": r.get("note", ""),
                "ban_status": r.get("ban_status", "pending"),
                "ban_date": r.get("ban_date"),
                "ban_announcement_url": r.get("ban_announcement_url"),
                "ban_bulletin_id": r.get("ban_bulletin_id"),
                "ban_result": r.get("ban_result"),
                "ban_masked_name": r.get("ban_masked_name"),
                "ban_checked_at": r.get("ban_checked_at"),
            }
            conn.execute("""
                INSERT INTO reports (
                    record_id, time, suspect_id, server, map, url, status, note,
                    ban_status, ban_date, ban_announcement_url, ban_bulletin_id,
                    ban_result, ban_masked_name, ban_checked_at
                ) VALUES (
                    :record_id, :time, :suspect_id, :server, :map, :url, :status, :note,
                    :ban_status, :ban_date, :ban_announcement_url, :ban_bulletin_id,
                    :ban_result, :ban_masked_name, :ban_checked_at
                )
                ON CONFLICT(record_id) DO UPDATE SET
                    time=excluded.time,
                    suspect_id=excluded.suspect_id,
                    server=excluded.server,
                    map=excluded.map,
                    url=excluded.url,
                    status=excluded.status,
                    note=excluded.note,
                    ban_status=excluded.ban_status,
                    ban_date=excluded.ban_date,
                    ban_announcement_url=excluded.ban_announcement_url,
                    ban_bulletin_id=excluded.ban_bulletin_id,
                    ban_result=excluded.ban_result,
                    ban_masked_name=excluded.ban_masked_name,
                    ban_checked_at=excluded.ban_checked_at;
            """, params)

        self._execute(_upsert)

    def clear_reports(self) -> None:
        def _clear(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM reports;")

        self._execute(_clear)

    # --- Bulletins & Sanctions Operations ---

    def save_bulletin(self, b: BulletinDetail) -> None:
        def _save_b(conn: sqlite3.Connection) -> None:
            conn.execute("""
                INSERT INTO bulletins (bid, publication_date, title, url, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(bid) DO UPDATE SET
                    publication_date=excluded.publication_date,
                    title=excluded.title,
                    url=excluded.url,
                    fetched_at=excluded.fetched_at;
            """, (b.bid, b.publication_date, b.title, b.url, b.fetched_at))

            conn.execute("DELETE FROM sanction_entries WHERE bid = ?;", (b.bid,))
            conn.executemany(
                "INSERT INTO sanction_entries (bid, masked_name, result) VALUES (?, ?, ?);",
                [(b.bid, e.masked_name, e.result) for e in b.entries],
            )

        self._execute(_save_b)

    def load_all_bulletins(self) -> dict[str, BulletinDetail]:
        def _load_all(conn: sqlite3.Connection) -> dict[str, BulletinDetail]:
            b_rows = conn.execute("SELECT * FROM bulletins ORDER BY bid DESC;").fetchall()
            bulletins_dict: dict[str, BulletinDetail] = {}
            for row in b_rows:
                bid = row["bid"]
                e_rows = conn.execute(
                    "SELECT masked_name, result FROM sanction_entries WHERE bid = ?;",
                    (bid,)
                ).fetchall()
                entries = tuple(SanctionEntry(r["masked_name"], r["result"]) for r in e_rows)
                bulletins_dict[str(bid)] = BulletinDetail(
                    bid=bid,
                    publication_date=row["publication_date"],
                    title=row["title"],
                    url=row["url"],
                    fetched_at=row["fetched_at"],
                    entries=entries,
                )
            return bulletins_dict

        return self._execute(_load_all)

    # --- Sync Metadata & Dates ---

    def save_sync_dates(self, dates: dict[str, DateCacheEntry]) -> None:
        def _save_d(conn: sqlite3.Connection) -> None:
            for d_str, entry in dates.items():
                conn.execute("""
                    INSERT INTO sync_dates (date, state, last_success_at, bulletin_ids)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        state=excluded.state,
                        last_success_at=excluded.last_success_at,
                        bulletin_ids=excluded.bulletin_ids;
                """, (d_str, entry.state, entry.last_success_at, json.dumps(entry.bulletin_ids)))

        self._execute(_save_d)

    def load_sync_dates(self) -> dict[str, DateCacheEntry]:
        def _load_d(conn: sqlite3.Connection) -> dict[str, DateCacheEntry]:
            rows = conn.execute("SELECT * FROM sync_dates;").fetchall()
            res: dict[str, DateCacheEntry] = {}
            for r in rows:
                b_ids = json.loads(r["bulletin_ids"]) if r["bulletin_ids"] else []
                res[r["date"]] = DateCacheEntry(
                    state=r["state"],
                    last_success_at=r["last_success_at"],
                    bulletin_ids=b_ids,
                )
            return res

        return self._execute(_load_d)

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        def _get_m(conn: sqlite3.Connection) -> str | None:
            row = conn.execute("SELECT value FROM sync_meta WHERE key = ?;", (key,)).fetchone()
            return row["value"] if row else default

        return self._execute(_get_m)

    def set_meta(self, key: str, value: str | None) -> None:
        def _set_m(conn: sqlite3.Connection) -> None:
            if value is None:
                conn.execute("DELETE FROM sync_meta WHERE key = ?;", (key,))
            else:
                conn.execute("""
                    INSERT INTO sync_meta (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
                """, (key, value))

        self._execute(_set_m)

    def reset_all_cache(self) -> None:
        def _reset(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM sanction_entries;")
            conn.execute("DELETE FROM bulletins;")
            conn.execute("DELETE FROM sync_dates;")
            conn.execute("DELETE FROM sync_meta;")

        self._execute(_reset)
