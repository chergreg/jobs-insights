"""
test_top3.py - Tests unitaires hors ligne pour le pipeline TOP 3.
Vérifie la déduplication, la fusion multi-sources et la génération de statistiques.
"""

import os
import sys
import unittest

DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)

from models import JobOffer
from collecte_top3 import PipelineTop3


class TestPipelineTop3(unittest.TestCase):

    def setUp(self):
        self.pipeline = PipelineTop3()

        self.offre_1 = JobOffer(
            id="gc-101",
            titre="Développeur Python Full Stack",
            entreprise="CGI Inc.",
            lieu="Montréal (QC)",
            province="QC",
            modalite="Hybride",
            competences_cles=["Python", "React", "Docker"],
            description="Poste de développeur à Montréal.",
            url_source="https://www.guichetemplois.gc.ca/offre/101",
            source="Guichet-Emplois"
        )

        # Doublon identique (provenant d'un autre site avec URL différente mais même signature)
        self.offre_doublon_signature = JobOffer(
            id="jb-202",
            titre="Développeur Python Full-Stack",
            entreprise="CGI",
            lieu="Montréal",
            province="QC",
            modalite="Hybride",
            competences_cles=["Python"],
            description="Description courte.",
            url_source="https://www.jobboom.com/fr/offre-emploi/developpeur-cgi_p202",
            source="Jobboom"
        )

        # Doublon par URL
        self.offre_doublon_url = JobOffer(
            id="gc-101-bis",
            titre="Autre titre",
            entreprise="Autre",
            url_source="https://www.guichetemplois.gc.ca/offre/101?source=feed",
            source="Guichet-Emplois"
        )

        # Offre distincte
        self.offre_remotive = JobOffer(
            id="rem-303",
            titre="Backend Go Engineer",
            entreprise="Shopify",
            lieu="Télétravail (Canada)",
            province="Télétravail",
            modalite="Télétravail",
            competences_cles=["Go", "Kubernetes", "AWS"],
            description="100% remote software developer.",
            url_source="https://remotive.com/job/303",
            source="Remotive"
        )

    def test_cle_deduplication(self):
        cle1 = self.offre_1.cle_deduplication()
        cle2 = self.offre_doublon_signature.cle_deduplication()
        self.assertEqual(cle1, cle2, "Les signatures normalisées doivent concorder malgré les tirets et 'Inc.'")

    def test_deduplication_pipeline(self):
        toutes = [self.offre_1, self.offre_doublon_signature, self.offre_doublon_url, self.offre_remotive]
        uniques, nb_doublons = self.pipeline.dedupliquer_offres(toutes)

        self.assertEqual(len(uniques), 2, "Il ne doit rester que 2 offres uniques distinctes.")
        self.assertEqual(nb_doublons, 2, "2 doublons doivent avoir été rejetés.")

        ids = [o.id for o in uniques]
        self.assertIn("gc-101", ids)
        self.assertIn("rem-303", ids)

    def test_statistiques(self):
        offres = [self.offre_1, self.offre_remotive]
        stats = self.pipeline.generer_statistiques(offres)

        self.assertEqual(stats["total_offres"], 2)
        self.assertEqual(stats["repartition_sources"]["Guichet-Emplois"], 1)
        self.assertEqual(stats["repartition_sources"]["Remotive"], 1)
        self.assertEqual(stats["repartition_modalites"]["Hybride"], 1)
        self.assertEqual(stats["repartition_modalites"]["Télétravail"], 1)
        self.assertIn("Python", stats["top_10_competences"])
        self.assertIn("Go", stats["top_10_competences"])


if __name__ == "__main__":
    unittest.main()
