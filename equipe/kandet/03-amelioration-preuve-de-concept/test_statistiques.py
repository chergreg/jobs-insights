"""Tests hors ligne des statistiques (analyse.build_summary), sur des offres préparées à la main."""

from datetime import date
import unittest

from analyse import build_summary, expiring_soon, salary_statistics
from fusion import aggregate_records
from modele import AggregatedOffer, SourceRecord


def offer(number: int, **changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id=str(number),
                url=f"https://example.test/{number}",
                title=f"poste {number}",
                origin_site="Guichet-Emplois",
            )
        ]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


def hourly(number: int, low: float, high: float | None = None) -> AggregatedOffer:
    return offer(number, salary_min=low, salary_max=high, salary_unit="heure", salary_currency="CAD")


class SalaryStatisticsTests(unittest.TestCase):
    def test_median_with_odd_number_of_offers(self) -> None:
        stats = salary_statistics([hourly(1, 20.0), hourly(2, 30.0, 40.0), hourly(3, 25.0)])
        self.assertEqual(
            stats["CAD / heure"],
            {"offers": 3, "lowest": 20.0, "highest": 40.0, "median_low": 25.0},
        )

    def test_median_with_even_number_of_offers(self) -> None:
        stats = salary_statistics([hourly(1, 20.0), hourly(2, 30.0), hourly(3, 25.0), hourly(4, 35.0)])
        self.assertEqual(stats["CAD / heure"]["median_low"], 27.5)

    def test_units_and_currencies_are_never_mixed(self) -> None:
        offers = [
            hourly(1, 30.0),
            offer(2, salary_min=60000.0, salary_max=80000.0, salary_unit="année", salary_currency="CAD"),
            offer(3, salary_min=14.0, salary_unit="heure"),  # Remotive : devise non écrite
        ]
        stats = salary_statistics(offers)
        self.assertEqual(set(stats), {"CAD / heure", "CAD / année", "devise non précisée / heure"})
        self.assertEqual(stats["CAD / année"]["highest"], 80000.0)

    def test_salary_without_unit_is_left_out(self) -> None:
        stats = salary_statistics([offer(1, salary_min=170000.0, salary_unit="")])
        self.assertEqual(stats, {})

    def test_no_salary_at_all(self) -> None:
        self.assertEqual(salary_statistics([offer(1), offer(2)]), {})


class ExpiringTests(unittest.TestCase):
    def test_offers_expiring_within_seven_days(self) -> None:
        offers = [
            offer(1, expires_at="2026-11-17"),  # aujourd'hui : compris
            offer(2, expires_at="2026-11-24"),  # dans 7 jours : compris
            offer(3, expires_at="2026-11-25"),  # trop loin
            offer(4, expires_at="2026-11-16"),  # déjà expirée
            offer(5, expires_at=""),
        ]
        soon = expiring_soon(offers, today=date(2026, 11, 17))
        self.assertEqual([item["title"] for item in soon], ["poste 1", "poste 2"])


class BuildSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.offers = [
            offer(1, technologies=["Python", "SQL"], skills=["Bases de données"], city="Montréal", level="débutant"),
            offer(2, technologies=["SQL"], city="Montréal", level="avancé", job_type="Temps plein"),
            offer(3, technologies=["SQL", "Azure"], city="Québec", description="texte"),
        ]
        self.summary = build_summary(self.offers, today=date(2026, 11, 17))

    def test_top_lists(self) -> None:
        self.assertEqual(self.summary["top_technologies"], {"SQL": 3, "Python": 1, "Azure": 1})
        self.assertEqual(self.summary["top_skills"], {"Bases de données": 1})
        self.assertEqual(self.summary["top_cities"], {"Montréal": 2, "Québec": 1})

    def test_levels_and_job_types_count_missing_values(self) -> None:
        self.assertEqual(self.summary["levels"], {"débutant": 1, "avancé": 1, "Non précisé": 1})
        self.assertEqual(self.summary["job_types"], {"Non précisé": 2, "Temps plein": 1})

    def test_filled_fields(self) -> None:
        filled = self.summary["filled_fields"]
        self.assertEqual(filled["technologies"], 3)
        self.assertEqual(filled["description"], 1)
        self.assertEqual(filled["salary_min"], 0)

    def test_empty_list_does_not_fail(self) -> None:
        summary = build_summary([], today=date(2026, 11, 17))
        self.assertEqual(summary["salaries"], {})
        self.assertEqual(summary["top_technologies"], {})
        self.assertEqual(summary["expiring_within_7_days"], [])


if __name__ == "__main__":
    unittest.main()
