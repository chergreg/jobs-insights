"""Tests hors ligne du prototype (aucun appel réseau).

Lancer depuis ce dossier : python -m unittest -v test_poc_multi_source.py
"""

import unittest
from datetime import datetime, timedelta, timezone
from email.message import Message
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from poc_multi_source import (
    CNP_CODES_TI,
    GUICHET_DELAY_SECONDS,
    SourceRecord,
    aggregate_records,
    build_search_url,
    build_summary,
    classify_stage,
    fetch_guichet,
    fetch_url,
    load_remotive_payload,
    parse_display_date,
    parse_remotive_payload,
    parse_search_page,
)


def make_article(
    job_id: int,
    title: str = "développeur Web/développeuse Web",
    origin: str = "Guichet-Emplois",
    employer: str = "Exemple inc.",
    location: str = "Québec (QC)",
    salary: str | None = "30,00 $ de l'heure",
    telework: str | None = None,
    date: str = "12 novembre 2026",
) -> str:
    """Reproduit le balisage d'une offre sur la page de résultats (novembre 2026)."""
    flags = '<span class="new">Nouveau</span>'
    if telework:
        flags += f'<span class="telework">{telework}</span>'
    if origin == "Guichet-Emplois":
        flags += (
            '<span class="appmethod">Candidature directe</span>'
            '<span class="postedonJB">Publiée sur le Guichet-Emplois'
            '<span class="description"><span class="fa fa-info-circle"></span>'
            "Cette offre d’emploi a été publiée directement par l’employeur.</span></span>"
        )
    salary_html = (
        f'<li class="salary"><span class="fa fa-dollar"></span> Salaire : {salary}</li>'
        if salary
        else ""
    )
    return f"""
<article id="article-{job_id}" class="action-buttons">
  <a href="/rechercheemplois/offredemploi/{job_id};jsessionid=ABC123.jobsearch76?source=searchresults"
     class="resultJobItem">
    <h3 class="title">
      <span class="flag">{flags}</span>
      <span class="job-source job-source-icon-16"><span class="wb-inv">{origin}</span></span>
      <span class="noctitle"> {title}
      </span>
    </h3>
    <ul class="list-unstyled">
      <li class="date">{date}
      </li>
      <li class="business">{employer}</li>
      <li class="location"><span class="fas fa-map-marker-alt"></span>
        <span class="wb-inv">Emplacement</span>
        {location}
      </li>
      {salary_html}
      <li class="source"><span class="job-source"><span class="wb-inv">{origin}</span></span>
        <span class="wb-inv">Numéro de l’offre :</span>
        <span class="fa fa-hashtag"></span>
        {job_id + 9000}</li>
    </ul></a>
  <div class="float job-action"><section class="mfp-hide"><p>Connexion<br>requise</p></section></div>
</article>"""


def make_page(articles: list[str], total: int | None = 3) -> str:
    count = f'<h2><span class="found" id="results-count">{total}</span> résultats</h2>' if total else ""
    return f"<html><body>{count}<div id='results'>{''.join(articles)}</div></body></html>"


FIXTURE_PAGE = make_page(
    [
        make_article(101, telework="Sur place"),
        make_article(
            102,
            title="agent/agente de soutien aux utilisateurs",
            origin="Jobillico",
            employer="GolfIn - Saint-Georges",
            location="Saint-Georges (QC)",
            salary="52 000,00 $ à 60 000,00 $ par année",
        ),
        make_article(
            103,
            title="stagiaire en programmation informatique",
            origin="Talent.com",
            employer="Studio Nord",
            location="Montréal (QC)",
            salary=None,
            telework="Hybride",
            date="9 novembre 2026",
        ),
    ]
)


class ParseSearchPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = parse_search_page(FIXTURE_PAGE, search_term="web")
        self.direct, self.jobillico, self.talent = self.page.records

    def test_reads_every_article_and_announced_total(self) -> None:
        self.assertEqual(len(self.page.records), 3)
        self.assertEqual(self.page.announced_total, 3)

    def test_extracts_main_fields(self) -> None:
        self.assertEqual(self.direct.title, "développeur Web/développeuse Web")
        self.assertEqual(self.direct.employer, "Exemple inc.")
        self.assertEqual(self.direct.location, "Québec (QC)")
        self.assertEqual(self.direct.salary, "30,00 $ de l'heure")
        self.assertEqual(self.direct.published_at, "2026-11-12")
        self.assertEqual(self.direct.work_mode, "Sur place")
        self.assertEqual(self.direct.source_id, "101")
        self.assertEqual(self.direct.source_data["job_number"], "9101")
        self.assertEqual(self.direct.search_terms, ["web"])

    def test_screen_reader_labels_are_not_kept(self) -> None:
        self.assertNotIn("Emplacement", self.direct.location)
        self.assertNotIn("Numéro", str(self.direct.source_data["job_number"]))
        self.assertNotIn("Nouveau", self.direct.work_mode)

    def test_removes_session_id_from_posting_link(self) -> None:
        self.assertEqual(
            self.direct.url,
            "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/101",
        )

    def test_keeps_origin_site_of_partner_postings(self) -> None:
        self.assertEqual(self.direct.origin_site, "Guichet-Emplois")
        self.assertTrue(self.direct.source_data["posted_on_guichet"])
        self.assertEqual(self.jobillico.origin_site, "Jobillico")
        self.assertFalse(self.jobillico.source_data["posted_on_guichet"])

    def test_missing_fields_stay_empty(self) -> None:
        self.assertEqual(self.talent.salary, "")
        self.assertEqual(self.jobillico.work_mode, "")

    def test_detects_stage_in_title(self) -> None:
        self.assertEqual(self.talent.stage_status, "confirmed_stage")
        self.assertEqual(self.direct.stage_status, "not_indicated")

    def test_page_without_results(self) -> None:
        page = parse_search_page(make_page([], total=None))
        self.assertEqual(page.records, [])
        self.assertIsNone(page.announced_total)


class SearchUrlTests(unittest.TestCase):
    def test_default_url_filters_it_codes_and_quebec(self) -> None:
        query = parse_qs(urlparse(build_search_url()).query)
        self.assertEqual(query["fn21"], list(CNP_CODES_TI))
        self.assertEqual(query["fprov"], ["QC"])
        self.assertNotIn("page", query)
        self.assertNotIn("searchstring", query)

    def test_url_with_term_page_and_no_filters(self) -> None:
        query = parse_qs(
            urlparse(build_search_url(page=4, term="stage", province=None, cnp_codes=None)).query
        )
        self.assertEqual(query["searchstring"], ["stage"])
        self.assertEqual(query["page"], ["4"])
        self.assertNotIn("fn21", query)
        self.assertNotIn("fprov", query)


