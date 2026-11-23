"""
test_jobboom.py - Tests unitaires hors ligne pour le scraper Jobboom.
Vérifie le parsing des liens de recherche, la conversion JSON-LD et le filtrage strict TI.
"""

import json
import os
import sys
import unittest

# Assurer l'importation locale des modules du dossier jobboom
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)
sys.modules.pop("models", None)
sys.modules.pop("parsers", None)

from models import JobOffer
from parsers import (
    extract_job_links_from_html,
    extract_json_ld_from_detail_html,
    parse_jobboom_json_ld,
    extract_tech_skills,
    detect_modalite,
    is_it_offer
)

SAMPLE_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="job-list">
        <a href="/fr/offre-emploi/developpeur-python_p123456?source=search">Développeur Python</a>
        <a href="/fr/offre-emploi/analyste-qa_p789012">Analyste QA</a>
        <a href="/fr/a-propos">À propos</a>
    </div>
</body>
</html>
"""

SAMPLE_JSON_LD = {
    "@context": "http://schema.org/",
    "@type": "JobPosting",
    "title": "Développeur Full Stack Python / React",
    "datePosted": "2026-11-15",
    "description": "<p>Poste en <strong>télétravail</strong>. Nous recherchons un développeur maîtrisant <em>Python</em>, <em>Docker</em> et <em>React</em>.</p>",
    "hiringOrganization": {
        "@type": "Organization",
        "name": "Solutions Tech Québec"
    },
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Québec",
            "addressRegion": "QC"
        }
    },
    "employmentType": "FULL_TIME"
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
    <h1>Détail du poste</h1>
</body>
</html>
"""


class TestJobboomScraper(unittest.TestCase):

    def test_extract_job_links_from_html(self):
        links = extract_job_links_from_html(SAMPLE_SEARCH_HTML, base_url="https://www.jobboom.com")
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.jobboom.com/fr/offre-emploi/developpeur-python_p123456", links)
        self.assertIn("https://www.jobboom.com/fr/offre-emploi/analyste-qa_p789012", links)

    def test_extract_json_ld_from_detail_html(self):
        extracted = extract_json_ld_from_detail_html(SAMPLE_DETAIL_HTML)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["title"], "Développeur Full Stack Python / React")

    def test_parse_jobboom_json_ld(self):
        url = "https://www.jobboom.com/fr/offre-emploi/developpeur-python_p123456"
        offer = parse_jobboom_json_ld(SAMPLE_JSON_LD, url)

        self.assertIsInstance(offer, JobOffer)
        self.assertEqual(offer.id, "jb-123456")
        self.assertEqual(offer.titre, "Développeur Full Stack Python / React")
        self.assertEqual(offer.entreprise, "Solutions Tech Québec")
        self.assertEqual(offer.lieu, "Québec")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("Docker", offer.competences_cles)
        self.assertIn("React", offer.competences_cles)
        self.assertEqual(offer.source, "Jobboom")

    def test_is_it_offer_rejections(self):
        """Vérifie que les métiers hors-sujet sont fermement rejetés."""
        non_it_titles = [
            "Adjoint chef magasinier",
            "ADJOINT(E) ADMINISTRATIF(VE), GESTION PRIVÉE",
            "Adjointe administrative – Cabinet comptable HL",
            "Assembleur(euse)",
            "Assembleur(se) recherché(e) – quart de jour",
            "Associé, service à la clientele",
            "Associé Spécialisé Pro",
            "Associe, ventes et service a la clientele",
            "Caissier(ère) - En Milieu Bancaire -",
            "Chargé(e) de projet en ventilation",
            "Commis à la plomberie",
            "Manoeuvre en usine",
            "Électromécanicien industriel"
        ]
        for titre in non_it_titles:
            self.assertFalse(is_it_offer(titre), f"Le poste '{titre}' n'aurait pas dû être validé comme TI")

    def test_is_it_offer_approvals(self):
        """Vérifie que les métiers informatiques sont correctement validés."""
        it_titles = [
            "Développeur Full Stack Python / React",
            "Administrateur des systèmes et de l'infrastructure informatique",
            "Administrateur Système Linux",
            "Analyste ECM",
            "Analyste Support Dynamics",
            "Analyste systèmes et intégration de données",
            "Architecte infrastructure senior",
            "Ingénieur DevOps et intégration infonuagique",
            "Spécialiste en réseaux",
            "Soutien technique",
            "Chef.fe d'équipe TI",
            "Programmeur-analyste C# .NET"
        ]
        for titre in it_titles:
            self.assertTrue(is_it_offer(titre), f"Le poste '{titre}' aurait dû être validé comme TI")


if __name__ == "__main__":
    unittest.main()
