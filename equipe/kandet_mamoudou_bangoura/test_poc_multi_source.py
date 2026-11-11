import unittest
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from poc_multi_source import (
    JOB_BANK_PAGE_SIZE,
    aggregate_records,
    build_feed_url,
    classify_stage,
    fetch_job_bank,
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
        jobs = parse_feed(ATOM_FIXTURE, search_term="developpeur")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Développeur logiciel")
        self.assertEqual(jobs[0].location, "Montréal (QC)")
        self.assertEqual(jobs[0].employer, "Exemple inc.")
        self.assertEqual(jobs[0].salary, "$30.00 hourly")
        self.assertEqual(jobs[0].url, "https://example.test/job/1")
        self.assertEqual(jobs[0].source_id, "123")
        self.assertEqual(jobs[0].search_terms, ["developpeur"])

    def test_location_filter_ignores_accents(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE, location="Montreal")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].location, "Montréal (QC)")

    def test_none_location_keeps_all_entries(self) -> None:
        jobs = parse_feed(ATOM_FIXTURE, location=None)

        self.assertEqual(len(jobs), 2)

    def test_skips_empty_feed_placeholder_entries(self) -> None:
        feed = b"""<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title></title><summary></summary></entry>
        </feed>"""

        self.assertEqual(parse_feed(feed, location=None), [])

    def test_feed_url_includes_relevant_category_filters(self) -> None:
        query = parse_qs(urlparse(build_feed_url("developpeur")).query)

        self.assertEqual(query["fn21"], ["21230", "21232", "21234"])
        self.assertEqual(query["term"], ["developpeur"])
        self.assertEqual(query["rows"], [str(JOB_BANK_PAGE_SIZE)])
        self.assertNotIn("page", query)

    def test_feed_url_targets_requested_page(self) -> None:
        query = parse_qs(urlparse(build_feed_url("developpeur", page=7)).query)

        self.assertEqual(query["page"], ["7"])

    def test_fetch_job_bank_continues_until_feed_pages_are_exhausted(self) -> None:
        def make_feed(start: int, count: int) -> bytes:
            entries = "".join(
                f"""
                <entry>
                  <title>Developer {job_id}</title>
                  <link rel="alternate" href="https://example.test/job/{job_id}"/>
                  <summary type="html"><![CDATA[
                    <strong>Job number:</strong> {job_id}<br />
                    <strong>Location:</strong> Montréal (QC)<br />
                    <strong>Employer:</strong> Example Inc.<br />
                    <strong>Salary:</strong> $30 hourly
                  ]]></summary>
                </entry>
                """
                for job_id in range(start, start + count)
            )
            return (
                f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'
            ).encode()

        full_page_one = make_feed(1, JOB_BANK_PAGE_SIZE)
        full_page_two = make_feed(JOB_BANK_PAGE_SIZE + 1, JOB_BANK_PAGE_SIZE)
        empty_page = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with (
            patch(
                "poc_multi_source.fetch_url",
                side_effect=[full_page_one, full_page_two, empty_page],
            ) as fetch,
            patch("poc_multi_source.time.sleep") as sleep,
        ):
            records, page_count = fetch_job_bank("developer", "QC")

        self.assertEqual(len(records), JOB_BANK_PAGE_SIZE * 2)
        self.assertEqual(page_count, 3)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        requested_pages = [
            parse_qs(urlparse(call.args[0]).query).get("page", ["1"])[0]
            for call in fetch.call_args_list
        ]
        self.assertEqual(requested_pages, ["1", "2", "3"])

    def test_fetch_job_bank_does_not_stop_at_a_short_nonempty_page(self) -> None:
        empty_page = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with (
            patch(
                "poc_multi_source.fetch_url",
                side_effect=[ATOM_FIXTURE, empty_page],
            ) as fetch,
            patch("poc_multi_source.time.sleep"),
        ):
            records, page_count = fetch_job_bank("developer", "QC")

        self.assertEqual(len(records), 1)
        self.assertEqual(page_count, 2)
        self.assertEqual(fetch.call_count, 2)

    def test_fetch_job_bank_stops_if_a_page_repeats(self) -> None:
        def make_full_page() -> bytes:
            entries = "".join(
                f"""
                <entry>
                  <title>Developer {job_id}</title>
                  <link rel="alternate" href="https://example.test/job/{job_id}"/>
                  <summary type="html"><![CDATA[
                    <strong>Job number:</strong> {job_id}<br />
                    <strong>Location:</strong> Montréal (QC)<br />
                    <strong>Employer:</strong> Example Inc.<br />
                    <strong>Salary:</strong> $30 hourly
                  ]]></summary>
                </entry>
                """
                for job_id in range(JOB_BANK_PAGE_SIZE)
            )
            return f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'.encode()

        repeated_page = make_full_page()
        with (
            patch(
                "poc_multi_source.fetch_url",
                side_effect=[repeated_page, repeated_page],
            ) as fetch,
            patch("poc_multi_source.time.sleep"),
        ):
            records, page_count = fetch_job_bank("developer", "QC")

        self.assertEqual(len(records), JOB_BANK_PAGE_SIZE)
        self.assertEqual(page_count, 2)
        self.assertEqual(fetch.call_count, 2)


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
            },
            location_filter=True,
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "Remotive")
        self.assertEqual(jobs[0].source_id, "42")
        self.assertEqual(jobs[0].description, "Build tools with Python .")
        self.assertEqual(jobs[0].stage_status, "confirmed_stage")
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

    def test_includes_all_remotive_locations_by_default(self) -> None:
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
            }
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
                        "request_url": "https://remotive.com/api/remote-jobs",
                        "payload": payload,
                    }
                ),
                encoding="utf-8",
            )
            with patch("poc_multi_source.fetch_url") as fetch:
                cached_payload = load_remotive_payload(cache_path)

        self.assertEqual(cached_payload, payload)
        fetch.assert_not_called()

    def test_refetches_legacy_cache_without_the_unlimited_endpoint_marker(self) -> None:
        payload = {"jobs": []}
        with TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "remotive-cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "payload": {"jobs": [{"id": "stale-limited-result"}]},
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "poc_multi_source.fetch_url",
                return_value=json.dumps(payload).encode(),
            ) as fetch:
                refreshed = load_remotive_payload(cache_path)

            stored_cache = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(refreshed, payload)
        fetch.assert_called_once_with(
            "https://remotive.com/api/remote-jobs",
            "application/json",
        )
        self.assertEqual(stored_cache["request_url"], "https://remotive.com/api/remote-jobs")


