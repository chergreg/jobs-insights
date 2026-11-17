"""Tests hors ligne du module guichet (page de résultats et pagination)."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fixtures import FIXTURE_PAGE, make_article, make_page
from guichet import (
    CNP_CODES_TI,
    GUICHET_DELAY_SECONDS,
    build_search_url,
    fetch_guichet,
    parse_search_page,
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
            patch("guichet.fetch_url", side_effect=responses) as fetch,
            patch("guichet.time.sleep"),
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
            patch("guichet.fetch_url", side_effect=responses),
            patch("guichet.time.sleep") as sleep,
        ):
            fetch_guichet()

        self.assertEqual(sleep.call_count, 2)
        for call in sleep.call_args_list:
            self.assertGreaterEqual(call.args[0], GUICHET_DELAY_SECONDS)

    def test_stops_on_empty_page_when_total_is_unknown(self) -> None:
        responses = self.pages([25, 3], total=None) + [make_page([], None).encode()]
        with (
            patch("guichet.fetch_url", side_effect=responses) as fetch,
            patch("guichet.time.sleep"),
        ):
            records, summary = fetch_guichet()

        self.assertEqual(len(records), 28)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(summary["pages_read"], 3)

    def test_stops_if_site_repeats_the_same_page(self) -> None:
        page = self.pages([25], total=None)[0]
        with (
            patch("guichet.fetch_url", side_effect=[page, page]) as fetch,
            patch("guichet.time.sleep"),
        ):
            records, _summary = fetch_guichet()

        self.assertEqual(len(records), 25)
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
