"""Tests hors ligne de l'aide à la candidature (candidature.py). Tous les CV sont fictifs."""

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from candidature import (
    build_profile,
    build_report,
    match_offer,
    rank_offers,
    read_cv,
    stage_offers,
    suggestions,
)
from fusion import aggregate_records
from modele import AggregatedOffer, SourceRecord
from test_filtres_export import CollecteSimulee


CV_ETUDIANT = """Camille Exemple (CV fictif)
Étudiante au DEC en Techniques de l'informatique
Recherche : stage en développement Web
Langages : Python, JavaScript, HTML/CSS, SQL. Outils : Git.
Projet : site Web en React avec une base de données PostgreSQL.
Langues : français, anglais"""

CV_TECHNICIEN = """Alex Exemple (CV fictif)
Technicien, 2 ans d'expérience en soutien technique
Stage chez une PME en 2024 (terminé)
Windows, Active Directory, Microsoft 365, réseaux informatiques
Langue : français"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>Camille Exemple</w:t></w:r></w:p>
<w:p><w:r><w:t>Langages :</w:t></w:r><w:r><w:tab/><w:t>Python, SQL</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Outils</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Git</w:t><w:br/><w:t>Linux</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>"""


def make_docx(path: Path) -> None:
    """Un .docx minimal : un dossier compressé avec word/document.xml."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", DOCUMENT_XML)


def offer(number: int, **changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id=str(number),
                url=f"https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{number}",
                title=f"poste {number}",
                employer="Exemple inc.",
            )
        ]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


class ReadCvTests(unittest.TestCase):
    def test_text_file_utf8_and_windows(self) -> None:
        with TemporaryDirectory() as folder:
            utf8 = Path(folder) / "cv.txt"
            utf8.write_text("Développeur Python", encoding="utf-8")
            ansi = Path(folder) / "cv-ansi.txt"
            ansi.write_bytes("Développeur Python".encode("cp1252"))
            self.assertEqual(read_cv(utf8), "Développeur Python")
            self.assertEqual(read_cv(ansi), "Développeur Python")

    def test_word_file(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "cv.docx"
            make_docx(path)
            text = read_cv(path)
        self.assertEqual(text.splitlines()[:2], ["Camille Exemple", "Langages : Python, SQL"])
        self.assertIn("Git\nLinux", text)  # texte d'un tableau, avec un saut de ligne

    def test_unreadable_files_give_a_clear_message(self) -> None:
        with TemporaryDirectory() as folder:
            pdf = Path(folder) / "cv.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            with self.assertRaisesRegex(ValueError, "Enregistrez le CV en .docx"):
                read_cv(pdf)
            fake = Path(folder) / "faux.docx"
            fake.write_text("pas un fichier Word", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pas un fichier Word"):
                read_cv(fake)


class ProfileTests(unittest.TestCase):
    def test_student_looking_for_a_stage(self) -> None:
        profile = build_profile(CV_ETUDIANT)
        for name in ("Python", "JavaScript", "HTML/CSS", "SQL", "Git", "React", "PostgreSQL"):
            self.assertIn(name, profile.technologies)
        self.assertIn("Développement Web", profile.skills)
        self.assertEqual((profile.years, profile.level), (0.0, "débutant"))
        self.assertTrue(profile.wants_stage)
        self.assertEqual(profile.languages, ["Français", "Anglais"])
        self.assertFalse(profile.has_bachelor)

    def test_past_internship_is_not_a_stage_search(self) -> None:
        profile = build_profile(CV_TECHNICIEN)
        self.assertEqual((profile.years, profile.level), (2.0, "intermédiaire"))
        self.assertFalse(profile.wants_stage)
        self.assertEqual(profile.languages, ["Français"])
        self.assertIn("Soutien aux utilisateurs", profile.skills)

    def test_nothing_is_guessed(self) -> None:
        profile = build_profile("Jean Exemple, personne motivée.")
        self.assertEqual((profile.technologies, profile.skills, profile.years, profile.level), ([], [], None, ""))


class MatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.student = build_profile(CV_ETUDIANT)

    def test_offer_without_information_is_not_scored(self) -> None:
        self.assertIsNone(match_offer(self.student, offer(1)))

    def test_shared_and_missing_lists(self) -> None:
        match = match_offer(self.student, offer(1, technologies=["Python", "SQL", "Docker"], level="débutant"))
        self.assertEqual(match.shared_technologies, ["Python", "SQL"])
        self.assertEqual(match.missing_technologies, ["Docker"])
        self.assertIn("2 technologie(s) sur 3 en commun", match.reasons)
        self.assertIn("niveau débutant : accessible", match.reasons)

    def test_level_above_the_cv_lowers_the_score(self) -> None:
        base = dict(technologies=["Python", "SQL", "Git", "React"])
        accessible = match_offer(self.student, offer(1, level="débutant", **base)).score
        one_above = match_offer(self.student, offer(2, level="intermédiaire", **base)).score
        two_above = match_offer(self.student, offer(3, level="avancé", **base)).score
        self.assertEqual(accessible, 100)
        self.assertGreater(accessible, one_above)
        self.assertGreater(one_above, two_above)

    def test_offer_with_little_information_cannot_reach_the_top(self) -> None:
        thin = match_offer(self.student, offer(1, skills=["Développement Web"], level="débutant"))
        rich = match_offer(self.student, offer(2, technologies=["Python", "SQL", "Git", "React", "Docker"], level="débutant"))
        self.assertEqual(thin.score, 70)
        self.assertIn("peu d'information dans l'offre (1 élément(s))", thin.reasons)
        self.assertGreater(rich.score, thin.score)

    def test_stage_bonus_only_for_a_stage_search(self) -> None:
        stage = offer(1, technologies=["Python"], level="débutant", stage_status="confirmed_stage")
        same_without_stage = offer(2, technologies=["Python"], level="débutant")
        self.assertEqual(
            match_offer(self.student, stage).score,
            match_offer(self.student, same_without_stage).score + 10,
        )
        technician = build_profile(CV_TECHNICIEN)
        self.assertNotIn("stage, comme demandé dans le CV", match_offer(technician, stage).reasons)

    def test_ranking_and_offers_without_information(self) -> None:
        offers = [
            offer(1, technologies=["Docker"], level="avancé"),
            offer(2, technologies=["Python", "SQL", "Git", "React"], level="débutant"),
            offer(3),
            offer(4, skills=["Développement Web"], stage_status="confirmed_stage"),
        ]
        matches, without_information = rank_offers(self.student, offers)
        self.assertEqual([m.offer.source_records[0].source_id for m in matches], ["2", "4", "1"])
        self.assertEqual(without_information, 1)
        self.assertEqual([(rank, m.offer.source_records[0].source_id) for rank, m in stage_offers(matches)], [(2, "4")])


class SuggestionTests(unittest.TestCase):
    TODAY = date(2026, 11, 20)

    def tips(self, profile_text: str, **changes: object) -> list[str]:
        profile = build_profile(profile_text)
        return suggestions(profile, match_offer(profile, offer(1, **changes)), today=self.TODAY)

    def test_technologies_to_highlight_and_to_learn(self) -> None:
        tips = self.tips(CV_ETUDIANT, technologies=["Python", "Docker"])
        self.assertTrue(tips[0].startswith("Mettez en avant Python"))
        self.assertTrue(any("Docker. Ajoutez-la seulement si vous la connaissez" in tip for tip in tips))
        tips = self.tips(CV_ETUDIANT, technologies=["Python", "Docker", "Azure"])
        self.assertTrue(any("Docker, Azure. Ajoutez-les seulement si vous les connaissez" in tip for tip in tips))

    def test_bilingual_offer_and_french_only_cv(self) -> None:
        tips = self.tips(CV_TECHNICIEN, technologies=["Windows"], languages=["Bilingue"])
        self.assertIn("Langue(s) demandée(s) par l'offre et absente(s) du CV : Anglais.", tips)
        tips = self.tips(CV_ETUDIANT, technologies=["Python"], languages=["Bilingue"])
        self.assertFalse(any(tip.startswith("Langue") for tip in tips))

    def test_experience_and_studies(self) -> None:
        tips = self.tips(CV_ETUDIANT, technologies=["Python"], experience="1 an à moins de 2 ans",
                         experience_years_min=1.0, education="Baccalauréat, ou expérience équivalente")
        self.assertTrue(any("1 an à moins de 2 ans d'expérience" in tip for tip in tips))
        self.assertTrue(any(tip.startswith("Études demandées : Baccalauréat") for tip in tips))

    def test_tasks_and_link_to_full_offer(self) -> None:
        tips = self.tips(CV_ETUDIANT, technologies=["Python"], tasks=["Développer des API", "Tester le code"],
                         original_url="https://www.jobillico.com/offre/1")
        self.assertIn("Reliez vos projets à ces tâches de l'offre : Développer des API; Tester le code.", tips)
        self.assertIn("La description complète est seulement sur le site d'origine : https://www.jobillico.com/offre/1", tips)

    def test_stage_and_expiration_notes(self) -> None:
        tips = self.tips(CV_ETUDIANT, technologies=["Python"], expires_at=self.TODAY.isoformat())
        self.assertIn("Cette offre n'est pas présentée comme un stage : demandez à l'employeur s'il accepte les stagiaires.", tips)
        self.assertIn("Postulez vite : l'offre expire aujourd'hui (2026-11-20).", tips)
        soon = (self.TODAY + timedelta(days=3)).isoformat()
        self.assertIn(f"Postulez vite : l'offre expire le {soon} (dans 3 jours).",
                      self.tips(CV_ETUDIANT, technologies=["Python"], expires_at=soon))

    def test_no_tip_about_technologies_when_there_are_none(self) -> None:
        tips = self.tips(CV_TECHNICIEN, skills=["Réseaux"])
        self.assertFalse(any("Mettez en avant" in tip or "mentionne aussi" in tip for tip in tips))


class ReportTests(unittest.TestCase):
    def test_report_content(self) -> None:
        profile = build_profile(CV_ETUDIANT)
        offers = [
            offer(1, original_title="Développeur | Web", technologies=["Python", "SQL"], city="Québec", level="débutant"),
            offer(2, technologies=["Docker"], stage_status="confirmed_stage"),
        ]
        matches, without_information = rank_offers(profile, offers)
        report = build_report(profile, matches, without_information, "aucun filtre", top=5, detailed=1,
                              today=date(2026, 11, 20))
        self.assertIn("- Cherche un stage : oui", report)
        self.assertIn("| 1 | ", report)
        self.assertIn("[Développeur / Web](https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/1)", report)
        self.assertIn("### Stages dans le classement", report)
        self.assertIn("## 1. Développeur | Web — Exemple inc.", report)
        self.assertNotIn("## 2.", report)  # une seule offre détaillée


class MainCvTests(CollecteSimulee, unittest.TestCase):
    def test_cv_ranking_and_report(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            cv_path = Path(folder) / "cv.txt"
            cv_path.write_text(CV_ETUDIANT, encoding="utf-8")
            report_path = Path(folder) / "rapport.md"
            text = self.run_offline("--depuis", str(result_path), "--cv", str(cv_path), "--rapport-cv", str(report_path))
            report = report_path.read_text(encoding="utf-8")

        self.assertIn("=== Comparaison avec le CV cv.txt ===", text)
        self.assertIn(" 1. [", text)
        self.assertIn("Stages dans le classement : n° 1 Software Engineer Intern", text)
        self.assertIn("# Offres les plus proches de mon CV", report)

    def test_pdf_cv_stops_with_a_clear_message(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            pdf = Path(folder) / "cv.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            with self.assertRaises(SystemExit) as error:
                self.run_offline("--depuis", str(result_path), "--cv", str(pdf))
        self.assertIn("Enregistrez le CV en .docx", str(error.exception))


if __name__ == "__main__":
    unittest.main()
