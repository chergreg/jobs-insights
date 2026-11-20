"""Tests hors ligne du convertisseur vers le format commun.

Le dernier test valide les offres avec le modèle JobOffer de Gregory (lu sans
rien modifier dans son dossier). Il est sauté si Pydantic n'est pas installé.
"""

import csv
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from convertir import CHAMPS, NON_SPECIFIE, convertir, convertir_offre, ecrire_csv, main, type_poste


def offre(**changements):
    """Une offre comme dans offres.json (seulement les champs utiles)."""
    valeurs = {
        "title": "développeur Web/développeuse Web",
        "original_title": "Développeur full-stack",
        "employer": "Exemple inc.",
        "location": "Québec (QC)",
        "province": "QC",
        "published_at": "2026-11-20",
        "job_type": "Permanent, Temps plein",
        "work_mode": "Hybride",
        "stage_status": "not_indicated",
        "description": "Développer des applications Web.",
        "technologies": ["Python", "SQL"],
        "skills": ["Développement Web"],
        "salary": "30,00 $ de l'heure",
        "source_records": [{"source": "Guichet-Emplois", "source_id": "50585958",
                            "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50585958",
                            "origin_site": "Jobillico"}],
    }
    valeurs.update(changements)
    return valeurs


REMOTIVE = offre(
    title="Backend Engineer", original_title="", employer="Lemon.io", location="USA, Canada", province="",
    job_type="full_time", work_mode="Télétravail", technologies=["Python"], skills=[], salary="",
    source_records=[{"source": "Remotive", "source_id": "1234", "url": "https://remotive.com/1234", "origin_site": "Remotive"}],
)


class ConvertirTests(unittest.TestCase):
    def test_offre_du_guichet(self) -> None:
        o = convertir_offre(offre(), "2026-11-20T08:00:00+00:00")
        self.assertEqual(list(o), CHAMPS)
        self.assertEqual(o["id"], "ge-50585958")
        self.assertEqual((o["source"], o["source_partenaire"], o["pays"]), ("guichet-emplois", "Jobillico", "Canada"))
        self.assertEqual(o["titre"], "développeur Web/développeuse Web")  # titre CNP, comme dans le jeu de Gregory
        self.assertEqual(o["competences_cles"], ["Python", "SQL", "Développement Web"])
        self.assertEqual((o["type_poste"], o["modalite"], o["est_stage"]), ("Temps plein", "Hybride", False))
        self.assertEqual(o["date_extraction"], "2026-11-20T08:00:00+00:00")

    def test_offre_publiee_directement_sur_le_guichet(self) -> None:
        o = convertir_offre(offre(source_records=[{**offre()["source_records"][0], "origin_site": "Guichet-Emplois"}]), "")
        self.assertIsNone(o["source_partenaire"])

    def test_remotive_rien_n_est_devine(self) -> None:
        o = convertir_offre(REMOTIVE, "")
        self.assertEqual(o["id"], "rem-1234")
        self.assertEqual((o["province"], o["pays"]), (NON_SPECIFIE, NON_SPECIFIE))
        self.assertEqual(o["lieu"], "USA, Canada")  # texte de l'offre, pas réécrit
        self.assertEqual((o["type_poste"], o["salaire"]), ("Temps plein", None))

    def test_champs_absents(self) -> None:
        o = convertir_offre(offre(employer="", location="", province="", job_type="", work_mode="",
                                  description="", salary="", published_at=""), "")
        self.assertEqual((o["entreprise"], o["lieu"], o["province"]), (NON_SPECIFIE,) * 3)
        self.assertEqual((o["type_poste"], o["modalite"], o["description"], o["salaire"], o["date_publication"]),
                         (None,) * 5)

    def test_types_de_poste(self) -> None:
        self.assertEqual(type_poste(offre(stage_status="confirmed_stage")), "Stage")
        self.assertEqual(type_poste(offre(job_type="Durée fixe ou contrat, Temps plein")), "Contrat")
        self.assertEqual(type_poste(offre(job_type="Temps partiel")), "Temps partiel")
        self.assertEqual(type_poste(offre(job_type="freelance")), "Pigiste / Freelance")
        self.assertEqual(type_poste(offre(job_type="contract")), "Contrat")
        self.assertIsNone(type_poste(offre(job_type="")))

    def test_stage_possible_n_est_pas_un_stage(self) -> None:
        o = convertir_offre(offre(stage_status="possible_stage"), "")
        self.assertEqual((o["est_stage"], o["statut_stage"]), (False, "possible_stage"))

    def test_fichier_qui_n_est_pas_un_offres_json(self) -> None:
        with self.assertRaises(ValueError):
            convertir({"jobs": []})


class FichiersTests(unittest.TestCase):
    def test_json_csv_et_echantillon(self) -> None:
        with TemporaryDirectory() as dossier:
            entree = Path(dossier) / "offres.json"
            entree.write_text(json.dumps({"generated_at": "2026-11-20", "offers": [offre(), REMOTIVE]}), encoding="utf-8")
            sortie = Path(dossier) / "commun.json"
            csv_chemin = Path(dossier) / "commun.csv"
            main(["--entree", str(entree), "--sortie", str(sortie), "--csv", str(csv_chemin)])
            offres = json.loads(sortie.read_text(encoding="utf-8"))
            octets = csv_chemin.read_bytes()
            lignes = list(csv.reader(octets.decode("utf-8-sig").splitlines(), delimiter=";"))
        self.assertEqual([o["id"] for o in offres], ["ge-50585958", "rem-1234"])
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(lignes[0], CHAMPS)
        self.assertEqual(dict(zip(CHAMPS, lignes[1]))["competences_cles"], "Python, SQL, Développement Web")

    def test_message_clair_si_pas_de_collecte(self) -> None:
        with self.assertRaises(SystemExit) as erreur:
            main(["--entree", "introuvable.json"])
        self.assertIn("Lancez d'abord la collecte", str(erreur.exception))


MODELE_GREGORY = Path(__file__).resolve().parents[2] / "gregory" / "livrable3" / "models.py"


@unittest.skipUnless(importlib.util.find_spec("pydantic") and MODELE_GREGORY.exists(),
                     "Pydantic ou le modèle de Gregory absent : validation sautée")
class ModeleDeGregoryTests(unittest.TestCase):
    def test_offres_acceptees_telles_quelles_par_le_modele(self) -> None:
        # Lecture seule : on n'écrit aucun fichier .pyc dans le dossier de Gregory.
        ancien = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location("modele_gregory", MODELE_GREGORY)
        module = importlib.util.module_from_spec(spec)
        # Pydantic a besoin de trouver le module dans sys.modules pour lire ses annotations.
        sys.modules["modele_gregory"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = ancien
        self.addCleanup(sys.modules.pop, "modele_gregory", None)
        for brute in (offre(), REMOTIVE, offre(employer="", job_type="", salary="")):
            converti = convertir_offre(brute, "2026-11-20T08:00:00+00:00")
            with self.subTest(id=converti["id"]):
                self.assertEqual(module.JobOffer(**converti).model_dump(), converti)


if __name__ == "__main__":
    unittest.main()
