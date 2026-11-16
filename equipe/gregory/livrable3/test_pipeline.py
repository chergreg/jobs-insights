"""
test_pipeline.py - Suite de tests unitaires 100 % hors ligne pour le pipeline d'unification.

Valide l'ensemble des fonctionnalités du Lot 5 :
1. Normalisation du texte, des employeurs, des titres et des localisations.
2. Déduplication intra-source (par identifiant unique et URL propre).
3. Déduplication inter-sources (par empreinte normalisée titre + employeur + lieu).
4. Fusion intelligente avec maximisation de la richesse informationnelle :
   - Préservation de la description la plus longue.
   - Cumul des compétences techniques sans doublon.
   - Priorisation stricte du signal de stage (confirmed > possible > not_indicated).
   - Conservation du partenaire d'origine (ex: Jobillico).
   - Complétion des salaires, modalités et types de contrat.
5. Exports finaux JSON (UTF-8 structuré) et CSV (utf-8-sig, délimiteur ';', compatible Excel Windows).
6. Intégration globale de bout en bout et rapport statistique.

Garantit zéro appel réseau pendant les tests (conformité AGENTS.md).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Assure la résolution des modules locaux quel que soit le répertoire courant
CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from pipeline import (
    STAGE_PRIORITY,
    PipelineStats,
    clean_url,
    compute_identity,
    export_to_csv,
    export_to_json,
    get_publisher_key,
    is_cross_source_match,
    is_intra_source_duplicate,
    is_valid_identity,
    load_all_datasets,
    load_offers_from_json,
    merge_job_offers,
    normalize_employer,
    normalize_location,
    normalize_text,
    normalize_title,
    unify_offers,
)


class TestPipelineNormalizationAndIdentity(unittest.TestCase):
    """Vérifie la robustesse des fonctions de normalisation textuelle et géographique."""

    def test_normalize_text(self):
        self.assertEqual(normalize_text("Développeur / Développeuse Full-Stack"), "developpeur developpeuse full stack")
        self.assertEqual(normalize_text("  Éléphant  CÔTÉ   "), "elephant cote")
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")

    def test_clean_url(self):
        url1 = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50701948?source=search&page=1#details"
        self.assertEqual(clean_url(url1), "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50701948")

        url2 = "https://www.jobboom.com/fr/description-de-poste/technicien-ti/12345/"
        self.assertEqual(clean_url(url2), "https://www.jobboom.com/fr/description-de-poste/technicien-ti/12345")

        self.assertEqual(clean_url(""), "")
        self.assertEqual(clean_url(None), "")

    def test_normalize_employer(self):
        # Retrait des suffixes corporatifs
        self.assertEqual(normalize_employer("CGI Inc."), "cgi")
        self.assertEqual(normalize_employer("Mouvement Desjardins Ltée"), "mouvement desjardins")
        self.assertEqual(normalize_employer("Amazon Canada"), "amazon")
        self.assertEqual(normalize_employer("Bell Solutions"), "bell")
        self.assertEqual(normalize_employer("Groupe CGI"), "cgi")
        self.assertEqual(normalize_employer("Umbrella Technologies Inc."), "umbrella")
        self.assertEqual(normalize_employer(""), "")
        self.assertEqual(normalize_employer(None), "")

    def test_normalize_title(self):
        self.assertEqual(normalize_title("Développeur / Développeuse Python"), "developpeur python")
        self.assertEqual(normalize_title("Programmeur-analyste (H/F)"), "analyste programmeur")
        self.assertEqual(normalize_title("Stagiaire en informatique (Temps plein)"), "stagiaire en informatique")
        self.assertEqual(normalize_title("Analyste fonctionnelle / Analyste fonctionnel"), "analyste fonctionnel")
        self.assertEqual(normalize_title(""), "")

    def test_normalize_location(self):
        self.assertEqual(normalize_location("Montréal, QC"), "montreal")
        self.assertEqual(normalize_location("Ville de Québec (QC)"), "quebec")
        self.assertEqual(normalize_location("Lévis, Québec"), "levis")
        self.assertEqual(normalize_location("Télétravail au Canada"), "teletravail")
        self.assertEqual(normalize_location("Remote - Anywhere in Canada"), "teletravail")
        self.assertEqual(normalize_location("Sherbrooke"), "sherbrooke")

    def test_is_valid_identity(self):
        self.assertTrue(is_valid_identity("developpeur python", "cgi", "montreal"))
        # Rejet des employeurs inconnus ou génériques
        self.assertFalse(is_valid_identity("developpeur python", "non specifie", "montreal"))
        self.assertFalse(is_valid_identity("developpeur python", "inconnu", "montreal"))
        self.assertFalse(is_valid_identity("developpeur python", "", "montreal"))
        # Rejet des titres trop courts
        self.assertFalse(is_valid_identity("ti", "cgi", "montreal"))
        # Rejet des lieux vides
        self.assertFalse(is_valid_identity("developpeur python", "cgi", ""))

    def test_compute_identity(self):
        offer = JobOffer(
            id="ge-100",
            titre="Développeur / Développeuse Python (H/F)",
            entreprise="CGI Inc.",
            lieu="Montréal, QC",
            url="https://example.com/job/100",
        )
        ident = compute_identity(offer)
        self.assertEqual(ident, ("developpeur python", "cgi", "montreal"))


class TestIntraSourceDeduplication(unittest.TestCase):
    """Vérifie la détection des doublons au sein d'une même source technique."""

    def test_same_id_same_source(self):
        offer_a = JobOffer(
            id="ge-50701948",
            titre="Développeur Logiciel",
            entreprise="CGI",
            lieu="Montréal (QC)",
            url="https://www.guichetemplois.gc.ca/job/50701948",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="ge-50701948",
            titre="Développeur Logiciel Enrichi",
            entreprise="CGI",
            lieu="Montréal (QC)",
            url="https://www.guichetemplois.gc.ca/job/50701948?session=abc",
            source="guichet-emplois",
        )
        self.assertTrue(is_intra_source_duplicate(offer_a, offer_b))

    def test_same_clean_url_same_source(self):
        offer_a = JobOffer(
            id="jb-111",
            titre="Analyste QA",
            entreprise="Desjardins",
            lieu="Lévis, QC",
            url="https://www.jobboom.com/fr/description-de-poste/qa/111",
            source="jobboom",
        )
        offer_b = JobOffer(
            id="jb-222",  # ID différent mais même URL propre
            titre="Analyste QA",
            entreprise="Desjardins",
            lieu="Lévis, QC",
            url="https://www.jobboom.com/fr/description-de-poste/qa/111?tracking=promo",
            source="jobboom",
        )
        self.assertTrue(is_intra_source_duplicate(offer_a, offer_b))

    def test_distinct_offers_same_source(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Développeur Java",
            entreprise="CGI",
            lieu="Montréal",
            url="https://guichet.ca/1",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="ge-2",
            titre="Développeur Python",
            entreprise="CGI",
            lieu="Montréal",
            url="https://guichet.ca/2",
            source="guichet-emplois",
        )
        self.assertFalse(is_intra_source_duplicate(offer_a, offer_b))

    def test_same_id_different_sources(self):
        offer_a = JobOffer(
            id="100",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://source-a.com/100",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="100",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://source-b.com/100",
            source="jobboom",
        )
        # Ne doit pas être considéré comme un doublon INTRA-source car les sources diffèrent
        self.assertFalse(is_intra_source_duplicate(offer_a, offer_b))


