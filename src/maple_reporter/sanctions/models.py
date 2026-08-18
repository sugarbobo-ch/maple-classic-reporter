"""Typed data models and schemas for sanction status checking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DateState = Literal["mutable", "finalized"]
SanctionSyncPhase = Literal["listing", "fetching", "matching"]
SanctionTrigger = Literal["startup", "manual"]
StartSyncReason = Literal["already_running", "disabled", "fresh", "no_history"]


@dataclass(frozen=True)
class SanctionEntry:
    """Single sanctioned character entry extracted from an official announcement."""

    masked_name: str
    result: str


@dataclass(frozen=True)
class BulletinHeader:
    """Announcement metadata extracted from the bulletin list endpoint."""

    bid: int
    title: str
    publication_date: str  # YYYY-MM-DD
    url: str


@dataclass(frozen=True)
class BulletinDetail:
    """Full parsed sanction bulletin with parsed entries."""

    bid: int
    publication_date: str  # YYYY-MM-DD
    title: str
    url: str
    fetched_at: str  # ISO 8601 timestamp with offset
    entries: tuple[SanctionEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid": self.bid,
            "publication_date": self.publication_date,
            "title": self.title,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "entries": [
                {"masked_name": e.masked_name, "result": e.result}
                for e in self.entries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BulletinDetail:
        entries = tuple(
            SanctionEntry(
                masked_name=str(e.get("masked_name", "")),
                result=str(e.get("result", "")),
            )
            for e in data.get("entries", [])
            if e.get("masked_name")
        )
        return cls(
            bid=int(data["bid"]),
            publication_date=str(data["publication_date"]),
            title=str(data["title"]),
            url=str(data["url"]),
            fetched_at=str(data.get("fetched_at", "")),
            entries=entries,
        )


@dataclass
class DateCacheEntry:
    """Status and associated bulletins for a specific calendar date."""

    state: DateState
    last_success_at: str  # ISO 8601
    bulletin_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "last_success_at": self.last_success_at,
            "bulletin_ids": list(self.bulletin_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DateCacheEntry:
        return cls(
            state=data.get("state", "mutable"),
            last_success_at=str(data.get("last_success_at", "")),
            bulletin_ids=[int(b) for b in data.get("bulletin_ids", [])],
        )


@dataclass
class SanctionCache:
    """Locally persisted sanction announcement cache schema."""

    schema_version: int = 1
    last_attempt_at: str = ""
    last_complete_sync_at: str = ""
    bootstrap_start_date: str = ""  # YYYY-MM-DD
    dates: dict[str, DateCacheEntry] = field(default_factory=dict)
    bulletins: dict[str, BulletinDetail] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "last_attempt_at": self.last_attempt_at,
            "last_complete_sync_at": self.last_complete_sync_at,
            "bootstrap_start_date": self.bootstrap_start_date,
            "dates": {d: entry.to_dict() for d, entry in self.dates.items()},
            "bulletins": {bid: b.to_dict() for bid, b in self.bulletins.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SanctionCache:
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return cls()

        dates = {}
        for d, entry_data in data.get("dates", {}).items():
            if isinstance(entry_data, dict):
                dates[str(d)] = DateCacheEntry.from_dict(entry_data)

        bulletins = {}
        for bid, b_data in data.get("bulletins", {}).items():
            if isinstance(b_data, dict) and "bid" in b_data:
                bulletins[str(bid)] = BulletinDetail.from_dict(b_data)

        return cls(
            schema_version=int(data.get("schema_version", 1)),
            last_attempt_at=str(data.get("last_attempt_at", "")),
            last_complete_sync_at=str(data.get("last_complete_sync_at", "")),
            bootstrap_start_date=str(data.get("bootstrap_start_date", "")),
            dates=dates,
            bulletins=bulletins,
        )


@dataclass(frozen=True)
class SanctionSyncStatus:
    """Real-time progress and state of the sanction synchronizer."""

    running: bool = False
    trigger: SanctionTrigger | None = None
    phase: SanctionSyncPhase | None = None
    current: int | None = None
    total: int | None = None
    message: str | None = None
    last_complete_sync_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"running": self.running}
        if self.trigger is not None:
            res["trigger"] = self.trigger
        if self.phase is not None:
            res["phase"] = self.phase
        if self.current is not None:
            res["current"] = self.current
        if self.total is not None:
            res["total"] = self.total
        if self.message is not None:
            res["message"] = self.message
        if self.last_complete_sync_at is not None:
            res["last_complete_sync_at"] = self.last_complete_sync_at
        return res


@dataclass(frozen=True)
class SanctionSyncSummary:
    """Summary of changes and metrics after completing or partially failing a sync."""

    completed: bool
    bulletin_count: int
    checked_record_count: int
    newly_banned_count: int
    changed_to_unbanned_count: int
    unchanged_count: int
    indeterminate_count: int
    failed_request_count: int
    last_complete_sync_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "bulletin_count": self.bulletin_count,
            "checked_record_count": self.checked_record_count,
            "newly_banned_count": self.newly_banned_count,
            "changed_to_unbanned_count": self.changed_to_unbanned_count,
            "unchanged_count": self.unchanged_count,
            "indeterminate_count": self.indeterminate_count,
            "failed_request_count": self.failed_request_count,
            "last_complete_sync_at": self.last_complete_sync_at,
        }


@dataclass(frozen=True)
class StartSyncResult:
    """Return value when triggering synchronization."""

    started: bool
    reason: StartSyncReason | None = None
    status: SanctionSyncStatus = field(default_factory=SanctionSyncStatus)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "started": self.started,
            "status": self.status.to_dict(),
        }
        if self.reason is not None:
            res["reason"] = self.reason
        return res
