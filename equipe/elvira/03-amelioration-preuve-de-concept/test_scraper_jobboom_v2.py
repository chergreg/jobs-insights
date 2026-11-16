"""
Tests unitaires hors ligne pour `scraper_jobboom_v2.py` (Livrable 3).
Aucun appel réseau n'est effectué pendant ces tests.
"""

from __future__ import annotations

import json
import unittest
import urllib.robotparser
from pathlib import Path

from scraper_jobboom_v2 import (
    USER_AGENT,
    extract_job_id,
    extract_salary,
    is_it_job,
    is_url_allowed,
    merge_discovered_urls,
    normalize_job_posting,
    parse_job_links_from_html,
    parse_job_posting_json_from_html,
    upgrade_existing_file,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "jobboom_fixture.json"


class TestScraperJobboomV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_parse_job_links_combines_href_and_data_url_and_filters_non_it(self) -> None:
        """Vérifie l'extraction combinée `<a href>` (Elvira) + `data-url` (Mamadou) et le filtrage hors-TI."""
        html_sample = self.fixtures["search_html_sample"]
        links, raw_count = parse_job_links_from_html(html_sample)

        self.assertEqual(raw_count, 3)
        self.assertEqual(
            links,
            [
                "https://www.jobboom.com/fr/offre-emploi/stage-developpeur-web_studio-quebec_p3799001",
                "https://www.jobboom.com/fr/offre-emploi/programmeur-analyste-python_tech-montreal_p3799003",
            ],
        )

    def test_is_it_job_positive_and_exclusion(self) -> None:
        """Vérifie que les titres TI passent et que les postes hors-TI (comptable, CVC, ventes) sont exclus."""
        self.assertTrue(is_it_job("Développeur Fullstack Python", ""))
        self.assertTrue(is_it_job("Stage en soutien informatique", ""))
        self.assertFalse(is_it_job("Commis comptable", ""))
        self.assertFalse(is_it_job("Technicien CVC / bâtiment", ""))
        self.assertFalse(is_it_job("Conseiller aux ventes en succursale", ""))

    def test_parse_and_normalize_job_posting(self) -> None:
        """Vérifie l'extraction du JSON-LD `JobPosting` et sa normalisation complète."""
        detail_html = self.fixtures["job_detail_html_sample"]
        job_data = parse_job_posting_json_from_html(detail_html)
        self.assertIsNotNone(job_data)
        assert job_data is not None

        url = "https://www.jobboom.com/fr/offre-emploi/stage-developpeur-web_studio-quebec_p3799001"
        normalized = normalize_job_posting(
            job_data,
            url,
            origines_decouverte=["categorie_ti:_i10lfr_p1", "mot_cle:stage informatique"],
        )

        self.assertEqual(normalized["id"], "jb-3799001")
        self.assertEqual(normalized["titre"], "Stage développeur Web Python / React")
        self.assertEqual(normalized["entreprise"], "Studio Numérique Québec")
        self.assertEqual(normalized["ville"], "Québec")
        self.assertEqual(normalized["province"], "QC")
        self.assertEqual(normalized["code_postal"], "G1K 3C2")
        self.assertEqual(normalized["coordonnees_gps"], {"latitude": 46.8139, "longitude": -71.208})
        self.assertEqual(normalized["salaire"], "22 à 26 CAD / heure")
        self.assertEqual(normalized["modalite"], "Hybride")
        self.assertTrue(normalized["est_stage"])
        self.assertIn("Python", normalized["competences_cles"])
        self.assertIn("React", normalized["competences_cles"])
        self.assertIn("PostgreSQL", normalized["competences_cles"])
        # "soins de la vue" ne doit PAS déclencher "Vue.js"
        self.assertNotIn("Vue.js", normalized["competences_cles"])

    def test_extract_salary_when_absent_or_present(self) -> None:
        """Vérifie que le salaire n'est jamais inventé lorsqu'il est absent (`None`)."""
        self.assertIsNone(extract_salary({}))
        self.assertEqual(
            extract_salary(
                {
                    "baseSalary": {
                        "@type": "MonetaryAmount",
                        "currency": "CAD",
                        "value": {"@type": "QuantitativeValue", "value": 75000, "unitText": "YEAR"},
                    }
                }
            ),
            "75000 CAD / an",
        )

    def test_merge_discovered_urls_deduplicates_and_tracks_origins(self) -> None:
        """Vérifie la déduplication par ID Jobboom et la fusion des origines de découverte."""
        url_a = "https://www.jobboom.com/fr/offre-emploi/dev-python_acme_p1111111"
        url_b = "https://www.jobboom.com/fr/offre-emploi/stage-ti_beta_p2222222"
        batches = [
            ("categorie_ti:_i10lfr_p1", [url_a, url_b]),
            ("mot_cle:stage informatique", [url_b]),
        ]
        merged = merge_discovered_urls(batches)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0], (url_a, ["categorie_ti:_i10lfr_p1"]))
        self.assertEqual(
            merged[1],
            (url_b, ["categorie_ti:_i10lfr_p1", "mot_cle:stage informatique"]),
        )
        self.assertEqual(extract_job_id(url_a), "jb-1111111")

    def test_robots_txt_permission(self) -> None:
        """Vérifie le respect des règles `robots.txt` via `RobotFileParser`."""
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(
            [
                "User-agent: *",
                "Disallow: /fr/admin/",
                "Allow: /fr/",
            ]
        )
        self.assertTrue(is_url_allowed(rp, "https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr", USER_AGENT))
        self.assertFalse(is_url_allowed(rp, "https://www.jobboom.com/fr/admin/secret", USER_AGENT))

    def test_upgrade_existing_file_fuses_elvira_and_mamadou_samples(self) -> None:
        """Vérifie la fusion hors ligne de l'échantillon v1 d'Elvira et des offres Jobboom de Mamadou."""
        import tempfile

        v1_path = Path(__file__).resolve().parent.parent / "02-preuve-de-concept-scraping" / "offres_jobboom.json"
        mamadou_path = (
            Path(__file__).resolve().parent.parent.parent
            / "mamadou"
            / "02-preuve-de-concept-scraping"
            / "sample_scraped_jobs.json"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "merged.json"
            merged = upgrade_existing_file(v1_path, out_path, mamadou_file=mamadou_path)
            self.assertEqual(len(merged), 23)
            ids = {item["id"] for item in merged}
            self.assertIn("jb-3718101", ids)  # Offre Cybersécurité issue de Mamadou (_i10lfr)
            self.assertIn("jb-3698100", ids)  # Offre Technicien TI issue d'Elvira (mots-clés)


if __name__ == "__main__":
    unittest.main()
