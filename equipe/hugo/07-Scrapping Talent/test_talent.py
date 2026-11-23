"""
test_talent.py - Tests unitaires hors ligne pour le scraper Talent.com Canada.
Vérifie l'extraction des URLs de recherche, le parsing des JobPosting JSON-LD,
le formatage des salaires et le filtrage strict TI sans aucun appel réseau.
"""

import json
import os
import sys
import unittest

# Assurer l'importation locale des modules du dossier talent
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)
sys.modules.pop("models", None)
sys.modules.pop("parsers", None)

from models import JobOffer
from parsers import (
    extract_job_urls_from_search_html,
    extract_json_ld_job_posting_from_detail_html,
    parse_talent_job_posting,
    format_salary,
    is_it_offer,
    matches_keyword
)

SAMPLE_SEARCH_JSON_LD = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "ItemList",
            "@id": "#jobList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "WebPage",
                        "url": "https://ca.talent.com/fr/view?id=634537925073176368"
                    }
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "item": {
                        "@type": "WebPage",
                        "url": "https://ca.talent.com/fr/view?id=640918690502021004"
                    }
                }
            ]
        }
    ]
}

SAMPLE_SEARCH_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {json.dumps(SAMPLE_SEARCH_JSON_LD)}
    </script>
</head>
<body>
    <div class="jobs">
        <a href="/fr/view?id=634537925073176368">Offre 1</a>
        <a href="/fr/view?id=640918690502021004">Offre 2</a>
        <a href="/fr/view?id=999999999999999999">Offre HTML seule</a>
        <a href="/fr/contact">Contact</a>
    </div>
</body>
</html>
"""

SAMPLE_DETAIL_JOB_POSTING = {
    "@type": "JobPosting",
    "title": "Analyste en informatique",
    "hiringOrganization": {
        "@type": "Organization",
        "name": "CHU de Québec - Université Laval"
    },
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Québec City",
            "addressRegion": "Quebec",
            "addressCountry": "ca"
        }
    },
    "datePosted": "2026-10-10",
    "employmentType": "FULL_TIME",
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "CAD",
        "value": {
            "@type": "QuantitativeValue",
            "minValue": 30.59,
            "maxValue": 52.43,
            "unitText": "HOUR"
        }
    },
    "description": "<p>Poste en <strong>télétravail hybride</strong>. Environnements <em>Linux</em>, <em>Python</em>, <em>SQL</em> et <em>Azure</em>.</p>"
}

SAMPLE_DETAIL_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@graph": [
            {json.dumps(SAMPLE_DETAIL_JOB_POSTING)}
        ]
    }}
    </script>
</head>
<body>
    <h1>Détail offre</h1>
</body>
</html>
"""


class TestTalentScraper(unittest.TestCase):

    def test_extract_job_urls_from_search_html(self):
        urls = extract_job_urls_from_search_html(SAMPLE_SEARCH_HTML, base_url="https://ca.talent.com")
        self.assertEqual(len(urls), 3)
        self.assertIn("https://ca.talent.com/fr/view?id=634537925073176368", urls)
        self.assertIn("https://ca.talent.com/fr/view?id=640918690502021004", urls)
        self.assertIn("https://ca.talent.com/fr/view?id=999999999999999999", urls)

    def test_extract_json_ld_job_posting_from_detail_html(self):
        posting = extract_json_ld_job_posting_from_detail_html(SAMPLE_DETAIL_HTML)
        self.assertIsNotNone(posting)
        self.assertEqual(posting.get("title"), "Analyste en informatique")

    def test_parse_talent_job_posting(self):
        url = "https://ca.talent.com/fr/view?id=640918690502021004"
        offer = parse_talent_job_posting(SAMPLE_DETAIL_JOB_POSTING, url_source=url)

        self.assertIsInstance(offer, JobOffer)
        self.assertEqual(offer.id, "tal-640918690502021004")
        self.assertEqual(offer.titre, "Analyste en informatique")
        self.assertEqual(offer.entreprise, "CHU de Québec - Université Laval")
        self.assertEqual(offer.lieu, "Québec City")
        self.assertEqual(offer.province, "Quebec")
        self.assertEqual(offer.salaire, "30.59 $ - 52.43 $ CAD / heure")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertEqual(offer.type_poste, "Temps plein")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("Linux", offer.competences_cles)
        self.assertIn("SQL", offer.competences_cles)
        self.assertIn("Azure", offer.competences_cles)
        self.assertEqual(offer.source, "Talent.com")

    def test_format_salary(self):
        # 1. Taux horaire variable
        sal1 = {
            "currency": "CAD",
            "value": {"minValue": 25.0, "maxValue": 35.0, "unitText": "HOUR"}
        }
        self.assertEqual(format_salary(sal1), "25.0 $ - 35.0 $ CAD / heure")

        # 2. Salaire annuel fixe
        sal2 = {
            "currency": "CAD",
            "value": 75000
        }
        self.assertEqual(format_salary(sal2), "75000 $ CAD")

        # 3. Non spécifié
        self.assertEqual(format_salary(None), "Non spécifié")

    def test_is_it_offer_rejections(self):
        """Vérifie que les métiers non-TI sont rejetés."""
        non_it = [
            "Commis aux pièces et inventaire",
            "Adjoint(e) administratif(ve) - Clinique",
            "Caissier / Caissière de jour",
            "Magasinier cariste",
            "Chauffeur livreur classe 3",
            "Plombier de maintenance",
            "Agent de sécurité de nuit"
        ]
        for titre in non_it:
            self.assertFalse(is_it_offer(titre), f"Le poste '{titre}' n'aurait pas dû être accepté.")

    def test_is_it_offer_approvals(self):
        """Vérifie que les postes informatiques sont validés."""
        it_jobs = [
            "Analyste en informatique",
            "Technicien(ne) informatique",
            "Technicien réseau, support aux technologies opérationnelles",
            "Développeur Web Full-Stack Python",
            "Administrateur système Linux / Cloud",
            "Analyste-programmeur C# .NET",
            "Ingénieur DevOps",
            "Spécialiste en cybersécurité"
        ]
        for titre in it_jobs:
            self.assertTrue(is_it_offer(titre), f"Le poste '{titre}' aurait dû être validé.")


if __name__ == "__main__":
    unittest.main()