class StageDetectionTests(unittest.TestCase):
    def test_detects_stage_in_title_or_job_type(self) -> None:
        status, signals = classify_stage("Stagiaire développeur", "", "")

        self.assertEqual(status, "confirmed_stage")
        self.assertEqual(signals, ["stage_term_in_title"])

    def test_explicit_internship_job_type_is_confirmed(self) -> None:
        self.assertEqual(
            classify_stage("Software engineer", "internship", "Build APIs."),
            ("confirmed_stage", ["explicit_internship_job_type"]),
        )

    def test_detects_internship_role_in_description_as_possible(self) -> None:
        status, signals = classify_stage(
            "Junior developer",
            "full_time",
            "This internship position is for a junior developer.",
        )

        self.assertEqual(status, "possible_stage")
        self.assertEqual(signals, ["stage_role_in_description"])

    def test_does_not_mark_prior_internship_experience_as_a_stage(self) -> None:
        self.assertEqual(
            classify_stage(
                "Junior developer",
                "full_time",
                "Previous internship experience is an asset.",
            ),
            ("not_indicated", []),
        )

    def test_detects_french_student_eligibility_without_accent_dependency(self) -> None:
        self.assertEqual(
            classify_stage(
                "Développeur junior",
                "temps plein",
                "Le candidat doit être inscrit à un programme universitaire.",
            ),
            ("possible_stage", ["student_eligibility_in_description"]),
        )

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

    def test_merges_repeat_search_hits_and_keeps_all_query_terms(self) -> None:
        first = parse_feed(ATOM_FIXTURE, search_term="developpeur")[0]
        second = parse_feed(ATOM_FIXTURE, search_term="programmeur")[0]

        offers = aggregate_records([first, second])

        self.assertEqual(len(offers), 1)
        self.assertEqual(len(offers[0].source_records), 1)
        self.assertEqual(
            offers[0].source_records[0].search_terms,
            ["developpeur", "programmeur"],
        )

    def test_keeps_distinct_same_source_job_ids_with_same_employer_and_title(self) -> None:
        first = parse_feed(ATOM_FIXTURE)[0]
        second = type(first)(
            source=first.source,
            source_id="another-job-number",
            url="https://example.test/job/another",
            title=first.title,
            employer=first.employer,
            location=first.location,
        )

        offers = aggregate_records([first, second])

        self.assertEqual(len(offers), 2)


if __name__ == "__main__":
    unittest.main()
