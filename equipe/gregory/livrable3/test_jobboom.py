"""
test_jobboom.py - Tests unitaires 100 % hors ligne pour le connecteur Jobboom Québec.

Vérifie l'ensemble des fonctionnalités sans aucun appel réseau réel :
1. Modèle commun Pydantic JobOffer et intégrité des données Jobboom.
2. Fonctions pures de nettoyage, normalisation des URLs et extraction d'identifiants.
3. Parsing de listing HTML (catégorie/recherche, attributs data-url, total annoncé).
4. Extraction robuste JSON-LD schema.org/JobPosting (scripts directs, listes, @graph).
5. Typage des contrats, détection de stages et extraction de salaire MonetaryAmount.
6. Extraction des compétences techniques sans faux positifs.
7. Repli élégant sur le DOM en cas d'absence de JSON-LD.
8. Gestionnaire de cache local et pagination simulée multi-pages en mode hors ligne.
9. Validation du jeu d'essai exporté dans data/offres_jobboom.json.

Exécution :
    python -m unittest test_jobboom.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from models import JobOffer
from scrapers.jobboom import (
    JOBBOOM_BASE_URL,
    JOBBOOM_DELAY_SECONDS,
    JobboomScraper,
    build_category_url,
    build_search_url,
    clean_jobboom_url,
    clean_text,
    extract_jobboom_id,
    extract_json_ld_job_posting,
    extract_tech_skills,
    parse_date_iso,
    parse_jobboom_detail_html,
    parse_jobboom_employment_type,
    parse_jobboom_location,
    parse_jobboom_salary,
    parse_listing_page_html,
)


# ==============================================================================
# FIXTURES LOCALES HORS LIGNE
# ==============================================================================

FIXTURE_LISTING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head><title>Emplois Technologies et médias numériques - Jobboom</title></head>
<body>
  <div class="search-header">
    <h1>Emplois en TI au Québec</h1>
    <div class="pagination-info">1 - 15 de 131 résultats</div>
  </div>

  <div class="job-listings">
    <!-- Offre 1 : Lien classique <a> -->
    <div class="job-card">
      <a class="job-title-link" href="/fr/offre-emploi/specialiste-en-informatique-pour-utilisateurs-finaux-end-user-computing-specialist_services-de-gestion-quantum-ltee_p3661921?utm_source=test">
        Spécialiste en informatique pour utilisateurs finaux
      </a>
      <span class="company">Services de Gestion Quantum Ltée</span>
      <span class="location">Montréal, QC</span>
    </div>

    <!-- Offre 2 : Lien avec attribut data-url (pattern Mamadou) -->
    <div class="job-card" data-url="/fr/offre-emploi/technicien-ne-en-informatique-en-support-technique_services-plus_p3132854">
      <a href="/fr/offre-emploi/technicien-ne-en-informatique-en-support-technique_services-plus_p3132854">
        Technicien (ne) en informatique en support technique
      </a>
      <span class="company">Services plus</span>
    </div>

    <!-- Offre 3 : Doublon avec fragment d'ancre (doit être ignoré) -->
    <div class="job-card">
      <a href="/fr/offre-emploi/specialiste-en-informatique-pour-utilisateurs-finaux-end-user-computing-specialist_services-de-gestion-quantum-ltee_p3661921#apply">
        Spécialiste en informatique (Lien d'action doublon)
      </a>
    </div>

    <!-- Offre 4 : Stage TI -->
    <div class="job-card">
      <a href="https://www.jobboom.com/fr/offre-emploi/stagiaire-developpeur-fullstack-ete-2027_tech-studio_p3720100">
        Stagiaire développeur Fullstack - Été 2027
      </a>
      <span class="company">Tech Studio</span>
    </div>
  </div>
</body>
</html>
"""

