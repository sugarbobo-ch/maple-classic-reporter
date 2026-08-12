import atexit
import logging
import threading
import time
from typing import Tuple
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from maple_reporter.automation.playwright_runtime import (
    PlaywrightBrowserError,
    make_launch_error,
    resolve_chromium_executable,
)


FORM_URL = "https://forms.gamania.com/s/eLGg4"
SUBMISSION_ENDPOINT = "https://forms.gamania.com/api/v2/s/submit"
# The website owns the daily submission limit; the app deliberately does not
# persist or enforce a local counter.
LOGGER = logging.getLogger(__name__)

_RETAINED_SUBMISSION_SESSIONS = []
_RETAINED_SUBMISSION_SESSIONS_LOCK = threading.Lock()


class _RetainedSubmissionSession:
    """Keep a failed visible submission page open until the user closes it."""

    def __init__(self, playwright, browser):
        self.playwright = playwright
        self.browser = browser
        try:
            browser.on("disconnected", self._on_browser_disconnected)
        except Exception as error:  # pragma: no cover - Playwright runtime only
            LOGGER.warning("監聽表單瀏覽器關閉事件失敗 (%s)", type(error).__name__)

    def _on_browser_disconnected(self, *_args) -> None:
        with _RETAINED_SUBMISSION_SESSIONS_LOCK:
            if self in _RETAINED_SUBMISSION_SESSIONS:
                _RETAINED_SUBMISSION_SESSIONS.remove(self)
        try:
            self.playwright.stop()
        except Exception as error:  # pragma: no cover - Playwright runtime only
            LOGGER.debug("釋放已關閉的表單 Playwright 失敗 (%s)", type(error).__name__)

    def close(self) -> None:
        try:
            self.browser.close()
        except Exception as error:  # pragma: no cover - Playwright runtime only
            LOGGER.debug("關閉失敗表單瀏覽器失敗 (%s)", type(error).__name__)
        finally:
            try:
                self.playwright.stop()
            except Exception as error:  # pragma: no cover - Playwright runtime only
                LOGGER.debug("釋放失敗表單 Playwright 失敗 (%s)", type(error).__name__)


def _retain_submission_session(playwright, browser) -> None:
    session = _RetainedSubmissionSession(playwright, browser)
    with _RETAINED_SUBMISSION_SESSIONS_LOCK:
        _RETAINED_SUBMISSION_SESSIONS.append(session)


def _close_retained_submission_sessions() -> None:
    with _RETAINED_SUBMISSION_SESSIONS_LOCK:
        sessions = list(_RETAINED_SUBMISSION_SESSIONS)
        _RETAINED_SUBMISSION_SESSIONS.clear()
    for session in sessions:
        session.close()


atexit.register(_close_retained_submission_sessions)

SUBMISSION_FAILURE_SELECTORS = (
    ('[role="alert"]', "網站回報表單顯示錯誤訊息"),
    ('text="請確認必填欄位"', "表單仍有必填欄位未完成"),
    ('text="欄位為必填"', "表單仍有必填欄位未完成"),
    ('text="送出失敗"', "網站回報表單回報送出失敗"),
    ('text="發生錯誤"', "網站回報表單發生錯誤"),
)


# These are the verified SurveyCake completion signals. The API response is
# authoritative; the page text and explicit ``thankyou`` redirect are fallbacks.
SUBMISSION_SUCCESS_SELECTORS = ('text="收到你的回覆囉！"',)
SUBMISSION_SUCCESS_URL_MARKERS = ("thankyou",)
SUBMISSION_WINDOW_FAILURE_MESSAGE = (
    "已按下送出但未收到可確認成功的正常回應；表單視窗會保持開啟，"
    "請查看失敗畫面後手動關閉。本機證據會保留。"
)


def _is_visible(locator) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception as error:
        LOGGER.debug("表單元素狀態暫時無法讀取 (%s)", type(error).__name__)
        return False


def _page_has_success_url(page, initial_url: str | None = None) -> bool:
    try:
        current_url = page.url
    except Exception as error:
        LOGGER.debug("無法讀取表單頁面網址 (%s)", type(error).__name__)
        return False
    if not isinstance(current_url, str):
        return False
    if initial_url and isinstance(initial_url, str) and current_url == initial_url:
        return False
    current_parts = urlsplit(current_url)
    expected_parts = urlsplit(FORM_URL)
    if current_parts.netloc and current_parts.netloc != expected_parts.netloc:
        return False
    if initial_url:
        initial_parts = urlsplit(initial_url)
        if initial_parts.netloc and current_parts.netloc != initial_parts.netloc:
            return False
    lowered_url = current_url.lower()
    return any(marker in lowered_url for marker in SUBMISSION_SUCCESS_URL_MARKERS)


