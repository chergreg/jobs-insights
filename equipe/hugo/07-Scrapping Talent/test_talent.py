"""
test_talent.py - Tests unitaires hors ligne pour le scraper Talent.com Canada.
Vérifie l'extraction des structures JSON-LD @graph et la conversion en JobOffer sans appel réseau.
"""

import json
import os
import sys
import unittest

# Assurer l'importation locale des modules du dossier talent.com
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)
sys.modules.pop("models", None)
sys.modules.pop("parsers", None)

from models import JobOffer
from parsers import (
    extract_json_ld_job_postings_from_html,
    parse_talent_job_posting
)

SAMPLE_TALENT_JSON_LD = {
    "@context": "http://schema.org",
    "@graph": [
        {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "JobPosting",
                        "title": "Développeur Web Full-Stack",
                        "url": "https://ca.talent.com/fr/view?id=8392019",
                        "datePosted": "2026-11-10",
                        "description": "Poste en <strong>télétravail</strong> avec <em>TypeScript</em>, <em>Node.js</em> et <em>PostgreSQL</em>.",
                        "hiringOrganization": {
                            "@type": "Organization",
                            "name": "Agence Numérique QC"
                        },
                        "jobLocation": {
                            "@type": "Place",
                            "address": {
                                "@type": "PostalAddress",
                                "addressLocality": "Montréal",
                                "addressRegion": "QC"
                            }
                        },
                        "employmentType": "FULL_TIME"
                    }
                }
            ]
        }
    ]
}

SAMPLE_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {json.dumps(SAMPLE_TALENT_JSON_LD)}
    </script>
</head>
<body>
    <h1>Résultats Talent.com</h1>
</body>
</html>
"""


class TestTalentScraper(unittest.TestCase):

    def test_extract_json_ld_job_postings_from_html(self):
        postings = extract_json_ld_job_postings_from_html(SAMPLE_HTML)
        self.assertEqual(len(postings), 1)
        self.assertEqual(postings[0]["title"], "Développeur Web Full-Stack")

    def test_parse_talent_job_posting(self):
        postings = extract_json_ld_job_postings_from_html(SAMPLE_HTML)
        offer = parse_talent_job_posting(postings[0])

        self.assertIsInstance(offer, JobOffer)
        self.assertEqual(offer.id, "tal-8392019")
        self.assertEqual(offer.titre, "Développeur Web Full-Stack")
        self.assertEqual(offer.entreprise, "Agence Numérique QC")
        self.assertEqual(offer.lieu, "Montréal")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertIn("TypeScript", offer.competences_cles)
        self.assertIn("Node.js", offer.competences_cles)
        self.assertIn("PostgreSQL", offer.competences_cles)
        self.assertEqual(offer.source, "Talent.com")


if __name__ == "__main__":
    unittest.main()
