"""
test_remotive.py - Tests unitaires hors ligne pour le scraper Remotive API.
Vérifie la conversion du payload API JSON en JobOffer et le filtre d'éligibilité Canada.
"""

import os
import sys
import unittest

# Assurer l'importation locale des modules du dossier remotive
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)
sys.modules.pop("models", None)
sys.modules.pop("parsers", None)

from models import JobOffer
from parsers import is_canada_eligible, parse_remotive_job, extract_tech_skills

SAMPLE_JOB_PAYLOAD = {
    "id": 1928374,
    "url": "https://remotive.com/remote-jobs/software-dev/senior-python-developer-1928374",
    "title": "Senior Python Backend Developer",
    "company_name": "CloudTech Global",
    "category": "software-dev",
    "tags": ["python", "django", "aws", "docker"],
    "job_type": "full_time",
    "publication_date": "2026-11-14T12:00:00",
    "candidate_required_location": "Canada or USA",
    "salary": "95,000 $ - 120,000 $ CAD",
    "description": "<p>We are seeking a <strong>Python</strong> engineer experienced with <em>Django</em>, <em>Docker</em> and <em>AWS</em>.</p>"
}

SAMPLE_JOB_NOT_CANADA = {
    "id": 1111111,
    "title": "React Developer",
    "candidate_required_location": "UK, Germany only",
    "description": "European timezone only."
}


class TestRemotiveScraper(unittest.TestCase):

    def test_is_canada_eligible(self):
        self.assertTrue(is_canada_eligible(SAMPLE_JOB_PAYLOAD))
        self.assertFalse(is_canada_eligible(SAMPLE_JOB_NOT_CANADA))
        self.assertTrue(is_canada_eligible({"candidate_required_location": "Worldwide"}))
        self.assertTrue(is_canada_eligible({"candidate_required_location": "North America"}))

    def test_parse_remotive_job(self):
        offer = parse_remotive_job(SAMPLE_JOB_PAYLOAD)

        self.assertIsInstance(offer, JobOffer)
        self.assertEqual(offer.id, "rem-1928374")
        self.assertEqual(offer.titre, "Senior Python Backend Developer")
        self.assertEqual(offer.entreprise, "CloudTech Global")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertEqual(offer.type_poste, "Temps plein")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("AWS", offer.competences_cles)
        self.assertIn("Docker", offer.competences_cles)
        self.assertEqual(offer.source, "Remotive")
        self.assertEqual(offer.methode_extraction, "REST-API")


if __name__ == "__main__":
    unittest.main()
