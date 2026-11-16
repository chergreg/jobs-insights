"""
test_guichet_emplois.py - Tests unitaires 100 % hors ligne pour Guichet-Emplois fusionné.

Vérifie l'ensemble des fonctionnalités sans aucun appel réseau réel :
1. Modèle commun Pydantic JobOffer et intégrité des données.
2. Nettoyage HTML, URLs et normalisation des dates (français/anglais).
3. Détection contextuelle des compétences sans faux positifs (C et Vue.js).
4. Qualification des stages (confirmé, possible, non indiqué).
5. Parsing de résultats de recherche HTML (articles, partenaires, balises wb-inv).
6. Enrichissement en cascade sur fiche détaillée (RDFa sémantique et repli DOM).
7. Parsing de flux Atom XML.
8. Gestionnaire de cache local et pagination simulée hors ligne.

Exécution :
    python -m unittest test_guichet_emplois.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from models import JobOffer
from scrapers.guichet_emplois import (
    CNP_CODES_TI,
    GUICHET_DELAY_SECONDS,
    GuichetEmploisScraper,
    build_search_url,
    classify_stage,
    clean_posting_url,
    clean_text,
    enrich_job_offer_from_detail,
    extract_tech_skills,
    parse_atom_feed,
    parse_display_date,
    parse_search_page_html,
)


# ==============================================================================
# FIXTURES LOCALES HORS LIGNE
# ==============================================================================

FIXTURE_HTML_SEARCH = """
<!DOCTYPE html>
<html lang="fr">
<body>
  <h2><span class="found" id="results-count">42</span> résultats trouvés</h2>
  <div id="results-list">
    <!-- Offre 1 : Partenaire externe Jobillico avec télétravail -->
    <article id="article-50701948" class="action-buttons">
      <a class="resultJobItem" href="/rechercheemplois/offredemploi/50701948;jsessionid=ABC123XYZ.jobsearch?source=searchresults">
        <h3 class="title">
          <span class="telework">Télétravail</span>
          <span class="job-source job-source-icon-16"><span class="wb-inv">Jobillico</span></span>
          <span class="noctitle">Développeur Python et Django</span>
        </h3>
        <ul class="list-unstyled">
          <li class="business">CGI Inc.</li>
          <li class="location"><span class="wb-inv">Emplacement</span>Montréal (QC)</li>
          <li class="salary">Salaire : 85 000 $ à 105 000 $ par an</li>
          <li class="date">12 novembre 2026</li>
        </ul>
      </a>
    </article>

    <!-- Offre 2 : Stage publié directement sur Guichet-Emplois -->
    <article id="article-50684844" class="action-buttons">
      <a class="resultJobItem" href="/rechercheemplois/offredemploi/50684844">
        <h3 class="title">
          <span class="job-source"><span class="wb-inv">Guichet-Emplois</span></span>
          <span class="noctitle">Stagiaire en développement web et logiciel</span>
        </h3>
        <ul class="list-unstyled">
          <li class="business">Studio Web Québec</li>
          <li class="location">emplacement Québec (QC)</li>
          <li class="salary">salaire: 24,00 $ de l'heure</li>
          <li class="date">9 nov 2026</li>
        </ul>
      </a>
    </article>

    <!-- Offre 3 : Données partielles sans salaire ni modalité -->
    <article id="article-50699999" class="action-buttons">
      <a class="resultJobItem" href="/rechercheemplois/offredemploi/50699999">
        <h3 class="title">
          <span class="noctitle">Technicien en soutien informatique</span>
        </h3>
        <ul class="list-unstyled">
          <li class="business">Services Informatiques Express</li>
          <li class="location">Laval (QC)</li>
          <li class="date">2026-11-05</li>
        </ul>
      </a>
    </article>
  </div>
</body>
</html>
"""

FIXTURE_HTML_DETAIL_RDFA = """
<!DOCTYPE html>
<html lang="fr">
<body>
  <ul class="job-posting-brief">
    <li>Modalité de travail : Télétravail régulier</li>
    <li>Conditions d'emploi : Temps plein</li>
  </ul>
  <div property="description">
    <h3>Description du poste</h3>
    <p>Nous recherchons un développeur senior pour rejoindre notre équipe agile.</p>
    <h4>Exigences :</h4>
    <ul>
      <li>Maîtrise de Python, FastAPI et Docker en environnement Linux.</li>
      <li>Excellente maîtrise des bases de données PostgreSQL et MySQL.</li>
      <li>Connaissance des pipelines CI/CD sous Git et principes Scrum.</li>
    </ul>
  </div>
