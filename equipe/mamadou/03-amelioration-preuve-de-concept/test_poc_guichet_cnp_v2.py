"""Tests unitaires hors ligne pour le collecteur multi-sources enrichi (Livrable 3)."""

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from poc_guichet_cnp_v2 import (
    CNP_CODES_TI,
    JobBankOffer,
    _cache_file_for_url,
    build_cnp_search_url,
    build_jobboom_listing_url,
    collect_guichet_paginated_offers,
    collect_jobboom_paginated_urls,
    detect_stage_status,
    extract_tech_skills,
    get_cached_or_fetch,
    parse_iso_date,
    parse_job_detail_html,
    parse_jobboom_listing_html,
    parse_json_ld_job_posting,
    parse_search_results_html,
    parse_talent_job_detail_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPocGuichetCnpV2(unittest.TestCase):
    def setUp(self) -> None:
        self.list_html = (FIXTURES_DIR / "liste_resultats_exemple.html").read_text(encoding="utf-8")
        self.detail_html = (FIXTURES_DIR / "fiche_offre_imbriquee.html").read_text(encoding="utf-8")

    def test_build_cnp_search_url_includes_14_cnp_and_filters(self) -> None:
        url = build_cnp_search_url(province="QC", student_only=True, page=2)
        self.assertIn("fprov=QC", url)
        self.assertIn("fsrc=16", url)
        self.assertIn("page=2", url)
        self.assertEqual(len(CNP_CODES_TI), 14)
        for code in CNP_CODES_TI:
            self.assertIn(f"fn21={code}", url)

    def test_parse_search_results_extracts_iso_date_clean_salary_and_partner(self) -> None:
        offers = parse_search_results_html(self.list_html)
        self.assertEqual(len(offers), 2)

        first = offers[0]
        self.assertEqual(first.id, "ge-50711091")
        self.assertEqual(first.source_id, "50711091")
        self.assertEqual(first.cnp_title, "agent/agente de soutien aux utilisateurs")
        self.assertEqual(first.entreprise, "GolfIn - Saint-Georges")
        self.assertEqual(first.modalite, "Hybride")
        self.assertEqual(first.salaire, "22,50 $ de l'heure")
        self.assertEqual(first.date_publication, "2026-11-12")
        self.assertEqual(first.source_partenaire, "Jobillico")

        second = offers[1]
        self.assertIsNone(second.salaire)
        self.assertEqual(second.date_publication, "2026-11-10")
        self.assertEqual(second.source_partenaire, "Guichet-Emplois")

    def test_parse_job_detail_handles_nested_divs_and_extracts_skills(self) -> None:
        offer = JobBankOffer(
            id="ge-50711091",
            source_id="50711091",
            url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091",
            cnp_title="agent/agente de soutien aux utilisateurs",
            titre="agent/agente de soutien aux utilisateurs",
        )
        enriched = parse_job_detail_html(self.detail_html, offer)

        self.assertEqual(enriched.titre, "Stagiaire en soutien informatique et réseaux")
        self.assertEqual(enriched.date_fin, "2026-12-15")
        self.assertEqual(enriched.type_poste, "Temporaire, Temps plein")
        self.assertEqual(enriched.niveau_etudes, "Études collégiales (DEC)")
        self.assertIsNotNone(enriched.description)
        self.assertIn("Responsabilités principales après le premier div imbriqué", enriched.description or "")
        self.assertIn("Linux", enriched.competences_cles)
        self.assertTrue(enriched.est_stage)
        self.assertEqual(enriched.statut_stage, "confirmed_stage")

    def test_parse_job_detail_cleans_double_escaped_partner_html_and_brief_fallback(self) -> None:
        partner_html = """
        <main>
          <span property="title">architecte d'applications</span>
          <div class="source-title-inner">
            <span class="orig-title-label">Appellation affichée :</span> Stagiaire Python &amp; Docker
          </div>
          <span class="hidden" property="description">
            &lt;p&gt;&lt;strong&gt;Poste offert :&lt;/strong&gt; Développement backend FastAPI et PostgreSQL&lt;/p&gt;
          </span>
        </main>
        """
        offer = JobBankOffer(id="ge-50726141", source_id="50726141", url="https://example.com")
        enriched = parse_job_detail_html(partner_html, offer)
        self.assertEqual(enriched.titre_employeur, "Stagiaire Python & Docker")
        self.assertEqual(enriched.description, "Poste offert : Développement backend FastAPI et PostgreSQL")
        self.assertEqual(enriched.statut_stage, "confirmed_stage")
        self.assertEqual(enriched.competences_cles, ["Docker", "FastAPI", "PostgreSQL", "Python"])

    def test_extract_tech_skills_ignores_french_false_positives(self) -> None:
        skills = extract_tech_skills("C'est une vue d'ensemble du projet en Python, C# et Vue.js.")
        self.assertEqual(skills, ["C#", "Python", "Vue.js"])
        self.assertNotIn("C", skills)

    def test_detect_stage_excludes_supervision_false_positive(self) -> None:
        status = detect_stage_status(
            "Développeur senior Python",
            "Vous serez amené à superviser des stagiaires et accompagner les juniors.",
        )
        self.assertEqual(status, "not_indicated")

    def test_parse_talent_and_jobboom_json_ld(self) -> None:
        talent_html = """
        <html><head><script type="application/ld+json">
        {"@context":"https://schema.org","@graph":[{
          "@type":"JobPosting",
          "title":"Stagiaire Développeur Python",
          "datePosted":"2026-11-15",
          "employmentType":"INTERN",
          "description":"<p>Maîtrise de Python, Docker et SQL.</p>",
          "hiringOrganization":{"name":"Tech Québec"},
          "jobLocation":{
            "address":{"addressLocality":"Québec","addressRegion":"QC"},
            "geo":{"latitude":46.8139,"longitude":-71.2080}
          }
        }]}
        </script></head></html>
        """
        tc_offer = parse_talent_job_detail_html(talent_html, "https://ca.talent.com/fr/view?id=999")
        self.assertIsNotNone(tc_offer)
        assert tc_offer is not None
        self.assertEqual(tc_offer.id, "tc-999")
        self.assertEqual(tc_offer.latitude, 46.8139)
        self.assertEqual(tc_offer.competences_cles, ["Docker", "Python", "SQL"])
        self.assertTrue(tc_offer.est_stage)

        jb_list_html = """
        <div class="job_item job_item_sponsorship" data-url="/fr/offre-emploi/sponsor_p111"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-python_p222222"></div>
        """
        jb_urls = parse_jobboom_listing_html(jb_list_html)
        self.assertEqual(jb_urls, ["https://www.jobboom.com/fr/offre-emploi/dev-python_p222222"])

    def test_disk_cache_hit_skips_network_and_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            target_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091"

            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "<html>Fiche mise en cache</html>"
            mock_session.get.return_value = mock_resp

            # 1er appel : téléchargement HTTP et écriture dans le cache
            content_1, from_cache_1 = get_cached_or_fetch(
                mock_session,
                target_url,
                cache_dir=cache_dir,
                ttl_seconds=86400,
                delay=0.0,
                use_cache=True,
            )
            self.assertFalse(from_cache_1)
            self.assertEqual(content_1, "<html>Fiche mise en cache</html>")
            self.assertEqual(mock_session.get.call_count, 1)

            # 2e appel (< 24 h) : lecture directe du cache sans requête HTTP ni time.sleep
            with patch("poc_guichet_cnp_v2.time.sleep") as mock_sleep:
                content_2, from_cache_2 = get_cached_or_fetch(
                    mock_session,
                    target_url,
                    cache_dir=cache_dir,
                    ttl_seconds=86400,
                    delay=5.0,
                    use_cache=True,
                )
                self.assertTrue(from_cache_2)
                self.assertEqual(content_2, "<html>Fiche mise en cache</html>")
                self.assertEqual(mock_session.get.call_count, 1)
                mock_sleep.assert_not_called()

    def test_disk_cache_expired_refetches_from_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            target_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/99999999"
            cache_file = _cache_file_for_url(target_url, cache_dir=cache_dir)

            # Écriture d'une entrée expirée (vieille de 25 heures)
            expired_payload = {
                "url": target_url,
                "fetched_at": time.time() - (25 * 3600),
                "content": "<html>Ancienne version expirée</html>",
            }
            cache_file.write_text(json.dumps(expired_payload), encoding="utf-8")

            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "<html>Nouvelle version fraîche</html>"
            mock_session.get.return_value = mock_resp

            content, from_cache = get_cached_or_fetch(
                mock_session,
                target_url,
                cache_dir=cache_dir,
                ttl_seconds=86400,
                delay=0.0,
                use_cache=True,
            )
            self.assertFalse(from_cache)
            self.assertEqual(content, "<html>Nouvelle version fraîche</html>")
            self.assertEqual(mock_session.get.call_count, 1)

    def test_pagination_guichet_and_jobboom_multi_pages_deduplicates(self) -> None:
        self.assertIn("page=2", build_jobboom_listing_url(page=2))

        # Test pagination Guichet-Emplois sur 2 pages avec déduplication d'une offre commune
        page2_html = """
        <article id="article-50711091">
          <span class="noctitle">agent/agente de soutien aux utilisateurs</span>
          <li class="business">GolfIn - Saint-Georges</li>
        </article>
        <article id="article-50999999">
          <span class="noctitle">développeur/développeuse Python</span>
          <li class="business">Québec Numérique</li>
        </article>
        """
        mock_ge_session = MagicMock()
        resp_p1 = MagicMock(text=self.list_html)
        resp_p2 = MagicMock(text=page2_html)
        mock_ge_session.get.side_effect = [resp_p1, resp_p2]

        ge_offers = collect_guichet_paginated_offers(mock_ge_session, pages=2, delay=0.0)
        self.assertEqual(mock_ge_session.get.call_count, 2)
        self.assertEqual([o.id for o in ge_offers], ["ge-50711091", "ge-50684844", "ge-50999999"])

        # Test pagination Jobboom sur 2 pages (hors commandites et sans doublons)
        jb_p1 = """
        <div class="job_item job_item_sponsorship" data-url="/fr/offre-emploi/pub_p100"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-a_p111111"></div>
        """
        jb_p2 = """
        <div class="job_item" data-url="/fr/offre-emploi/dev-a_p111111"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-b_p222222"></div>
        """
        mock_jb_session = MagicMock()
        mock_jb_session.get.side_effect = [MagicMock(text=jb_p1), MagicMock(text=jb_p2)]

        jb_urls = collect_jobboom_paginated_urls(mock_jb_session, pages=2, delay=0.0)
        self.assertEqual(mock_jb_session.get.call_count, 2)
        self.assertEqual(
            jb_urls,
            [
                "https://www.jobboom.com/fr/offre-emploi/dev-a_p111111",
                "https://www.jobboom.com/fr/offre-emploi/dev-b_p222222",
            ],
        )


if __name__ == "__main__":
    unittest.main()
