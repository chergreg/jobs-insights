"""Tests hors ligne des filtres, de l'export CSV et de la relecture d'un offres.json."""

import contextlib
import csv
from dataclasses import asdict
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from export import load_offers, write_csv
from filtres import Filters, filter_offers
from fixtures import FIXTURE_PAGE, REMOTIVE_PAYLOAD, make_posting
from fusion import aggregate_records
import main
from modele import AggregatedOffer, SourceRecord


def offer(number: int, **changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id=str(number),
                url=f"https://example.test/{number}",
                title=f"poste {number}",
                employer="Exemple inc.",
                origin_site="Jobillico",
            )
        ]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


OFFERS = [
    offer(1, city="Montréal", technologies=["Python", "SQL"], level="débutant",
          salary_min=60000.0, salary_max=70000.0, salary_unit="année"),
    offer(2, city="Québec", technologies=["C#"], level="avancé", stage_status="confirmed_stage",
          salary_min=25.5, salary_unit="heure", employer="Ville de Québec"),
    offer(3, city="Saint-Augustin-de-Desmaures", technologies=["SQL"], level="intermédiaire",
          salary_min=50000.0, salary_unit="année"),
    offer(4, city="", technologies=[], level=""),
]


def numbers(offers: list[AggregatedOffer]) -> list[str]:
    return [item.source_records[0].source_id for item in offers]


class FilterTests(unittest.TestCase):
    def test_no_filter_keeps_everything(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters())), ["1", "2", "3", "4"])
        self.assertTrue(Filters().is_empty())

    def test_city_ignores_accents_and_case(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(city="montreal"))), ["1"])

    def test_city_is_exact(self) -> None:
        # « Québec » ne doit pas trouver « Saint-Augustin-de-Desmaures » ni une ville vide.
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(city="Québec"))), ["2"])

    def test_technology(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(technology="sql"))), ["1", "3"])
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(technology="C#"))), ["2"])
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(technology="C"))), [])

    def test_level_without_accent(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(level="debutant"))), ["1"])

    def test_stages_only(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(stages_only=True))), ["2"])

    def test_salary_minimum_in_the_same_unit(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(salary_min=55000))), ["1"])
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(salary_min=20, salary_unit="heure"))), ["2"])
        # Un taux horaire n'est jamais comparé à un salaire annuel.
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(salary_min=20))), ["1", "3"])

    def test_employer_part_of_name(self) -> None:
        self.assertEqual(numbers(filter_offers(OFFERS, Filters(employer="ville de"))), ["2"])

    def test_filters_are_combined(self) -> None:
        filters = Filters(technology="SQL", level="intermédiaire")
        self.assertEqual(numbers(filter_offers(OFFERS, filters)), ["3"])
        self.assertEqual(filters.describe(), "technologie = SQL, niveau = intermédiaire")


class CsvTests(unittest.TestCase):
    def test_csv_opens_in_excel(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "offres.csv"
            write_csv(OFFERS[:2], path)
            raw = path.read_bytes()
            rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))  # BOM utf-8 pour Excel
        header, first, second = rows
        self.assertEqual(header[:4], ["titre", "titre_employeur", "employeur", "ville"])
        values = dict(zip(header, first))
        self.assertEqual(values["salaire_min"], "60000")
        self.assertEqual(values["technologies"], "Python, SQL")
        self.assertEqual(values["site_origine"], "Jobillico")
        values = dict(zip(header, second))
        self.assertEqual(values["salaire_min"], "25,5")  # virgule décimale
        self.assertEqual(values["salaire_max"], "")
        self.assertEqual(values["stage"], "confirmé")

    def test_empty_selection_writes_only_the_header(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "vide.csv"
            write_csv([], path)
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(len(lines), 1)


class LoadOffersTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "offres.json"
            path.write_text(json.dumps({"offers": [asdict(item) for item in OFFERS]}), encoding="utf-8")
            loaded = load_offers(path)
        self.assertEqual([asdict(item) for item in loaded], [asdict(item) for item in OFFERS])

    def test_wrong_file(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "autre.json"
            path.write_text('{"jobs": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_offers(path)


class CollecteSimulee:
    """Aide pour les tests : une collecte avec réponses simulées, puis des relectures sans réseau."""

    def collect_into(self, folder: str) -> Path:
        result_path = Path(folder) / "offres.json"
        with (
            patch("guichet.fetch_url", return_value=FIXTURE_PAGE.encode("utf-8")),
            patch("guichet.time.sleep"),
            patch("fiches.fetch_url", return_value=make_posting().encode("utf-8")),
            patch("fiches.time.sleep"),
            patch("main.load_remotive_payload", return_value=REMOTIVE_PAYLOAD),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            main.main(["--cache-fiches", str(Path(folder) / "cache"), "--sortie", str(result_path)])
        return result_path

    def run_offline(self, *args: str) -> str:
        output = io.StringIO()
        with (
            patch("guichet.fetch_url", side_effect=AssertionError("aucun appel réseau attendu")),
            patch("fiches.fetch_url", side_effect=AssertionError("aucun appel réseau attendu")),
            patch("main.load_remotive_payload", side_effect=AssertionError("aucun appel réseau attendu")),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            main.main(list(args))
        return output.getvalue()


class MainFiltersTests(CollecteSimulee, unittest.TestCase):
    def test_reread_and_filter_without_network(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            before = result_path.read_text(encoding="utf-8")
            csv_path = Path(folder) / "montreal.csv"
            text = self.run_offline("--depuis", str(result_path), "--ville", "montreal", "--csv", str(csv_path))
            rows = csv_path.read_text(encoding="utf-8-sig").splitlines()
            after = result_path.read_text(encoding="utf-8")

        # La fiche de test indique Vaudreuil-Dorion pour les 3 offres du Guichet-Emplois.
        self.assertIn("5 offres relues", text)
        self.assertIn("Offres affichées (ville = montreal) : 0 sur 5", text)
        self.assertEqual(len(rows), 1)  # seulement l'en-tête
        self.assertEqual(before, after)  # offres.json n'est pas réécrit

    def test_filter_by_technology_from_saved_file(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            text = self.run_offline("--depuis", str(result_path), "--techno", "python")

        # Seule l'offre Remotive « Software Engineer Intern » a le tag Python.
        self.assertIn("Offres affichées (technologie = python) : 1 sur 5", text)
        self.assertIn("Software Engineer Intern", text)

    def test_missing_file_gives_a_clear_message(self) -> None:
        with self.assertRaises(SystemExit) as error:
            self.run_offline("--depuis", "fichier-introuvable.json")
        self.assertIn("Impossible de lire", str(error.exception))


if __name__ == "__main__":
    unittest.main()