</body>
</html>
"""

FIXTURE_HTML_DETAIL_DOM = """
<!DOCTYPE html>
<html lang="fr">
<body>
  <ul class="job-posting-brief">
    <li>Emploi hybride à Québec</li>
    <li>Poste de stagiaire universitaire pour l'été</li>
  </ul>
  <div id="job-posting-detail">
    <h2>Sommaire des responsabilités</h2>
    <p>Concevoir et développer des interfaces web modernes avec Vue.js et TypeScript.</p>
    <p>Connaissance pratique du langage C et des protocoles REST.</p>
    <p>Doit être inscrit à un programme universitaire en informatique.</p>
  </div>
</body>
</html>
"""

FIXTURE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Recherche Guichet-Emplois</title>
  <entry>
    <id>gc-50691239</id>
    <title>Développeur d'applications dorsales / Backend</title>
    <link rel="alternate" href="https://www.guichetemplois.gc.ca/job/50691239" />
    <updated>2026-11-10T14:30:00Z</updated>
    <summary type="html"><![CDATA[
      <strong>Numéro d'emploi :</strong> 50691239<br />
      <strong>Employeur :</strong> TechCorp Solutions Inc.<br />
      <strong>Emplacement :</strong> Sainte-Thérèse (QC)<br />
      <strong>Salaire :</strong> 85 000 $ par année
    ]]></summary>
  </entry>
  <entry>
    <id>gc-50684844</id>
    <title>Stagiaire en programmation et développement logiciel</title>
    <link rel="alternate" href="https://www.guichetemplois.gc.ca/job/50684844" />
    <updated>2026-11-09T09:15:00Z</updated>
    <summary type="html"><![CDATA[
      <strong>Numéro d'emploi :</strong> 50684844<br />
      <strong>Employeur :</strong> Studio Web Québec<br />
      <strong>Emplacement :</strong> Québec (QC)<br />
      <strong>Salaire :</strong> 24,00 $ de l'heure
    ]]></summary>
  </entry>
</feed>
"""


# ==============================================================================
# SUITE DE TESTS
# ==============================================================================

class TestJobOfferModel(unittest.TestCase):
    """Vérifie la conformité du modèle Pydantic unifié JobOffer."""

    def test_creation_minimale_et_valeurs_par_defaut(self):
        offer = JobOffer(
            id="ge-101",
            titre="Développeur Python",
            url="https://guichetemplois.gc.ca/job/101"
        )
        self.assertEqual(offer.id, "ge-101")
        self.assertEqual(offer.titre, "Développeur Python")
        self.assertEqual(offer.source, "guichet-emplois")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.pays, "Canada")
        self.assertFalse(offer.est_stage)
        self.assertEqual(offer.statut_stage, "not_indicated")
        self.assertIsNone(offer.salaire)
        self.assertIsNone(offer.description)
        self.assertIsNone(offer.source_partenaire)
        self.assertEqual(offer.competences_cles, [])
        self.assertEqual(offer.url_source, offer.url)

    def test_serialisation_pydantic(self):
        offer = JobOffer(
            id="ge-202",
            titre="Analyste QA",
            entreprise="TestLab QC",
            lieu="Québec, QC",
            url="https://guichetemplois.gc.ca/job/202",
            salaire="65 000 $",
            competences_cles=["QA", "Git"]
        )
        data = offer.model_dump()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["id"], "ge-202")
        self.assertEqual(data["entreprise"], "TestLab QC")
        self.assertEqual(data["competences_cles"], ["QA", "Git"])

        json_str = offer.model_dump_json()
        self.assertIn('"id":"ge-202"', json_str)


