import unittest
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from poc_multi_source import (
    aggregate_records,
    build_feed_url,
    classify_stage,
    load_remotive_payload,
    parse_feed,
    parse_remotive_payload,
)


ATOM_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title><![CDATA[Développeur logiciel]]></title>
    <link rel="alternate" href="https://example.test/job/1"/>
    <updated>2026-11-09T10:00:00Z</updated>
    <summary type="html"><![CDATA[<strong>Job number:</strong> 123<br />
      <strong>Location:</strong> Montréal (QC)<br />
      <strong>Employer:</strong> Exemple inc.<br />
      <strong>Salary:</strong> $30.00 hourly]]></summary>
  </entry>
  <entry>
    <title><![CDATA[Software developer]]></title>
    <link rel="alternate" href="https://example.test/job/2"/>
    <summary type="html"><![CDATA[<strong>Job number:</strong> 456<br />
      <strong>Location:</strong> Toronto (ON)<br />
      <strong>Employer:</strong> Example Ltd.<br />
      <strong>Salary:</strong> $40.00 hourly]]></summary>
  </entry>
</feed>
""".encode("utf-8")


class ParseFeedTests(unittest.TestCase):
    def test_extracts_all_feed_entries_and_fields(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Développeur logiciel")
        self.assertEqual(jobs[0].location, "Montréal (QC)")
        self.assertEqual(jobs[0].employer, "Exemple inc.")
        self.assertEqual(jobs[0].salary, "$30.00 hourly")
        self.assertEqual(jobs[0].url, "https://example.test/job/1")
        self.assertEqual(jobs[0].source_id, "123")

    def test_location_filter_ignores_accents(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE, location="Montreal")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].location, "Montréal (QC)")

    def test_none_location_keeps_all_entries(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE, location=None)

        self.assertEqual(len(jobs), 2)

    def test_feed_url_includes_relevant_category_filters(self) -> None:
        query = parse_qs(urlparse(build_feed_url("developpeur", 100)).query)

        self.assertEqual(query["fn21"], ["21230", "21232", "21234"])
        self.assertEqual(query["term"], ["developpeur"])
        self.assertEqual(query["rows"], ["100"])


class RemotiveTests(unittest.TestCase):
    def test_parses_full_description_and_filters_non_canadian_locations(self) -> None:
        jobs = parse_remotive_payload(
            {
                "jobs": [
                    {
                        "id": 42,
                        "url": "https://remotive.com/remote-jobs/software-dev/intern-42",
                        "title": "Software Engineer Intern",
                        "company_name": "Example",
                        "candidate_required_location": "Canada",
                        "job_type": "internship",
                        "category": "Software Development",
                        "tags": ["Python", "Remote"],
                        "publication_date": "2026-11-09T10:00:00",
                        "salary": "$20/hour",
                        "description": "<p>Build tools with <strong>Python</strong>.</p>",
                    },
                    {
                        "id": 43,
                        "url": "https://remotive.com/remote-jobs/software-dev/other-43",
                        "title": "Developer",
                        "candidate_required_location": "United States",
                        "category": "Software Development",
                    },
                    {
                        "id": 44,
                        "url": "https://remotive.com/remote-jobs/writing/writer-44",
                        "title": "Technical Writer",
                        "candidate_required_location": "Worldwide",
                        "category": "Writing",
                    },
                ]
            }
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "Remotive")
        self.assertEqual(jobs[0].source_id, "42")
        self.assertEqual(jobs[0].description, "Build tools with Python .")
        self.assertEqual(jobs[0].stage_status, "likely_stage")
        self.assertIn("Python", jobs[0].tags)

    def test_can_include_remotive_jobs_for_other_locations(self) -> None:
        jobs = parse_remotive_payload(
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Developer",
                        "candidate_required_location": "France",
                        "category": "Software Development",
                    }
                ]
            },
            location_filter=False,
        )

        self.assertEqual(len(jobs), 1)

    def test_reuses_a_fresh_local_cache_without_calling_the_api(self) -> None:
        payload = {"jobs": [{"id": 42}]}
        with TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "remotive-cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "payload": payload,
                    }
                ),
                encoding="utf-8",
            )
            with patch("poc_multi_source.fetch_url") as fetch:
                cached_payload = load_remotive_payload(cache_path)

        self.assertEqual(cached_payload, payload)
        fetch.assert_not_called()


class StageDetectionTests(unittest.TestCase):
    def test_detects_stage_in_title_or_job_type(self) -> None:
        status, signals = classify_stage("Stagiaire développeur", "", "")

        self.assertEqual(status, "likely_stage")
        self.assertEqual(signals, ["stage_term_in_title_or_job_type"])

    def test_detects_stage_only_mentioned_in_description_as_possible(self) -> None:
        status, signals = classify_stage(
            "Junior developer",
            "full_time",
            "Must be enrolled as a student; internship experience is an asset.",
        )

        self.assertEqual(status, "possible_stage")
        self.assertEqual(signals, ["stage_term_in_description"])

    def test_non_stage_has_no_stage_signals(self) -> None:
        self.assertEqual(
            classify_stage("Software developer", "full_time", "Build APIs."),
            ("not_indicated", []),
        )


class AggregationTests(unittest.TestCase):
    def test_keeps_sources_when_duplicate_offers_are_merged(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE)
        duplicate = type(jobs[0])(
            source="Remotive",
            source_id="remotive-1",
            url="https://remotive.com/job/1",
            title=jobs[0].title,
            employer=jobs[0].employer,
            location=jobs[0].location,
            description="Internship position.",
            stage_status="possible_stage",
            stage_signals=["stage_term_in_description"],
        )

        offers = aggregate_records([jobs[0], duplicate])

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            [record.source for record in offers[0].source_records],
            ["Guichet-Emplois", "Remotive"],
        )
        self.assertEqual(offers[0].stage_status, "possible_stage")

    def test_removes_duplicate_results_from_the_same_source(self) -> None:
        job = parse_feed(ATOM_FIXTURE)[0]
        offers = aggregate_records([job, job])

        self.assertEqual(len(offers), 1)
        self.assertEqual(len(offers[0].source_records), 1)


if __name__ == "__main__":
    unittest.main()
