"""
test_scraper.py - Tests unitaires hors ligne pour le collecteur Jobs Insights.
Vérifie la logique de parsing, la détection des compétences, l'extraction de description,
le filtrage strict des métiers du DEC en informatique, et les parseurs Atom et HTML
sans effectuer aucun appel réseau.

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
    detect_stage,
    est_metier_dec_informatique,
    normaliser_url_francaise,
    extraire_identifiant_propre,
    extraire_code_cnp,
    est_cnp_dec_informatique
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
  <!-- Offres non-TI qui doivent être filtrées et exclues -->
  <entry>
    <id>https://www.guichetemplois.gc.ca/jobsearch/jobSearchRSSfeed?id=3720401</id>
    <title>apprenti monteur/apprentie monteuse de lignes - réseau électrique</title>
    <link rel="alternate" href="https://www.guichetemplois.gc.ca/jobsearch/jobposting/50738713" />
    <updated>2026-11-16T03:53:00Z</updated>
    <summary type="html"><![CDATA[
      <strong>Numéro d'emploi :</strong> 50738713<br />
      <strong>Employeur :</strong> Borea<br />
      <strong>Emplacement :</strong> Pointe-à-la-Garde (QC)<br />
      <strong>Salaire :</strong> 40,46 $ de l'heure
    ]]></summary>
  </entry>
  <entry>
    <id>gc-99999999</id>
    <title>Cleaning man/woman - Entretien ménager</title>
    <link rel="alternate" href="https://www.guichetemplois.gc.ca/job/99999999" />
    <updated>2026-11-09T09:15:00Z</updated>
    <summary type="html"><![CDATA[
      <strong>Numéro d'emploi :</strong> 99999999<br />
      <strong>Employeur :</strong> Nettoyage Express<br />
      <strong>Emplacement :</strong> Montréal (QC)<br />
      <strong>Salaire :</strong> 16,50 $ de l'heure
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
  <!-- Offre hors TI devant être ignorée -->
  <article id="article-88888888">
    <a class="resultJobItem" href="/jobsearch/jobposting/88888888">
      <span class="noctitle">Aide-cuisinier et plongeur</span>
    </a>
    <ul class="list-unstyled">
      <li class="business">Restaurant Bistro</li>
      <li class="location">Québec (QC)</li>
      <li class="salary">17,00 $ de l'heure</li>
    </ul>
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
  <div class="job-market-info">
    <h4>Infos sur le marché du travail</h4>
    <p>Développeur Web/développeuse Web</p>
    <span class="badge">CNP 21234</span>
  </div>
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

    def test_est_metier_dec_informatique_inclusions(self):
        """Vérifie que tous les métiers et branches du DEC en informatique sont acceptés."""
        metiers_dec = [
            "Développeur Web/développeuse Web",
            "Programmeur-analyste",
            "Ingénieur de logiciels",
            "Développeur de jeux vidéo",
            "Technicien en réseau informatique",
            "Agent de soutien aux utilisateurs",
            "Spécialiste de la cybersécurité",
            "Administrateur de bases de données",
            "Évaluateur de systèmes d'information (QA)",
            "Stagiaire en informatique",
            "Stagiaire en programmation",
            "Full Stack Software Developer",
            "DevOps Engineer",
            "IT Helpdesk Support"
        ]
        for metier in metiers_dec:
            self.assertTrue(
                est_metier_dec_informatique(metier),
                f"Le métier '{metier}' devrait être reconnu comme appartenant au DEC en informatique."
            )

    def test_est_metier_dec_informatique_exclusions(self):
        """Vérifie que les métiers hors TI (cleaning, cuisine, etc.) sont formellement rejetés."""
        metiers_hors_ti = [
            "Cleaning man/woman",
            "Nettoyeur de vitres",
            "Préposé à l'entretien ménager",
            "Concierge d'immeuble",
            "apprenti monteur/apprentie monteuse de lignes - réseau électrique",
            "Monteur de lignes haute tension",
            "Électricien industriel",
            "Aide-cuisinier",
            "Serveur en salle",
            "Plongeur de restaurant",
            "Commis d'entrepôt",
            "Chauffeur-livreur",
            "Préposé aux bénéficiaires",
            "Gardien de sécurité"
        ]
        for metier in metiers_hors_ti:
            self.assertFalse(
                est_metier_dec_informatique(metier),
                f"Le métier '{metier}' devrait être exclu (hors domaine informatique)."
            )

    def test_parse_atom_feed(self):
        """Vérifie l'extraction précise et le filtrage des métiers non-TI du flux Atom."""
        offers = parse_atom_feed(ATOM_FEED_FIXTURE)
        # Sur 3 entrées dans la fixture, 1 est "Cleaning man/woman" et doit être rejetée
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
        self.assertIn("lang=fra", first.url_source)
        self.assertIsNotNone(first.description)

        # Vérifie la détection de stage
        second = offers[1]
        self.assertEqual(second.type_poste, "Stage")
        self.assertEqual(second.entreprise, "Studio Web Québec")

    def test_parse_search_page_html(self):
        """Vérifie le parsing et l'exclusion automatique des cartes hors TI."""
        offers = parse_search_page_html(HTML_SEARCH_FIXTURE)
        # Sur 2 articles dans la fixture, 'Aide-cuisinier' doit être ignoré
        self.assertEqual(len(offers), 1)

        offer = offers[0]
        self.assertEqual(offer.id, "gc-50701948")
        self.assertEqual(offer.titre, "Programmeur-analyste Python et Django")
        self.assertEqual(offer.entreprise, "CGI Inc.")
        self.assertEqual(offer.lieu, "Montréal (QC)")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.partenaire, "Jobillico.com")
        self.assertIn("lang=fra", offer.url_source)
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("Django", offer.competences_cles)

    def test_enrich_detail_with_rdfa(self):
        """Vérifie l'enrichissement via les balises RDFa sémantiques et le remplissage de la description."""
        base_offer = JobOffer(
            id="gc-12345",
            titre="Développeur Backend",
            url_source="https://www.guichetemplois.gc.ca/job/12345?lang=fra"
        )
        self.assertIsNone(base_offer.description)

        enriched = enrich_offer_detail(base_offer, HTML_DETAIL_RDFA_FIXTURE)

        # Vérifie le remplissage de la description
        self.assertIsNotNone(enriched.description)
        self.assertIn("Nous recrutons un développeur senior", enriched.description)
        self.assertEqual(enriched.modalite, "Télétravail")
        self.assertEqual(enriched.cnp, "21234")
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
            url_source="https://www.guichetemplois.gc.ca/job/67890?lang=fra"
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

    def test_normaliser_url_francaise(self):
        """Vérifie que les URLs sont correctement normalisées avec le paramètre lang=fra."""
        url1 = normaliser_url_francaise("https://www.jobbank.gc.ca/jobsearch/jobposting/12345")
        self.assertIn("guichetemplois.gc.ca", url1)
        self.assertIn("lang=fra", url1)

        url2 = normaliser_url_francaise("/rechercheemplois/offredemploi/50738681?source=searchresults")
        self.assertTrue(url2.startswith("https://www.guichetemplois.gc.ca"))
        self.assertIn("lang=fra", url2)


    def test_extraire_identifiant_propre(self):
        """Vérifie que les identifiants bruts (y compris URLs de flux RSS) sont bien nettoyés."""
        id1 = extraire_identifiant_propre("article-50738681", "")
        self.assertEqual(id1, "gc-50738681")

        id2 = extraire_identifiant_propre(
            "https://www.guichetemplois.gc.ca/jobsearch/jobSearchRSSfeed?id=3720401",
            "https://www.guichetemplois.gc.ca/jobsearch/jobposting/50738713?lang=fra"
        )
        self.assertEqual(id2, "gc-50738713")

        id3 = extraire_identifiant_propre("50701948", "")
        self.assertEqual(id3, "gc-50701948")


    def test_extraire_code_cnp(self):
        """Vérifie l'extraction du code CNP à partir de texte et de balises HTML."""
        # 1. Extraction textuelle
        cnp1 = extraire_code_cnp("Information sur le marché du travail : CNP 21234 (Développeur Web)")
        self.assertEqual(cnp1, "21234")

        # 2. Extraction variante anglophone
        cnp2 = extraire_code_cnp("Labour market information: NOC 21230")
        self.assertEqual(cnp2, "21230")

        # 3. Extraction depuis balise sémantique HTML
        html_tag = '<meta property="occupationalCategory" content="21232" />'
        cnp3 = extraire_code_cnp(html_tag)
        self.assertEqual(cnp3, "21232")

        # 4. Absence de CNP
        self.assertIsNone(extraire_code_cnp("Poste de développeur sans code mentionné."))

    def test_est_cnp_dec_informatique(self):
        """Vérifie la classification formelle des codes CNP TI vs hors TI."""
        # Métiers DEC TI
        self.assertTrue(est_cnp_dec_informatique("21234"))  # Développeurs Web
        self.assertTrue(est_cnp_dec_informatique("21232"))  # Développeurs de logiciels
        self.assertTrue(est_cnp_dec_informatique("21230"))  # Informaticiens
        self.assertTrue(est_cnp_dec_informatique("22220"))  # Techniciens réseau
        self.assertTrue(est_cnp_dec_informatique("22221"))  # Soutien utilisateurs
        self.assertTrue(est_cnp_dec_informatique("22222"))  # QA / Évaluateurs systèmes
        self.assertTrue(est_cnp_dec_informatique("21220"))  # Cybersécurité

        # Métiers hors TI (ex: monteurs de lignes électriques CNP 72203)
        self.assertFalse(est_cnp_dec_informatique("72203"))
        self.assertFalse(est_cnp_dec_informatique("65310"))
        self.assertFalse(est_cnp_dec_informatique("72010"))

        # Valeurs nulles
        self.assertIsNone(est_cnp_dec_informatique(None))
        self.assertIsNone(est_cnp_dec_informatique(""))


if __name__ == "__main__":
    unittest.main()
