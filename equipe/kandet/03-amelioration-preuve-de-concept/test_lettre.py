"""Tests hors ligne de la vérification d'une lettre de motivation (lettre.py). Lettres fictives."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fusion import aggregate_records
from lettre import (
    build_letter_report,
    check_letter,
    employer_mentioned,
    find_offer,
    letter_tips,
    title_mentioned,
)
from modele import AggregatedOffer, SourceRecord
from test_filtres_export import CollecteSimulee


def full_stack_offer(**changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id="50585958",
                url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50585958",
                title="développeur/développeuse Web full-stack",
                employer="Les technologies Duologiq",
            )
        ]
    )[0]
    item.technologies = ["JavaScript", "C#", ".NET", "HTML/CSS", "React", "SQL", "Git"]
    item.skills = ["Développement Web"]
    item.tasks = ["Déterminer et documenter avec les clients les exigences du site Web",
                  "Développer l’architecture du site Web",
                  "Gérer des incidents"]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


LETTRE = """Madame, Monsieur,
Je vous écris pour poser ma candidature au poste de [nom du poste]. Je souhaite développer des sites Web utiles.
J'ai réalisé une application Web avec React et une API en Python, avec Git et une base de données SQL.
Camille Exemple"""


class EmployerAndTitleTests(unittest.TestCase):
    def test_common_words_of_the_employer_do_not_count(self) -> None:
        # « les » et « technologies » sont dans la lettre, mais pas « Duologiq ».
        self.assertFalse(employer_mentioned("Les technologies me passionnent.", "Les technologies Duologiq"))
        self.assertTrue(employer_mentioned("Je veux rejoindre Duologiq.", "Les technologies Duologiq"))
        self.assertTrue(employer_mentioned("Merci à la Ville de Québec.", "Ville de Québec"))
        self.assertIsNone(employer_mentioned("Bonjour", ""))

    def test_title_needs_most_of_its_words(self) -> None:
        offer = full_stack_offer()
        # « développer » seul ne suffit pas : il manque « full » et « stack ».
        self.assertFalse(title_mentioned("Je souhaite développer des sites Web.", offer))
        self.assertTrue(title_mentioned("Je postule au poste de développeur Web full-stack.", offer))

    def test_employer_title_is_also_accepted(self) -> None:
        offer = full_stack_offer(original_title="Analyste applicatif")
        self.assertTrue(title_mentioned("Le poste d'analyste applicatif m'intéresse.", offer))


class CheckLetterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.offer = full_stack_offer()
        self.check = check_letter(LETTRE, self.offer)

    def test_what_is_found(self) -> None:
        self.assertFalse(self.check.employer_mentioned)
        self.assertFalse(self.check.title_mentioned)
        self.assertEqual(self.check.technologies_cited, ["React", "SQL", "Git"])
        self.assertEqual(self.check.technologies_missing, ["JavaScript", "C#", ".NET", "HTML/CSS"])
        self.assertEqual(self.check.skills_cited, ["Développement Web"])
        self.assertEqual(self.check.placeholders, ["[nom du poste]"])
        self.assertLess(self.check.word_count, 200)

    def test_keywords_keep_their_accents_and_use_word_beginnings(self) -> None:
        # « développer » est dans la lettre : « Développer » (tâche) n'est donc pas signalé.
        self.assertIn("déterminer", self.check.keywords_missing)
        self.assertIn("exigences", self.check.keywords_missing)
        self.assertNotIn("développer", self.check.keywords_missing)

    def test_other_placeholders(self) -> None:
        check = check_letter("Bonjour <Nom de l'entreprise>, je suis XXXX. Signature : ______", self.offer)
        self.assertEqual(check.placeholders, ["<Nom de l'entreprise>", "XXXX", "______"])

    def test_corrected_letter(self) -> None:
        good = LETTRE.replace("[nom du poste]", "développeur Web full-stack chez Les technologies Duologiq")
        check = check_letter(good, self.offer)
        self.assertTrue(check.employer_mentioned)
        self.assertTrue(check.title_mentioned)
        self.assertEqual(check.placeholders, [])


class TipsTests(unittest.TestCase):
    def test_tips_with_cv(self) -> None:
        offer = full_stack_offer()
        tips = letter_tips(check_letter(LETTRE, offer), offer, cv_technologies=["JavaScript", "React", "SQL", "Git"])
        self.assertEqual(tips[0], "Zones à remplir oubliées : [nom du poste].")
        self.assertIn("Nommez l'employeur (Les technologies Duologiq) et dites pourquoi il vous intéresse.", tips)
        self.assertIn("Indiquez clairement le poste visé : « développeur/développeuse Web full-stack ».", tips)
        self.assertTrue(any(tip.startswith("Ces technologies sont dans votre CV mais pas dans la lettre : JavaScript.") for tip in tips))
        self.assertTrue(any(tip.startswith("Demandées par l'offre, absentes de la lettre et du CV : C#, .NET, HTML/CSS.") for tip in tips))
        self.assertTrue(any("La lettre est courte" in tip for tip in tips))

    def test_tips_without_cv(self) -> None:
        offer = full_stack_offer()
        tips = letter_tips(check_letter(LETTRE, offer), offer)
        self.assertTrue(any(tip.startswith("Technologies de l'offre absentes de la lettre : JavaScript, C#, .NET, HTML/CSS.") for tip in tips))

    def test_long_letter_and_link_to_full_offer(self) -> None:
        offer = full_stack_offer(description="", original_url="https://www.jobillico.com/offre/1")
        tips = letter_tips(check_letter("mot " * 500, offer), offer)
        self.assertTrue(any("La lettre est longue (500 mots)" in tip for tip in tips))
        self.assertIn("Lisez l'annonce complète avant d'envoyer la lettre : https://www.jobillico.com/offre/1", tips)


class FindOfferTests(unittest.TestCase):
    def test_by_number_or_link(self) -> None:
        offers = [full_stack_offer()]
        self.assertIs(find_offer(offers, "50585958"), offers[0])
        self.assertIs(find_offer(offers, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50585958"), offers[0])
        self.assertIsNone(find_offer(offers, "99999999"))
        self.assertIsNone(find_offer(offers, ""))


class ReportTests(unittest.TestCase):
    def test_report(self) -> None:
        offer = full_stack_offer()
        check = check_letter(LETTRE, offer)
        report = build_letter_report(check, offer, letter_tips(check, offer))
        self.assertIn("# Vérification de ma lettre de motivation", report)
        self.assertIn("| Employeur cité | non |", report)
        self.assertIn("| Zones à remplir oubliées | [nom du poste] |", report)


class MainLetterTests(CollecteSimulee, unittest.TestCase):
    def test_letter_for_a_collected_offer(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            letter = Path(folder) / "lettre.txt"
            letter.write_text("Je postule chez Exemple au poste de développeur Web. Python.", encoding="utf-8")
            report = Path(folder) / "rapport-lettre.md"
            text = self.run_offline("--depuis", str(result_path), "--lettre", str(letter), "--offre", "101",
                                    "--rapport-lettre", str(report))
            self.assertTrue(report.exists())
        self.assertIn("=== Lettre lettre.txt pour « développeur Web/développeuse Web » (Exemple inc.) ===", text)
        self.assertIn("employeur cité : oui | poste cité : oui", text)

    def test_missing_or_unknown_offer(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            letter = Path(folder) / "lettre.txt"
            letter.write_text("Bonjour", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "Indiquez l'offre visée avec --offre"):
                self.run_offline("--depuis", str(result_path), "--lettre", str(letter))
            with self.assertRaisesRegex(SystemExit, "introuvable"):
                self.run_offline("--depuis", str(result_path), "--lettre", str(letter), "--offre", "12345678")


if __name__ == "__main__":
    unittest.main()