class TestInterSourceDeduplication(unittest.TestCase):
    """Vérifie la détection des offres rediffusées sur plusieurs portails."""

    def test_republished_across_sources_matched(self):
        ge_offer = JobOffer(
            id="ge-501",
            titre="Développeur Full Stack",
            entreprise="Nord Quantique Inc.",
            lieu="Montréal (QC)",
            url="https://guichet.ca/job/501",
            source="guichet-emplois",
        )
        jb_offer = JobOffer(
            id="jb-702",
            titre="Développeur Full-Stack (H/F)",
            entreprise="Nord Quantique",
            lieu="Montréal, QC",
            url="https://jobboom.com/job/702",
            source="jobboom",
        )
        self.assertTrue(is_cross_source_match(ge_offer, jb_offer))

    def test_partner_source_cross_matching(self):
        # Une offre agrégée par Guichet-Emplois provenant de Jobillico
        # et une offre provenant directement de Jobillico ou Jobboom
        offer_agg = JobOffer(
            id="ge-800",
            titre="Analyste Cybersécurité",
            entreprise="Hydro-Québec",
            lieu="Montréal",
            url="https://guichet.ca/800",
            source="guichet-emplois",
            source_partenaire="Jobillico",
        )
        offer_direct = JobOffer(
            id="jb-900",
            titre="Analyste Cybersécurité",
            entreprise="Hydro-Québec",
            lieu="Montréal (QC)",
            url="https://jobboom.ca/900",
            source="jobboom",
            source_partenaire=None,
        )
        self.assertTrue(is_cross_source_match(offer_agg, offer_direct))

    def test_same_publisher_not_cross_merged(self):
        # Deux postes identiques d'un même employeur sur le même site doivent rester distincts
        offer_1 = JobOffer(
            id="ge-10",
            titre="Développeur Logiciel",
            entreprise="FOP Experts",
            lieu="Montréal",
            url="https://guichet.ca/10",
            source="guichet-emplois",
        )
        offer_2 = JobOffer(
            id="ge-20",
            titre="Développeur Logiciel",
            entreprise="FOP Experts",
            lieu="Montréal",
            url="https://guichet.ca/20",
            source="guichet-emplois",
        )
        self.assertFalse(is_cross_source_match(offer_1, offer_2))

    def test_different_employers_not_matched(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Développeur Python",
            entreprise="CGI",
            lieu="Montréal",
            url="https://guichet.ca/1",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="jb-2",
            titre="Développeur Python",
            entreprise="Desjardins",
            lieu="Montréal",
            url="https://jobboom.com/2",
            source="jobboom",
        )
        self.assertFalse(is_cross_source_match(offer_a, offer_b))

    def test_different_locations_not_matched(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Développeur Python",
            entreprise="CGI",
            lieu="Montréal",
            url="https://guichet.ca/1",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="jb-2",
            titre="Développeur Python",
            entreprise="CGI",
            lieu="Québec",
            url="https://jobboom.com/2",
            source="jobboom",
        )
        self.assertFalse(is_cross_source_match(offer_a, offer_b))

    def test_generic_employer_not_matched(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Développeur Web",
            entreprise="Non spécifié",
            lieu="Montréal",
            url="https://guichet.ca/1",
            source="guichet-emplois",
        )
        offer_b = JobOffer(
            id="jb-2",
            titre="Développeur Web",
            entreprise="Non spécifié",
            lieu="Montréal",
            url="https://jobboom.com/2",
            source="jobboom",
        )
        self.assertFalse(is_cross_source_match(offer_a, offer_b))


