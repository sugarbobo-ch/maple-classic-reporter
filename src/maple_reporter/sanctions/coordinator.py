"""Single-flight coordinator managing background sanction synchronization lifecycle."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Literal

from maple_reporter.sanctions.matcher import (
    TAIPEI_TZ,
    parse_taiwan_date,
)
from maple_reporter.sanctions.models import (
    BulletinDetail,
    BulletinHeader,
    SanctionSyncPhase,
    SanctionSyncStatus,
    SanctionSyncSummary,
    SanctionTrigger,
    StartSyncReason,
    StartSyncResult,
)
from maple_reporter.sanctions.official_api import (
    OfficialSanctionApiClient,
    SanctionSyncCancelledError,
)
from maple_reporter.sanctions.repository import (
    SanctionRepository,
    get_current_taipei_datetime,
    get_mutable_dates,
)
from maple_reporter.utils.config import load_config

LOGGER = logging.getLogger(__name__)

MIN_SYNC_INTERVAL_HOURS = 6.0


class SanctionSyncCoordinator:
    """Orchestrates single-flight sanction checking, progress events, and cancellations."""

    def __init__(
        self,
        repository: SanctionRepository | None = None,
        api_client: OfficialSanctionApiClient | None = None,
        event_emitter: Callable[[str, Any], None] | None = None,
    ) -> None:
        self.repository = repository or SanctionRepository()
        self.api_client = api_client or OfficialSanctionApiClient()
        self.event_emitter = event_emitter
        self._lock = threading.RLock()
        self._worker_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._current_status = SanctionSyncStatus(running=False)

    def _emit(self, event_type: str, data: Any = None) -> None:
        if self.event_emitter:
            try:
                self.event_emitter(event_type, data)
            except Exception as err:
                LOGGER.debug("Failed to emit sanction event %s: %s", event_type, err)

    def get_status(self) -> SanctionSyncStatus:
        with self._lock:
            cache = self.repository.load_cache()
            return SanctionSyncStatus(
                running=self._current_status.running,
                trigger=self._current_status.trigger,
                phase=self._current_status.phase,
                current=self._current_status.current,
                total=self._current_status.total,
                message=self._current_status.message,
                last_complete_sync_at=cache.last_complete_sync_at or None,
            )

    def start(self, trigger: SanctionTrigger = "manual") -> StartSyncResult:
        """Initiate sanction sync worker if conditions are met."""
        with self._lock:
            if self._current_status.running or (self._worker_thread and self._worker_thread.is_alive()):
                return StartSyncResult(
                    started=False,
                    reason="already_running",
                    status=self.get_status(),
                )

            # Check trigger-specific preconditions
            if trigger == "startup":
                cfg = load_config()
                if not bool(cfg.get("auto_check_sanction_status", True)):
                    return StartSyncResult(
                        started=False,
                        reason="disabled",
                        status=self.get_status(),
                    )

                history = self.repository.load_history()
                if not history:
                    return StartSyncResult(
                        started=False,
                        reason="no_history",
                        status=self.get_status(),
                    )

                cache = self.repository.load_cache()
                if cache.last_complete_sync_at:
                    try:
                        last_dt = datetime.fromisoformat(cache.last_complete_sync_at)
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=TAIPEI_TZ)
                        now = get_current_taipei_datetime()
                        hours_since = (now - last_dt).total_seconds() / 3600.0
                        if hours_since < MIN_SYNC_INTERVAL_HOURS:
                            return StartSyncResult(
                                started=False,
                                reason="fresh",
                                status=self.get_status(),
                            )
                    except Exception as e:
                        LOGGER.warning("Could not parse last_complete_sync_at: %s", e)

            self._cancel_event.clear()
            self._current_status = SanctionSyncStatus(
                running=True,
                trigger=trigger,
                phase="listing",
                message="正在檢查官方公告列表…",
                last_complete_sync_at=self.repository.load_cache().last_complete_sync_at or None,
            )

            self._worker_thread = threading.Thread(
                target=self._run_sync_worker,
                args=(trigger,),
                daemon=True,
            )
            self._worker_thread.start()

            self._emit("SANCTION_SYNC_STARTED", self._current_status.to_dict())
            return StartSyncResult(started=True, status=self._current_status)

    def cancel(self, timeout: float = 5.0) -> None:
        """Request cancellation and wait up to timeout seconds."""
        self._cancel_event.set()
        thread = self._worker_thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def _determine_required_dates(self, trigger: SanctionTrigger = "manual") -> tuple[set[str], str]:
        """Compute the set of dates that need checking and the earliest date threshold."""
        cache = self.repository.load_cache()
        now = get_current_taipei_datetime()
        today_str, yesterday_str = get_mutable_dates()

        required_dates = {today_str, yesterday_str}
        default_start_dt = now - timedelta(days=29)

        # Check earliest report date in history
        history = self.repository.load_history()
        earliest_report_dt = None
        for h in history:
            t = str(h.get("time", "")).strip()
            if len(t) >= 10:
                try:
                    r_dt = datetime.strptime(t[:10], "%Y-%m-%d").replace(tzinfo=TAIPEI_TZ)
                    if earliest_report_dt is None or r_dt < earliest_report_dt:
                        earliest_report_dt = r_dt
                except ValueError:
                    pass

        target_start_dt = default_start_dt
        if earliest_report_dt and earliest_report_dt < target_start_dt:
            target_start_dt = earliest_report_dt

        start_date_str = target_start_dt.strftime("%Y-%m-%d")
        if not cache.bootstrap_start_date or target_start_dt < default_start_dt:
            cache.bootstrap_start_date = start_date_str
            self.repository.save_cache(cache)

        curr = target_start_dt
        while curr <= now:
            d_str = curr.strftime("%Y-%m-%d")
            date_entry = cache.dates.get(d_str)

            # In manual check, or if date is missing/not finalized or has missing bulletin details:
            if trigger == "manual" or not date_entry or date_entry.state != "finalized":
                required_dates.add(d_str)
            elif date_entry.bulletin_ids:
                # Check if all bulletins for this date actually exist in cache
                if any(str(bid) not in cache.bulletins for bid in date_entry.bulletin_ids):
                    required_dates.add(d_str)

            curr += timedelta(days=1)

        earliest_date = min(required_dates)
        return required_dates, earliest_date

    def _run_sync_worker(self, trigger: SanctionTrigger) -> None:
        failed_count = 0
        cache = self.repository.load_cache()
        today_str, yesterday_str = get_mutable_dates()

        try:
            required_dates, earliest_date = self._determine_required_dates(trigger=trigger)
            LOGGER.info("Starting sanction sync (trigger=%s, earliest_date=%s)", trigger, earliest_date)

            # Step 1: Scan Bulletin Lists
            self._update_progress("listing", None, None, "正在檢查官方公告列表…")
            discovered_bulletins: list[BulletinHeader] = []
            seen_bids: set[int] = set()
            page = 1

            while not self._cancel_event.is_set():
                headers = self.api_client.fetch_bulletin_list(page, self._cancel_event)
                if not headers:
                    break

                new_headers = [h for h in headers if h.bid not in seen_bids]
                if not new_headers:
                    # No new bulletins found on this page
                    break

                for h in new_headers:
                    seen_bids.add(h.bid)
                    discovered_bulletins.append(h)

                oldest_on_page = min(h.publication_date for h in headers)
                if oldest_on_page < earliest_date:
                    # Surpassed earliest date
                    break

                page += 1
                if page > 20:  # Safety boundary
                    break

            if self._cancel_event.is_set():
                raise SanctionSyncCancelledError()

            # Group discovered bulletins by date
            bulletins_by_date: dict[str, list[BulletinHeader]] = {}
            for h in discovered_bulletins:
                if h.publication_date >= earliest_date:
                    bulletins_by_date.setdefault(h.publication_date, []).append(h)

            # Step 2: Determine which detail announcements to fetch
            bulletins_to_fetch: list[BulletinHeader] = []
            for d_str in required_dates:
                headers_for_day = bulletins_by_date.get(d_str, [])
                date_entry = cache.dates.get(d_str)

                if d_str in (today_str, yesterday_str):
                    # Mutable dates: always fetch details for all announcements
                    bulletins_to_fetch.extend(headers_for_day)
                else:
                    # Non-finalized or missing announcements
                    for h in headers_for_day:
                        cached_b = cache.bulletins.get(str(h.bid))
                        if not cached_b or len(cached_b.entries) == 0:
                            bulletins_to_fetch.append(h)

            # Step 3: Fetch Bulletin Details
            total_fetch = len(bulletins_to_fetch)
            fetched_details_by_date: dict[str, list[BulletinDetail]] = {}

            # Mark dates with 0 bulletins as successfully checked if fully scanned
            empty_dates_to_update = {
                d_str: [] for d_str in required_dates if d_str not in bulletins_by_date
            }
            if empty_dates_to_update:
                self.repository.update_dates_batch(empty_dates_to_update)

            for idx, header in enumerate(bulletins_to_fetch, start=1):
                if self._cancel_event.is_set():
                    raise SanctionSyncCancelledError()

                msg = f"正在檢查第 {idx}/{total_fetch} 篇公告 ({header.publication_date})"
                self._update_progress("fetching", idx, total_fetch, msg)

                try:
                    detail = self.api_client.fetch_bulletin_detail(header.bid, self._cancel_event)
                    fetched_details_by_date.setdefault(detail.publication_date, []).append(detail)
                    # Atomically save bulletin & partial positive hits
                    cache.bulletins[str(detail.bid)] = detail
                    self.repository.save_cache(cache)
                    self.repository.commit_sync_progress(cache, is_complete=False)
                except Exception as fetch_err:
                    LOGGER.warning("Failed to fetch detail for Bid %d: %s", header.bid, fetch_err)
                    failed_count += 1

            # Update dates that had bulletins
            dates_with_details: dict[str, list[BulletinDetail]] = {}
            for d_str, details in fetched_details_by_date.items():
                expected_count = len(bulletins_by_date.get(d_str, []))
                # Only mark date complete if all announcements for that date succeeded
                if len(details) == expected_count:
                    dates_with_details[d_str] = details
            if dates_with_details:
                self.repository.update_dates_batch(dates_with_details)

            if self._cancel_event.is_set():
                raise SanctionSyncCancelledError()

            # Step 4: Final Evaluation & Commit
            self._update_progress("matching", total_fetch, total_fetch, "正在比對回報歷史紀錄…")
            is_full_success = (failed_count == 0)
            summary, updated_history = self.repository.commit_sync_progress(
                cache=cache,
                is_complete=is_full_success,
                failed_requests_count=failed_count,
            )

            with self._lock:
                self._current_status = SanctionSyncStatus(
                    running=False,
                    last_complete_sync_at=summary.last_complete_sync_at,
                )

            if is_full_success:
                self._emit("SANCTION_SYNC_COMPLETED", {
                    "summary": summary.to_dict(),
                    "history": updated_history,
                })
            else:
                self._emit("SANCTION_SYNC_FAILED", {
                    "message": "部分制裁公告取得失敗，已保留已解析命中與既有歷史結果",
                    "summary": summary.to_dict(),
                    "history": updated_history,
                })

        except SanctionSyncCancelledError:
            LOGGER.info("Sanction sync was cancelled")
            with self._lock:
                self._current_status = SanctionSyncStatus(
                    running=False,
                    last_complete_sync_at=self.repository.load_cache().last_complete_sync_at or None,
                )
        except Exception as error:
            LOGGER.error("Sanction sync unhandled error: %s", error, exc_info=True)
            summary, updated_history = self.repository.commit_sync_progress(
                cache=cache,
                is_complete=False,
                failed_requests_count=failed_count + 1,
            )
            with self._lock:
                self._current_status = SanctionSyncStatus(
                    running=False,
                    last_complete_sync_at=summary.last_complete_sync_at,
                )
            self._emit("SANCTION_SYNC_FAILED", {
                "message": "連接官方公告伺服器失敗，請稍後重試",
                "summary": summary.to_dict(),
                "history": updated_history,
            })

    def _update_progress(
        self,
        phase: SanctionSyncPhase,
        current: int | None,
        total: int | None,
        message: str,
    ) -> None:
        with self._lock:
            self._current_status = SanctionSyncStatus(
                running=True,
                trigger=self._current_status.trigger,
                phase=phase,
                current=current,
                total=total,
                message=message,
                last_complete_sync_at=self.repository.load_cache().last_complete_sync_at or None,
            )
        self._emit("SANCTION_SYNC_PROGRESS", self._current_status.to_dict())

    def rebuild_cache_for_development(self) -> bool:
        """Developer utility to reset sanction_cache.json without touching settings or history."""
        with self._lock:
            if self._current_status.running:
                return False
            self.repository.reset_cache_for_development()
            return True
