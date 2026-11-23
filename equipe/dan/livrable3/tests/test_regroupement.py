"""Tests hors ligne de regroupement.py (doublons) et de main.py (faux scrapers, aucun réseau)."""

import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import main
from modele import Offre
from regroupement import (empreinte, entreprise_normalisee, fusionner, nb_champs_remplis, regrouper,
                          titre_normalise, ville_normalisee)


def ge(numero, **champs):
    return Offre(id=f"ge-{numero}", source="guichet-emplois", titre=champs.pop("titre", "développeur Web/développeuse Web"),
                 url=f"https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{numero}", **champs)


def tc(numero, **champs):
    return Offre(id=f"tc-{numero}", source="talent", titre=champs.pop("titre", "Développeur Web"),
                 url=f"https://ca.talent.com/fr/view?id={numero}", **champs)


def jb(numero, **champs):
    return Offre(id=f"jb-{numero}", source="jobboom", titre=champs.pop("titre", "Développeur Web"),
                 url=f"https://www.jobboom.com/fr/offre-emploi/x_p{numero}", **champs)


class TestNormalisation(unittest.TestCase):
    def test_titre(self):
        self.assertEqual(titre_normalise("développeur Web/développeuse Web"), "developpeur web")
        self.assertEqual(titre_normalise("  DÉVELOPPEUR   web! "), "developpeur web")

    def test_entreprise_sans_forme_juridique(self):
        self.assertEqual(entreprise_normalisee("Mewlogic Inc."), "mewlogic")
        self.assertEqual(entreprise_normalisee("Groupe Exemple ltée"), "groupe exemple")

    def test_ville(self):
        for lieu in ("Québec City (QC)", "Québec (QC)", "Québec, QC", "QUEBEC"):
            with self.subTest(lieu=lieu):
                self.assertEqual(ville_normalisee(lieu), "quebec")
        self.assertEqual(ville_normalisee("Lévis (QC)"), "levis")

    def test_empreinte_incomplete(self):
        self.assertIsNone(empreinte(tc(1, entreprise="Mewlogic", lieu=None)))
        self.assertIsNone(empreinte(tc(1, entreprise=None, lieu="Québec (QC)")))


class TestFusion(unittest.TestCase):
    def test_garde_la_plus_complete_et_comble_les_trous(self):
        liste = ge(1, entreprise="Mewlogic Inc.", lieu="Québec (QC)", salaire="43,27 $ de l'heure",
                   source_partenaire="Talent.com")
        fiche = tc(9, entreprise="Mewlogic", lieu="Québec City (QC)", latitude=46.8, longitude=-71.2,
                   description="Texte", type_poste="Temps plein", competences=["Python"])
        fusion = fusionner(liste, fiche)
        self.assertIs(fusion, fiche)                            # plus de champs remplis
        self.assertEqual(fusion.salaire, "43,27 $ de l'heure")  # comblé depuis le Guichet
        self.assertEqual(fusion.lieu, "Québec City (QC)")       # valeur gardée, pas écrasée
        self.assertIsNone(fusion.source_partenaire)             # pas recopié : décrit l'annonce du Guichet
        self.assertEqual(fusion.doublons, ["ge-1"])

    def test_rien_n_est_invente(self):
        fusion = fusionner(tc(1, entreprise="A", lieu="Québec"), tc(2, entreprise="A", lieu="Québec"))
        self.assertIsNone(fusion.salaire)
        self.assertIsNone(fusion.est_stage)

    def test_competences_reunies_sans_double(self):
        a = tc(1, competences=["Python", "SQL"])
        b = jb(2, competences=["SQL", "Docker"])
        self.assertEqual(fusionner(a, b).competences, ["Python", "SQL", "Docker"])

    def test_a_egalite_la_premiere_est_gardee(self):
        a = ge(1, entreprise="A", lieu="Québec (QC)")
        b = tc(2, entreprise="A", lieu="Québec (QC)")
        self.assertIs(fusionner(a, b), a)

    def test_nb_champs_remplis(self):
        self.assertEqual(nb_champs_remplis(tc(1)), 4)            # id, source, titre, url


