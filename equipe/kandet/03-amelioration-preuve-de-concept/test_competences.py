"""Tests hors ligne du module competences (technologies, expérience, niveau, stages, résumé)."""

import unittest

from competences import (
    SUMMARY_MAX_LENGTH,
    enrich_offer,
    experience_level,
    experience_years,
    find_skills,
    find_technologies,
    short_summary,
)
from fusion import aggregate_records
from modele import SourceRecord


class TechnologyTests(unittest.TestCase):
    def test_no_false_positives_in_french(self) -> None:
        self.assertEqual(find_technologies("Une vue d'ensemble du projet, niveau C."), [])
        self.assertNotIn("Java", find_technologies("Bonne maîtrise de JavaScript"))
        self.assertNotIn("JavaScript", find_technologies("API en Node.js"))
        self.assertNotIn("Go", find_technologies("Vous allez go de l'avant"))

    def test_detects_languages_with_symbols(self) -> None:
        found = find_technologies("C#, C++ et le langage C; interface en Vue.js")
        self.assertEqual(found, ["C#", "C++", "C", "Vue.js"])

    def test_common_stack(self) -> None:
        found = find_technologies("Python, Django, PostgreSQL, Docker, Kubernetes sur AWS, Git et CI/CD")
        for name in ("Python", "Django", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Git", "CI/CD"):
            self.assertIn(name, found)

    def test_microsoft_tools(self) -> None:
        found = find_technologies("Soutien Office 365, Active Directory, SharePoint et Power BI")
        self.assertEqual(found, ["Active Directory", "Microsoft 365", "SharePoint", "Power BI"])

    def test_skills_without_accents(self) -> None:
        found = find_skills("Offrir le soutien technique, gérer les réseaux informatiques et la sécurité informatique")
        self.assertEqual(found, ["Soutien aux utilisateurs", "Réseaux", "Cybersécurité"])


class ExperienceTests(unittest.TestCase):
    def test_guichet_field(self) -> None:
        self.assertEqual(experience_years("5 ans ou plus"), 5.0)
        self.assertEqual(experience_years("1 an à moins de 2 ans"), 1.0)
        self.assertEqual(experience_years("7 mois à moins d'un an"), 0.6)
        self.assertEqual(experience_years("Aucune expérience"), 0.0)
        self.assertEqual(experience_years("Expérience un atout"), 0.0)

    def test_description_when_field_is_empty(self) -> None:
        self.assertEqual(experience_years("", "Minimum de 3 ans d'expérience en .NET"), 3.0)
        self.assertEqual(experience_years("", "You have 5+ years of experience with React."), 5.0)
        self.assertEqual(experience_years("", "De 3 à 5 ans d’expérience pertinente"), 3.0)

    def test_nothing_written(self) -> None:
        self.assertIsNone(experience_years("", "Équipe dynamique, horaire flexible."))

    def test_levels_from_years(self) -> None:
        self.assertEqual(experience_level("analyste", 5.0), "avancé")
        self.assertEqual(experience_level("analyste", 2.0), "intermédiaire")
        self.assertEqual(experience_level("analyste", 1.0), "débutant")
        self.assertEqual(experience_level("analyste", 0.0), "débutant")
        self.assertEqual(experience_level("analyste", None), "")

    def test_title_wins_over_years(self) -> None:
        self.assertEqual(experience_level("Développeur Senior", None), "avancé")
        self.assertEqual(experience_level("Développeur junior", 5.0), "débutant")
        self.assertEqual(experience_level("Développeur - Niveau Intermédiaire", None), "intermédiaire")


class SummaryTests(unittest.TestCase):
    def test_uses_first_two_tasks(self) -> None:
        self.assertEqual(
            short_summary(["Installer les postes", "Répondre aux appels", "Faire l'inventaire"], ""),
            "Installer les postes; Répondre aux appels",
        )

    def test_guichet_description_starts_after_tasks_label(self) -> None:
        description = "Études: Baccalauréat. Informatique. Tâches: Coordonner les projets. Évaluer des logiciels. Expérience: 5 ans."
        self.assertEqual(short_summary([], description), "Coordonner les projets. Évaluer des logiciels.")

    def test_repeated_title_is_removed(self) -> None:
        self.assertEqual(
            short_summary([], "Spécialiste des données Ce poste relève du directeur.", "Spécialiste des données"),
            "Ce poste relève du directeur.",
        )

    def test_long_text_is_cut_at_a_sentence(self) -> None:
        first = "Première phrase assez longue pour remplir l'espace " + "a" * 150 + "."
        second = "Deuxième phrase " + "b" * 200 + "."
        summary = short_summary([], f"{first} {second}")
        self.assertLessEqual(len(summary), SUMMARY_MAX_LENGTH)
        self.assertEqual(summary, first)

    def test_one_very_long_sentence_ends_with_ellipsis(self) -> None:
        summary = short_summary([], "mot " * 200)
        self.assertLessEqual(len(summary), SUMMARY_MAX_LENGTH + 2)
        self.assertTrue(summary.endswith("…"))

    def test_empty(self) -> None:
        self.assertEqual(short_summary([], ""), "")


def offer_from(**changes: object):
    values: dict[str, object] = {
        "source": "Guichet-Emplois",
        "source_id": "1",
        "url": "https://example.test/1",
        "title": "développeur Web/développeuse Web",
        "employer": "Exemple inc.",
        "location": "Québec (QC)",
    }
    values.update(changes)
    return aggregate_records([SourceRecord(**values)])[0]  # type: ignore[arg-type]


class EnrichOfferTests(unittest.TestCase):
    def test_guichet_stage_field_is_a_confirmed_stage(self) -> None:
        offer = offer_from(description="Expérience: 1 an. Stage: Ce poste est un stage rémunéré qui favorise la formation.")
        enrich_offer(offer)
        self.assertEqual(offer.stage_status, "confirmed_stage")
        self.assertEqual(offer.stage_signals, ["guichet_stage_field"])

    def test_stage_found_in_original_title(self) -> None:
        offer = offer_from(original_title="Stagiaire en développement logiciel - Été 2027")
        enrich_offer(offer)
        self.assertEqual(offer.stage_status, "confirmed_stage")
        self.assertEqual(offer.level, "débutant")

    def test_paid_stage_in_description_is_possible(self) -> None:
        offer = offer_from(description="Nous offrons un stage rémunéré en développement pour l'été.")
        enrich_offer(offer)
        self.assertEqual(offer.stage_status, "possible_stage")

    def test_regular_job_stays_not_indicated(self) -> None:
        offer = offer_from(description="Poste permanent. Développer des applications en C# et SQL Server.", experience="2 ans à moins de 3 ans")
        enrich_offer(offer)
        self.assertEqual(offer.stage_status, "not_indicated")
        self.assertEqual(offer.technologies, ["C#", "SQL", "SQL Server"])
        self.assertEqual((offer.experience_years_min, offer.level), (2.0, "intermédiaire"))
        self.assertEqual(offer.summary, "Poste permanent. Développer des applications en C# et SQL Server.")

    def test_remotive_tags_are_used(self) -> None:
        offer = offer_from(source="Remotive", title="Backend Engineer", tags=["python", "docker"])
        enrich_offer(offer)
        self.assertEqual(offer.technologies, ["Python", "Docker"])


if __name__ == "__main__":
    unittest.main()
