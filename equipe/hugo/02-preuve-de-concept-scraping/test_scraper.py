"""
test_scraper.py - Tests unitaires hors ligne pour le collecteur Jobs Insights.
Vérifie la logique de parsing, la détection des compétences, l'extraction de description,
et les parseurs Atom et HTML sans effectuer aucun appel réseau.

Exécution :
    python -m unittest test_scraper.py -v
"""

import unittest
from models import JobOffer
from parsers import (
    parse_atom_feed,
    parse_search_page_html,
    enrich_offer_detail,
    extract_tech_skills,
    detect_stage
)

# ==============================================================================
# FIXTURES LOCALES HORS LIGNE
# ==============================================================================

ATOM_FEED_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
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

HTML_SEARCH_FIXTURE = """
<div id="results-list">
  <article id="article-50701948">
    <a class="resultJobItem" href="/jobsearch/jobposting/50701948;jsessionid=xyz">
      <span class="noctitle">Programmeur-analyste Python et Django</span>
    </a>
    <ul class="list-unstyled">
      <li class="business">CGI Inc.</li>
      <li class="location">emplacement Montréal (QC)</li>
      <li class="salary">salaire: 75 000 $ à 90 000 $ par an</li>
      <li class="date">10 novembre 2026</li>
    </ul>
    <span class="job-source">Jobillico.com</span>
  </article>
</div>
"""

HTML_DETAIL_RDFA_FIXTURE = """
<html>
<body>
  <ul class="job-posting-brief">
    <li>Modalité de travail : Télétravail régulier</li>
    <li>Conditions d'emploi : Temps plein</li>
  </ul>
  <div property="description">
    <h3>Description du poste</h3>
    <p>Nous recrutons un développeur senior pour rejoindre notre équipe agile.</p>
    <h4>Exigences :</h4>
    <ul>
      <li>Maîtrise de Python, FastAPI et Docker.</li>
      <li>Bonne connaissance des bases de données PostgreSQL et MySQL.</li>
      <li>Expérience avec Git et les pipelines CI/CD sous Linux.</li>
    </ul>
  </div>
</body>
</html>
"""

HTML_DETAIL_DOM_FALLBACK_FIXTURE = """
<html>
<body>
  <ul class="job-posting-brief">
    <li>Emploi hybride à Québec</li>
    <li>Poste de stagiaire universitaire</li>
  </ul>
  <div id="job-posting-detail">
    <h2>Sommaire des responsabilités</h2>
    <p>Concevoir et développer des interfaces web modernes avec Vue.js et TypeScript.</p>
    <p>Connaissance pratique du langage C et des protocoles REST.</p>
  </div>
</body>
</html>
"""


