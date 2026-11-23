"""Tests hors ligne de convertir.py.  Lancer depuis equipe/dan/format-commun :
    python -m unittest test_convertir -v
"""

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import convertir

MODELE_DU_PROF = Path(__file__).resolve().parents[2] / "gregory" / "livrable3" / "models.py"

GUICHET = {
    "id": "ge-1", "source": "guichet-emplois", "titre": "technicien/technicienne en informatique",
    "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/1", "source_partenaire": "Québec emploi",
    "entreprise": "Université du Québec", "lieu": "Québec (QC)", "province": "QC", "latitude": None,
    "longitude": None, "date_publication": "2026-11-16", "type_poste": "Permanent, Temps plein",
    "modalite": "Sur place", "est_stage": None, "salaire": "30 $ de l'heure",
    "description": "Soutien Windows et Microsoft 365.", "competences": [], "doublons": ["ge-2"],
}
JOBBOOM_SANS_FICHE = {
    "id": "jb-9", "source": "jobboom", "titre": "Développeur Web", "url": "https://www.jobboom.com/x_p9",
    "source_partenaire": None, "entreprise": None, "lieu": None, "province": None, "latitude": None,
    "longitude": None, "date_publication": None, "type_poste": None, "modalite": None, "est_stage": None,
    "salaire": None, "description": None, "competences": [], "doublons": [],
}
DOCUMENT = {"date_export": "2026-11-18T16:14:02+00:00", "nombre": 2, "offres": [GUICHET, JOBBOOM_SANS_FICHE]}


class TestConvertir(unittest.TestCase):
    def setUp(self):
        self.ge, self.jb = convertir.convertir(DOCUMENT)

    def test_dix_huit_champs_dans_l_ordre_du_modele(self):
        self.assertEqual(list(self.ge), convertir.CHAMPS)
        self.assertEqual(len(convertir.CHAMPS), 18)
        self.assertNotIn("doublons", self.ge)
        self.assertNotIn("latitude", self.ge)

    def test_valeurs_reprises(self):
        self.assertEqual(self.ge["entreprise"], "Université du Québec")
        self.assertEqual(self.ge["source_partenaire"], "Québec emploi")
        self.assertEqual(self.ge["type_poste"], "Permanent, Temps plein")
        self.assertEqual(self.ge["date_extraction"], "2026-11-18T16:14:02+00:00")

    def test_rien_n_est_devine(self):
        self.assertEqual(self.jb["entreprise"], "Non spécifié")
        self.assertEqual(self.jb["lieu"], "Non spécifié")
        self.assertEqual(self.jb["province"], "Non spécifié")      # pas « QC » par défaut
        self.assertEqual(self.jb["pays"], "Non spécifié")
        self.assertIsNone(self.jb["type_poste"])                    # pas « Temps plein » par défaut
        self.assertIsNone(self.jb["description"])

    def test_pays_deduit_de_la_province(self):
        self.assertEqual(self.ge["pays"], "Canada")

    def test_province_mal_ecrite_nettoyee(self):
        offre = convertir.convertir_offre(dict(GUICHET, province=", QC"), "")
        self.assertEqual((offre["province"], offre["pays"]), ("QC", "Canada"))
        offre = convertir.convertir_offre(dict(GUICHET, province="Différentes régions"), "")
        self.assertEqual((offre["province"], offre["pays"]), ("Non spécifié", "Non spécifié"))

    def test_competences_detectees_si_absentes(self):
        self.assertEqual(self.ge["competences_cles"], ["Microsoft 365", "Windows"])
        self.assertEqual(self.jb["competences_cles"], [])
        deja = convertir.convertir_offre(dict(GUICHET, competences=["SQL"]), "")
        self.assertEqual(deja["competences_cles"], ["SQL"])         # celles de main.py sont gardées

    def test_statut_stage(self):
        self.assertEqual((self.ge["est_stage"], self.ge["statut_stage"]), (False, "not_indicated"))
        stage = convertir.convertir_offre(dict(GUICHET, titre="Stagiaire TI"), "")
        self.assertEqual((stage["est_stage"], stage["statut_stage"]), (True, "confirmed_stage"))
        possible = convertir.convertir_offre(dict(GUICHET, description="Statut : stage rémunéré"), "")
        self.assertEqual((possible["est_stage"], possible["statut_stage"]), (True, "possible_stage"))

    def test_fichier_inattendu(self):
        with self.assertRaises(ValueError):
            convertir.convertir([{"id": "x"}])

    @unittest.skipUnless(MODELE_DU_PROF.exists(), "modèle du prof absent")
    def test_valide_par_le_modele_joboffer_du_prof(self):
        try:
            import pydantic  # noqa: F401
        except ImportError:
            self.skipTest("pydantic non installé")
        sys.path.insert(0, str(MODELE_DU_PROF.parent))
        try:
            from models import JobOffer
        finally:
            sys.path.remove(str(MODELE_DU_PROF.parent))
        for offre in (self.ge, self.jb):
            valide = JobOffer(**offre).model_dump()
            self.assertEqual(valide, offre)                          # aucun défaut du modèle ajouté

    def test_main_json_csv_echantillon(self):
        with tempfile.TemporaryDirectory() as dossier:
            entree = Path(dossier) / "offres_unifiees.json"
            entree.write_text(json.dumps(DOCUMENT), encoding="utf-8")
            sortie = Path(dossier) / "offres_format_commun.json"
            console = StringIO()
            with redirect_stdout(console):
                convertir.main(["--entree", str(entree), "--sortie", str(sortie), "--csv", "--echantillon", "1"])
            self.assertEqual(len(json.loads(sortie.read_text(encoding="utf-8"))), 2)
            self.assertEqual(len(json.loads((Path(dossier) / "echantillon_format_commun.json").read_text(encoding="utf-8"))), 1)
            csv_texte = sortie.with_suffix(".csv").read_text(encoding="utf-8-sig")
            self.assertIn("Microsoft 365, Windows", csv_texte)
            self.assertIn("2 offres converties : 1 avec compétences", console.getvalue())


if __name__ == "__main__":
    unittest.main()