FIXTURE_DETAIL_JSON_LD_STANDARD = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <title>Développeur fullstack - Fed IT - Jobboom</title>
  <script type="application/ld+json">
  {
    "@context": "http://schema.org/",
    "@type": "JobPosting",
    "title": "Développeur fullstack",
    "datePosted": "2026-11-12",
    "validThrough": "2027-02-07",
    "employmentType": ["PERMANENT", "FULL_TIME"],
    "hiringOrganization": {
      "@type": "Organization",
      "name": "Fed IT",
      "logo": "https://images.jobboom.com/logo/test.jpg"
    },
    "jobLocation": {
      "@type": "Place",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Montréal",
        "addressRegion": "QC",
        "addressCountry": "CA",
        "postalCode": "H2M2T6"
      },
      "geo": {
        "@type": "GeoCoordinates",
        "latitude": "45.545402",
        "longitude": "-73.63923"
      }
    },
    "description": "<p>Nous recherchons un <strong>développeur fullstack</strong> pour notre client.</p><ul><li>2+ ans d'expérience avec C#, ASP.Net et JavaScript.</li><li>Maîtrise de SQL Server et PostgreSQL sous Linux.</li><li>Connaissance des conteneurs Docker et des principes CI/CD.</li></ul>"
  }
  </script>
</head>
<body>
  <h1>Développeur fullstack</h1>
</body>
</html>
"""

FIXTURE_DETAIL_JSON_LD_STAGE_ET_SALAIRE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <title>Stagiaire en assurance qualité logicielle (QA) - Studio Test QC</title>
  <script type="application/ld+json">
  {
    "@context": "http://schema.org/",
    "@type": "JobPosting",
    "title": "Stagiaire en assurance qualité logicielle",
    "datePosted": "2026-11-10T08:30:00Z",
    "employmentType": ["INTERN"],
    "jobLocationType": "TELECOMMUTE",
    "hiringOrganization": {
      "@type": "Organization",
      "name": "Studio Test QC"
    },
    "jobLocation": {
      "@type": "Place",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Québec",
        "addressRegion": "QC",
        "addressCountry": "Canada"
      }
    },
    "baseSalary": {
      "@type": "MonetaryAmount",
      "currency": "CAD",
      "value": {
        "@type": "QuantitativeValue",
        "minValue": 22.50,
        "maxValue": 26.00,
        "unitText": "HOUR"
      }
    },
    "description": "<p>Opportunité de stage étudiant pour l'été. Vous participerez aux tests automatisés en Python avec Git et méthodologie Agile.</p>"
  }
  </script>
</head>
<body>
  <h1>Stagiaire QA</h1>
</body>
</html>
"""

FIXTURE_DETAIL_JSON_LD_GRAPH = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <title>Analyste en cybersécurité - Régulvar</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        "itemListElement": []
      },
      {
        "@type": "JobPosting",
        "title": "Analyste junior en cybersécurité - Laval",
        "datePosted": "2026-11-10",
        "employmentType": "CONTRACTOR",
        "hiringOrganization": {
          "@type": "Organization",
          "name": "Régulvar inc."
        },
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Laval",
            "addressRegion": "QC",
            "addressCountry": "CA"
          }
        },
        "description": "<p>Poste contractuel de 6 mois en mode hybride à Laval. Connaissance de Linux, pare-feux et Python appréciée.</p>"
      }
    ]
  }
  </script>
</head>
<body><h1>Analyste junior</h1></body>
</html>
"""

FIXTURE_DETAIL_DOM_FALLBACK = """
<!DOCTYPE html>
<html lang="fr">
<head><title>Offre sans JSON-LD</title></head>
<body>
  <h1>Technicien réseau informatique</h1>
  <div class="company-name">Télécom Québec</div>
  <div class="job-description">
    <p>Installation et support de commutateurs réseau sous Linux et routeurs Cisco. Environnement sur place à Trois-Rivières.</p>
  </div>
