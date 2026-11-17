"""Tests hors ligne des modules collecte (HTTP) et texte (dates)."""

import unittest
from email.message import Message
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from collecte import fetch_url
from texte import parse_display_date


class FetchUrlTests(unittest.TestCase):
    def test_retries_once_after_too_many_requests(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        error = HTTPError("https://example.test", 429, "Too Many Requests", Message(), None)
        with (
            patch("collecte.urlopen", side_effect=[error, response]) as opener,
            patch("collecte.time.sleep") as sleep,
        ):
            self.assertEqual(fetch_url("https://example.test", "text/html"), b"ok")

        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once()

    def test_other_http_errors_are_not_retried(self) -> None:
        error = HTTPError("https://example.test", 404, "Not Found", Message(), None)
        with (
            patch("collecte.urlopen", side_effect=error) as opener,
            patch("collecte.time.sleep"),
        ):
            with self.assertRaises(HTTPError):
                fetch_url("https://example.test", "text/html")
        self.assertEqual(opener.call_count, 1)


class DateTests(unittest.TestCase):
    def test_french_and_english_dates(self) -> None:
        self.assertEqual(parse_display_date("12 novembre 2026"), "2026-11-12")
        self.assertEqual(parse_display_date("1 février 2026"), "2026-02-01")
        self.assertEqual(parse_display_date("November 12, 2026"), "2026-11-12")

    def test_unknown_format_stays_empty(self) -> None:
        self.assertEqual(parse_display_date(""), "")
        self.assertEqual(parse_display_date("hier"), "")


if __name__ == "__main__":
    unittest.main()
