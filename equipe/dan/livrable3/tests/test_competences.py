"""Tests hors ligne de competences.py (compétences TI et statut de stage)."""

import unittest

from competences import CONFIRME, NON_INDIQUE, POSSIBLE, detecter_competences, statut_stage


class TestCompetences(unittest.TestCase):
    def test_competences_triees_sans_double(self):
        self.assertEqual(detecter_competences("Développeur Python", "Python, Docker et SQL ; python encore."),
                         ["Docker", "Python", "SQL"])

    def test_faux_positifs_francais_evites(self):
        texte = ("Avoir une vue d'ensemble, un esprit agile, le permis de classe C. "
                 "Notre gîte accueille les nouveaux. Chaque node du réseau est surveillé.")
        self.assertEqual(detecter_competences(texte), [])

    def test_node_js_n_est_pas_javascript(self):
        self.assertEqual(detecter_competences("API en Node.js"), ["Node.js"])
        self.assertEqual(detecter_competences("JS, React et NodeJS"), ["JavaScript", "Node.js", "React"])

    def test_java_different_de_javascript(self):
        self.assertEqual(detecter_competences("JavaScript seulement"), ["JavaScript"])
        self.assertEqual(detecter_competences("Java et JavaScript"), ["Java", "JavaScript"])

    def test_langages_a_symboles(self):
        self.assertEqual(detecter_competences("C#, C++ et ASP.NET"), [".NET", "C#", "C++"])
        self.assertEqual(detecter_competences("Programmation C embarquée"), ["C"])

    def test_support_ti(self):
        texte = "Gestion Active Directory, Office 365, postes Windows 11 et réseau TCP/IP."
        self.assertEqual(detecter_competences(texte), ["Active Directory", "Microsoft 365", "TCP/IP", "Windows"])

    def test_agile_avec_contexte_seulement(self):
        self.assertEqual(detecter_competences("Connaissance des méthodologies AGILE"), ["Agile"])
        self.assertEqual(detecter_competences("Une personne agile et polyvalente"), [])

    def test_sans_texte_liste_vide(self):
        self.assertEqual(detecter_competences(None, ""), [])


class TestStatutStage(unittest.TestCase):
    def test_stage_dans_le_titre(self):
        self.assertEqual(statut_stage("Stagiaire en développement Web"), CONFIRME)
        self.assertEqual(statut_stage("Software Engineer Intern"), CONFIRME)

    def test_stage_deja_detecte_par_le_scraper(self):
        self.assertEqual(statut_stage("Technicien", None, est_stage=True), CONFIRME)

    def test_indice_dans_la_description(self):
        # Vraie offre Talent.com (tc-634537925073176368, 2026-11-18) : le titre ne dit pas « stage ».
        self.assertEqual(statut_stage("Technicien(ne) informatique", "Statut : Stage rémunéré / Temporaire"), POSSIBLE)
        self.assertEqual(statut_stage("Analyste", "Vous devez être inscrit à temps plein au cégep."), POSSIBLE)
        self.assertEqual(statut_stage("Developer", "This internship position starts in May."), POSSIBLE)

    def test_rien_d_indique(self):
        self.assertEqual(statut_stage("Technicien informatique", "Poste permanent à temps plein."), NON_INDIQUE)
        self.assertEqual(statut_stage("Technicien informatique"), NON_INDIQUE)
        self.assertEqual(statut_stage("Analyste", "Mise en scène du projet."), NON_INDIQUE)   # « scène » ≠ stage


if __name__ == "__main__":
    unittest.main()
