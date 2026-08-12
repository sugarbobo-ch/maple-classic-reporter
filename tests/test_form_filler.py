import unittest
from unittest.mock import Mock, patch

from maple_reporter.automation.form_filler import (
    FORM_URL,
    SUBMISSION_ENDPOINT,
    _capture_submission_response,
    _is_submission_success_payload,
    _wait_for_submission_confirmation,
    submit_gamania_report,
)


class _Locator:
    def __init__(self, *, visible=False, count=1):
        self._visible = visible
        self._count = count
        self.first = self
        self.last = self

    def count(self):
        return self._count

    def is_visible(self):
        return self._visible

    def fill(self, _value):
        pass

    def click(self):
        pass

    def nth(self, _index):
        return self


class _Request:
    method = "POST"


class _Response:
    status = 200
    request = _Request()

    def __init__(self, url=SUBMISSION_ENDPOINT, payload=None):
        self.url = url
        self._payload = payload or {
            "status": True,
            "data": {
                "redirect": "thankyou",
                "fileHash": "8291d2182c49bb2647e79ea2978305cc",
            },
        }

    def json(self):
        return self._payload


class SubmissionConfirmationTests(unittest.TestCase):
    def test_actual_surveycake_success_payload_is_accepted_without_file_hash(self):
        payload = {"status": True, "data": {"redirect": "thankyou"}}
        self.assertTrue(_is_submission_success_payload(payload))

    def test_submission_response_is_scoped_to_actual_post_endpoint(self):
        state = {"confirmed": False}
        _capture_submission_response(_Response(), state)
        self.assertTrue(state["confirmed"])

        state = {"confirmed": False}
        _capture_submission_response(
            _Response("https://forms.gamania.com/api/v2/s/other"), state
        )
        self.assertFalse(state["confirmed"])

    def test_api_confirmation_can_finish_without_page_url_guess(self):
        page = Mock()
        page.url = FORM_URL
        page.locator.return_value = _Locator(visible=False)
        self.assertTrue(
            _wait_for_submission_confirmation(
                page,
                timeout_ms=100,
                initial_url=FORM_URL,
                response_confirmation={"confirmed": True},
            )
        )

    def test_actual_success_message_is_accepted(self):
        page = Mock()
        page.url = FORM_URL
        page.locator.side_effect = lambda selector: _Locator(
            visible=selector == 'text="收到你的回覆囉！"'
        )
        self.assertTrue(_wait_for_submission_confirmation(page, timeout_ms=100))

    def test_confirmation_requires_visible_success_state(self):
        page = Mock()
        page.locator.return_value = _Locator(visible=False)
        with patch("maple_reporter.automation.form_filler.time.monotonic", side_effect=[0, 2]):
            self.assertFalse(_wait_for_submission_confirmation(page, timeout_ms=1000))

    def test_confirmation_accepts_explicit_visible_success_state(self):
        page = Mock()
        page.locator.return_value = _Locator(visible=True)
        self.assertTrue(_wait_for_submission_confirmation(page, timeout_ms=1000))

    @patch("maple_reporter.automation.form_filler._retain_submission_session")
    @patch("maple_reporter.automation.form_filler.resolve_chromium_executable")
    @patch("maple_reporter.automation.form_filler.sync_playwright")
    @patch("maple_reporter.automation.form_filler._wait_for_submission_confirmation")
    def test_unconfirmed_submit_is_reported_as_failure(
        self, confirm, sync_playwright, resolve_executable, retain_session
    ):
        resolve_executable.return_value = "chromium.exe"
        confirm.return_value = False
        page = Mock()

        def locator(selector):
            if selector == 'input[type="url"]':
                return _Locator(visible=True, count=1)
            return _Locator(visible=True)

        page.locator.side_effect = locator
        browser = Mock()
        browser.new_context.return_value.new_page.return_value = page
        runtime = Mock()
        runtime.chromium.launch.return_value = browser
        sync_playwright.return_value.start.return_value = runtime

        ok, message = submit_gamania_report(
            "suspect", "雪吉拉", "測試地圖", "note", "https://example.com/evidence"
        )

        self.assertFalse(ok)
        self.assertIn("保持開啟", message)
        self.assertIn("本機證據會保留", message)
        retain_session.assert_called_once_with(runtime, browser)
        browser.close.assert_not_called()
        runtime.stop.assert_not_called()

    @patch("maple_reporter.automation.form_filler._retain_submission_session")
    @patch("maple_reporter.automation.form_filler.resolve_chromium_executable")
    @patch("maple_reporter.automation.form_filler.sync_playwright")
    @patch("maple_reporter.automation.form_filler._wait_for_submission_confirmation")
    def test_confirmed_submit_closes_the_form_browser(
        self, confirm, sync_playwright, resolve_executable, retain_session
    ):
        resolve_executable.return_value = "chromium.exe"
        confirm.return_value = True
        page = Mock()

        def locator(selector):
            if selector == 'input[type="url"]':
                return _Locator(visible=True, count=1)
            return _Locator(visible=True)

        page.locator.side_effect = locator
        browser = Mock()
        browser.new_context.return_value.new_page.return_value = page
        runtime = Mock()
        runtime.chromium.launch.return_value = browser
        sync_playwright.return_value.start.return_value = runtime

        ok, _message = submit_gamania_report(
            "suspect", "server", "test map", "note", "https://example.com/evidence"
        )

        self.assertTrue(ok)
        retain_session.assert_not_called()
        browser.close.assert_called_once_with()
        runtime.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
