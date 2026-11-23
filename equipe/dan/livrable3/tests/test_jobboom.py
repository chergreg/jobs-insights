"""Tests hors ligne de scrapers/jobboom.py et scrapers/commun.py (fixtures locales, aucun réseau)."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from outils import AccesRefuse
from scrapers import commun, jsonld
from scrapers import jobboom as jb

FIXTURES = Path(__file__).with_name("fixtures")
FICHE_TECH = "https://www.jobboom.com/fr/offre-emploi/technicien-informatique_innovmetric-logiciels-inc_p3698100"
FICHE_STAGE = "https://www.jobboom.com/fr/offre-emploi/stage-developpeur-web_studio-quebec_p3799001"


def fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class TestCategorie(unittest.TestCase):
    def setUp(self):
        self.offres, self.total = jb.lire_categorie(fixture("jb_categorie.html"))

    def test_url_categorie(self):
        self.assertEqual(jb.url_categorie(), jb.URL_CATEGORIE_TI + "?sortBy=date")
        self.assertTrue(jb.url_categorie(3).endswith("?sortBy=date&page=3"))

    def test_commanditees_doublons_et_liens_sans_numero_exclus(self):
        self.assertEqual([o.id for o in self.offres], ["jb-3698100", "jb-3799001"])   # ordre d'affichage

    def test_lien_nettoye_et_titre_de_carte(self):
        stage = self.offres[1]
        self.assertEqual(stage.url, FICHE_STAGE)                                    # sans ?track=1
        self.assertEqual(stage.titre, "Stage développeur web")
        self.assertEqual(stage.source, "jobboom")

    def test_total_annonce(self):
        self.assertEqual(self.total, 131)

    def test_repli_sur_les_liens(self):
        html = ('<div class="job_item_sponsorship"><a href="/fr/offre-emploi/pub_p1">Pub</a></div>'
                '<a href="/fr/offre-emploi/dev-python_p3718101?x=1">Développeur Python</a>')
        offres, total = jb.lire_categorie(html)
        self.assertEqual([(o.id, o.titre) for o in offres], [("jb-3718101", "Développeur Python")])
        self.assertIsNone(total)

    def test_numero_offre(self):
        self.assertEqual(jb.numero_offre(FICHE_TECH), "3698100")
        self.assertIsNone(jb.numero_offre("https://www.jobboom.com/fr/offre-emploi/sans-numero"))


class TestFiche(unittest.TestCase):
    def test_fiche_complete(self):
        fiche = jb.lire_fiche(fixture("jb_fiche.html"))
        self.assertEqual(fiche["titre"], "Technicien informatique")
        self.assertEqual(fiche["entreprise"], "InnovMetric Logiciels Inc.")       # pas « Jobboom »
        self.assertEqual(fiche["lieu"], "Québec (QC)")
        self.assertEqual(fiche["province"], "QC")
        self.assertEqual((fiche["latitude"], fiche["longitude"]), (46.817136, -71.312079))
        self.assertEqual(fiche["date_publication"], "2026-09-30")
        self.assertEqual(fiche["type_poste"], "Permanent, Temps plein")
        self.assertEqual(fiche["modalite"], "Télétravail")
        self.assertEqual(fiche["salaire"], "52 000 $ à 60 000 $ par année")
        self.assertEqual(fiche["description"],
                         "Vous aimez résoudre des problèmes et offrir un service de qualité.\n"
                         "Soutien Windows et Azure\nGestion des tickets Jira")
        self.assertNotIn("est_stage", fiche)                                      # inconnu ≠ « non »

    def test_fiche_stage_graph_et_html_encode(self):
        fiche = jb.lire_fiche(fixture("jb_fiche_stage.html"))
        self.assertTrue(fiche["est_stage"])
        self.assertEqual(fiche["type_poste"], "Stage")
        self.assertEqual(fiche["description"], "Stage de 15 semaines à l’hiver.\nTechnologies : Python, React")
        self.assertEqual(fiche["lieu"], "Lévis (QC)")                             # « Québec » → QC
        self.assertEqual(fiche["date_publication"], "2026-11-10")
        for cle in ("salaire", "latitude", "modalite"):
            self.assertNotIn(cle, fiche)                                          # rien d'inventé

    def test_fiche_sans_jsonld(self):
        self.assertEqual(jb.lire_fiche(fixture("jb_fiche_sans_jsonld.html")), {})

    def test_salaire_variantes(self):
        horaire = {"baseSalary": {"value": {"minValue": 22.5, "maxValue": 26, "unitText": "HOUR"}}}
        self.assertEqual(jsonld.salaire(horaire), "22,50 $ à 26 $ de l'heure")
        exact = {"baseSalary": {"value": 55000, "unitText": "YEAR"}}
        self.assertEqual(jsonld.salaire(exact), "55 000 $ par année")
        self.assertIsNone(jsonld.salaire({}))


class TestCommun(unittest.TestCase):
    def test_html_vers_texte(self):
        self.assertEqual(commun.html_vers_texte("<p>Un</p><ul><li>Deux</li></ul>"), "Un\nDeux")
        self.assertEqual(commun.html_vers_texte("&lt;p&gt;Un&lt;/p&gt;&lt;p&gt;Deux&lt;/p&gt;"), "Un\nDeux")
        self.assertIsNone(commun.html_vers_texte(""))

    def test_balises_en_ligne_ne_coupent_pas_la_phrase(self):
        html = "<p>Nous cherchons un(e) <strong>stagiaire en développement Web</strong> en mode hybride.</p>"
        self.assertEqual(commun.html_vers_texte(html),
                         "Nous cherchons un(e) stagiaire en développement Web en mode hybride.")
        self.assertEqual(commun.html_vers_texte("Ligne 1<br>Ligne 2"), "Ligne 1\nLigne 2")

    def test_montant(self):
        self.assertEqual(commun.montant(52000), "52 000")
        self.assertEqual(commun.montant("43.27"), "43,27")
        self.assertEqual(commun.montant("selon expérience"), "selon expérience")

    def test_date_iso_avec_heure(self):
        self.assertEqual(commun.date_iso("2026-11-10T08:30:00-05:00"), "2026-11-10")


# --- Collecte avec un faux client ---------------------------------------------------------

class FauxClient:
    def __init__(self, pages, refus=frozenset()):
        self.pages, self.refus, self.demandes = pages, refus, []

    def telecharger(self, url):
        self.demandes.append(url)
        if url in self.refus:
            raise AccesRefuse(url, "HTTP 403 : le serveur refuse les robots.")
        return self.pages.get(url, "<html></html>")


class TestCollecter(unittest.TestCase):
    def collecter(self, client, **options):
        with redirect_stdout(StringIO()):
            return jb.collecter(client, **options)

    def test_fiches_completent_les_cartes(self):
        client = FauxClient({jb.url_categorie(1): fixture("jb_categorie.html"),
                             FICHE_TECH: fixture("jb_fiche.html"),
                             FICHE_STAGE: fixture("jb_fiche_stage.html")})
        offres = self.collecter(client, pages=1, fiches=2)
        self.assertEqual(len(offres), 2)
        self.assertEqual(offres[0].entreprise, "InnovMetric Logiciels Inc.")
        self.assertEqual(offres[1].titre, "Stage développeur Web Python / React")   # titre de la fiche
        self.assertTrue(offres[1].est_stage)

    def test_page_vide_arrete_la_pagination(self):
        client = FauxClient({jb.url_categorie(1): fixture("jb_categorie.html")})
        self.collecter(client, pages=4, fiches=0)
        self.assertEqual(client.demandes, [jb.url_categorie(1), jb.url_categorie(2)])

    def test_limite_de_fiches(self):
        client = FauxClient({jb.url_categorie(1): fixture("jb_categorie.html")})
        self.collecter(client, pages=1, fiches=1)
        self.assertEqual(client.demandes, [jb.url_categorie(1), FICHE_TECH])

    def test_offre_sans_titre_retiree(self):
        html = '<div class="job_item" data-url="/fr/offre-emploi/x_p42"></div>'
        client = FauxClient({jb.url_categorie(1): html})
        self.assertEqual(self.collecter(client, pages=1, fiches=0), [])

    def test_refus_arret_propre(self):
        client = FauxClient({jb.url_categorie(1): fixture("jb_categorie.html")}, refus={FICHE_TECH})
        offres = self.collecter(client, pages=1, fiches=2)
        self.assertEqual(len(offres), 2)                       # les cartes restent
        self.assertEqual(client.demandes[-1], FICHE_TECH)      # pas d'autre fiche après le refus

    def test_main_ecrit_json(self):
        client = FauxClient({jb.url_categorie(1): fixture("jb_categorie.html"),
                             FICHE_TECH: fixture("jb_fiche.html")})
        with tempfile.TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "offres_jobboom.json"
            with mock.patch.object(jb, "Client", return_value=client), redirect_stdout(StringIO()):
                jb.main(["--fiches", "1", "--sortie", str(sortie)])
            contenu = json.loads(sortie.read_text(encoding="utf-8"))
            self.assertEqual(contenu["nombre"], 2)
            self.assertEqual(contenu["offres"][0]["latitude"], 46.817136)


if __name__ == "__main__":
    unittest.main()
