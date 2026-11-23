"""Tests hors ligne de modele.py (dataclass Offre et exports JSON / CSV)."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from modele import CHAMPS, Offre, exporter_csv, exporter_json, lire_json


def offre_complete():
    return Offre(
        id="ge-50738681", source="guichet-emplois",
        titre="développeur Web/développeuse Web",
        url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50738681",
        source_partenaire="Jobillico", entreprise="Mewlogic Inc.", lieu="Vaudreuil-Dorion (QC)",
        province="QC", latitude=45.4, longitude=-74.03, date_publication="2026-11-16",
        type_poste="Temps plein", modalite="Hybride", est_stage=False,
        salaire="43,27 $ de l'heure", description="Tâches ; développer", competences=["Python", "SQL"],
    )


class TestOffre(unittest.TestCase):
    def test_champs_facultatifs_none_par_defaut(self):
        offre = Offre(id="jb-1", source="jobboom", titre="Stagiaire", url="https://x/1")
        self.assertIsNone(offre.entreprise)
        self.assertIsNone(offre.est_stage)
        self.assertEqual(offre.competences, [])

    def test_listes_non_partagees_entre_offres(self):
        a = Offre(id="a", source="s", titre="t", url="u")
        b = Offre(id="b", source="s", titre="t", url="u")
        a.competences.append("Java")
        self.assertEqual(b.competences, [])


class TestExports(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        self.offres = [offre_complete(), Offre(id="tc-2", source="talent", titre="Stage TI", url="https://x/2")]

    def tearDown(self):
        self.dossier.cleanup()

    def test_json_aller_retour_et_accents(self):
        chemin = exporter_json(self.offres, self.racine / "data" / "offres.json")
        texte = chemin.read_text(encoding="utf-8")
        self.assertIn("développeur", texte)                     # accents lisibles, pas é
        self.assertEqual(json.loads(texte)["nombre"], 2)
        self.assertEqual(lire_json(chemin), self.offres)

    def test_csv_excel_bom_et_point_virgule(self):
        chemin = exporter_csv(self.offres, self.racine / "offres.csv")
        self.assertTrue(chemin.read_bytes().startswith(b"\xef\xbb\xbf"))   # BOM utf-8-sig
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lignes = list(csv.reader(f, delimiter=";"))
        self.assertEqual(lignes[0], CHAMPS)
        ligne = dict(zip(CHAMPS, lignes[1]))
        self.assertEqual(ligne["competences"], "Python, SQL")
        self.assertEqual(ligne["est_stage"], "non")
        self.assertEqual(ligne["description"], "Tâches ; développer")  # « ; » protégé par des guillemets
        vide = dict(zip(CHAMPS, lignes[2]))
        self.assertEqual(vide["entreprise"], "")                # None → cellule vide
        self.assertEqual(vide["est_stage"], "")


if __name__ == "__main__":
    unittest.main()