class TestIntelligentMerging(unittest.TestCase):
    """Vérifie la fusion intelligente maximisant la richesse d'information."""

    def test_merge_preserves_longest_description(self):
        offer_short = JobOffer(
            id="ge-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            description="Poste de développeur à Montréal.",
        )
        offer_long = JobOffer(
            id="jb-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://jb.ca/1",
            source="jobboom",
            description=(
                "Superbe opportunité de développeur full-stack au sein de l'équipe agile de CGI. "
                "Vous participerez à la conception d'architectures microservices sur AWS avec Python et React."
            ),
        )
        merged = merge_job_offers(offer_short, offer_long)
        self.assertEqual(merged.description, offer_long.description)

    def test_merge_cumulates_skills_without_duplicates(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            competences_cles=["Python", "SQL", "Git"],
        )
        offer_b = JobOffer(
            id="jb-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://jb.ca/1",
            source="jobboom",
            competences_cles=["python", "Docker", "AWS", "SQL"],
        )
        merged = merge_job_offers(offer_a, offer_b)
        self.assertEqual(merged.competences_cles, ["AWS", "Docker", "Git", "Python", "SQL"])

    def test_merge_prioritizes_confirmed_stage(self):
        # confirmed_stage > possible_stage
        offer_possible = JobOffer(
            id="ge-1",
            titre="Développeur Junior",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            est_stage=False,
            statut_stage="possible_stage",
        )
        offer_confirmed = JobOffer(
            id="rem-1",
            titre="Développeur Stagiaire",
            entreprise="CGI",
            lieu="Montréal",
            url="https://rem.ca/1",
            source="remotive",
            est_stage=True,
            statut_stage="confirmed_stage",
        )
        merged = merge_job_offers(offer_possible, offer_confirmed)
        self.assertEqual(merged.statut_stage, "confirmed_stage")
        self.assertTrue(merged.est_stage)

    def test_merge_prioritizes_possible_over_not_indicated(self):
        offer_none = JobOffer(
            id="ge-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            est_stage=False,
            statut_stage="not_indicated",
        )
        offer_possible = JobOffer(
            id="jb-1",
            titre="Développeur",
            entreprise="CGI",
            lieu="Montréal",
            url="https://jb.ca/1",
            source="jobboom",
            est_stage=False,
            statut_stage="possible_stage",
        )
        merged = merge_job_offers(offer_none, offer_possible)
        self.assertEqual(merged.statut_stage, "possible_stage")

    def test_merge_preserves_partner_source(self):
        offer_ge = JobOffer(
            id="ge-1",
            titre="Dev",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            source_partenaire="Jobillico",
        )
        offer_jb = JobOffer(
            id="jb-1",
            titre="Dev",
            entreprise="CGI",
            lieu="Montréal",
            url="https://jb.ca/1",
            source="jobboom",
            source_partenaire=None,
        )
        merged = merge_job_offers(offer_jb, offer_ge)
        self.assertEqual(merged.source_partenaire, "Jobillico")

    def test_merge_preserves_salary_and_work_mode(self):
        offer_a = JobOffer(
            id="ge-1",
            titre="Dev",
            entreprise="CGI",
            lieu="Montréal",
            url="https://ge.ca/1",
            source="guichet-emplois",
            salaire=None,
            modalite=None,
        )
        offer_b = JobOffer(
            id="jb-1",
            titre="Dev",
            entreprise="CGI",
            lieu="Montréal",
            url="https://jb.ca/1",
            source="jobboom",
            salaire="85 000 $ à 95 000 $ par an",
            modalite="Hybride",
        )
        merged = merge_job_offers(offer_a, offer_b)
        self.assertEqual(merged.salaire, "85 000 $ à 95 000 $ par an")
        self.assertEqual(merged.modalite, "Hybride")


