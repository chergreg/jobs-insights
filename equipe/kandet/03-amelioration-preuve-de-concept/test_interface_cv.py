"""La comparaison avec un CV dans la page donne-t-elle les mêmes notes que Python ?

Le test exécute le script de la page (interface_cv.js) avec Node.js et compare
chaque note avec candidature.py. Si Node.js n'est pas installé, le test de
comparaison est sauté (les autres tests restent hors ligne et sans dépendance).
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from candidature import build_profile, rank_offers
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


if __name__ == "__main__":
    unittest.main()
