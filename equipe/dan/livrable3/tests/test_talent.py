"""Tests hors ligne de scrapers/talent.py et scrapers/jsonld.py (fixtures locales, aucun réseau)."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

from outils import AccesRefuse, Client
from scrapers import jsonld
from scrapers import talent as tc
from tests.test_outils import FausseHorloge, FausseReponse, FausseSession

FIXTURES = Path(__file__).with_name("fixtures")
FICHE_1 = "https://ca.talent.com/fr/view?id=640918690502021004"
FICHE_2 = "https://ca.talent.com/fr/view?id=634537925073176368"


def fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class TestRecherche(unittest.TestCase):
    def test_url_recherche(self):
        parametres = dict(parse_qsl(urlsplit(tc.url_recherche()).query))
        self.assertEqual(parametres, {"k": "informatique", "l": "Québec, QC"})
        self.assertEqual(dict(parse_qsl(urlsplit(tc.url_recherche(2)).query))["p"], "2")

    def test_itemlist_ordre_doublons_et_liens_sans_id(self):
        offres = tc.lire_resultats(fixture("tc_resultats.html"))
        self.assertEqual([o.id for o in offres], ["tc-640918690502021004", "tc-634537925073176368"])
        self.assertEqual(offres[0].url, FICHE_1)                 # sans utm_source
        self.assertEqual(offres[0].titre, "Analyste en informatique")
        self.assertEqual(offres[1].url, FICHE_2)                 # lien relatif rendu absolu
        self.assertEqual(offres[1].titre, "")                    # pas de titre dans la liste : rien d'inventé

    def test_identifiant(self):
        self.assertEqual(tc.identifiant(FICHE_1), "640918690502021004")
        self.assertIsNone(tc.identifiant("https://ca.talent.com/fr/jobs?k=python"))

    def test_page_sans_itemlist(self):
        self.assertEqual(tc.lire_resultats("<html><body>Aucun résultat</body></html>"), [])


class TestFiche(unittest.TestCase):
    def test_fiche_reelle_de_mamadou(self):
        fiche = tc.lire_fiche(fixture("tc_fiche.html"))
        self.assertEqual(fiche["titre"], "Analyste en informatique")
        self.assertEqual(fiche["entreprise"], "Chu De Quebec - Universite Laval")   # pas « Talent.com »
        self.assertEqual(fiche["lieu"], "Québec City (QC)")                         # « Quebec » → QC
        self.assertEqual(fiche["province"], "QC")
        self.assertEqual((fiche["latitude"], fiche["longitude"]), (46.8130816, -71.2074596))
        self.assertEqual(fiche["date_publication"], "2026-10-10")
        self.assertEqual(fiche["type_poste"], "Temps plein")
        self.assertEqual(fiche["description"],
                         "Informations de base\nLieu de travail : Centre administratif\n"
                         "Soutien Azure et Linux\nScripts Python")
        for cle in ("salaire", "modalite", "est_stage"):
            self.assertNotIn(cle, fiche)                                            # rien d'inventé

    def test_fiche_stage(self):
        fiche = tc.lire_fiche(fixture("tc_fiche_stage.html"))
        self.assertTrue(fiche["est_stage"])
        self.assertEqual(fiche["type_poste"], "Stage")
        self.assertEqual(fiche["lieu"], "Montréal (QC)")
        self.assertEqual(fiche["date_publication"], "2026-11-15")
        self.assertNotIn("latitude", fiche)

    def test_fiche_sans_jsonld(self):
        self.assertEqual(tc.lire_fiche("<html><h1>Offre expirée</h1></html>"), {})


class TestJsonld(unittest.TestCase):
    def test_province_francais_anglais_code(self):
        for texte, code in (("Quebec", "QC"), ("Québec", "QC"), ("qc", "QC"), ("Ontario", "ON"),
                            ("Nouveau-Brunswick", "NB"), ("British Columbia", "BC")):
            with self.subTest(texte=texte):
                self.assertEqual(jsonld.province(texte), code)
        self.assertIsNone(jsonld.province("Montérégie"))                # région inconnue : None
        self.assertIsNone(jsonld.province(None))

    def test_objets_jsonld_deplie_graph_et_ignore_invalide(self):
        types = [o.get("@type") for o in jsonld.objets_jsonld(fixture("tc_resultats.html"))]
        self.assertEqual(types, ["WebPage", "ItemList"])


# --- Collecte ------------------------------------------------------------------------------

class FauxClient:
    def __init__(self, pages, refus=frozenset()):
        self.pages, self.refus, self.demandes = pages, refus, []

    def telecharger(self, url):
        self.demandes.append(url)
        if url in self.refus:
            raise AccesRefuse(url, "HTTP 403 : le serveur refuse les robots — Cloudflare (protection anti-robot).")
        return self.pages.get(url, "<html></html>")


class TestCollecter(unittest.TestCase):
    def collecter(self, client, **options):
        sortie = StringIO()
        with redirect_stdout(sortie):
            offres = tc.collecter(client, **options)
        return offres, sortie.getvalue()

    def test_liste_puis_fiches(self):
        client = FauxClient({tc.url_recherche(1): fixture("tc_resultats.html"),
                             FICHE_1: fixture("tc_fiche.html"), FICHE_2: fixture("tc_fiche_stage.html")})
        offres, _ = self.collecter(client, pages=1, fiches=2)
        self.assertEqual([o.titre for o in offres], ["Analyste en informatique", "Stagiaire en développement logiciel"])
        self.assertEqual(offres[0].latitude, 46.8130816)
        self.assertTrue(offres[1].est_stage)

    def test_pagination_non_reconnue_arret(self):
        """Si « p=2 » est ignoré par le site, la page 2 répète la page 1 : on s'arrête."""
        page = fixture("tc_resultats.html")
        client = FauxClient({tc.url_recherche(1): page, tc.url_recherche(2): page})
        self.collecter(client, pages=5, fiches=0)
        self.assertEqual(client.demandes, [tc.url_recherche(1), tc.url_recherche(2)])

    def test_offre_sans_titre_retiree_si_fiche_non_lue(self):
        client = FauxClient({tc.url_recherche(1): fixture("tc_resultats.html")})
        offres, _ = self.collecter(client, pages=1, fiches=0)
        self.assertEqual([o.id for o in offres], ["tc-640918690502021004"])

    def test_porte_d_entree_403_arret_et_plan_b(self):
        client = FauxClient({}, refus={tc.url_recherche(1)})
        offres, sortie = self.collecter(client, pages=3, fiches=3)
        self.assertEqual(offres, [])
        self.assertEqual(client.demandes, [tc.url_recherche(1)])        # aucune autre tentative
        self.assertIn("Cloudflare", sortie)
        self.assertIn("plan B (Remotive)", sortie)

    def test_porte_d_entree_robots_txt_avec_le_vrai_client(self):
        """robots.txt interdit /fr/jobs : outils.Client refuse avant toute requête vers la recherche."""
        session = FausseSession({tc.BASE_URL + "/robots.txt":
                                 FausseReponse(200, "User-agent: *\nDisallow: /fr/jobs\n")})
        horloge = FausseHorloge()
        client = Client(session=session, attendre=horloge.attendre, horloge=horloge, cache_dossier=None)
        offres, sortie = self.collecter(client, pages=1, fiches=1)
        self.assertEqual(offres, [])
        self.assertEqual([u for u, _ in session.appels], [tc.BASE_URL + "/robots.txt"])
        self.assertIn("robots.txt interdit", sortie)

    def test_main_ecrit_json(self):
        client = FauxClient({tc.url_recherche(1): fixture("tc_resultats.html"), FICHE_1: fixture("tc_fiche.html")})
        with tempfile.TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "offres_talent.json"
            with mock.patch.object(tc, "Client", return_value=client), redirect_stdout(StringIO()):
                tc.main(["--fiches", "1", "--sortie", str(sortie)])
            contenu = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(contenu["nombre"], 1)
            self.assertEqual(contenu["offres"][0]["source"], "talent")


if __name__ == "__main__":
    unittest.main()
