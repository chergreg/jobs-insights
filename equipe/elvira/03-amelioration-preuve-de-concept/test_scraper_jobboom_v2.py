"""
Tests unitaires hors ligne pour le Livrable 3 Multi-Sources d'Elvira :
- `models.py` (`JobOffer`, filtre strict 2026 `is_recent_and_valid_offer`, `is_it_job`, `dedup_key`)
- `collecteurs.py` (`JobboomCollector`, `GuichetEmploisCollector`, `JobillicoCollector`, `RemotiveCollector`)
- `pipeline.py` (`MultiSourcePipeline` : déduplication inter-sources, filtrage et exports JSON/CSV)
- `scraper_jobboom_v2.py` (compatibilité v2 Jobboom)

Aucun appel réseau n'est effectué pendant ces tests.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.robotparser
from pathlib import Path

from collecteurs import (
    GuichetEmploisCollector,
    JobboomCollector,
    JobillicoCollector,
    RemotiveCollector,
)
from models import (
    JobOffer,
    extract_salary,
    is_it_job,
    is_recent_and_valid_offer,
)
from pipeline import MultiSourcePipeline
from scraper_jobboom_v2 import (
    USER_AGENT,
    extract_job_id,
    is_url_allowed,
    merge_discovered_urls,
    normalize_job_posting,
    parse_job_links_from_html,
    parse_job_posting_json_from_html,
    upgrade_existing_file,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "jobboom_fixture.json"


class TestScraperMultiSourcesV2(unittest.TestCase):
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
        """Vérifie que les titres TI passent et que les postes hors-TI sont exclus."""
        self.assertTrue(is_it_job("Développeur Fullstack Python", ""))
        self.assertTrue(is_it_job("Stage en soutien informatique", ""))
        self.assertFalse(is_it_job("Commis comptable", ""))
        self.assertFalse(is_it_job("Technicien CVC / bâtiment", ""))
        self.assertFalse(is_it_job("Journalier au désassemblage de matériel informatique", ""))

    def test_is_recent_and_valid_offer_rejects_past_years_and_expired(self) -> None:
        """Vérifie qu'aucune offre de l'année passée (< 2026) ou expirée n'est acceptée."""
        self.assertTrue(is_recent_and_valid_offer("2026-11-10", "2027-01-15", today_iso="2026-11-18"))
        self.assertTrue(is_recent_and_valid_offer("12 novembre 2026", None, today_iso="2026-11-18"))
        # Offres de 2023 ou 2025 rejetées même si la date d'expiration est en 2027
        self.assertFalse(is_recent_and_valid_offer("2023-11-25", "2027-02-07", today_iso="2026-11-18"))
        self.assertFalse(is_recent_and_valid_offer("2025-12-31", "2026-12-31", today_iso="2026-11-18"))
        # Offre de 2026 mais déjà expirée rejetée
        self.assertFalse(is_recent_and_valid_offer("2026-09-01", "2026-10-15", today_iso="2026-11-18"))

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
        self.assertEqual(normalized["salaire"], "22 à 26 CAD / heure")
        self.assertEqual(normalized["modalite"], "Hybride")
        self.assertTrue(normalized["est_stage"])
        self.assertIn("Python", normalized["competences_cles"])
        self.assertNotIn("Vue.js", normalized["competences_cles"])
        self.assertNotIn("raw_json_ld", normalized)

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
        self.assertEqual(merged[1], (url_b, ["categorie_ti:_i10lfr_p1", "mot_cle:stage informatique"]))
        self.assertEqual(extract_job_id(url_a), "jb-1111111")

    def test_robots_txt_permission(self) -> None:
        """Vérifie le respect des règles `robots.txt` via `RobotFileParser`."""
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /fr/admin/", "Allow: /fr/"])
        self.assertTrue(is_url_allowed(rp, "https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr", USER_AGENT))
        self.assertFalse(is_url_allowed(rp, "https://www.jobboom.com/fr/admin/secret", USER_AGENT))

    def test_guichet_emplois_collector_parsing_and_rdfa_enrichment(self) -> None:
        """Vérifie le parsing d'une carte Guichet-Emplois et son enrichissement RDFa."""
        search_html = """
        <article id="article-50711091">
          <a href="/rechercheemplois/offredemploi/50711091;jsessionid=ABC">
            <span class="noctitle">développeur/développeuse Web</span>
          </a>
          <li class="business">Techno Québec Inc.</li>
          <li class="location"><span class="wb-inv">Emplacement</span>Québec (QC)</li>
          <li class="salary"><span class="wb-inv">Salaire</span>32,00 $ de l'heure</li>
          <li class="date">14 novembre 2026</li>
          <li class="telework">Hybride</li>
          <li class="source"><span class="wb-inv">Jobillico</span></li>
        </article>
        """
        cards = GuichetEmploisCollector.parse_search_results_html(search_html)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "ge-50711091")
        self.assertEqual(cards[0]["partenaire_origine"], "Jobillico")
        self.assertEqual(cards[0]["date_publication"], "2026-11-14")

        detail_html = """
        <html><body>
          <span class="source-title-inner">Développeur Web Fullstack (Stage / Junior)</span>
          <div property="description"><p>Maîtrise de <strong>Python</strong>, <strong>React</strong> et <strong>SQL</strong>.</p></div>
        </body></html>
        """
        offer = GuichetEmploisCollector.enrich_from_detail_html(cards[0], detail_html)
        self.assertEqual(offer.titre, "Développeur Web Fullstack (Stage / Junior)")
        self.assertEqual(offer.modalite, "Hybride")
        self.assertTrue(offer.est_stage)
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("SQL", offer.competences_cles)

    def test_jobillico_and_remotive_collectors(self) -> None:
        """Vérifie les parseurs Jobillico (JSON-LD) et Remotive (API REST JSON)."""
        ji_html = """
        <html><head><script type="application/ld+json">
        {"@type":"JobPosting","title":"Programmeur analyste C#","description":"Poste télétravail avec C#, .NET et Azure.","datePosted":"2026-11-12","hiringOrganization":{"name":"Solutions Lévis"},"jobLocation":{"address":{"addressLocality":"Lévis","addressRegion":"QC"}}}
        </script></head></html>
        """
        ji_offer = JobillicoCollector.parse_job_posting_from_html(
            ji_html,
            "https://www.jobillico.com/fr/offre-d-emploi/solutions-levis/programmeur/17550001",
        )
        self.assertIsNotNone(ji_offer)
        assert ji_offer is not None
        self.assertEqual(ji_offer.id, "ji-17550001")
        self.assertEqual(ji_offer.source, "Jobillico")
        self.assertIn("C#", ji_offer.competences_cles)

        rem_payload = {
            "jobs": [
                {
                    "id": 9901,
                    "title": "Junior Python Software Developer Intern",
                    "company_name": "CloudNova",
                    "candidate_required_location": "Canada",
                    "publication_date": "2026-11-15T10:00:00",
                    "job_type": "internship",
                    "salary": "$25/hr",
                    "url": "https://remotive.com/remote-jobs/software-dev/intern-9901",
                    "description": "<p>Remote internship using Python, Docker, and PostgreSQL.</p>",
                },
                {
                    "id": 9902,
                    "title": "Old Developer 2024",
                    "company_name": "OldCorp",
                    "candidate_required_location": "Canada",
                    "publication_date": "2024-05-10T10:00:00",
                    "job_type": "full_time",
                    "url": "https://remotive.com/remote-jobs/software-dev/old-9902",
                    "description": "Python",
                },
            ]
        }
        rem_offers = RemotiveCollector.parse_api_jobs(rem_payload)
        self.assertEqual(len(rem_offers), 1)
        self.assertEqual(rem_offers[0].id, "rem-9901")
        self.assertTrue(rem_offers[0].est_stage)

    def test_cross_source_deduplication_and_merge(self) -> None:
        """Vérifie qu'une même offre présente sur Guichet-Emplois et sur Jobboom est fusionnée sans perte."""
        o1 = JobOffer(
            id="ge-5001",
            source="Guichet-Emplois",
            titre="Développeur Python",
            entreprise="InnovMetric Logiciels Inc.",
            ville="Québec (QC)",
            salaire="75 000 $ / an",
            competences_cles=["Python"],
            date_publication="2026-11-12",
            url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/5001",
            description_texte="Résumé court.",
        )
        o2 = JobOffer(
            id="jb-3001",
            source="Jobboom",
            titre="Développeur Python",
            entreprise="InnovMetric Logiciels",
            ville="Québec",
            code_postal="G1N4N6",
            coordonnees_gps={"latitude": 46.81, "longitude": -71.31},
            competences_cles=["Python", "Docker", "SQL"],
            date_publication="2026-11-12",
            url="https://www.jobboom.com/fr/offre-emploi/developpeur-python_p3001",
            description_texte="Description complète beaucoup plus détaillée avec Docker et SQL.",
        )
        merged = MultiSourcePipeline.deduplicate_and_merge([o1, o2])
        self.assertEqual(len(merged), 1)
        result = merged[0]
        self.assertEqual(result.salaire, "75 000 $ / an")
        self.assertEqual(result.code_postal, "G1N4N6")
        self.assertIn("Docker", result.competences_cles)
        self.assertEqual(len(result.urls_sources), 2)

    def test_upgrade_existing_file_keeps_only_2026_valid_offers(self) -> None:
        """Vérifie que la fusion v2 ne garde aucune offre des années passées."""
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
            self.assertEqual(len(merged), 15)
            for item in merged:
                self.assertTrue(str(item["date_publication"]).startswith("2026"))


if __name__ == "__main__":
    unittest.main()
