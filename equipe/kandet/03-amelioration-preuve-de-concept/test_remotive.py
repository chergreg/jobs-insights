"""Tests hors ligne du module remotive (filtres et cache 24 h)."""

import unittest
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fixtures import REMOTIVE_PAYLOAD
from remotive import load_remotive_payload, parse_remotive_payload


class RemotiveTests(unittest.TestCase):
    def test_keeps_it_categories_and_all_locations_by_default(self) -> None:
        jobs = parse_remotive_payload(REMOTIVE_PAYLOAD)
        self.assertEqual([job.source_id for job in jobs], ["42", "43"])

    def test_canada_filter(self) -> None:
        jobs = parse_remotive_payload(REMOTIVE_PAYLOAD, location_filter=True)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].description, "Build tools with Python .")
        self.assertEqual(jobs[0].stage_status, "confirmed_stage")
        self.assertEqual(jobs[0].origin_site, "Remotive")
        self.assertNotIn("description", jobs[0].source_data)

    def test_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            parse_remotive_payload({"jobs": "rien"})

    @staticmethod
    def write_cache(folder: str, fetched_at: datetime) -> Path:
        cache_path = Path(folder) / "remotive-cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": fetched_at.isoformat(),
                    "request_url": "https://remotive.com/api/remote-jobs",
                    "payload": {"jobs": [{"id": "en-cache"}]},
                }
            ),
            encoding="utf-8",
        )
        return cache_path

    def test_fresh_cache_avoids_api_call(self) -> None:
        with TemporaryDirectory() as folder:
            cache_path = self.write_cache(folder, datetime.now(timezone.utc))
            with patch("remotive.fetch_url") as fetch:
                payload = load_remotive_payload(cache_path)
        self.assertEqual(payload, {"jobs": [{"id": "en-cache"}]})
        fetch.assert_not_called()

    def test_old_cache_is_refreshed_and_saved(self) -> None:
        with TemporaryDirectory() as folder:
            cache_path = self.write_cache(folder, datetime.now(timezone.utc) - timedelta(hours=25))
            with patch(
                "remotive.fetch_url",
                return_value=json.dumps({"jobs": []}).encode(),
            ) as fetch:
                payload = load_remotive_payload(cache_path)
            saved = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(payload, {"jobs": []})
        fetch.assert_called_once()
        self.assertEqual(saved["payload"], {"jobs": []})


if __name__ == "__main__":
    unittest.main()