class TestExportsAndFileManagement(unittest.TestCase):
    """Vérifie la génération des fichiers de sortie JSON et CSV."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sample_offers = [
            JobOffer(
                id="ge-101",
                titre="Développeur Python & Cloud",
                entreprise="CloudLab Inc.",
                lieu="Montréal (QC)",
                province="QC",
                pays="Canada",
                url="https://example.com/job/101",
                source="guichet-emplois",
                source_partenaire="Jobillico",
                date_publication="2026-11-10",
                type_poste="Temps plein",
                modalite="Hybride",
                est_stage=False,
                statut_stage="not_indicated",
                description="Conception d'APIs REST en Python.\nBonne ambiance de travail.",
                competences_cles=["Python", "FastAPI", "AWS"],
                salaire="75 000 $ par an",
            ),
            JobOffer(
                id="rem-202",
                titre="Stagiaire Développement Logiciel",
                entreprise="TechDistributed",
                lieu="Québec (QC)",
                province="QC",
                pays="Canada",
                url="https://example.com/job/202",
                source="remotive",
                date_publication="2026-11-12",
                type_poste="Stage",
                modalite="Télétravail",
                est_stage=True,
                statut_stage="confirmed_stage",
                description="Stage rémunéré en développement web.",
                competences_cles=["JavaScript", "React", "Docker"],
                salaire="25 $ de l'heure",
            ),
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_and_load_json(self):
        json_file = self.temp_dir / "test_offres.json"
        export_to_json(self.sample_offers, json_file)

        self.assertTrue(json_file.is_file())
        reloaded = load_offers_from_json(json_file)
        self.assertEqual(len(reloaded), 2)
        self.assertEqual(reloaded[0].id, "ge-101")
        self.assertEqual(reloaded[1].statut_stage, "confirmed_stage")

    def test_export_csv_excel_compatibility(self):
        csv_file = self.temp_dir / "test_offres.csv"
        export_to_csv(self.sample_offers, csv_file, delimiter=";", encoding="utf-8-sig")

        self.assertTrue(csv_file.is_file())
        raw_bytes = csv_file.read_bytes()
        # Vérification du BOM UTF-8 (\xef\xbb\xbf) obligatoire pour Excel Windows
        self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))

        # Relecture standard avec csv.reader
        with open(csv_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)

        self.assertEqual(len(rows), 3)  # En-tête + 2 offres
        headers = rows[0]
        self.assertIn("id", headers)
        self.assertIn("titre", headers)
        self.assertIn("competences_cles", headers)
        self.assertIn("statut_stage", headers)

        # Vérification que les sauts de ligne ont été remplacés dans la description
        desc_in_row = rows[1][headers.index("description")]
        self.assertNotIn("\n", desc_in_row)
        self.assertIn("Conception d'APIs REST en Python. Bonne ambiance de travail.", desc_in_row)

        # Vérification de la jointure des compétences
        skills_in_row = rows[1][headers.index("competences_cles")]
        self.assertEqual(skills_in_row, "Python, FastAPI, AWS")

    def test_load_offers_from_json_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_offers_from_json(self.temp_dir / "inexistant.json")


class TestPipelineEndToEnd(unittest.TestCase):
    """Vérifie l'exécution complète du pipeline sur des cas réels et synthétiques."""

    def test_unify_synthetic_batch_with_duplicates(self):
        batch = [
            # 1. Offre de base
            JobOffer(
                id="ge-001",
                titre="Développeur Python",
                entreprise="CGI Inc.",
                lieu="Montréal (QC)",
                url="https://ge.ca/001",
                source="guichet-emplois",
                description="Court texte.",
                competences_cles=["Python"],
                statut_stage="not_indicated",
            ),
            # 2. Doublon INTRA-source (même ID)
            JobOffer(
                id="ge-001",
                titre="Développeur Python",
                entreprise="CGI Inc.",
                lieu="Montréal (QC)",
                url="https://ge.ca/001?track=1",
                source="guichet-emplois",
                description="Texte un peu plus long pour tester la fusion.",
                competences_cles=["Python", "SQL"],
                statut_stage="possible_stage",
            ),
            # 3. Doublon INTER-sources (Jobboom republie le même poste avec stage confirmé)
            JobOffer(
                id="jb-555",
                titre="Développeur Python (H/F)",
                entreprise="CGI",
                lieu="Montréal",
                url="https://jb.ca/555",
                source="jobboom",
                description="Description intégrale exhaustive de CGI avec tous les avantages sociaux.",
                competences_cles=["Docker", "AWS"],
                statut_stage="confirmed_stage",
                est_stage=True,
            ),
            # 4. Offre distincte (autre entreprise)
            JobOffer(
                id="rem-888",
                titre="Développeur Python",
                entreprise="Shopify",
                lieu="Télétravail",
                url="https://rem.ca/888",
                source="remotive",
                statut_stage="not_indicated",
            ),
        ]

        unified, stats = unify_offers(batch)

        # 4 offres en entrée -> 2 offres uniques en sortie
        self.assertEqual(stats.total_input, 4)
        self.assertEqual(stats.intra_duplicates_merged, 1)
        self.assertEqual(stats.cross_duplicates_merged, 1)
        self.assertEqual(stats.total_unified, 2)
        self.assertEqual(len(unified), 2)

        # Vérification de la première offre fusionnée
        cgi_offer = next(o for o in unified if "cgi" in o.entreprise.lower())
        self.assertEqual(cgi_offer.statut_stage, "confirmed_stage")
        self.assertTrue(cgi_offer.est_stage)
        self.assertIn("exhaustive de CGI", cgi_offer.description)
        self.assertEqual(cgi_offer.competences_cles, ["AWS", "Docker", "Python", "SQL"])

    def test_pipeline_stats_formatting(self):
        stats = PipelineStats(
            total_input=10,
            intra_duplicates_merged=2,
            cross_duplicates_merged=1,
            total_unified=7,
            by_source={"guichet-emplois": 5, "jobboom": 2},
            by_stage_status={"not_indicated": 6, "confirmed_stage": 1},
            top_skills=[("Python", 5), ("SQL", 3)],
        )
        report = stats.format_summary()
        self.assertIn("RAPPORT DU PIPELINE D'UNIFICATION", report)
        self.assertIn("Total d'annonces en entrée       : 10", report)
        self.assertIn("Offres uniques consolidées       : 7", report)
        self.assertIn("guichet-emplois", report)
        self.assertIn("Python", report)

    def test_load_and_unify_actual_datasets(self):
        """Vérifie le chargement et l'unification des 140 offres réelles sous data/."""
        data_dir = Path(__file__).resolve().parent / "data"
        if not data_dir.is_dir():
            self.skipTest("Dossier data/ non présent.")

        offers = load_all_datasets(data_dir)
        self.assertEqual(len(offers), 140)

        unified, stats = unify_offers(offers)
        self.assertGreater(stats.total_unified, 0)
        self.assertLessEqual(stats.total_unified, 140)
        self.assertEqual(stats.by_source.get("guichet-emplois", 0), 97)
        self.assertEqual(stats.by_source.get("jobboom", 0), 31)
        self.assertEqual(stats.by_source.get("remotive", 0), 12)
        self.assertGreater(stats.by_stage_status.get("confirmed_stage", 0), 0)


if __name__ == "__main__":
    unittest.main()