class TestHelpersAndNormalizers(unittest.TestCase):
    """Vérifie les fonctions pures de parsing et nettoyage de texte/dates."""

    def test_clean_text(self):
        raw = "<p>Ligne 1</p>\n<div>Ligne 2 &amp; test   multi-espaces</div>"
        cleaned = clean_text(raw)
        self.assertEqual(cleaned, "Ligne 1 Ligne 2 & test multi-espaces")
        self.assertEqual(clean_text(""), "")

    def test_clean_posting_url(self):
        raw = "/rechercheemplois/offredemploi/50701948;jsessionid=XYZ123?source=search"
        clean = clean_posting_url(raw)
        self.assertEqual(clean, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50701948")

        absolute = "https://www.guichetemplois.gc.ca/job/123;session=999"
        self.assertEqual(clean_posting_url(absolute), "https://www.guichetemplois.gc.ca/job/123")

    def test_parse_display_date_formats(self):
        # Français
        self.assertEqual(parse_display_date("12 novembre 2026"), "2026-11-12")
        self.assertEqual(parse_display_date("9 nov 2026"), "2026-11-09")
        self.assertEqual(parse_display_date("1er janvier 2026"), "2026-01-01")

        # Anglais
        self.assertEqual(parse_display_date("November 10, 2026"), "2026-11-10")

        # Déjà ISO
        self.assertEqual(parse_display_date("2026-11-15"), "2026-11-15")

        # Inconnu / Invalide
        self.assertIsNone(parse_display_date(""))
        self.assertIsNone(parse_display_date("Date non précisée"))

    def test_build_search_url(self):
        url = build_search_url(page=2, term="python", province="QC", cnp_codes=("21230", "21232"))
        self.assertIn("searchstring=python", url)
        self.assertIn("fn21=21230", url)
        self.assertIn("fn21=21232", url)
        self.assertIn("fprov=QC", url)
        self.assertIn("page=2", url)


class TestTechSkillsExtraction(unittest.TestCase):
    """Vérifie l'exclusion stricte des faux positifs en français et la détection juste."""

    def test_exclusion_faux_positifs_vue_et_c(self):
        # 1. Pas de Vue.js sur 'vue d'ensemble'
        phrase_vue = "Le candidat doit posséder une bonne vue d'ensemble de l'architecture."
        skills = extract_tech_skills(phrase_vue)
        self.assertNotIn("Vue.js", skills)

        # 2. Pas de C sur lettre isolée ou abréviation
        phrase_c = "C'est un poste à temps plein, c. à d. 40h/semaine."
        skills_c = extract_tech_skills(phrase_c)
        self.assertNotIn("C", skills_c)

    def test_detection_positive_technologies(self):
        phrase_tech = "Développement d'APIs en Python et FastAPI avec PostgreSQL, Docker sous Linux."
        skills = extract_tech_skills(phrase_tech)
        self.assertIn("Python", skills)
        self.assertIn("FastAPI", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertIn("Docker", skills)
        self.assertIn("Linux", skills)

    def test_detection_langage_c_et_vuejs(self):
        phrase = "Programmation en langage C et interface web dynamique avec Vue.js et TypeScript."
        skills = extract_tech_skills(phrase)
        self.assertIn("C", skills)
        self.assertIn("Vue.js", skills)
        self.assertIn("TypeScript", skills)

    def test_c_sharp_et_c_plus_plus(self):
        phrase = "Expérience exigée en C# (.NET) et modules en C++."
        skills = extract_tech_skills(phrase)
        self.assertIn("C#", skills)
        self.assertIn("C++", skills)


class TestStageClassification(unittest.TestCase):
    """Vérifie la qualification précise des offres de stage / emplois étudiants."""

    def test_stage_confirme_dans_titre(self):
        est_stage, statut, _ = classify_stage("Stagiaire en développement logiciel")
        self.assertTrue(est_stage)
        self.assertEqual(statut, "confirmed_stage")

        est_stage_en, statut_en, _ = classify_stage("Software Engineering Intern (Summer 2026)")
        self.assertTrue(est_stage_en)
        self.assertEqual(statut_en, "confirmed_stage")

    def test_stage_confirme_via_type_poste(self):
        est_stage, statut, _ = classify_stage("Développeur Python", job_type="internship")
        self.assertTrue(est_stage)
        self.assertEqual(statut, "confirmed_stage")

    def test_stage_possible_dans_description(self):
        desc = "Ce stage rémunéré s'adresse aux étudiants en informatique."
        est_stage, statut, signaux = classify_stage("Adjoint technique", description=desc)
        self.assertTrue(est_stage)
        self.assertEqual(statut, "possible_stage")
        self.assertIn("stage_role_in_description", signaux)

    def test_experience_passee_ne_qualifie_pas_en_stage(self):
        desc = "Le candidat doit posséder 2 ans d'expérience ou avoir complété un stage antérieur."
        est_stage, statut, _ = classify_stage("Développeur Senior", description=desc)
        self.assertFalse(est_stage)
        self.assertEqual(statut, "not_indicated")


class TestSearchPageHtmlParser(unittest.TestCase):
    """Vérifie l'extraction complète et fidèle depuis les pages de recherche HTML."""

    def test_parsing_page_complete(self):
        offers, total = parse_search_page_html(FIXTURE_HTML_SEARCH)
        self.assertEqual(total, 42)
        self.assertEqual(len(offers), 3)

        # Offre 1 : Partenaire Jobillico
        off1 = offers[0]
        self.assertEqual(off1.id, "ge-50701948")
        self.assertEqual(off1.titre, "Développeur Python et Django")
        self.assertEqual(off1.entreprise, "CGI Inc.")
        self.assertEqual(off1.lieu, "Montréal (QC)")
        self.assertEqual(off1.province, "QC")
        self.assertEqual(off1.source_partenaire, "Jobillico")
        self.assertEqual(off1.modalite, "Télétravail")
        self.assertEqual(off1.date_publication, "2026-11-12")
        self.assertEqual(off1.salaire, "85 000 $ à 105 000 $ par an")
        self.assertIn("Python", off1.competences_cles)
        self.assertIn("Django", off1.competences_cles)
        self.assertFalse(off1.est_stage)

        # Offre 2 : Stage direct Guichet-Emplois
        off2 = offers[1]
        self.assertEqual(off2.id, "ge-50684844")
        self.assertEqual(off2.titre, "Stagiaire en développement web et logiciel")
        self.assertEqual(off2.entreprise, "Studio Web Québec")
        self.assertEqual(off2.lieu, "Québec (QC)")
        self.assertIsNone(off2.source_partenaire)  # Guichet direct -> None
        self.assertEqual(off2.date_publication, "2026-11-09")
        self.assertEqual(off2.salaire, "24,00 $ de l'heure")
        self.assertTrue(off2.est_stage)
        self.assertEqual(off2.statut_stage, "confirmed_stage")
        self.assertEqual(off2.type_poste, "Stage")

        # Offre 3 : Données partielles
        off3 = offers[2]
        self.assertEqual(off3.id, "ge-50699999")
        self.assertIsNone(off3.salaire)
        self.assertIsNone(off3.modalite)
        self.assertEqual(off3.date_publication, "2026-11-05")

    def test_page_vide_ou_invalide(self):
        offers, total = parse_search_page_html("<html><body><p>Aucun résultat</p></body></html>")
        self.assertEqual(offers, [])
        self.assertIsNone(total)


class TestDetailEnrichment(unittest.TestCase):
    """Vérifie l'enrichissement sémantique RDFa et le repli DOM."""

    def test_enrichissement_via_rdfa(self):
        base_offer = JobOffer(
            id="ge-50701948",
            titre="Développeur Python",
            url="https://guichetemplois.gc.ca/job/50701948"
        )
        self.assertIsNone(base_offer.description)

        enriched = enrich_job_offer_from_detail(base_offer, FIXTURE_HTML_DETAIL_RDFA)
        self.assertIsNotNone(enriched.description)
        self.assertIn("Nous recherchons un développeur senior", enriched.description)
        self.assertEqual(enriched.modalite, "Télétravail")
        self.assertIn("Python", enriched.competences_cles)
        self.assertIn("FastAPI", enriched.competences_cles)
        self.assertIn("Docker", enriched.competences_cles)
        self.assertIn("PostgreSQL", enriched.competences_cles)
        self.assertIn("Linux", enriched.competences_cles)

    def test_enrichissement_via_dom_fallback(self):
        base_offer = JobOffer(
            id="ge-50684844",
            titre="Programmeur Junior",
            url="https://guichetemplois.gc.ca/job/50684844"
        )
        enriched = enrich_job_offer_from_detail(base_offer, FIXTURE_HTML_DETAIL_DOM)
        self.assertIsNotNone(enriched.description)
        self.assertIn("Sommaire des responsabilités", enriched.description)
        self.assertEqual(enriched.modalite, "Hybride")
        self.assertEqual(enriched.type_poste, "Stage")
        self.assertTrue(enriched.est_stage)
        self.assertIn("Vue.js", enriched.competences_cles)
        self.assertIn("TypeScript", enriched.competences_cles)
        self.assertIn("C", enriched.competences_cles)


class TestAtomFeedParser(unittest.TestCase):
    """Vérifie l'extraction depuis le flux officiel Atom XML."""

    def test_parsing_atom(self):
        offers = parse_atom_feed(FIXTURE_ATOM_XML)
        self.assertEqual(len(offers), 2)

        first = offers[0]
        self.assertEqual(first.id, "ge-50691239")
        self.assertEqual(first.entreprise, "TechCorp Solutions Inc.")
        self.assertEqual(first.lieu, "Sainte-Thérèse (QC)")
        self.assertEqual(first.salaire, "85 000 $ par année")
        self.assertEqual(first.type_poste, "Temps plein")

        second = offers[1]
        self.assertTrue(second.est_stage)
        self.assertEqual(second.type_poste, "Stage")


class TestCacheAndScraperOffline(unittest.TestCase):
    """Vérifie le fonctionnement du cache local et le mode hors ligne strict."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.scraper = GuichetEmploisScraper(
            cache_dir=self.cache_dir,
            offline_mode=True,
            delai_secondes=0.0
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_offline_mode_bloque_appels_reseau_si_cache_absent(self):
        with self.assertRaises(RuntimeError):
            self.scraper.fetch_url("https://www.guichetemplois.gc.ca/test-url-inconnu")

    def test_lecture_et_ecriture_cache(self):
        self.scraper.write_cache("search", "cle_test", "<p>Contenu mis en cache</p>")
        cached = self.scraper.read_cache("search", "cle_test")
        self.assertEqual(cached, "<p>Contenu mis en cache</p>")

    def test_expiration_du_cache(self):
        self.scraper.write_cache("search", "cle_expiree", "<p>Ancien contenu</p>")
        # max_age_hours négatif simule un cache expiré immédiatement
        cached = self.scraper.read_cache("search", "cle_expiree", max_age_hours=-1.0)
        self.assertIsNone(cached)

    def test_pagination_complete_simulee_via_cache(self):
        # Pré-remplir le cache pour la page 1 et la page 2
        page1_html = """
        <html><body>
          <span id="results-count">3</span>
          <article id="article-101"><a class="resultJobItem" href="/job/101"><span class="noctitle">Job 1</span></a></article>
          <article id="article-102"><a class="resultJobItem" href="/job/102"><span class="noctitle">Job 2</span></a></article>
        </body></html>
        """
        page2_html = """
        <html><body>
          <span id="results-count">3</span>
          <article id="article-103"><a class="resultJobItem" href="/job/103"><span class="noctitle">Job 3</span></a></article>
        </body></html>
        """
        self.scraper.write_cache("search", "search_QC__page_1", page1_html)
        self.scraper.write_cache("search", "search_QC__page_2", page2_html)

        collected = self.scraper.search(term="", province="QC", use_cache=True)
        self.assertEqual(len(collected), 3)
        self.assertEqual([o.id for o in collected], ["ge-101", "ge-102", "ge-103"])


class TestDatasetValidation(unittest.TestCase):
    """Vérifie la validité du jeu d'essai exporté dans data/offres_guichet_emplois.json."""

    def test_jeu_dessai_exporte(self):
        dataset_path = Path(__file__).resolve().parent / "data" / "offres_guichet_emplois.json"
        self.assertTrue(dataset_path.is_file(), "Le fichier data/offres_guichet_emplois.json doit exister.")

        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 50, "Le jeu d'essai doit contenir un volume substantiel d'offres.")

        for item in data:
            offer = JobOffer.model_validate(item)
            self.assertTrue(offer.id.startswith("ge-"))
            self.assertEqual(offer.source, "guichet-emplois")
            self.assertIn(offer.province, ["QC", "ON", "BC", "AB", "MB", "NB", "NS"])
            self.assertTrue(offer.url.startswith("http"))



if __name__ == "__main__":
    unittest.main()
