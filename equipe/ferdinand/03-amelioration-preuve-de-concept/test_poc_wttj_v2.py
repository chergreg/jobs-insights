"""Tests hors ligne (aucun appel réseau) pour poc_wttj_v2.py.

Lancer :
    python -m unittest test_poc_wttj_v2.py -v
"""

import json
import unittest
from pathlib import Path

from poc_wttj_v2 import dedupliquer, extraire_bureaux, normaliser

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reponse_api_exemple.json"


class TestPocWttj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as f:
            cls.offres = json.load(f)["data"]

    def test_offre_avec_bureau_a_montreal_est_au_canada(self):
        ligne = normaliser(self.offres[0])
        self.assertEqual(ligne["villes"], "Montreal, Paris")
        self.assertEqual(ligne["pays"], "CA, FR")
        self.assertTrue(ligne["au_canada"])

    def test_offre_en_france_seulement_n_est_pas_au_canada(self):
        ligne = normaliser(self.offres[1])
        self.assertEqual(ligne["villes"], "Lyon")
        self.assertFalse(ligne["au_canada"])

    def test_lien_construit_depuis_les_slugs(self):
        ligne = normaliser(self.offres[1])
        self.assertEqual(
            ligne["lien"],
            "https://www.welcometothejungle.com/fr/companies/"
            "entreprise-exemple/jobs/developpeur-python-junior_EXEMPLE_abc",
        )

    def test_champs_absents_restent_vides(self):
        ligne = normaliser(self.offres[2])
        self.assertIsNone(ligne["entreprise"])
        self.assertIsNone(ligne["villes"])
        self.assertIsNone(ligne["lien"])
        self.assertFalse(ligne["au_canada"])

    def test_office_utilise_si_offices_absent(self):
        bureaux = extraire_bureaux({"office": {"city": "Laval", "country_code": "CA"}})
        self.assertEqual(bureaux, [{"city": "Laval", "country_code": "CA"}])

    def test_dedupliquer_garde_l_ordre(self):
        lignes = [normaliser(o) for o in self.offres]
        resultat = dedupliquer(lignes + [lignes[0]])
        self.assertEqual(len(resultat), 3)
        self.assertEqual(resultat[0]["id_source"], lignes[0]["id_source"])


if __name__ == "__main__":
    unittest.main()