class TestScraperParsers(unittest.TestCase):
    """Suite de tests unitaires hors ligne validant le parsing et la normalisation."""

    def test_parse_atom_feed(self):
        """Vérifie l'extraction précise des métadonnées du flux Atom officiel."""
        offers = parse_atom_feed(ATOM_FEED_FIXTURE)
        self.assertEqual(len(offers), 2)

        first = offers[0]
        self.assertEqual(first.id, "gc-50691239")
        self.assertEqual(first.titre, "Développeur d'applications dorsales / Backend")
        self.assertEqual(first.entreprise, "TechCorp Solutions Inc.")
        self.assertEqual(first.lieu, "Sainte-Thérèse (QC)")
        self.assertEqual(first.province, "QC")
        self.assertEqual(first.salaire, "85 000 $ par année")
        self.assertEqual(first.type_poste, "Temps plein")
        self.assertEqual(first.methode_extraction, "Atom-XML")
        self.assertIsNotNone(first.description)

        # Vérifie la détection de stage
        second = offers[1]
        self.assertEqual(second.type_poste, "Stage")
        self.assertEqual(second.entreprise, "Studio Web Québec")

    def test_parse_search_page_html(self):
        """Vérifie le parsing des résultats de recherche HTML de Guichet-Emplois."""
        offers = parse_search_page_html(HTML_SEARCH_FIXTURE)
        self.assertEqual(len(offers), 1)

        offer = offers[0]
        self.assertEqual(offer.id, "gc-50701948")
        self.assertEqual(offer.titre, "Programmeur-analyste Python et Django")
        self.assertEqual(offer.entreprise, "CGI Inc.")
        self.assertEqual(offer.lieu, "Montréal (QC)")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.partenaire, "Jobillico.com")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("Django", offer.competences_cles)

    def test_enrich_detail_with_rdfa(self):
        """Vérifie l'enrichissement via les balises RDFa sémantiques et le remplissage de la description."""
        base_offer = JobOffer(
            id="gc-12345",
            titre="Développeur Backend",
            url_source="https://guichetemplois.gc.ca/job/12345"
        )
        self.assertIsNone(base_offer.description)

        enriched = enrich_offer_detail(base_offer, HTML_DETAIL_RDFA_FIXTURE)

        # Vérifie le remplissage de la description
        self.assertIsNotNone(enriched.description)
        self.assertIn("Nous recrutons un développeur senior", enriched.description)
        self.assertEqual(enriched.modalite, "Télétravail")
        self.assertIn("Python", enriched.competences_cles)
        self.assertIn("FastAPI", enriched.competences_cles)
        self.assertIn("Docker", enriched.competences_cles)
        self.assertIn("PostgreSQL", enriched.competences_cles)
        self.assertIn("CI/CD", enriched.competences_cles)

    def test_enrich_detail_with_dom_fallback(self):
        """Vérifie le mécanisme de repli vers le DOM lorsque le RDFa n'est pas présent."""
        base_offer = JobOffer(
            id="gc-67890",
            titre="Développeur Frontend",
            url_source="https://guichetemplois.gc.ca/job/67890"
        )
        enriched = enrich_offer_detail(base_offer, HTML_DETAIL_DOM_FALLBACK_FIXTURE)

        self.assertIsNotNone(enriched.description)
        self.assertIn("Sommaire des responsabilités", enriched.description)
        self.assertEqual(enriched.modalite, "Hybride")
        self.assertEqual(enriched.type_poste, "Stage")
        self.assertIn("Vue.js", enriched.competences_cles)
        self.assertIn("TypeScript", enriched.competences_cles)
        self.assertIn("C", enriched.competences_cles)

    def test_tech_skills_exclusion_faux_positifs(self):
        """Vérifie strictement l'élimination des faux positifs 'Vue' et 'C' en français."""
        # 1. Ne doit PAS détecter Vue.js sur une 'vue d'ensemble'
        phrase_fr = "Le candidat doit avoir une bonne vue d'ensemble du projet, en vue d'une embauche future."
        skills_fr = extract_tech_skills(phrase_fr)
        self.assertNotIn("Vue.js", skills_fr)
        self.assertNotIn("VUE", skills_fr)

        # 2. Ne doit PAS détecter C sur une abréviation ou lettre isolée
        phrase_c_faux = "C'est un travail temps plein, c. à d. 40h/semaine avec avantages."
        skills_c_faux = extract_tech_skills(phrase_c_faux)
        self.assertNotIn("C", skills_c_faux)

        # 3. DOIT détecter Vue.js quand il s'agit du framework
        phrase_vue_ok = "Développement d'applications SPA avec Vue.js et Tailwind."
        skills_vue_ok = extract_tech_skills(phrase_vue_ok)
        self.assertIn("Vue.js", skills_vue_ok)

        # 4. DOIT détecter C quand il est mentionné comme langage
        phrase_c_ok = "Excellente connaissance du langage C, de C++ et programmation bas niveau."
        skills_c_ok = extract_tech_skills(phrase_c_ok)
        self.assertIn("C", skills_c_ok)
        self.assertIn("C++", skills_c_ok)

    def test_detect_stage(self):
        """Vérifie la détection du statut de stage ou poste régulier."""
        self.assertEqual(detect_stage("Stagiaire en développement"), "Stage")
        self.assertEqual(detect_stage("Internship - Software QA"), "Stage")
        self.assertEqual(detect_stage("Emploi étudiant en informatique"), "Étudiant")
        self.assertEqual(detect_stage("Architecte de solutions infonuagiques"), "Temps plein")


if __name__ == "__main__":
    unittest.main()
