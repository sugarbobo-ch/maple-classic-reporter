"""Official API client with rate limiting, retries, and cancellable waiting."""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from typing import Callable

import requests

from maple_reporter.sanctions.models import BulletinDetail, BulletinHeader
from maple_reporter.sanctions.parser import (
    OFFICIAL_ORIGIN,
    parse_bulletin_detail_json,
    parse_bulletin_list_json,
)
from maple_reporter.sanctions.repository import get_current_taipei_datetime

LOGGER = logging.getLogger(__name__)

LIST_URL = f"{OFFICIAL_ORIGIN}/api/Bulletin/FindBulletin"
DETAIL_PAGE_URL_TEMPLATE = "https://maplestory.beanfun.com/bulletin?bid={bid}"
DETAIL_HANDLER_URL = "https://maplestory.beanfun.com/bulletin?handler=BulletinDetail"

DEFAULT_CONNECT_TIMEOUT = 8.0
DEFAULT_READ_TIMEOUT = 15.0
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)
MAX_RETRIES = 2  # Total 3 attempts


class SanctionSyncCancelledError(Exception):
    """Raised when synchronization is cancelled by user or shutdown."""


class OfficialSanctionApiClient:
    """HTTP client for beanfun MapleStory Classic bulletin endpoints."""

    def __init__(
        self,
        session: requests.Session | None = None,
        random_delay_func: Callable[[float, float], float] | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or requests.Session()
        self.random_delay_func = random_delay_func or random.uniform
        self.timeout = timeout
        self._has_sent_first_request = False

    def _wait_cancellable(
        self,
        cancel_event: threading.Event,
        min_sec: float = 3.0,
        max_sec: float = 8.0,
    ) -> None:
        """Wait randomly 3-8 seconds if not the very first request."""
        if not self._has_sent_first_request:
            self._has_sent_first_request = True
            return

        if cancel_event.is_set():
            raise SanctionSyncCancelledError("Sync was cancelled before waiting")

        delay = self.random_delay_func(min_sec, max_sec)
        cancelled = cancel_event.wait(timeout=delay)
        if cancelled or cancel_event.is_set():
            raise SanctionSyncCancelledError("Sync was cancelled during wait")

    def _execute_request_with_retry(
        self,
        method: str,
        url: str,
        cancel_event: threading.Event,
        json_body: dict | None = None,
        data: dict | None = None,
        extra_headers: dict | None = None,
    ) -> requests.Response:
        """Execute request with cancellable wait and up to 2 retries (3 attempts)."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            if cancel_event.is_set():
                raise SanctionSyncCancelledError("Sync cancelled before request")

            # Cancellable wait before each attempt
            self._wait_cancellable(cancel_event, min_sec=3.0, max_sec=8.0)

            if cancel_event.is_set():
                raise SanctionSyncCancelledError("Sync cancelled during wait")

            try:
                LOGGER.debug("Sending %s request to %s (attempt %d/%d)", method, url, attempt + 1, MAX_RETRIES + 1)
                req_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/plain, */*",
                }
                if extra_headers:
                    req_headers.update(extra_headers)

                response = self.session.request(
                    method=method,
                    url=url,
                    json=json_body,
                    data=data,
                    timeout=self.timeout,
                    headers=req_headers,
                )

                if response.status_code == 200:
                    return response

                # Handle 429 Too Many Requests
                if response.status_code == 429:
                    retry_after = 5.0
                    header_val = response.headers.get("Retry-After")
                    if header_val:
                        try:
                            retry_after = min(float(header_val), 60.0)
                        except (ValueError, TypeError):
                            pass
                    LOGGER.warning("HTTP 429 Rate Limited. Waiting %.1fs before retry", retry_after)
                    cancelled = cancel_event.wait(timeout=retry_after)
                    if cancelled or cancel_event.is_set():
                        raise SanctionSyncCancelledError("Sync cancelled during 429 retry wait")
                    last_error = requests.HTTPError(f"HTTP 429 Rate Limited: {response.text}")
                    continue

                # Handle 5xx Server Errors (retryable)
                if response.status_code >= 500:
                    LOGGER.warning("HTTP %d error from %s. Retrying...", response.status_code, url)
                    last_error = requests.HTTPError(f"HTTP {response.status_code}: {response.text}")
                    continue

                # Other 4xx client errors (non-retryable)
                LOGGER.error("Non-retryable HTTP %d error from %s", response.status_code, url)
                response.raise_for_status()

            except (requests.Timeout, requests.ConnectionError) as net_err:
                LOGGER.warning("Network error on attempt %d: %s", attempt + 1, net_err)
                last_error = net_err
                continue
            except SanctionSyncCancelledError:
                raise
            except requests.HTTPError:
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed after {MAX_RETRIES + 1} attempts: {url}")

    def fetch_bulletin_list(
        self,
        page: int,
        cancel_event: threading.Event,
    ) -> list[BulletinHeader]:
        """Fetch and parse announcement list page."""
        payload = {
            "page": page,
            "pageSize": 30,
            "bulletinTypeId": 758,
        }
        resp = self._execute_request_with_retry(
            method="POST",
            url=LIST_URL,
            cancel_event=cancel_event,
            json_body=payload,
        )
        return parse_bulletin_list_json(resp.content)

    def fetch_bulletin_detail(
        self,
        bid: int,
        cancel_event: threading.Event,
    ) -> BulletinDetail:
        """Fetch and parse full bulletin detail using CSRF token and handler endpoint."""
        page_url = DETAIL_PAGE_URL_TEMPLATE.format(bid=bid)
        page_resp = self._execute_request_with_retry(
            method="GET",
            url=page_url,
            cancel_event=cancel_event,
        )
        token_match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page_resp.text)
        token = token_match.group(1) if token_match else ""

        headers = {
            "X-CSRF-TOKEN": token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
            "Origin": "https://maplestory.beanfun.com",
        }
        resp = self._execute_request_with_retry(
            method="POST",
            url=DETAIL_HANDLER_URL,
            cancel_event=cancel_event,
            data={"Bid": bid},
            extra_headers=headers,
        )
        title, pub_date, link_url, entries = parse_bulletin_detail_json(resp.content, bid=bid)
        now_iso = get_current_taipei_datetime().isoformat()
        return BulletinDetail(
            bid=bid,
            publication_date=pub_date,
            title=title,
            url=link_url,
            fetched_at=now_iso,
            entries=tuple(entries),
        )
