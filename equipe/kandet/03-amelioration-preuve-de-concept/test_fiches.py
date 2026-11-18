"""Tests hors ligne du module fiches (lecture RDFa et cache)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fiches import apply_details, enrich_with_postings, parse_job_posting
from fixtures import PARTNER_POSTING, make_posting
from guichet import GUICHET_DELAY_SECONDS
from modele import SourceRecord


def record(source_id: str, source: str = "Guichet-Emplois") -> SourceRecord:
    return SourceRecord(
        source=source,
        source_id=source_id,
        url=f"https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{source_id}",
        title="développeur Web/développeuse Web",
        location="Vaudreuil-Dorion (QC)",
    )


class ParseJobPostingTests(unittest.TestCase):
    def test_reads_fields_of_a_guichet_posting(self) -> None:
        details = parse_job_posting(make_posting())

        self.assertEqual(details.title, "développeur Web/développeuse Web")
        self.assertEqual(details.employer, "Mewlogic Inc.")
        self.assertTrue(details.description.startswith("Études: Baccalauréat."))
        self.assertEqual(details.expires_at, "2026-12-07")
        self.assertEqual(details.start_date, "2027-01-15")
        self.assertEqual(details.job_type, "Permanent, Temps plein")
        self.assertEqual(details.city, "Vaudreuil-Dorion")
        self.assertEqual(details.province, "QC")
        self.assertEqual(details.postal_code, "J7V 0M7")
        self.assertEqual(details.salary_min, "43,27")
        self.assertEqual(details.salary_max, "")
        self.assertEqual(details.salary_unit, "HOUR")
        self.assertEqual(details.conditions, "Jour, Horaire flexible")

    def test_reads_requirements_and_tasks(self) -> None:
        details = parse_job_posting(make_posting())

        self.assertEqual(details.education, "Baccalauréat, ou expérience équivalente, Informatique")
        self.assertEqual(details.experience, "5 ans ou plus")
        self.assertEqual(details.languages, ["Anglais"])
        self.assertEqual(
            details.tasks,
            [
                "Coordonner les projets informatiques",
                "Évaluer des logiciels d’application et résoudre des problèmes",
            ],
        )

    def test_screen_reader_text_is_not_kept(self) -> None:
        details = parse_job_posting(make_posting())
        self.assertNotIn("nouvelle fenêtre", details.employer)

    def test_partner_posting(self) -> None:
        details = parse_job_posting(PARTNER_POSTING)

        self.assertEqual(details.original_title, "Architecte d?ordinateur quantique Niveau 1")
        self.assertEqual(details.employer, "Nord Quantique")
        self.assertEqual(details.salary_min, "123 000")
        self.assertEqual(details.salary_max, "140 000")
        self.assertEqual(details.salary_unit, "YEAR")
        self.assertTrue(details.original_url.startswith("https://www.jobillico.com/"))

    def test_double_encoded_description_becomes_plain_text(self) -> None:
        details = parse_job_posting(PARTNER_POSTING)

        self.assertEqual(
            details.description,
            "Poste offert Vous ferez partie d?une organisation en croissance.",
        )
        self.assertNotIn("<", details.description)

    def test_missing_information_stays_empty(self) -> None:
        details = parse_job_posting(PARTNER_POSTING)
        self.assertEqual(details.education, "")
        self.assertEqual(details.experience, "")
        self.assertEqual(details.languages, [])
        self.assertEqual(details.tasks, [])

        no_salary = parse_job_posting(make_posting(salary_html="", valid_through=None))
        self.assertEqual((no_salary.salary_min, no_salary.salary_unit), ("", ""))
        self.assertEqual(no_salary.expires_at, "")

    def test_unicode_escapes_written_in_the_page_are_decoded(self) -> None:
        # Vu sur 10 fiches : « Général » écrit tel quel dans le HTML.
        details = parse_job_posting(
            make_posting(description=r"Études: Maîtrise. Informatique. Général.")
        )
        self.assertEqual(details.description, "Études: Maîtrise. Informatique. Général.")

    def test_empty_description_on_guichet(self) -> None:
        # Cas observé pour Québec emploi : la description est vide sur le Guichet-Emplois.
        details = parse_job_posting(make_posting(description=""))
        self.assertEqual(details.description, "")


class ApplyDetailsTests(unittest.TestCase):
    def test_fills_record_without_overwriting(self) -> None:
        item = record("1")
        item.job_type = "déjà connu"

        apply_details(item, parse_job_posting(make_posting()))

        self.assertEqual(item.job_type, "déjà connu")
        self.assertEqual(item.expires_at, "2026-12-07")
        self.assertEqual(item.city, "Vaudreuil-Dorion")
        self.assertEqual(item.source_data["posting"]["salary_unit"], "HOUR")


class EnrichWithPostingsTests(unittest.TestCase):
    def test_downloads_saves_and_waits_five_seconds(self) -> None:
        records = [record("1"), record("2")]
        with TemporaryDirectory() as folder:
            with (
                patch("fiches.fetch_url", return_value=make_posting().encode()) as fetch,
                patch("fiches.time.sleep") as sleep,
            ):
                summary = enrich_with_postings(records, Path(folder))
            saved = sorted(path.name for path in Path(folder).iterdir())

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [GUICHET_DELAY_SECONDS] * 2)
        self.assertEqual(saved, ["1.html", "2.html"])
        self.assertEqual(summary["downloaded"], 2)
        self.assertEqual(records[0].expires_at, "2026-12-07")

    def test_cached_posting_needs_no_request_and_no_delay(self) -> None:
        records = [record("1")]
        with TemporaryDirectory() as folder:
            (Path(folder) / "1.html").write_text(PARTNER_POSTING, encoding="utf-8")
            with (
                patch("fiches.fetch_url") as fetch,
                patch("fiches.time.sleep") as sleep,
            ):
                summary = enrich_with_postings(records, Path(folder))

        fetch.assert_not_called()
        sleep.assert_not_called()
        self.assertEqual(summary["from_cache"], 1)
        self.assertEqual(records[0].original_title, "Architecte d?ordinateur quantique Niveau 1")

    def test_max_postings_limits_requests(self) -> None:
        records = [record(str(number)) for number in range(1, 6)]
        with TemporaryDirectory() as folder:
            with (
                patch("fiches.fetch_url", return_value=make_posting().encode()) as fetch,
                patch("fiches.time.sleep"),
            ):
                summary = enrich_with_postings(records, Path(folder), max_postings=3)

        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(summary["read"], 3)
        self.assertEqual(records[3].expires_at, "")

    def test_remotive_records_are_skipped(self) -> None:
        records = [record("r1", source="Remotive")]
        with TemporaryDirectory() as folder:
            with patch("fiches.fetch_url") as fetch, patch("fiches.time.sleep"):
                summary = enrich_with_postings(records, Path(folder))
        fetch.assert_not_called()
        self.assertEqual(summary["read"], 0)

    def test_error_page_is_reported_and_not_cached(self) -> None:
        records = [record("1"), record("2")]
        pages = [b"<html><body>Offre introuvable</body></html>", make_posting().encode()]
        with TemporaryDirectory() as folder:
            with patch("fiches.fetch_url", side_effect=pages), patch("fiches.time.sleep"):
                summary = enrich_with_postings(records, Path(folder))
            saved = sorted(path.name for path in Path(folder).iterdir())

        self.assertEqual(len(summary["errors"]), 1)
        self.assertIn("1 :", summary["errors"][0])
        self.assertEqual(saved, ["2.html"])
        self.assertEqual(summary["read"], 1)

    def test_network_error_does_not_stop_the_others(self) -> None:
        records = [record("1"), record("2")]
        with TemporaryDirectory() as folder:
            with (
                patch("fiches.fetch_url", side_effect=[OSError("délai dépassé"), make_posting().encode()]),
                patch("fiches.time.sleep"),
            ):
                summary = enrich_with_postings(records, Path(folder))

        self.assertEqual(summary["read"], 1)
        self.assertEqual(records[1].city, "Vaudreuil-Dorion")


if __name__ == "__main__":
    unittest.main()
