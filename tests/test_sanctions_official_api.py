"""Unit tests for OfficialSanctionApiClient retries, delay injection, and cancellation."""

import json
import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

from maple_reporter.sanctions.official_api import (
    OfficialSanctionApiClient,
    SanctionSyncCancelledError,
)


class TestOfficialSanctionApiClient(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock(spec=requests.Session)
        self.recorded_delays: list[float] = []

        def mock_delay(min_s, max_s):
            self.recorded_delays.append(min_s)
            return 0.0  # Zero sleep for deterministic fast tests

        self.client = OfficialSanctionApiClient(
            session=self.mock_session,
            random_delay_func=mock_delay,
            timeout=(1.0, 1.0),
        )
        self.cancel_event = threading.Event()

    def test_first_request_executes_without_wait(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"myDataSet": {"table": []}}).encode("utf-8")
        self.mock_session.request.return_value = mock_response

        # 1st request -> no delay recorded
        headers = self.client.fetch_bulletin_list(page=1, cancel_event=self.cancel_event)
        self.assertEqual(len(self.recorded_delays), 0)

        # 2nd request -> delay recorded (3-8 seconds)
        headers2 = self.client.fetch_bulletin_list(page=2, cancel_event=self.cancel_event)
        self.assertEqual(len(self.recorded_delays), 1)

    def test_retry_on_500_server_error_and_success_on_attempt_2(self):
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.text = "Internal Server Error"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.content = json.dumps({"myDataSet": {"table": []}}).encode("utf-8")

        self.mock_session.request.side_effect = [resp_500, resp_200]

        headers = self.client.fetch_bulletin_list(page=1, cancel_event=self.cancel_event)
        self.assertEqual(self.mock_session.request.call_count, 2)

    def test_non_retryable_404_error_raises_immediately(self):
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        self.mock_session.request.return_value = resp_404

        with self.assertRaises(requests.HTTPError):
            self.client.fetch_bulletin_list(page=1, cancel_event=self.cancel_event)

        self.assertEqual(self.mock_session.request.call_count, 1)

    def test_cancellation_during_wait_raises_cancelled_error(self):
        self.client._has_sent_first_request = True
        self.cancel_event.set()

        with self.assertRaises(SanctionSyncCancelledError):
            self.client.fetch_bulletin_list(page=1, cancel_event=self.cancel_event)


if __name__ == "__main__":
    unittest.main()
