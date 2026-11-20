"""La page donne-t-elle les mêmes résultats que Python pour un CV et pour une lettre ?

Le test exécute le script de la page (interface_cv.js) avec Node.js et compare
chaque note avec candidature.py, et chaque vérification de lettre avec lettre.py.
Si Node.js n'est pas installé, ces tests sont sautés (les autres tests restent
hors ligne et sans dépendance).
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from candidature import build_profile, rank_offers
from lettre import check_letter, letter_tips
from fusion import aggregate_records
from interface import CV_SCRIPT_FILE, browser_rules, build_html, offer_to_row
from modele import AggregatedOffer, SourceRecord


def offer(number: int, **changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id=str(number),
                url=f"https://example.test/{number}",
                title=f"poste {number:02d}",
                employer="Exemple inc.",
            )
        ]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


OFFERS = [
    offer(1, technologies=["Python", "SQL", "Git", "React"], skills=["Développement Web"], level="débutant"),
    offer(2, technologies=["C#", ".NET", "SQL Server"], level="intermédiaire"),
    offer(3, technologies=["Windows", "Active Directory"], skills=["Soutien aux utilisateurs", "Réseaux"], level="avancé"),
    offer(4, skills=["Développement Web"], stage_status="confirmed_stage"),
    offer(5),  # aucune information : pas classée
    offer(6, technologies=["Python"], level="débutant"),
    offer(7, technologies=["JavaScript", "HTML/CSS", "SQL", "Git", "Linux", "PHP"], skills=["Bases de données"]),
    offer(8, technologies=["Java", "Spring"], level="avancé", stage_status="possible_stage"),
]

CVS = {
    "etudiant": "Étudiante au DEC. Recherche : stage en développement Web. Python, SQL, Git, React, "
                "JavaScript, HTML/CSS, Linux, bases de données. Langues : français, anglais.",
    "technicien": "Technicien, 3 ans d'expérience en soutien technique. Windows, Active Directory, "
                  "réseaux informatiques, Microsoft 365. Français.",
    "senior": "Développeur, minimum de 6 ans d'expérience en C#, .NET, SQL Server et Java.",
    "vide": "Personne motivée et curieuse.",
}

LETTRES = {
    "a_completer": "Madame, Monsieur, je postule au poste de [nom du poste]. J'ai utilisé Python, SQL et Git "
                   "dans un projet Web. Camille Exemple",
    "complete": "Bonjour, je postule au poste 01 chez Exemple. J'ai développé des applications avec Python, "
                "SQL, Git et React, en équipe, avec des bases de données. J'ai participé aux réunions. " * 12,
    "trous": "Bonjour <Nom de l'entreprise>, je suis XXXX. Signature : ______",
}


def offers_for_letters() -> list[AggregatedOffer]:
    """Offres variées : tâches ou résumé, avec ou sans description, titre de l'employeur, employeur inconnu."""
    return [
        offer(1, technologies=["Python", "SQL", "Docker"], skills=["Développement Web"],
              # « partenaires » et « participé » se ressemblent sur 4 lettres, pas sur 5 : le test vérifie la règle exacte.
              tasks=["Déterminer les exigences du site Web", "Développer des API", "Rencontrer les partenaires"],
              description="texte"),
        offer(2, original_title="Analyste applicatif", technologies=["Java"], summary="Analyser les besoins et rédiger la documentation.",
              original_url="https://www.jobillico.com/offre/2"),
        offer(3, employer="", technologies=["Windows"], skills=["Réseaux"], tasks=["Gérer des incidents"]),
    ]


