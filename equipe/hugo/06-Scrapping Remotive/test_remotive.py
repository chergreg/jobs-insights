"""
test_remotive.py - Tests unitaires hors ligne pour le scraper Remotive API.
Vérifie la conversion du payload API JSON en JobOffer, le filtre d'éligibilité Canada,
la validation stricte TI et la recherche par mot-clé bilingue.
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
from parsers import (
    is_canada_eligible,
    parse_remotive_job,
    extract_tech_skills,
    is_it_offer,
    matches_keyword
)

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

    def test_is_it_offer_rejections(self):
        """Vérifie que les offres non-TI retournées par Remotive sont bien rejetées."""
        non_it_titles = [
            "Content Reviewer - Online Media",
            "Customer Support Specialist (Remote)",
            "Inside Sales Contractor",
            "Freelance Copywriter & Content Creator",
            "Virtual Assistant / Office Support",
            "Data Entry Clerk",
            "Telemarketing Agent",
            "Patient Care Coordinator"
        ]
        for titre in non_it_titles:
            self.assertFalse(is_it_offer(titre), f"Le poste '{titre}' n'aurait pas dû être accepté comme TI")

    def test_is_it_offer_approvals(self):
        """Vérifie que les postes informatiques / TI sont bien validés."""
        it_titles = [
            "Senior Python Backend Developer",
            "Full Stack Software Engineer",
            "DevOps and Cloud Infrastructure Specialist",
            "QA Automation Test Engineer",
            "Data Analyst & BI Specialist",
            "Cybersecurity Specialist",
            "Mobile iOS / Android Developer",
            "Junior Web Programmer"
        ]
        for titre in it_titles:
            self.assertTrue(is_it_offer(titre), f"Le poste '{titre}' aurait dû être accepté comme TI")

    def test_matches_keyword_bilingual(self):
        """Vérifie le mapping d'équivalence bilingue français / anglais."""
        titre = "Senior Python Developer"
        desc = "Software development in cloud environment"
        tags = ["python", "aws"]

        # 'programmeur' doit matcher 'developer'
        self.assertTrue(matches_keyword(titre, desc, tags, "programmeur"))
        # 'developpeur' doit matcher 'developer'
        self.assertTrue(matches_keyword(titre, desc, tags, "developpeur"))
        # 'logiciel' doit matcher 'software'
        self.assertTrue(matches_keyword(titre, desc, tags, "logiciel"))
        # 'python' doit matcher le tag
        self.assertTrue(matches_keyword(titre, desc, tags, "python"))
        # Mot-clé inexistant
        self.assertFalse(matches_keyword(titre, desc, tags, "comptable"))


if __name__ == "__main__":
    unittest.main()
