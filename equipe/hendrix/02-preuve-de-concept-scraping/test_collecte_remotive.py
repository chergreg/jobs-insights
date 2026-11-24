import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import collecte_remotive as script


class TestCollecteRemotive(unittest.TestCase):
    def setUp(self):
        chemin = script.DOSSIER / "fixtures" / "reponse_simulee.json"
        self.reponse = json.loads(chemin.read_text(encoding="utf-8"))

    def test_extraction(self):
        offre, incomplete = script.extraire_offres(self.reponse, 2)
        self.assertEqual(offre, {
            "titre": "Développeur junior",
            "entreprise": "Entreprise fictive",
            "localisation": "Canada",
            "date_publication": "2026-01-01T12:00:00",
            "description": "Offre fictive pour le test.",
            "salaire": "50 000 CAD par an",
            "url_originale": "https://example.invalid/offre/1",
        })
        self.assertIsNone(incomplete["salaire"])
        self.assertIsNone(incomplete["entreprise"])
        self.assertIsNone(incomplete["url_originale"])

    def test_limite_et_liste_vide(self):
        self.assertEqual(len(script.extraire_offres(self.reponse, 1)), 1)
        self.assertEqual(script.extraire_offres({"jobs": []}, 3), [])

    def test_structure_invalide(self):
        for reponse in ({}, {"jobs": {}}, {"jobs": [None]}, {"jobs": [{"title": 1}]}):
            with self.subTest(reponse=reponse), self.assertRaises(ValueError):
                script.extraire_offres(reponse, 3)

    @patch("collecte_remotive.urlopen")
    def test_requete(self, ouvrir):
        ouvrir.return_value.__enter__.return_value = io.BytesIO(
            json.dumps(self.reponse).encode("utf-8")
        )
        self.assertEqual(script.consulter_api(3), self.reponse)
        ouvrir.assert_called_once()
        self.assertEqual(ouvrir.call_args.args[0].full_url, script.API_URL + "?limit=3")
        self.assertEqual(ouvrir.call_args.kwargs["timeout"], 15)

    @patch("collecte_remotive.urlopen")
    def test_mode_simule(self, ouvrir):
        with TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "export.json"
            with patch.object(sys, "argv", ["script", "--sortie", str(sortie)]):
                self.assertEqual(script.main(), 0)
            export = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(export["mode"], "simule")
            self.assertEqual(export["nombre_offres"], 2)
            self.assertEqual(export["offres"][0]["titre"], "Développeur junior")
        ouvrir.assert_not_called()

    @patch("collecte_remotive.urlopen")
    def test_echecs_sans_export_ni_relance(self, ouvrir):
        with TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "export.json"
            arguments = ["script", "--reel", "--sortie", str(sortie)]
            for erreur in (HTTPError(script.API_URL, 429, "", {}, None),
                           URLError("hors ligne"), json.JSONDecodeError("invalide", "", 0)):
                with self.subTest(erreur=erreur):
                    ouvrir.reset_mock()
                    ouvrir.side_effect = erreur
                    with patch.object(sys, "argv", arguments), redirect_stderr(io.StringIO()):
                        self.assertEqual(script.main(), 1)
                    self.assertFalse(sortie.exists())
                    ouvrir.assert_called_once()

    
    def test_nettoyage_html(self):
        html = """
        <style>body { color: red; }</style>
        <p>Bonjour <strong>Hendrix</strong> !</p>
        <script>alert('test')</script>
        <p>Python &amp; SQL</p>
        """

        resultat = script.nettoyer_description(html)

        self.assertEqual(
            resultat,
            "Bonjour Hendrix ! Python & SQL"
        )



if __name__ == "__main__":
    unittest.main()
