"""
test_jobillico.py - Tests unitaires hors ligne pour le scraper Jobillico.
Vérifie l'extraction des liens de recherche et la conversion du bloc JSON-LD en JobOffer.
"""

import json
import os
import sys
import unittest

# Assurer l'importation locale des modules du dossier jobillico
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)
sys.modules.pop("models", None)
sys.modules.pop("parsers", None)

from models import JobOffer
from parsers import (
    extract_job_links_from_html,
    extract_json_ld_from_detail_html,
    parse_jobillico_json_ld
)

SAMPLE_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="result-list">
        <a href="/fr/offre-emploi/analyste-programmeur-java/1029384?ref=search">Analyste Programmeur Java</a>
        <div data-href="/fr/offre-emploi/technicien-support-ti/5049382">Technicien Support</div>
        <a href="/fr/entreprises/index">Entreprises</a>
    </div>
</body>
</html>
"""

SAMPLE_JSON_LD = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Analyste Programmeur Java / Spring",
    "datePosted": "2026-11-12",
    "description": "<p>Poste situé à <strong>Québec</strong> en mode <strong>hybride</strong>. Maîtrise de <em>Java</em>, <em>Spring</em> et <em>SQL</em> requise.</p>",
    "hiringOrganization": {
        "@type": "Organization",
        "name": "Solutions TI Québec"
    },
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Québec",
            "addressRegion": "QC"
        }
    },
    "employmentType": "FULL_TIME",
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "CAD",
        "value": {
            "@type": "QuantitativeValue",
            "minValue": 65000,
            "maxValue": 85000
        }
    }
}

SAMPLE_DETAIL_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {json.dumps(SAMPLE_JSON_LD)}
    </script>
</head>
<body>
    <h1>Offre Jobillico</h1>
</body>
</html>
"""


class TestJobillicoScraper(unittest.TestCase):

    def test_extract_job_links_from_html(self):
        links = extract_job_links_from_html(SAMPLE_SEARCH_HTML, base_url="https://www.jobillico.com")
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.jobillico.com/fr/offre-emploi/analyste-programmeur-java/1029384", links)
        self.assertIn("https://www.jobillico.com/fr/offre-emploi/technicien-support-ti/5049382", links)

    def test_extract_json_ld_from_detail_html(self):
        extracted = extract_json_ld_from_detail_html(SAMPLE_DETAIL_HTML)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["title"], "Analyste Programmeur Java / Spring")

    def test_parse_jobillico_json_ld(self):
        url = "https://www.jobillico.com/fr/offre-emploi/analyste-programmeur-java/1029384"
        offer = parse_jobillico_json_ld(SAMPLE_JSON_LD, url)

        self.assertIsInstance(offer, JobOffer)
        self.assertEqual(offer.id, "ji-1029384")
        self.assertEqual(offer.titre, "Analyste Programmeur Java / Spring")
        self.assertEqual(offer.entreprise, "Solutions TI Québec")
        self.assertEqual(offer.lieu, "Québec")
        self.assertEqual(offer.modalite, "Hybride")
        self.assertIn("Java", offer.competences_cles)
        self.assertIn("Spring", offer.competences_cles)
        self.assertIn("SQL", offer.competences_cles)
        self.assertEqual(offer.source, "Jobillico")
        self.assertEqual(offer.salaire, "65000 - 85000 CAD")


if __name__ == "__main__":
    unittest.main()