class TestRegrouper(unittest.TestCase):
    def test_meme_id(self):
        uniques, bilan = regrouper([tc(1, entreprise="A"), tc(1, salaire="20 $")])
        self.assertEqual(len(uniques), 1)
        self.assertEqual(uniques[0].salaire, "20 $")
        self.assertEqual(bilan.doublons_meme_id, 1)

    def test_offre_talent_reprise_par_le_guichet(self):
        offres = [
            ge(50612345, titre="stagiaire en programmation informatique", entreprise="Studio Nord",
               lieu="Québec (QC)", source_partenaire="Talent.com"),
            tc(640918690502021004, titre="Stagiaire en programmation informatique", entreprise="Studio Nord inc.",
               lieu="Québec City (QC)", description="Texte complet", latitude=46.8),
        ]
        uniques, bilan = regrouper(offres)
        self.assertEqual(len(uniques), 1)
        self.assertEqual(uniques[0].id, "tc-640918690502021004")
        self.assertEqual(uniques[0].doublons, ["ge-50612345"])
        self.assertEqual(bilan.doublons_empreinte, 1)
        self.assertEqual(bilan.exemples, ["tc-640918690502021004 = ge-50612345"])

    def test_meme_diffuseur_numeros_differents_pas_fusionnes(self):
        """Jobboom publie deux fois « Développeur Web » chez le même employeur : deux vrais postes."""
        uniques, bilan = regrouper([jb(1, entreprise="A", lieu="Québec (QC)"),
                                    jb(2, entreprise="A", lieu="Québec (QC)")])
        self.assertEqual(len(uniques), 2)
        self.assertEqual(bilan.doublons, 0)

    def test_guichet_meme_partenaire_pas_fusionne_partenaires_differents_fusionnes(self):
        a = ge(1, entreprise="A", lieu="Laval (QC)", source_partenaire="Jobillico")
        b = ge(2, entreprise="A", lieu="Laval (QC)", source_partenaire="Jobillico")
        c = ge(3, entreprise="A", lieu="Laval (QC)")                        # publiée sur le Guichet lui-même
        uniques, _ = regrouper([a, b, c])
        self.assertEqual([o.id for o in uniques], ["ge-1", "ge-2"])          # c fusionnée avec a
        self.assertEqual(uniques[0].doublons, ["ge-3"])

    def test_sans_entreprise_pas_de_fusion(self):
        uniques, _ = regrouper([ge(1, lieu="Québec (QC)"), tc(2, lieu="Québec (QC)")])
        self.assertEqual(len(uniques), 2)

    def test_chaine_de_trois_sources(self):
        offres = [ge(1, entreprise="A", lieu="Québec (QC)", source_partenaire="Talent.com"),
                  jb(2, entreprise="A", lieu="Québec (QC)", salaire="50 000 $"),
                  tc(3, entreprise="A", lieu="Québec City (QC)", description="D")]
        uniques, bilan = regrouper(offres)
        self.assertEqual(len(uniques), 1)
        self.assertEqual(sorted([uniques[0].id, *uniques[0].doublons]), ["ge-1", "jb-2", "tc-3"])
        self.assertEqual(uniques[0].salaire, "50 000 $")
        self.assertEqual(bilan.doublons, 2)

    def test_ordre_de_premiere_apparition(self):
        uniques, _ = regrouper([tc(1, titre="B"), jb(2, titre="A"), ge(3, titre="C")])
        self.assertEqual([o.id for o in uniques], ["tc-1", "jb-2", "ge-3"])


# --- main.py avec de faux scrapers ---------------------------------------------------------

class FauxScraper:
    def __init__(self, source, offres=None, erreur=None):
        self.SOURCE, self.offres, self.erreur, self.appels = source, offres or [], erreur, []

    def collecter(self, client, pages, fiches):
        self.appels.append((pages, fiches))
        if self.erreur:
            raise self.erreur
        return self.offres


