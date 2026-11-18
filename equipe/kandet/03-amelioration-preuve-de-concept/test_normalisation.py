"""Tests hors ligne du module normalisation (lieu, salaire, dates)."""

import unittest

from fusion import aggregate_records
from modele import SourceRecord
from normalisation import normalize_record, parse_amount, parse_salary_text, split_location


class LocationTests(unittest.TestCase):
    def test_city_and_province(self) -> None:
        self.assertEqual(split_location("Montréal (QC)"), ("Montréal", "QC"))
        self.assertEqual(split_location("Saint-Jean-sur-Richelieu (QC)"), ("Saint-Jean-sur-Richelieu", "QC"))
        self.assertEqual(split_location("Longueuil, QC"), ("Longueuil", "QC"))
        self.assertEqual(split_location("  Ottawa   (ON) "), ("Ottawa", "ON"))

    def test_unclear_location_stays_empty(self) -> None:
        self.assertEqual(split_location("Différentes régions"), ("", ""))
        self.assertEqual(split_location("Lieu de travail indéterminé"), ("", ""))
        self.assertEqual(split_location("USA, Canada"), ("", ""))
        self.assertEqual(split_location("Paris (FR)"), ("", ""))
        self.assertEqual(split_location(""), ("", ""))


class AmountTests(unittest.TestCase):
    def test_french_amounts(self) -> None:
        self.assertEqual(parse_amount("43,27"), 43.27)
        self.assertEqual(parse_amount("52 000,00"), 52000.0)
        self.assertEqual(parse_amount("123 000"), 123000.0)  # espace insécable
        self.assertEqual(parse_amount("4 337"), 4337.0)

    def test_english_amounts(self) -> None:
        self.assertEqual(parse_amount("$80,000"), 80000.0)
        self.assertEqual(parse_amount("$20.50"), 20.5)
        self.assertEqual(parse_amount("1,000.50"), 1000.5)

    def test_thousands_with_k(self) -> None:
        self.assertEqual(parse_amount("$3.5k"), 3500.0)
        self.assertEqual(parse_amount("$35,3k"), 35300.0)
        self.assertEqual(parse_amount("70K"), 70000.0)

    def test_no_amount(self) -> None:
        self.assertIsNone(parse_amount("Competitive"))
        self.assertIsNone(parse_amount(""))


class SalaryTextTests(unittest.TestCase):
    def test_guichet_formats(self) -> None:
        self.assertEqual(parse_salary_text("34,62 $ de l'heure"), (34.62, None, "heure"))
        self.assertEqual(
            parse_salary_text("52 000,00 $ à 60 000,00 $ par année"), (52000.0, 60000.0, "année")
        )
        self.assertEqual(
            parse_salary_text("30,59 $ à 52,43 $ de l'heure (à négocier)"), (30.59, 52.43, "heure")
        )
        self.assertEqual(parse_salary_text("135,00 $ par jour"), (135.0, None, "jour"))
        self.assertEqual(
            parse_salary_text("4 337,00 $ à 6 413,00 $ par mois (à négocier)"), (4337.0, 6413.0, "mois")
        )

    def test_weekly_hours_are_not_an_amount(self) -> None:
        self.assertEqual(
            parse_salary_text("43,27 $ de l’heure / 40 heures par semaine"), (43.27, None, "heure")
        )

    def test_remotive_formats(self) -> None:
        self.assertEqual(parse_salary_text("$14 - $20/hour"), (14.0, 20.0, "heure"))
        self.assertEqual(parse_salary_text("$3.5k–$5k/month"), (3500.0, 5000.0, "mois"))
        self.assertEqual(parse_salary_text("OTE $25k - $35k"), (25000.0, 35000.0, ""))

    def test_unit_is_not_guessed(self) -> None:
        # Sans unité écrite, on ne suppose pas que c'est un salaire annuel.
        self.assertEqual(parse_salary_text("$170k - $200k"), (170000.0, 200000.0, ""))

    def test_text_without_amount(self) -> None:
        self.assertEqual(parse_salary_text("Competitive"), (None, None, ""))
        self.assertEqual(parse_salary_text(""), (None, None, ""))


def record(**changes: object) -> SourceRecord:
    values: dict[str, object] = {
        "source": "Guichet-Emplois",
        "source_id": "1",
        "url": "https://example.test/1",
        "title": "développeur Web/développeuse Web",
        "employer": "Exemple inc.",
        "location": "Montréal (QC)",
        "salary": "52 000,00 $ à 60 000,00 $ par année (à négocier)",
    }
    values.update(changes)
    values["url"] = f"https://example.test/{values['source_id']}"  # un lien différent par annonce
    return SourceRecord(**values)  # type: ignore[arg-type]


class NormalizeRecordTests(unittest.TestCase):
    def test_list_text_is_used_without_posting(self) -> None:
        item = record()
        normalize_record(item)

        self.assertEqual((item.city, item.province), ("Montréal", "QC"))
        self.assertEqual((item.salary_min, item.salary_max, item.salary_unit), (52000.0, 60000.0, "année"))
        self.assertEqual(item.salary_currency, "CAD")
        self.assertTrue(item.salary_negotiable)

    def test_posting_values_are_preferred(self) -> None:
        item = record(salary="texte illisible")
        item.source_data["posting"] = {"salary_min": "123 000", "salary_max": "", "salary_unit": "YEAR"}
        normalize_record(item)

        self.assertEqual((item.salary_min, item.salary_max, item.salary_unit), (123000.0, None, "année"))
        self.assertFalse(item.salary_negotiable)

    def test_posting_city_is_kept(self) -> None:
        item = record(location="Différentes régions", city="Sherbrooke", province="QC")
        normalize_record(item)
        self.assertEqual((item.city, item.province), ("Sherbrooke", "QC"))

    def test_no_salary(self) -> None:
        item = record(salary="")
        normalize_record(item)
        self.assertIsNone(item.salary_min)
        self.assertEqual((item.salary_unit, item.salary_currency), ("", ""))

    def test_remotive_currency_is_not_guessed(self) -> None:
        item = record(source="Remotive", salary="$14/hour", location="USA, Canada")
        normalize_record(item)
        self.assertEqual((item.salary_min, item.salary_unit), (14.0, "heure"))
        self.assertEqual(item.salary_currency, "")
        self.assertEqual((item.city, item.province), ("", ""))

    def test_dates_keep_only_the_day(self) -> None:
        item = record(published_at="2026-11-09T10:00:00", expires_at="2026-12-07", start_date="bientôt")
        normalize_record(item)
        self.assertEqual(item.published_at, "2026-11-09")
        self.assertEqual(item.expires_at, "2026-12-07")
        self.assertEqual(item.start_date, "")


class SalaryMergeTests(unittest.TestCase):
    def test_salary_fields_come_from_the_same_posting(self) -> None:
        without_salary = record(source_id="1", salary="", origin_site="Jobillico")
        with_salary = record(source_id="2", salary="34,62 $ de l'heure", origin_site="Talent.com")
        for item in (without_salary, with_salary):
            normalize_record(item)

        offers = aggregate_records([without_salary, with_salary])

        self.assertEqual(len(offers), 1)
        self.assertEqual((offers[0].salary_min, offers[0].salary_unit), (34.62, "heure"))
        self.assertEqual(offers[0].salary_currency, "CAD")


if __name__ == "__main__":
    unittest.main()