class RulesInPageTests(unittest.TestCase):
    def test_rules_in_the_page_are_the_python_rules(self) -> None:
        page = build_html(OFFERS, generated_on="2026-11-20")
        match = re.search(r'<script type="application/json" id="regles">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match)
        rules = json.loads(match.group(1))
        self.assertEqual(rules, json.loads(json.dumps(browser_rules())))
        self.assertEqual(len(rules["technologies"]), 51)

    def test_script_is_included_and_safe(self) -> None:
        page = build_html(OFFERS, generated_on="2026-11-20")
        self.assertIn("function creerComparateur", page)
        self.assertIn("async function texteDocx", page)
        self.assertNotIn("innerHTML", CV_SCRIPT_FILE.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé : comparaison JavaScript sautée")
class SameScoresAsPythonTests(unittest.TestCase):
    def run_javascript(self, rows: list[dict[str, object]]) -> dict[str, object]:
        script = """
const { creerComparateur } = require(process.argv[2]);
const donnees = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const c = creerComparateur(donnees.regles);
const sortie = {};
for (const [nom, texte] of Object.entries(donnees.cvs)) {
  const p = c.profil(texte);
  const { resultats, sansInfo } = c.classer(p, donnees.offres);
  sortie[nom] = { profil: [p.technos, p.competences, p.annees, p.niveau, p.langues, p.chercheStage],
                  classement: resultats.map((r) => [r.offre.id, r.note]), sansInfo };
}
console.log(JSON.stringify(sortie));
"""
        with TemporaryDirectory() as folder:
            data = Path(folder) / "donnees.json"
            data.write_text(json.dumps({"regles": browser_rules(), "cvs": CVS, "offres": rows}, ensure_ascii=False), encoding="utf-8")
            runner = Path(folder) / "essai.js"
            runner.write_text(script, encoding="utf-8")
            result = subprocess.run(
                ["node", str(runner), str(CV_SCRIPT_FILE), str(data)],
                capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
            )
        return json.loads(result.stdout)

    def test_same_profiles_scores_and_order(self) -> None:
        rows = [offer_to_row(item, number) for number, item in enumerate(OFFERS, start=1)]
        javascript = self.run_javascript(rows)
        for name, text in CVS.items():
            with self.subTest(cv=name):
                profile = build_profile(text)
                matches, without_information = rank_offers(profile, OFFERS)
                expected = [[OFFERS.index(match.offer) + 1, match.score] for match in matches]
                self.assertEqual(
                    javascript[name]["profil"],
                    [profile.technologies, profile.skills, profile.years, profile.level, profile.languages, profile.wants_stage],
                )
                self.assertEqual(javascript[name]["classement"], expected)
                self.assertEqual(javascript[name]["sansInfo"], without_information)

    def test_same_letter_checks_and_tips(self) -> None:
        offers = offers_for_letters()
        rows = [offer_to_row(item, number) for number, item in enumerate(offers, start=1)]
        cv_technologies = build_profile(CVS["etudiant"]).technologies
        script = """
const { creerVerificateurLettre } = require(process.argv[2]);
const d = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const v = creerVerificateurLettre(d.regles);
const sortie = {};
for (const [nom, texte] of Object.entries(d.lettres)) for (const o of d.offres) {
  const r = v.verifier(texte, o);
  sortie[nom + "|" + o.id] = [[r.nbMots, r.employeurCite, r.posteCite, r.technosCitees, r.technosAbsentes, r.competencesCitees,
    r.competencesAbsentes, r.motsAbsents, r.zones], v.suggestions(r, o, null), v.suggestions(r, o, d.cv)];
}
console.log(JSON.stringify(sortie));
"""
        with TemporaryDirectory() as folder:
            data = Path(folder) / "donnees.json"
            data.write_text(json.dumps({"regles": browser_rules(), "lettres": LETTRES, "offres": rows, "cv": cv_technologies},
                                       ensure_ascii=False), encoding="utf-8")
            runner = Path(folder) / "essai.js"
            runner.write_text(script, encoding="utf-8")
            result = subprocess.run(["node", str(runner), str(CV_SCRIPT_FILE), str(data)],
                                    capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
        javascript = json.loads(result.stdout)
        for name, text in LETTRES.items():
            for number, item in enumerate(offers, start=1):
                with self.subTest(lettre=name, offre=number):
                    check = check_letter(text, item)
                    expected = [
                        [check.word_count, check.employer_mentioned, check.title_mentioned, check.technologies_cited,
                         check.technologies_missing, check.skills_cited, check.skills_missing, check.keywords_missing,
                         check.placeholders],
                        letter_tips(check, item),
                        letter_tips(check, item, cv_technologies),
                    ]
                    self.assertEqual(javascript[f"{name}|{number}"], expected)


if __name__ == "__main__":
    unittest.main()
