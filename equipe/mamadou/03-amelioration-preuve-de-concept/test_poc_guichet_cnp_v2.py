"""Tests unitaires hors ligne pour le Livrable 3 (poc_guichet_cnp_v2.py)."""

from pathlib import Path
import unittest

from poc_guichet_cnp_v2 import (
    CNP_CODES_TI,
    JobBankOffer,
    build_cnp_search_url,
    detect_stage_status,
    parse_job_detail_html,
    parse_search_results_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPocGuichetCnpV2(unittest.TestCase):
    def setUp(self) -> None:
        self.list_html = (FIXTURES_DIR / "liste_resultats_exemple.html").read_text(encoding="utf-8")
        self.detail_html = (FIXTURES_DIR / "fiche_offre_imbriquee.html").read_text(encoding="utf-8")

    def test_build_cnp_search_url_includes_cnp_and_filters(self) -> None:
        url = build_cnp_search_url(province="QC", student_only=True, page=2)
        self.assertIn("fprov=QC", url)
        self.assertIn("fsrc=16", url)
        self.assertIn("page=2", url)
        for code in CNP_CODES_TI:
            self.assertIn(f"fn21={code}", url)

    def test_parse_search_results_extracts_clean_fields_and_partner(self) -> None:
        offers = parse_search_results_html(self.list_html)
        self.assertEqual(len(offers), 2)

        first = offers[0]
        self.assertEqual(first.source_id, "50711091")
        self.assertEqual(first.cnp_title, "agent/agente de soutien aux utilisateurs")
        self.assertEqual(first.employer, "GolfIn - Saint-Georges")
        self.assertEqual(first.location, "Saint-Georges (QC) Hybride")
        self.assertEqual(first.workplace_mode, "Hybride")
        self.assertEqual(first.salary, "22,50 $ de l'heure")
        self.assertEqual(first.origin_partner, "Jobillico")
        self.assertEqual(first.url, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091")

        # La 2e offre a un salaire 'Non disponible' -> doit rester None (zéro donnée inventée)
        second = offers[1]
        self.assertIsNone(second.salary)
        self.assertEqual(second.origin_partner, "Guichet-Emplois")

    def test_parse_job_detail_handles_nested_divs_without_truncation(self) -> None:
        """Vérifie la correction du bug regex v1 : le texte après le 1er </div> imbriqué est conservé."""
        offer = JobBankOffer(
            source_id="50711091",
            url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091",
            cnp_title="agent/agente de soutien aux utilisateurs",
            title="agent/agente de soutien aux utilisateurs",
        )
        enriched = parse_job_detail_html(self.detail_html, offer)

        # Le vrai titre de la fiche remplace le titre générique CNP
        self.assertEqual(enriched.title, "Stagiaire en soutien informatique et réseaux")
        self.assertEqual(enriched.valid_through, "2026-12-15")
        self.assertEqual(enriched.employment_type, "Temporaire, Temps plein")
        self.assertEqual(enriched.education_level, "Études collégiales (DEC)")

        # La description contient bien le 2e bloc situé après le 1er </div> imbriqué
        self.assertIsNotNone(enriched.description)
        self.assertIn("Responsabilités principales après le premier div imbriqué", enriched.description or "")
        self.assertIn("Configurer les postes Windows et Linux", enriched.description or "")
        self.assertNotIn("<strong>", enriched.description or "")

        # Le stage invisible dans la liste CNP est maintenant détecté grâce à la fiche
        self.assertEqual(enriched.stage_status, "confirmed_stage")

    def test_detect_stage_excludes_supervision_false_positive(self) -> None:
        status = detect_stage_status(
            "Développeur senior Python",
            "Vous serez amené à superviser des stagiaires et accompagner les juniors.",
        )
        self.assertEqual(status, "not_indicated")

    def test_parse_job_detail_cleans_double_escaped_partner_html(self) -> None:
        """Vérifie le nettoyage du HTML doublement échappé (&lt;p&gt;) des offres partenaires Jobillico."""
        partner_html = """
        <main>
          <span property="title">architecte d'applications</span>
          <span class="hidden" property="description">
            &lt;p&gt;&lt;strong&gt;Poste offert :&lt;/strong&gt; Stagiaire DevOps&lt;/p&gt;
          </span>
        </main>
        """
        offer = JobBankOffer(source_id="50726141", url="https://example.com")
        enriched = parse_job_detail_html(partner_html, offer)
        self.assertEqual(enriched.description, "Poste offert : Stagiaire DevOps")
        self.assertEqual(enriched.stage_status, "confirmed_stage")


if __name__ == "__main__":
    unittest.main()
