"""Tests hors ligne des modules analyse (stages) et fusion (doublons)."""

import unittest

from analyse import build_summary, classify_stage
from fusion import aggregate_records
from modele import SourceRecord


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


def record(source_id: str, origin: str, source: str = "Guichet-Emplois", **changes: str) -> SourceRecord:
    values = {
        "title": "développeur Web/développeuse Web",
        "employer": "Exemple inc.",
        "location": "Québec (QC)",
    }
    values.update(changes)
    return SourceRecord(
        source=source,
        source_id=source_id,
        url=f"https://example.test/{source_id}",
        origin_site=origin,
        **values,
    )


class AggregationTests(unittest.TestCase):
    def test_same_posting_found_by_two_searches_is_kept_once(self) -> None:
        first = record("1", "Jobillico")
        first.search_terms = ["web"]
        second = record("1", "Jobillico")
        second.search_terms = ["developpeur"]

        offers = aggregate_records([first, second])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].source_records[0].search_terms, ["web", "developpeur"])

    def test_same_job_republished_by_two_partner_sites_is_merged(self) -> None:
        jobillico = record("1", "Jobillico", salary="")
        talent = record("2", "Talent.com", salary="30,00 $ de l'heure")

        offers = aggregate_records([jobillico, talent])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].salary, "30,00 $ de l'heure")
        self.assertEqual(
            [item.origin_site for item in offers[0].source_records],
            ["Jobillico", "Talent.com"],
        )
        self.assertEqual(build_summary(offers)["merged_offers"], 1)

    def test_two_identical_titles_from_same_site_stay_separate(self) -> None:
        offers = aggregate_records([record("1", "Jobillico"), record("2", "Jobillico")])
        self.assertEqual(len(offers), 2)

    def test_different_employers_are_not_merged(self) -> None:
        offers = aggregate_records(
            [record("1", "Jobillico"), record("2", "Talent.com", employer="Autre inc.")]
        )
        self.assertEqual(len(offers), 2)

    def test_stage_status_keeps_strongest_signal(self) -> None:
        guichet = record("1", "Jobillico")
        remotive = record("r1", "Remotive", source="Remotive")
        remotive.stage_status = "possible_stage"

        offers = aggregate_records([guichet, remotive])

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].stage_status, "possible_stage")


if __name__ == "__main__":
    unittest.main()