</body>
</html>
"""


# ==============================================================================
# SUITE DE TESTS UNITAIRES
# ==============================================================================

class TestJobOfferJobboomModel(unittest.TestCase):
    """Vérifie la conformité du modèle Pydantic unifié JobOffer pour la source Jobboom."""

    def test_creation_minimale_et_valeurs_jobboom(self):
        offer = JobOffer(
            id="jb-3661921",
            titre="Spécialiste EUC",
            entreprise="Quantum",
            lieu="Montréal, QC",
            url="https://www.jobboom.com/fr/offre-emploi/euc_p3661921",
            source="jobboom"
        )
        self.assertEqual(offer.id, "jb-3661921")
        self.assertEqual(offer.source, "jobboom")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.pays, "Canada")
        self.assertFalse(offer.est_stage)
        self.assertEqual(offer.statut_stage, "not_indicated")
        self.assertIsNone(offer.salaire)
        self.assertEqual(offer.url_source, offer.url)

    def test_serialisation_pydantic(self):
        offer = JobOffer(
            id="jb-9999",
            titre="Dev Python",
            entreprise="Lab TI",
            lieu="Québec, QC",
            url="https://www.jobboom.com/fr/offre-emploi/dev_p9999",
            source="jobboom",
            competences_cles=["Python", "FastAPI"]
        )
        data = offer.model_dump()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["id"], "jb-9999")
        self.assertEqual(data["competences_cles"], ["Python", "FastAPI"])

        json_str = offer.model_dump_json()
        self.assertIn('"id":"jb-9999"', json_str)
        self.assertIn('"source":"jobboom"', json_str)


class TestJobboomHelpersAndNormalizers(unittest.TestCase):
    """Vérifie les fonctions pures de normalisation d'URLs, identifiants et dates."""

    def test_clean_jobboom_url(self):
        raw = "https://www.jobboom.com/fr/offre-emploi/poste-dev_p1234?dk=informatique&sortBy=date#apply"
        cleaned = clean_jobboom_url(raw)
        self.assertEqual(cleaned, "https://www.jobboom.com/fr/offre-emploi/poste-dev_p1234")

        relative = "/fr/offre-emploi/analyste_p5678?page=1"
        self.assertEqual(clean_jobboom_url(relative), "https://www.jobboom.com/fr/offre-emploi/analyste_p5678")
        self.assertEqual(clean_jobboom_url(""), "")

    def test_extract_jobboom_id(self):
        # Format avec tiret bas _p
        self.assertEqual(
            extract_jobboom_id("https://www.jobboom.com/fr/offre-emploi/titre_entreprise_p3661921"),
            "jb-3661921"
        )
        # Format avec trait d'union -p
        self.assertEqual(
            extract_jobboom_id("https://www.jobboom.com/fr/offre-emploi/titre-p3718101"),
            "jb-3718101"
        )
        # Format avec barre oblique /p
        self.assertEqual(
            extract_jobboom_id("https://www.jobboom.com/fr/offre-emploi/p123456"),
            "jb-123456"
        )
        # URL sans identifiant numérique 'p' (repli sur le slug)
        self.assertTrue(
            extract_jobboom_id("https://www.jobboom.com/fr/offre-emploi/architecte-solution").startswith("jb-architecte")
        )

    def test_parse_date_iso(self):
        self.assertEqual(parse_date_iso("2026-11-12"), "2026-11-12")
        self.assertEqual(parse_date_iso("2026-11-10T08:30:00Z"), "2026-11-10")
        self.assertEqual(parse_date_iso("12 novembre 2026"), "2026-11-12")
        self.assertIsNone(parse_date_iso(None))
        self.assertIsNone(parse_date_iso(""))

    def test_build_urls(self):
        # Catégorie page 1
        cat_p1 = build_category_url(page=1)
        self.assertIn("/fr/technologies-medias-numeriques/_i10lfr", cat_p1)
        self.assertIn("sortBy=date", cat_p1)
        self.assertNotIn("page=1", cat_p1)

        # Catégorie page 2
        cat_p2 = build_category_url(page=2)
        self.assertIn("page=2", cat_p2)

        # Recherche par mot-clé
        search_url = build_search_url("stage informatique", page=2)
        self.assertIn("/fr/emploi/stage-informatique/_lfrk", search_url)
        self.assertIn("dk=stage+informatique", search_url)
        self.assertIn("page=2", search_url)

    def test_clean_text(self):
        raw = "<p>Ligne 1</p>\n<div>Ligne 2 &amp; test   espaces</div>"
        self.assertEqual(clean_text(raw), "Ligne 1 Ligne 2 & test espaces")
        self.assertEqual(clean_text(""), "")

    def test_extract_tech_skills(self):
        # Exclusion des faux positifs en français
        phrase_piege = "Le candidat doit avoir une vue d'ensemble du poste, c. à d. polyvalent."
        skills_piege = extract_tech_skills(phrase_piege)
        self.assertNotIn("Vue.js", skills_piege)
        self.assertNotIn("C", skills_piege)

        # Détection positive
        phrase_tech = "Développeur C# et C++ avec bases PostgreSQL, Docker sous Linux et framework Vue.js."
        skills = extract_tech_skills(phrase_tech)
        self.assertIn("C#", skills)
        self.assertIn("C++", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertIn("Docker", skills)
        self.assertIn("Linux", skills)
        self.assertIn("Vue.js", skills)


class TestJobboomListingParser(unittest.TestCase):
    """Vérifie le parsing de la page de listing Jobboom (ordonné, dédupliqué, pagination)."""

    def test_parsing_listing_page_complete(self):
        urls, total = parse_listing_page_html(FIXTURE_LISTING_PAGE_HTML, base_url=JOBBOOM_BASE_URL)

        # Total annoncé dans la pagination ("1 - 15 de 131 résultats")
        self.assertEqual(total, 131)

        # 3 offres uniques attendues (l'offre 3 étant un doublon avec fragment #apply)
        self.assertEqual(len(urls), 3)

        # Préservation de l'ordre d'apparition
        self.assertEqual(
            urls[0],
            "https://www.jobboom.com/fr/offre-emploi/specialiste-en-informatique-pour-utilisateurs-finaux-end-user-computing-specialist_services-de-gestion-quantum-ltee_p3661921"
        )
        self.assertEqual(
            urls[1],
            "https://www.jobboom.com/fr/offre-emploi/technicien-ne-en-informatique-en-support-technique_services-plus_p3132854"
        )
        self.assertEqual(
            urls[2],
            "https://www.jobboom.com/fr/offre-emploi/stagiaire-developpeur-fullstack-ete-2027_tech-studio_p3720100"
        )

    def test_parsing_listing_page_vide(self):
        urls, total = parse_listing_page_html("")
        self.assertEqual(urls, [])
        self.assertIsNone(total)


class TestJobboomJsonLdExtractionAndParsing(unittest.TestCase):
    """Vérifie l'extraction et la désérialisation du bloc JSON-LD Schema.org/JobPosting."""

    def test_extraction_json_ld_standard(self):
        data = extract_json_ld_job_posting(FIXTURE_DETAIL_JSON_LD_STANDARD)
        self.assertIsNotNone(data)
        self.assertEqual(data.get("@type"), "JobPosting")
        self.assertEqual(data.get("title"), "Développeur fullstack")

    def test_extraction_json_ld_graph(self):
        # Support des structures @graph Schema.org
        data = extract_json_ld_job_posting(FIXTURE_DETAIL_JSON_LD_GRAPH)
        self.assertIsNotNone(data)
        self.assertEqual(data.get("@type"), "JobPosting")
        self.assertEqual(data.get("title"), "Analyste junior en cybersécurité - Laval")

    def test_parse_jobboom_location(self):
        data = {
            "jobLocation": {
                "address": {
                    "addressLocality": "Boucherville",
                    "addressRegion": "QC",
                    "addressCountry": "CA"
                }
            }
        }
        lieu, province, pays = parse_jobboom_location(data)
        self.assertEqual(lieu, "Boucherville, QC")
        self.assertEqual(province, "QC")
        self.assertEqual(pays, "Canada")

    def test_parse_jobboom_employment_type(self):
        # Permanent temps plein
        t1, st1, stat1 = parse_jobboom_employment_type({"employmentType": ["PERMANENT", "FULL_TIME"]}, "Dev", "")
        self.assertEqual(t1, "Temps plein")
        self.assertFalse(st1)

        # Stage explicite
        t2, st2, stat2 = parse_jobboom_employment_type({"employmentType": ["INTERN"]}, "Stagiaire", "")
        self.assertEqual(t2, "Stage")
        self.assertTrue(st2)
        self.assertEqual(stat2, "confirmed_stage")

        # Contrat
        t3, st3, stat3 = parse_jobboom_employment_type({"employmentType": "CONTRACTOR"}, "Consultant", "")
        self.assertEqual(t3, "Contrat")

    def test_parse_jobboom_salary(self):
        # Salaire horaire avec plage min/max
        data_sal = {
            "baseSalary": {
                "value": {
                    "minValue": 24.0,
                    "maxValue": 28.5,
                    "unitText": "HOUR"
                }
            }
        }
        self.assertEqual(parse_jobboom_salary(data_sal), "24.0 $ à 28.5 $ de l'heure")

        # Sans salaire (doit retourner None conformément à AGENTS.md)
        self.assertIsNone(parse_jobboom_salary({}))

    def test_parse_detail_html_complet(self):
        url = "https://www.jobboom.com/fr/offre-emploi/developpeur-fullstack_fed-it_p3149892"
        offer = parse_jobboom_detail_html(FIXTURE_DETAIL_JSON_LD_STANDARD, url)

        self.assertIsNotNone(offer)
        self.assertEqual(offer.id, "jb-3149892")
        self.assertEqual(offer.titre, "Développeur fullstack")
        self.assertEqual(offer.entreprise, "Fed IT")
        self.assertEqual(offer.lieu, "Montréal, QC")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.pays, "Canada")
        self.assertEqual(offer.date_publication, "2026-11-12")
        self.assertEqual(offer.type_poste, "Temps plein")
        self.assertFalse(offer.est_stage)
        self.assertIsNone(offer.salaire)
        self.assertIn("C#", offer.competences_cles)
        self.assertIn("JavaScript", offer.competences_cles)
        self.assertIn("Docker", offer.competences_cles)
        self.assertIn("Linux", offer.competences_cles)
        self.assertIn("PostgreSQL", offer.competences_cles)

    def test_parse_detail_html_stage_et_modalite(self):
        url = "https://www.jobboom.com/fr/offre-emploi/stagiaire-qa_studio-test_p3720999"
        offer = parse_jobboom_detail_html(FIXTURE_DETAIL_JSON_LD_STAGE_ET_SALAIRE, url)

        self.assertIsNotNone(offer)
        self.assertEqual(offer.id, "jb-3720999")
        self.assertTrue(offer.est_stage)
        self.assertEqual(offer.statut_stage, "confirmed_stage")
        self.assertEqual(offer.type_poste, "Stage")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertEqual(offer.salaire, "22.5 $ à 26.0 $ de l'heure")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("Git", offer.competences_cles)
        self.assertIn("Agile", offer.competences_cles)

    def test_repli_dom_si_pas_de_json_ld(self):
        url = "https://www.jobboom.com/fr/offre-emploi/technicien-reseau_telecom_p3999999"
        offer = parse_jobboom_detail_html(FIXTURE_DETAIL_DOM_FALLBACK, url)

        self.assertIsNotNone(offer)
        self.assertEqual(offer.id, "jb-3999999")
        self.assertEqual(offer.titre, "Technicien réseau informatique")
        self.assertEqual(offer.entreprise, "Télécom Québec")
        self.assertIn("Linux", offer.competences_cles)


