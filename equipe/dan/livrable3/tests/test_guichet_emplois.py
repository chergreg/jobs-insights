"""Tests hors ligne de scrapers/guichet_emplois.py (fixtures HTML locales, aucun appel réseau)."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

from modele import Offre
from outils import AccesRefuse
from scrapers import guichet_emplois as ge

FIXTURES = Path(__file__).with_name("fixtures")


def fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class TestUrlRecherche(unittest.TestCase):
    def test_filtres_quebec_cnp_et_tri(self):
        parametres = parse_qsl(urlsplit(ge.url_recherche()).query)
        self.assertEqual([v for k, v in parametres if k == "fn21"], list(ge.CODES_CNP_TI))
        self.assertIn(("fprov", "QC"), parametres)
        self.assertIn(("sort", "D"), parametres)
        self.assertNotIn("page", dict(parametres))              # page 1 : pas de paramètre

    def test_page_et_mot_cle(self):
        parametres = dict(parse_qsl(urlsplit(ge.url_recherche(3, "stage")).query))
        self.assertEqual(parametres["page"], "3")
        self.assertEqual(parametres["searchstring"], "stage")


class TestLireResultats(unittest.TestCase):
    def setUp(self):
        self.offres, self.total = ge.lire_resultats(fixture("ge_resultats.html"))
        self.par_id = {o.id: o for o in self.offres}

    def test_trois_offres_et_total(self):
        self.assertEqual(self.total, 3)
        self.assertEqual(list(self.par_id), ["ge-50738681", "ge-50636267", "ge-50612345"])  # pub ignorée

    def test_offre_directe(self):
        o = self.par_id["ge-50738681"]
        self.assertEqual(o.source, "guichet-emplois")
        self.assertEqual(o.titre, "développeur Web/développeuse Web")
        self.assertEqual(o.url, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50738681")
        self.assertIsNone(o.source_partenaire)                  # publiée sur le Guichet-Emplois
        self.assertEqual(o.entreprise, "Mewlogic Inc.")
        self.assertEqual(o.lieu, "Vaudreuil-Dorion (QC)")       # sans « Emplacement »
        self.assertEqual(o.province, "QC")
        self.assertEqual(o.date_publication, "2026-11-16")
        self.assertEqual(o.salaire, "43,27 $ de l'heure")       # sans « Salaire : »
        self.assertEqual(o.modalite, "Sur place")

    def test_site_d_origine_garde(self):
        self.assertEqual(self.par_id["ge-50636267"].source_partenaire, "Jobillico")
        self.assertEqual(self.par_id["ge-50612345"].source_partenaire, "Talent.com")

    def test_champs_absents_restent_none(self):
        o = self.par_id["ge-50612345"]
        self.assertIsNone(o.salaire)
        self.assertIsNone(o.modalite)
        self.assertIsNone(o.description)
        self.assertIsNone(self.par_id["ge-50738681"].est_stage)  # pas un stage connu ≠ « non »

    def test_stage_detecte_dans_le_titre(self):
        self.assertTrue(self.par_id["ge-50612345"].est_stage)

    def test_page_vide(self):
        self.assertEqual(ge.lire_resultats("<html><body></body></html>"), ([], None))


class TestLireFiche(unittest.TestCase):
    def test_fiche_directe(self):
        fiche = ge.lire_fiche(fixture("ge_fiche_directe.html"))
        self.assertEqual(fiche["description"], "Études: Baccalauréat. Informatique. Tâches: Coordonner "
                                               "les projets informatiques. Expérience: 5 ans ou plus.")
        self.assertEqual(fiche["entreprise"], "Mewlogic Inc.")    # sans « Ce lien ouvrira… »
        self.assertEqual(fiche["lieu"], "Vaudreuil-Dorion (QC)")
        self.assertEqual(fiche["date_publication"], "2026-11-16")
        self.assertEqual(fiche["type_poste"], "Permanent, Temps plein")
        self.assertEqual(fiche["salaire"], "43,27 $ de l'heure")
        self.assertEqual(fiche["modalite"], "Sur place")
        self.assertNotIn("est_stage", fiche)

    def test_fiche_partenaire_html_encode_deux_fois(self):
        fiche = ge.lire_fiche(fixture("ge_fiche_partenaire.html"))
        description = fiche["description"]
        self.assertNotIn("<", description)
        self.assertNotIn("&lt;", description)
        self.assertEqual(description.splitlines()[0], "Poste offert")   # un paragraphe par ligne
        self.assertIn("Python\nKubernetes", description)               # une puce par ligne
        self.assertEqual(fiche["salaire"], "123 000 $ à 140 000 $ par année")
        self.assertEqual(fiche["modalite"], "Hybride")
        self.assertTrue(fiche["est_stage"])                             # titre d'origine : « Stagiaire… »

    def test_repli_dom_sans_rdfa(self):
        fiche = ge.lire_fiche(fixture("ge_fiche_sans_rdfa.html"))
        self.assertIn("Développer des écrans web", fiche["description"])
        self.assertIn("Langages : Java, SQL", fiche["description"])
        self.assertNotIn("Postuler", fiche["description"])              # hors de #job-posting-detail
        for cle in ("entreprise", "lieu", "date_publication", "salaire"):
            self.assertNotIn(cle, fiche)                                # rien d'inventé

    def test_completer_ne_remplace_que_les_trous(self):
        offre = Offre(id="ge-1", source="guichet-emplois", titre="t", url="u",
                      lieu="Montréal (QC)", salaire=None)
        ge.completer(offre, {"lieu": "Autre", "salaire": "20 $", "description": "Texte"})
        self.assertEqual(offre.lieu, "Montréal (QC)")
        self.assertEqual(offre.salaire, "20 $")
        self.assertEqual(offre.description, "Texte")


class TestPetitsOutils(unittest.TestCase):
    def test_date_iso(self):
        self.assertEqual(ge.date_iso("Publiée le 1 décembre 2026"), "2026-12-01")
        self.assertEqual(ge.date_iso("November 10, 2026"), "2026-11-10")
        self.assertEqual(ge.date_iso("2026-12-07\n"), "2026-12-07")
        self.assertIsNone(ge.date_iso("bientôt"))
        self.assertIsNone(ge.date_iso(None))

    def test_province(self):
        self.assertEqual(ge.province_de("Québec (QC)"), "QC")
        self.assertIsNone(ge.province_de("Télétravail"))

    def test_lien_nettoye(self):
        self.assertEqual(ge.nettoyer_lien("/rechercheemplois/offredemploi/1;jsessionid=X?source=a"),
                         "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/1")

    def test_stage(self):
        self.assertTrue(ge.est_un_stage("Stage en développement"))
        self.assertTrue(ge.est_un_stage("Software Engineer Intern"))
        self.assertIsNone(ge.est_un_stage("Analyste de données"))
        self.assertIsNone(ge.est_un_stage("Gestionnaire de l'étage"))   # « étage » n'est pas « stage »


# --- Collecte avec un faux client (aucun réseau) ---------------------------------------

class FauxClient:
    def __init__(self, pages: dict, refus: set = frozenset()):
        self.pages = pages
        self.refus = refus
        self.demandes = []

    def telecharger(self, url):
        self.demandes.append(url)
        if url in self.refus:
            raise AccesRefuse(url, "HTTP 403 : le serveur refuse les robots.")
        return self.pages.get(url, "<html></html>")


FICHE_1 = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50738681"
FICHE_2 = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50636267"


class TestCollecter(unittest.TestCase):
    def collecter(self, client, **options):
        with redirect_stdout(StringIO()):
            return ge.collecter(client, **options)

    def test_arret_au_total_annonce(self):
        client = FauxClient({ge.url_recherche(1): fixture("ge_resultats.html")})
        offres = self.collecter(client, pages=5, fiches=0)
        self.assertEqual(len(offres), 3)
        self.assertEqual(client.demandes, [ge.url_recherche(1)])   # total atteint : pas de page 2

    def test_arret_sur_page_vide(self):
        sans_total = fixture("ge_resultats.html").replace('id="results-count"', 'id="autre"')
        client = FauxClient({ge.url_recherche(1): sans_total})
        self.collecter(client, pages=5, fiches=0)
        self.assertEqual(client.demandes, [ge.url_recherche(1), ge.url_recherche(2)])

    def test_limite_de_fiches_et_description(self):
        client = FauxClient({
            ge.url_recherche(1): fixture("ge_resultats.html"),
            FICHE_1: fixture("ge_fiche_directe.html"),
            FICHE_2: fixture("ge_fiche_partenaire.html"),
        })
        offres = self.collecter(client, pages=1, fiches=2)
        self.assertEqual(len(client.demandes), 3)                  # 1 page + 2 fiches
        self.assertIsNotNone(offres[0].description)
        self.assertTrue(offres[1].est_stage)
        self.assertIsNone(offres[2].description)                    # 3e fiche non ouverte

    def test_refus_du_site_arret_propre(self):
        client = FauxClient({ge.url_recherche(1): fixture("ge_resultats.html")}, refus={FICHE_1})
        offres = self.collecter(client, pages=1, fiches=3)
        self.assertEqual(len(offres), 3)                            # la liste est gardée
        self.assertEqual(client.demandes[-1], FICHE_1)              # on n'insiste pas après le refus

    def test_refus_des_la_premiere_page(self):
        client = FauxClient({}, refus={ge.url_recherche(1)})
        self.assertEqual(self.collecter(client, pages=3, fiches=3), [])

    def test_main_ecrit_json_et_csv(self):
        client = FauxClient({ge.url_recherche(1): fixture("ge_resultats.html"),
                             FICHE_1: fixture("ge_fiche_directe.html")})
        with tempfile.TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "offres.json"
            with mock.patch.object(ge, "Client", return_value=client), redirect_stdout(StringIO()):
                ge.main(["--fiches", "1", "--sortie", str(sortie), "--csv"])
            contenu = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(contenu["nombre"], 3)
            self.assertEqual(contenu["offres"][0]["type_poste"], "Permanent, Temps plein")
            self.assertTrue(sortie.with_suffix(".csv").exists())


if __name__ == "__main__":
    unittest.main()