class FetchGuichetTests(unittest.TestCase):
    @staticmethod
    def pages(sizes: list[int], total: int | None) -> list[bytes]:
        result = []
        next_id = 1
        for size in sizes:
            articles = [make_article(job_id) for job_id in range(next_id, next_id + size)]
            next_id += size
            result.append(make_page(articles, total).encode("utf-8"))
        return result

    def test_reads_all_pages_without_cap(self) -> None:
        # 12 pages de 25 + 1 page de 10 = 310 offres : aucun plafond ne doit s'appliquer.
        responses = self.pages([25] * 12 + [10], total=310)
        with (
            patch("poc_multi_source.fetch_url", side_effect=responses) as fetch,
            patch("poc_multi_source.time.sleep") as sleep,
        ):
            records, summary = fetch_guichet()

        self.assertEqual(len(records), 310)
        self.assertEqual(summary["collected"], 310)
        self.assertEqual(summary["pages_read"], 13)
        self.assertEqual(fetch.call_count, 13)
        requested = [
            parse_qs(urlparse(call.args[0]).query).get("page", ["1"])[0]
            for call in fetch.call_args_list
        ]
        self.assertEqual(requested, [str(number) for number in range(1, 14)])

    def test_waits_five_seconds_between_pages(self) -> None:
        responses = self.pages([25, 25, 5], total=55)
        with (
            patch("poc_multi_source.fetch_url", side_effect=responses),
            patch("poc_multi_source.time.sleep") as sleep,
        ):
            fetch_guichet()

        self.assertEqual(sleep.call_count, 2)
        for call in sleep.call_args_list:
            self.assertGreaterEqual(call.args[0], GUICHET_DELAY_SECONDS)

    def test_stops_on_empty_page_when_total_is_unknown(self) -> None:
        responses = self.pages([25, 3], total=None) + [make_page([], None).encode()]
        with (
            patch("poc_multi_source.fetch_url", side_effect=responses) as fetch,
            patch("poc_multi_source.time.sleep"),
        ):
            records, summary = fetch_guichet()

        self.assertEqual(len(records), 28)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(summary["pages_read"], 3)

    def test_stops_if_site_repeats_the_same_page(self) -> None:
        page = self.pages([25], total=None)[0]
        with (
            patch("poc_multi_source.fetch_url", side_effect=[page, page]) as fetch,
            patch("poc_multi_source.time.sleep"),
        ):
            records, _summary = fetch_guichet()

        self.assertEqual(len(records), 25)
        self.assertEqual(fetch.call_count, 2)


class FetchUrlTests(unittest.TestCase):
    def test_retries_once_after_too_many_requests(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        error = HTTPError("https://example.test", 429, "Too Many Requests", Message(), None)
        with (
            patch("poc_multi_source.urlopen", side_effect=[error, response]) as opener,
            patch("poc_multi_source.time.sleep") as sleep,
        ):
            self.assertEqual(fetch_url("https://example.test", "text/html"), b"ok")

        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once()

    def test_other_http_errors_are_not_retried(self) -> None:
        error = HTTPError("https://example.test", 404, "Not Found", Message(), None)
        with (
            patch("poc_multi_source.urlopen", side_effect=error) as opener,
            patch("poc_multi_source.time.sleep"),
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


class RemotiveTests(unittest.TestCase):
    PAYLOAD = {
        "total-job-count": 3,
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
                "title": "Technical Writer",
                "candidate_required_location": "Worldwide",
                "category": "Writing",
            },
        ],
    }

    def test_keeps_it_categories_and_all_locations_by_default(self) -> None:
        jobs = parse_remotive_payload(self.PAYLOAD)
        self.assertEqual([job.source_id for job in jobs], ["42", "43"])

    def test_canada_filter(self) -> None:
        jobs = parse_remotive_payload(self.PAYLOAD, location_filter=True)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].description, "Build tools with Python .")
        self.assertEqual(jobs[0].stage_status, "confirmed_stage")
        self.assertEqual(jobs[0].origin_site, "Remotive")
        self.assertNotIn("description", jobs[0].source_data)

    def test_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            parse_remotive_payload({"jobs": "rien"})

    def write_cache(self, folder: str, fetched_at: datetime, **extra: object) -> Path:
        cache_path = Path(folder) / "remotive-cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": fetched_at.isoformat(),
                    "request_url": "https://remotive.com/api/remote-jobs",
                    "payload": {"jobs": [{"id": "en-cache"}]},
                    **extra,
                }
            ),
            encoding="utf-8",
        )
        return cache_path

    def test_fresh_cache_avoids_api_call(self) -> None:
        with TemporaryDirectory() as folder:
            cache_path = self.write_cache(folder, datetime.now(timezone.utc))
            with patch("poc_multi_source.fetch_url") as fetch:
                payload = load_remotive_payload(cache_path)
        self.assertEqual(payload, {"jobs": [{"id": "en-cache"}]})
        fetch.assert_not_called()

    def test_old_cache_is_refreshed_and_saved(self) -> None:
        with TemporaryDirectory() as folder:
            cache_path = self.write_cache(folder, datetime.now(timezone.utc) - timedelta(hours=25))
            with patch(
                "poc_multi_source.fetch_url",
                return_value=json.dumps({"jobs": []}).encode(),
            ) as fetch:
                payload = load_remotive_payload(cache_path)
            saved = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(payload, {"jobs": []})
        fetch.assert_called_once()
        self.assertEqual(saved["payload"], {"jobs": []})