class TestMain(unittest.TestCase):
    def lancer(self, sources, arguments):
        with tempfile.TemporaryDirectory() as dossier:
            sortie = StringIO()
            with mock.patch.dict(main.SOURCES, sources, clear=True), \
                 mock.patch.object(main, "Client"), redirect_stdout(sortie):
                code = main.main(arguments + ["--dossier", dossier])
            fichiers = {p.name: p.read_text(encoding="utf-8-sig") for p in Path(dossier).iterdir()}
        return code, sortie.getvalue(), fichiers

    def test_une_source_en_erreur_n_arrete_pas_les_autres(self):
        guichet = FauxScraper("guichet-emplois", [ge(1, entreprise="A", lieu="Québec (QC)", source_partenaire="Talent.com")])
        jobboom = FauxScraper("jobboom", erreur=ValueError("format inattendu"))
        talent = FauxScraper("talent", [tc(9, entreprise="A", lieu="Québec City (QC)", description="D",
                                           latitude=46.8)])                 # plus complète que celle du Guichet
        code, sortie, fichiers = self.lancer(
            {"guichet": ("Guichet-Emplois", guichet), "jobboom": ("Jobboom", jobboom), "talent": ("Talent.com", talent)},
            ["--pages", "2", "--fiches", "3", "--csv"])

        self.assertEqual(code, 0)
        self.assertEqual(talent.appels, [(2, 3)])                          # lancé malgré l'erreur de Jobboom
        self.assertIn("erreur : ValueError: format inattendu", sortie)
        self.assertIn("2 offres reçues, 1 doublons fusionnés", sortie)
        self.assertIn("doublon : tc-9 = ge-1", sortie)

        unifie = json.loads(fichiers["offres_unifiees.json"])
        self.assertEqual(unifie["nombre"], 1)
        self.assertEqual(unifie["offres"][0]["doublons"], ["ge-1"])
        lignes = list(csv.reader(StringIO(fichiers["offres_unifiees.csv"]), delimiter=";"))
        self.assertEqual(len(lignes), 2)                                    # en-tête + 1 offre
        self.assertIn("offres_guichet_emplois.json", fichiers)              # fichier par source
        self.assertIn("offres_talent.csv", fichiers)                        # --csv : CSV par source
        self.assertNotIn("offres_jobboom.json", fichiers)                   # source vide : pas de fichier

    def test_option_sites(self):
        guichet, talent = FauxScraper("guichet-emplois", [ge(1)]), FauxScraper("talent", [tc(2)])
        self.lancer({"guichet": ("Guichet-Emplois", guichet), "talent": ("Talent.com", talent)},
                    ["--sites", "talent"])
        self.assertEqual(guichet.appels, [])
        self.assertEqual(talent.appels, [(1, 5)])                           # valeurs par défaut

    def test_bout_en_bout_avec_les_vrais_scrapers(self):
        """Les 3 vrais scrapers lisent les fixtures des lots 3 à 5 servies par un faux client."""
        from scrapers import guichet_emplois, jobboom, talent
        fixtures = Path(__file__).with_name("fixtures")
        lire = lambda nom: (fixtures / nom).read_text(encoding="utf-8")
        pages = {
            guichet_emplois.url_recherche(1): lire("ge_resultats.html"),
            "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50738681": lire("ge_fiche_directe.html"),
            jobboom.url_categorie(1): lire("jb_categorie.html"),
            "https://www.jobboom.com/fr/offre-emploi/technicien-informatique_innovmetric-logiciels-inc_p3698100":
                lire("jb_fiche.html"),
            talent.url_recherche(1): lire("tc_resultats.html"),
            "https://ca.talent.com/fr/view?id=640918690502021004": lire("tc_fiche.html"),
        }

        class ClientFixtures:
            def telecharger(self, url):
                return pages.get(url, "<html></html>")

        with tempfile.TemporaryDirectory() as dossier, redirect_stdout(StringIO()) as sortie, \
             mock.patch.object(main, "Client", return_value=ClientFixtures()):
            code = main.main(["--fiches", "1", "--dossier", dossier])
            unifie = json.loads((Path(dossier) / "offres_unifiees.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(unifie["nombre"], 3 + 2 + 1)        # Guichet 3, Jobboom 2, Talent 1 (l'autre sans titre)
        self.assertEqual({o["source"] for o in unifie["offres"]}, {"guichet-emplois", "jobboom", "talent"})
        self.assertIn("6 offres reçues, 0 doublons fusionnés", sortie.getvalue())

    def test_aucune_offre_code_1(self):
        vide = FauxScraper("talent", [])
        code, sortie, fichiers = self.lancer({"talent": ("Talent.com", vide)}, [])
        self.assertEqual(code, 1)
        self.assertIn("0 offre (refus ou page vide", sortie)
        self.assertEqual(json.loads(fichiers["offres_unifiees.json"])["nombre"], 0)


if __name__ == "__main__":
    unittest.main()