class TestJobboomCacheAndOfflineScraper(unittest.TestCase):
    """Vérifie le gestionnaire de cache local et le mode 100 % hors ligne."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name)
        self.scraper = JobboomScraper(cache_dir=self.cache_path, delai_secondes=0.0, offline_mode=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lecture_et_ecriture_cache(self):
        content = "<html><body>Offre Jobboom en cache</body></html>"
        self.scraper.write_cache("details", "detail_123", content)

        cached = self.scraper.read_cache("details", "detail_123")
        self.assertEqual(cached, content)

    def test_expiration_du_cache(self):
        content = "<html>Contenu expiré</html>"
        p = self.scraper.write_cache("search", "search_old", content)

        # Simuler un fichier vieux de 48h
        old_time = time.time() - (48 * 3600)
        import os
        os.utime(p, (old_time, old_time))

        # Lecture avec max_age_hours=24h -> None
        cached = self.scraper.read_cache("search", "search_old", max_age_hours=24.0)
        self.assertIsNone(cached)

    def test_offline_mode_bloque_appels_reseau_si_cache_absent(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.scraper.fetch_url("https://www.jobboom.com/fr/inconnu", category="details")
        self.assertIn("Mode hors ligne actif", str(ctx.exception))

    def test_pagination_complete_simulee_via_cache(self):
        """Simule la découverte et l'extraction multi-pages sans aucun accès réseau."""
        # Page 1 de recherche en cache (2 offres)
        page1_html = """
        <html><body>
          <div class="pagination-info">1 - 2 de 3 résultats</div>
          <a href="/fr/offre-emploi/dev-python_p1001">Dev Python</a>
          <a href="/fr/offre-emploi/dev-react_p1002">Dev React</a>
        </body></html>
        """
        # Page 2 de recherche en cache (1 offre)
        page2_html = """
        <html><body>
          <div class="pagination-info">3 de 3 résultats</div>
          <a href="/fr/offre-emploi/dev-java_p1003">Dev Java</a>
        </body></html>
        """
        self.scraper.write_cache("search", "category_ti_page_1", page1_html)
        self.scraper.write_cache("search", "category_ti_page_2", page2_html)

        # Fiches détaillées en cache
        def make_job_posting(title, emp, skill):
            return f"""
            <html><head><script type="application/ld+json">
            {{
              "@context": "http://schema.org/",
              "@type": "JobPosting",
              "title": "{title}",
              "datePosted": "2026-11-12",
              "employmentType": "FULL_TIME",
              "hiringOrganization": {{"@type": "Organization", "name": "{emp}"}},
              "jobLocation": {{"@type": "Place", "address": {{"addressLocality": "Montréal", "addressRegion": "QC"}}}},
              "description": "Poste axé sur {skill} en environnement Linux."
            }}
            </script></head><body><h1>{title}</h1></body></html>
            """

        self.scraper.write_cache("details", "detail_1001", make_job_posting("Dev Python", "Ent 1", "Python"))
        self.scraper.write_cache("details", "detail_1002", make_job_posting("Dev React", "Ent 2", "React"))
        self.scraper.write_cache("details", "detail_1003", make_job_posting("Dev Java", "Ent 3", "Java"))

        # Exécution de la collecte sur 2 pages
        collected = self.scraper.search(max_pages=2, use_cache=True)
        self.assertEqual(len(collected), 3)
        self.assertEqual([o.id for o in collected], ["jb-1001", "jb-1002", "jb-1003"])
        self.assertEqual(collected[0].titre, "Dev Python")
        self.assertEqual(collected[1].titre, "Dev React")
        self.assertEqual(collected[2].titre, "Dev Java")
        self.assertIn("Python", collected[0].competences_cles)
        self.assertIn("React", collected[1].competences_cles)
        self.assertIn("Java", collected[2].competences_cles)


class TestJobboomDatasetValidation(unittest.TestCase):
    """Vérifie la conformité et la richesse du jeu d'essai exporté dans data/offres_jobboom.json."""

    def test_jeu_dessai_exporte(self):
        dataset_path = Path(__file__).resolve().parent / "data" / "offres_jobboom.json"
        self.assertTrue(dataset_path.is_file(), "Le fichier data/offres_jobboom.json doit exister.")

        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 5, "Le jeu d'essai doit contenir au moins les offres validées du Lot 3.")

        for item in data:
            offer = JobOffer.model_validate(item)
            self.assertTrue(offer.id.startswith("jb-"), f"L'ID '{offer.id}' doit commencer par 'jb-'")
            self.assertEqual(offer.source, "jobboom")
            self.assertIn(offer.province, ["QC", "ON", "BC", "AB"])
            self.assertTrue(offer.url.startswith("http"))
            self.assertIsInstance(offer.competences_cles, list)


if __name__ == "__main__":
    unittest.main()
