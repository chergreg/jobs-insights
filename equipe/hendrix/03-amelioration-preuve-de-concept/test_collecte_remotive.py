"""Tests hors ligne du prototype Remotive, dont le cache de 24 heures."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
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
            "categorie_localisation": "canada",
            "province_code": None,
        })
        self.assertIsNone(incomplete["salaire"])
        self.assertIsNone(incomplete["entreprise"])
        self.assertIsNone(incomplete["url_originale"])
        self.assertEqual(incomplete["categorie_localisation"], "inconnue")
        self.assertIsNone(incomplete["province_code"])

    def test_limite_et_liste_vide(self):
        self.assertEqual(len(script.extraire_offres(self.reponse, 1)), 1)
        self.assertEqual(script.extraire_offres({"jobs": []}, 3), [])

    def test_structure_invalide(self):
        for reponse in ({}, {"jobs": {}}, {"jobs": [None]}, {"jobs": [{"title": 1}]}):
            with self.subTest(reponse=reponse), self.assertRaises(ValueError):
                script.extraire_offres(reponse, 3)

    def test_suppression_doublons(self):
        premiere = self.reponse["jobs"][0]
        doublon = dict(premiere)
        doublon["title"] = "Titre modifié"
        sans_url = {"title": "Offre sans URL"}
        reponse = {"jobs": [premiere, doublon, sans_url, dict(sans_url)]}
        offres = script.extraire_offres(reponse, 4)
        self.assertEqual(len(offres), 3)
        self.assertEqual(offres[0]["titre"], "Développeur junior")
        self.assertIsNone(offres[1]["url_originale"])
        self.assertIsNone(offres[2]["url_originale"])

    def test_cache_reutilise_reponse(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            with patch.object(script, "consulter_api", return_value=self.reponse) as api:
                premier = script.charger_reponse_avec_cache(2, cache)
                second = script.charger_reponse_avec_cache(2, cache)
            self.assertEqual(premier, second)
            api.assert_called_once_with(2)
            contenu = json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(contenu["request_url"], script.API_URL + "?limit=2")
            self.assertEqual(contenu["payload"], self.reponse)

    def test_cache_expire(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            ancien = {
                "request_url": script.API_URL + "?limit=2",
                "fetched_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
                "payload": {"jobs": []},
            }
            cache.write_text(json.dumps(ancien), encoding="utf-8")
            with patch.object(script, "consulter_api", return_value=self.reponse) as api:
                resultat = script.charger_reponse_avec_cache(2, cache)
            self.assertEqual(resultat, self.reponse)
            api.assert_called_once_with(2)

    def test_cache_limites_differentes(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            with patch.object(script, "consulter_api", return_value=self.reponse) as api:
                script.charger_reponse_avec_cache(1, cache)
                script.charger_reponse_avec_cache(2, cache)
            self.assertEqual(api.call_count, 2)

    def test_cache_corrompu(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            cache.write_text("JSON invalide", encoding="utf-8")
            with patch.object(script, "consulter_api", return_value=self.reponse) as api:
                resultat = script.charger_reponse_avec_cache(2, cache)
            self.assertEqual(resultat, self.reponse)
            api.assert_called_once_with(2)

    def test_cache_date_invalide(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            cache.write_text(json.dumps({
                "request_url": script.API_URL + "?limit=2",
                "fetched_at": "date inconnue",
                "payload": {"jobs": []},
            }), encoding="utf-8")
            with patch.object(script, "consulter_api", return_value=self.reponse) as api:
                resultat = script.charger_reponse_avec_cache(2, cache)
            self.assertEqual(resultat, self.reponse)
            api.assert_called_once_with(2)

    def test_cache_reponse_invalide(self):
        with TemporaryDirectory() as dossier:
            cache = Path(dossier) / "cache.json"
            with patch.object(script, "consulter_api", return_value={"jobs": None}) as api:
                with self.assertRaises(ValueError):
                    script.charger_reponse_avec_cache(2, cache)
            api.assert_called_once_with(2)
            self.assertFalse(cache.exists())

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
            with (
                patch.object(sys, "argv", ["script", "--sortie", str(sortie)]),
                patch.object(script, "charger_reponse_avec_cache") as charger,
            ):
                self.assertEqual(script.main(), 0)
            export = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(export["mode"], "simule")
            self.assertEqual(export["nombre_offres"], 2)
            self.assertEqual(export["offres"][0]["titre"], "Développeur junior")
            charger.assert_not_called()
        ouvrir.assert_not_called()

    @patch("collecte_remotive.urlopen")
    def test_echecs_sans_export_ni_relance(self, ouvrir):
        with TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "export.json"
            arguments = ["script", "--reel", "--sortie", str(sortie)]
            erreurs = (
                HTTPError(script.API_URL, 429, "", {}, None),
                URLError("hors ligne"),
                json.JSONDecodeError("invalide", "", 0),
            )
            for erreur in erreurs:
                with self.subTest(erreur=erreur):
                    ouvrir.reset_mock()
                    ouvrir.side_effect = erreur
                    with (
                        patch.object(sys, "argv", arguments),
                        redirect_stderr(io.StringIO()),
                        patch.object(
                            script,
                            "charger_reponse_avec_cache",
                            side_effect=lambda limite, chemin: script.consulter_api(limite),
                        ),
                    ):
                        self.assertEqual(script.main(), 1)
                    self.assertFalse(sortie.exists())
                    ouvrir.assert_called_once()

    def test_main_utilise_cache_en_mode_reel(self):
        with TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "export.json"
            with (
                patch.object(sys, "argv", ["script", "--reel", "--sortie", str(sortie)]),
                patch.object(
                    script, "charger_reponse_avec_cache", return_value=self.reponse
                ) as charger,
                patch("collecte_remotive.urlopen") as ouvrir,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(script.main(), 0)
            charger.assert_called_once_with(3, script.DOSSIER / "remotive-cache.json")
            ouvrir.assert_not_called()
            export = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(export["mode"], "reel")
            self.assertEqual(export["nombre_offres"], 2)

    def test_nettoyage_html(self):
        html = """
        <style>body { color: red; }</style>
        <p>Bonjour <strong>Hendrix</strong> !</p>
        <script>alert('test')</script>
        <p>Python &amp; SQL</p>
        """
        resultat = script.nettoyer_description(html)
        self.assertEqual(resultat, "Bonjour Hendrix ! Python & SQL")

    def test_classification_localisation(self):
        cas = {
            "Canada": "canada",
            "Québec": "quebec",
            "Montréal, Canada": "quebec",
            "USA": "etats_unis",
            "United States": "etats_unis",
            "Worldwide": "mondiale",
            "Anywhere": "mondiale",
            "North America": "amerique_du_nord",
            "Canada, USA": "amerique_du_nord",
            "France": "autre",
            "": "inconnue",
            None: "inconnue",
        }
        for localisation, categorie_attendue in cas.items():
            with self.subTest(localisation=localisation):
                self.assertEqual(
                    script.classifier_localisation(localisation), categorie_attendue
                )

    def test_province_explicite_sans_inventer_qc(self):
        cas = {
            "Québec": "QC",
            "Montréal, Canada": "QC",
            "Laval, Canada": "QC",
            "Toronto, Ontario": "ON",
            "Ontario": "ON",
            "Canada": None,
            "North America": None,
            "Worldwide": None,
            "Anywhere": None,
            "USA": None,
            "Laval": None,
            "Laval, France": None,
            "": None,
            None: None,
        }
        for localisation, code_attendu in cas.items():
            with self.subTest(localisation=localisation):
                self.assertEqual(
                    script.extraire_province_code(localisation), code_attendu
                )

    def test_laval_ambigu_ne_devient_pas_quebec(self):
        self.assertEqual(script.classifier_localisation("Laval"), "autre")
        self.assertEqual(script.classifier_localisation("Laval, France"), "autre")
        self.assertEqual(script.classifier_localisation("Laval, Canada"), "quebec")
        self.assertEqual(script.classifier_localisation("Toronto, Ontario"), "canada")

    def test_export_conserve_localisation_source_et_province_inconnue(self):
        zones = ("Canada", "Worldwide", "North America", None, "Montréal")
        entree = {"jobs": [
            {"title": "Offre fictive", "candidate_required_location": zone}
            for zone in zones
        ]}
        offres = script.extraire_offres(entree, len(zones))
        self.assertEqual([offre["localisation"] for offre in offres], list(zones))
        self.assertEqual(
            [offre["province_code"] for offre in offres],
            [None, None, None, None, "QC"],
        )
        self.assertEqual(
            [offre["categorie_localisation"] for offre in offres],
            ["canada", "mondiale", "amerique_du_nord", "inconnue", "quebec"],
        )


if __name__ == "__main__":
    unittest.main()