class StageDetectionTests(unittest.TestCase):
    def test_stage_word_in_title(self) -> None:
        self.assertEqual(
            classify_stage("Stagiaire développeur", "", ""),
            ("confirmed_stage", ["stage_term_in_title"]),
        )

    def test_internship_job_type(self) -> None:
        self.assertEqual(
            classify_stage("Software engineer", "internship", "Build APIs."),
            ("confirmed_stage", ["explicit_internship_job_type"]),
        )

    def test_internship_role_in_description_is_possible(self) -> None:
        self.assertEqual(
            classify_stage("Junior developer", "full_time", "This internship position is open."),
            ("possible_stage", ["stage_role_in_description"]),
        )

    def test_past_internship_experience_is_not_a_stage(self) -> None:
        self.assertEqual(
            classify_stage("Junior developer", "full_time", "Previous internship experience is an asset."),
            ("not_indicated", []),
        )

    def test_french_student_condition_without_accents(self) -> None:
        self.assertEqual(
            classify_stage("Développeur junior", "", "Le candidat doit être inscrit à un programme."),
            ("possible_stage", ["student_eligibility_in_description"]),
        )


class AggregationTests(unittest.TestCase):
    @staticmethod
    def record(source_id: str, origin: str, **changes: str) -> SourceRecord:
        values = {
            "title": "développeur Web/développeuse Web",
            "employer": "Exemple inc.",
            "location": "Québec (QC)",
        }
        values.update(changes)
        return SourceRecord(
            source=changes.pop("source", "Guichet-Emplois"),
            source_id=source_id,
            url=f"https://example.test/{source_id}",
            origin_site=origin,
            **{key: value for key, value in values.items() if key != "source"},
        )

    def test_same_posting_found_by_two_searches_is_kept_once(self) -> None:
        first = self.record("1", "Jobillico")
        first.search_terms = ["web"]
        second = self.record("1", "Jobillico")
        second.search_terms = ["developpeur"]

        offers = aggregate_records([first, second])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].source_records[0].search_terms, ["web", "developpeur"])

    def test_same_job_republished_by_two_partner_sites_is_merged(self) -> None:
        jobillico = self.record("1", "Jobillico", salary="")
        talent = self.record("2", "Talent.com", salary="30,00 $ de l'heure")

        offers = aggregate_records([jobillico, talent])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].salary, "30,00 $ de l'heure")
        self.assertEqual(
            [record.origin_site for record in offers[0].source_records],
            ["Jobillico", "Talent.com"],
        )
        self.assertEqual(build_summary(offers)["merged_offers"], 1)

    def test_two_identical_titles_from_same_site_stay_separate(self) -> None:
        offers = aggregate_records([self.record("1", "Jobillico"), self.record("2", "Jobillico")])
        self.assertEqual(len(offers), 2)

    def test_different_employers_are_not_merged(self) -> None:
        offers = aggregate_records(
            [self.record("1", "Jobillico"), self.record("2", "Talent.com", employer="Autre inc.")]
        )
        self.assertEqual(len(offers), 2)

    def test_stage_status_keeps_strongest_signal(self) -> None:
        guichet = self.record("1", "Jobillico")
        remotive = self.record("r1", "Remotive", source="Remotive")
        remotive.stage_status = "possible_stage"

        offers = aggregate_records([guichet, remotive])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].stage_status, "possible_stage")


if __name__ == "__main__":
    unittest.main()