def _is_submission_success_payload(payload: object) -> bool:
    """Validate the observed SurveyCake submit response schema."""

    if not isinstance(payload, dict) or payload.get("status") is not True:
        return False
    data = payload.get("data")
    return isinstance(data, dict) and data.get("redirect") == "thankyou"


def _is_submission_endpoint(response_url: object) -> bool:
    if not isinstance(response_url, str):
        return False
    response_parts = urlsplit(response_url)
    endpoint_parts = urlsplit(SUBMISSION_ENDPOINT)
    return (
        response_parts.scheme.lower() == endpoint_parts.scheme.lower()
        and response_parts.netloc.lower() == endpoint_parts.netloc.lower()
        and response_parts.path.rstrip("/") == endpoint_parts.path.rstrip("/")
    )


def _capture_submission_response(response, confirmation_state: dict[str, bool]) -> None:
    """Capture only the known submit endpoint's successful JSON response."""

    try:
        if not _is_submission_endpoint(getattr(response, "url", None)):
            return
        if getattr(response, "status", None) != 200:
            return
        request = getattr(response, "request", None)
        method = getattr(request, "method", None)
        if not isinstance(method, str) or method.upper() != "POST":
            return
        if _is_submission_success_payload(response.json()):
            confirmation_state["confirmed"] = True
    except Exception as error:
        # Response bodies can disappear while the SPA replaces its page.
        LOGGER.debug("讀取表單送出回應失敗 (%s)", type(error).__name__)


def _submission_failure_reason(page) -> str | None:
    for selector, reason in SUBMISSION_FAILURE_SELECTORS:
        try:
            if _is_visible(page.locator(selector)):
                return reason
        except Exception as error:
            LOGGER.debug(
                "讀取表單錯誤訊息失敗 (%s)", type(error).__name__
            )
    return None


def _wait_for_submission_confirmation(
    page,
    timeout_ms: int = 15_000,
    initial_url: str | None = None,
    response_confirmation: dict[str, bool] | None = None,
) -> bool:
    """Return True only after SurveyCake renders an explicit success state."""
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if response_confirmation and response_confirmation.get("confirmed") is True:
            return True
        if _page_has_success_url(page, initial_url):
            return True
        for selector in SUBMISSION_SUCCESS_SELECTORS:
            try:
                if _is_visible(page.locator(selector)):
                    return True
            except Exception as error:
                # The page may replace its DOM while the request completes.
                LOGGER.debug(
                    "讀取表單成功訊息失敗 (%s)", type(error).__name__
                )
                continue
        try:
            page.wait_for_timeout(200)
        except Exception as error:
            LOGGER.debug("等待表單回應失敗 (%s)", type(error).__name__)
            time.sleep(0.2)
    return False


def _fill_required_field(locator, value: str, field_name: str) -> tuple[bool, str]:
    if not _is_visible(locator):
        return False, f"找不到表單的「{field_name}」欄位，已取消送出。"
    try:
        locator.first.fill(value)
    except Exception as error:
        LOGGER.warning("填寫表單欄位失敗 (%s: %s)", field_name, type(error).__name__)
        return False, f"無法填寫表單的「{field_name}」欄位，已取消送出。"
    return True, ""


