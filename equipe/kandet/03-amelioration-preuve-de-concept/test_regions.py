"""Tests hors ligne des régions administratives (regions.py, preparer_regions.py)."""

from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from export import load_offers
from filtres import Filters, filter_offers
from fusion import aggregate_records
from modele import SourceRecord
from normalisation import normalize_record
from preparer_regions import reduce_rows
from regions import build_region_index, clean_region, region_of


ROWS = [
    {"nom": "Montréal", "type": "municipalité", "region": "Montréal (06)"},
    {"nom": "Brossard", "type": "municipalité", "region": "Montérégie (16)"},
    {"nom": "Saint-Laurent", "type": "arrondissement", "region": "Montréal (06)"},
    # Même nom dans deux régions : on ne choisit pas.
    {"nom": "Sainte-Croix", "type": "municipalité", "region": "Chaudière-Appalaches (12)"},
    {"nom": "Sainte-Croix", "type": "municipalité", "region": "Montérégie (16)"},
    # Même nom pour une municipalité et un arrondissement : la municipalité l'emporte.
    {"nom": "Desjardins", "type": "municipalité", "region": "Estrie (05)"},
    {"nom": "Desjardins", "type": "arrondissement", "region": "Chaudière-Appalaches (12)"},
]


class RegionIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = build_region_index(ROWS)

    def test_region_name_without_code(self) -> None:
        self.assertEqual(clean_region("Montérégie (16)"), "Montérégie")
        self.assertEqual(clean_region("Capitale-Nationale (03)"), "Capitale-Nationale")

    def test_municipality_and_borough(self) -> None:
        self.assertEqual(region_of("Brossard", self.index), "Montérégie")
        self.assertEqual(region_of("saint-laurent", self.index), "Montréal")
        self.assertEqual(region_of("MONTREAL", self.index), "Montréal")

    def test_ambiguous_or_unknown_name_stays_empty(self) -> None:
        self.assertEqual(region_of("Sainte-Croix", self.index), "")
        self.assertEqual(region_of("Saint-Antoine-Abbé", self.index), "")
        self.assertEqual(region_of("Différentes régions", self.index), "")
        self.assertEqual(region_of("", self.index), "")

    def test_municipality_wins_over_borough(self) -> None:
        self.assertEqual(region_of("Desjardins", self.index), "Estrie")


class OfficialFileTests(unittest.TestCase):
    """Vérifie le fichier regions_quebec.csv livré avec le projet."""

    def test_cities_seen_in_our_offers(self) -> None:
        expected = {
            "Montréal": "Montréal",
            "Brossard": "Montérégie",
            "Québec": "Capitale-Nationale",
            "Sherbrooke": "Estrie",
            "Lévis": "Chaudière-Appalaches",
            "Saint-Laurent": "Montréal",
            "Lachine": "Montréal",
            "Laval": "Laval",
        }
        for city, region in expected.items():
            self.assertEqual(region_of(city), region, city)


class ReduceRowsTests(unittest.TestCase):
    def test_personal_columns_are_dropped(self) -> None:
        municipalities = "mcode,munnom,regadm,maire,mcourriel\n46005,Abercorn,Estrie (05),Jean Exemple,dg@exemple.ca\n"
        boroughs = "arrcod,arrnom,arrregion,president\nREA01,Desjardins,Chaudière-Appalaches (12),Ann Exemple\n"
        rows = reduce_rows(municipalities, boroughs)
        self.assertEqual(
            rows,
            [
                {"nom": "Desjardins", "type": "arrondissement", "region": "Chaudière-Appalaches (12)"},
                {"nom": "Abercorn", "type": "municipalité", "region": "Estrie (05)"},
            ],
        )
        self.assertNotIn("Jean Exemple", str(rows))


def record(city_text: str, **changes: str) -> SourceRecord:
    values = {
        "source": "Guichet-Emplois",
        "source_id": city_text,
        "url": f"https://example.test/{city_text}",
        "title": "analyste",
        "employer": "Exemple inc.",
        "location": city_text,
    }
    values.update(changes)
    return SourceRecord(**values)


class NormalizeRegionTests(unittest.TestCase):
    def test_region_is_added_for_quebec(self) -> None:
        item = record("Brossard (QC)")
        normalize_record(item)
        self.assertEqual(item.region, "Montérégie")

    def test_other_provinces_get_no_region(self) -> None:
        # Windsor existe en Ontario et en Estrie : seule la province QC compte.
        item = record("Windsor (ON)")
        normalize_record(item)
        self.assertEqual((item.province, item.region), ("ON", ""))

    def test_unclear_location(self) -> None:
        item = record("Différentes régions")
        normalize_record(item)
        self.assertEqual(item.region, "")


class RegionFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        records = [record("Brossard (QC)"), record("Montréal (QC)"), record("Québec (QC)"), record("Différentes régions")]
        for item in records:
            normalize_record(item)
        self.offers = aggregate_records(records)

    def test_filter_by_full_name_or_beginning(self) -> None:
        def cities(filters: Filters) -> list[str]:
            return [offer.city for offer in filter_offers(self.offers, filters)]

        self.assertEqual(cities(Filters(region="Montérégie")), ["Brossard"])
        self.assertEqual(cities(Filters(region="monteregie")), ["Brossard"])
        self.assertEqual(cities(Filters(region="capitale")), ["Québec"])
        self.assertEqual(cities(Filters(region="Montréal")), ["Montréal"])
        self.assertEqual(Filters(region="capitale").describe(), "région = capitale")

    def test_old_json_without_region_gets_one_when_reloaded(self) -> None:
        raw = [asdict(offer) for offer in self.offers]
        for item in raw:
            del item["region"]  # comme un offres.json créé avant l'ajout des régions
        with TemporaryDirectory() as folder:
            path = Path(folder) / "offres.json"
            path.write_text(json.dumps({"offers": raw}), encoding="utf-8")
            loaded = load_offers(path)
        self.assertEqual([offer.region for offer in loaded], ["Montérégie", "Montréal", "Capitale-Nationale", ""])


if __name__ == "__main__":
    unittest.main()
