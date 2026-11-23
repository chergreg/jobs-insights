"""Tests hors ligne (aucun appel réseau) pour convertir.py.

Lancer depuis ce dossier :
    python -m unittest -v test_convertir.py
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from convertir import (CHAMPS, NON_SPECIFIE, convertir, convertir_offre,
                       lieu_province_pays, salaire, statut_stage)

DOSSIER = Path(__file__).resolve().parent
FIXTURE = DOSSIER / "fixtures" / "reponse_api_exemple.json"
MODELE_GREGORY = DOSSIER.parents[1] / "gregory" / "livrable3" / "models.py"
DATE = "2026-11-23T12:00:00+00:00"


def charger_offres() -> list[dict]:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)["data"]


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.offres = charger_offres()
        self.vona = convertir_offre(self.offres[0], DATE)

    def test_tous_les_champs_du_format_commun(self):
        self.assertEqual(list(self.vona), CHAMPS)

    def test_identifiant_et_source(self):
        self.assertEqual(self.vona["id"], "wttj-33e7a622-7ec4-4434-b386-7151ae990688")
        self.assertEqual(self.vona["source"], "welcome-to-the-jungle")

    def test_bureau_canadien_prioritaire(self):
        # VONA a des bureaux à Paris et à Montréal : on garde Montréal.
        self.assertEqual(self.vona["lieu"], "Montreal")
        self.assertEqual(self.vona["province"], "QC")
        self.assertEqual(self.vona["pays"], "Canada")

    def test_stage_confirme(self):
        self.assertEqual(self.vona["type_poste"], "Stage")
        self.assertTrue(self.vona["est_stage"])
        self.assertEqual(self.vona["statut_stage"], "confirmed_stage")

    def test_salaire_et_date(self):
        self.assertEqual(self.vona["salaire"], "jusqu'à 1500 EUR par mois")
        self.assertEqual(self.vona["date_publication"], "2026-09-21")

    def test_offre_en_france(self):
        lyon = convertir_offre(self.offres[1], DATE)
        self.assertEqual(lyon["pays"], "France")
        self.assertEqual(lyon["province"], NON_SPECIFIE)
        self.assertEqual(lyon["type_poste"], "Temps plein")
        self.assertEqual(lyon["modalite"], "Hybride")
        self.assertIsNone(lyon["salaire"])

    def test_offre_incomplete_ignoree(self):
        # Pas d'URL possible : le modèle commun exige une URL.
        self.assertIsNone(convertir_offre(self.offres[2], DATE))

    def test_convertir_garde_le_canada_sans_doublon(self):
        offres = convertir(self.offres + [self.offres[0]], DATE)
        self.assertEqual([o["id"] for o in offres], [self.vona["id"]])

    def test_convertir_partout(self):
        offres = convertir(self.offres, DATE, canada_seulement=False)
        self.assertEqual(len(offres), 2)


class PetitesFonctionsTests(unittest.TestCase):
    def test_ville_canadienne_hors_liste_sans_province(self):
        offre = {"offices": [{"city": "Toronto", "country_code": "CA"}]}
        self.assertEqual(lieu_province_pays(offre), ("Toronto", NON_SPECIFIE, "Canada"))

    def test_sans_bureau(self):
        self.assertEqual(lieu_province_pays({}), (NON_SPECIFIE,) * 3)

    def test_stage_possible_dans_le_titre(self):
        self.assertEqual(statut_stage({"name": "Fintech Intern", "contract_type": "full_time"}),
                         "possible_stage")
        self.assertEqual(statut_stage({"name": "Développeur Python"}), "not_indicated")

    def test_salaire_fourchette(self):
        offre = {"salary_min": 50000, "salary_max": 60000,
                 "salary_currency": "CAD", "salary_period": "yearly"}
        self.assertEqual(salaire(offre), "50000 à 60000 CAD par an")


@unittest.skipUnless(importlib.util.find_spec("pydantic") and MODELE_GREGORY.exists(),
                     "pydantic ou le models.py de Gregory est absent")
class ModeleDeGregoryTests(unittest.TestCase):
    """Vérifie que mes offres sont acceptées par le modèle JobOffer de Gregory."""

    def test_offres_acceptees_par_jobOffer(self):
        spec = importlib.util.spec_from_file_location("modele_gregory", MODELE_GREGORY)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # nécessaire pour que Pydantic résolve les annotations
        spec.loader.exec_module(module)
        for offre in convertir(charger_offres(), DATE, canada_seulement=False):
            modele = module.JobOffer(**offre)
            # Le modèle ne doit pas remplacer nos valeurs par ses valeurs par défaut.
            self.assertEqual(modele.province, offre["province"])
            self.assertEqual(modele.type_poste, offre["type_poste"])


if __name__ == "__main__":
    unittest.main()