def submit_gamania_report(
    suspect_id: str,
    server_name: str,
    map_name: str,
    note: str,
    evidence_url: str,
    headless: bool = False,
) -> Tuple[bool, str]:
    """
    Automate filling out Gamania MapleStory Classic report form using Playwright.
    Returns (success_boolean, status_message).
    """
    try:
        executable_path = resolve_chromium_executable()
        try:
            playwright = sync_playwright().start()
        except Exception as error:
            raise make_launch_error(executable_path, error) from error

        browser = None
        keep_browser_open = False
        try:
            try:
                browser = playwright.chromium.launch(
                    headless=headless,
                    executable_path=str(executable_path),
                )
            except Exception as error:
                raise make_launch_error(executable_path, error) from error

            context = browser.new_context()
            page = context.new_page()

            page.goto(FORM_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_selector("form, #survey, [data-subject-id]", timeout=15000)

            # 1. Fill suspect ID (Text input)
            # Find subject container containing "角色ID" or first text subject
            text_inputs = page.locator('input[type="text"]')
            ok, message = _fill_required_field(
                text_inputs.nth(0), suspect_id, "角色 ID"
            )
            if not ok:
                return False, message

            # 2. Select Server (Radio button: 雪吉拉 or 菇菇寶貝)
            # Find radio option containing server_name
            server_label = page.locator(
                f'label:has-text("{server_name}"), div:has-text("{server_name}")'
            ).last
            if not _is_visible(server_label):
                return False, "找不到表單的伺服器選項，已取消送出。"
            try:
                server_label.click()
            except Exception as error:
                LOGGER.warning("選取伺服器失敗 (%s)", type(error).__name__)
                return False, "無法選取表單的伺服器選項，已取消送出。"

            # 3. Fill Map Name (Text input)
            ok, message = _fill_required_field(
                text_inputs.nth(1), map_name, "地圖名稱"
            )
            if not ok:
                return False, message

            # 4. Fill Note (Text input)
            ok, message = _fill_required_field(
                text_inputs.nth(2), note, "違規說明"
            )
            if not ok:
                return False, message

            # SurveyCake can reorder text fields; the evidence field is a URL input.
            url_input = page.locator('input[type="url"]')
            if url_input.count() != 1 or not _is_visible(url_input):
                return False, "找不到唯一的事證網址欄位，已取消送出。"
            try:
                url_input.first.fill(evidence_url)
            except Exception as error:
                LOGGER.warning("填寫事證網址失敗 (%s)", type(error).__name__)
                return False, "無法填寫事證網址欄位，已取消送出。"

            # Wait briefly before submit.
            time.sleep(1)

            # Find Submit Button
            submit_btn = page.locator(
                'button:has-text("送出"), [role="button"]:has-text("送出"), '
                'div:has-text("送出")'
            ).last
            if not _is_visible(submit_btn):
                return False, "無法在表單找到「送出」按鈕，已取消送出。"
            try:
                current_url = page.url
                initial_url = current_url if isinstance(current_url, str) else None
            except Exception as error:
                LOGGER.debug("讀取送出前表單網址失敗 (%s)", type(error).__name__)
                initial_url = None
            response_confirmation = {"confirmed": False}
            try:
                page.on(
                    "response",
                    lambda response: _capture_submission_response(
                        response, response_confirmation
                    ),
                )
            except Exception as error:
                LOGGER.debug("監聽表單送出回應失敗 (%s)", type(error).__name__)
            keep_browser_open = True
            try:
                submit_btn.click()
            except Exception as error:
                LOGGER.warning("點擊表單送出按鈕失敗 (%s)", type(error).__name__)
                return False, "無法確認表單送出結果；表單視窗會保持開啟，請查看後手動關閉。"
            if _wait_for_submission_confirmation(
                page,
                initial_url=initial_url,
                response_confirmation=response_confirmation,
            ):
                return True, f"外掛 ID「{suspect_id}」成功送出回報！"
            reason = _submission_failure_reason(page)
            if reason:
                return False, f"{reason}。{SUBMISSION_WINDOW_FAILURE_MESSAGE}"
            return False, SUBMISSION_WINDOW_FAILURE_MESSAGE
        finally:
            if keep_browser_open and browser is not None:
                try:
                    _retain_submission_session(playwright, browser)
                    browser = None
                    playwright = None
                except Exception as error:  # pragma: no cover - runtime only
                    LOGGER.warning(
                        "保留失敗表單視窗失敗 (%s)", type(error).__name__
                    )
            if browser is not None:
                try:
                    browser.close()
                except Exception as error:  # pragma: no cover - runtime only
                    LOGGER.debug("關閉表單瀏覽器失敗 (%s)", type(error).__name__)
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception as error:  # pragma: no cover - runtime only
                    LOGGER.debug("停止表單 Playwright 失敗 (%s)", type(error).__name__)
    except PlaywrightBrowserError:
        raise
    except Exception as error:
        LOGGER.warning(
            "Gamania report submission failed (%s)", type(error).__name__
        )
        return False, "Playwright 表單發送失敗，請檢查網路與表單頁面後再試。"
