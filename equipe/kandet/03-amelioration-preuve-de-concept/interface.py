"""Page HTML pour chercher les offres dans un navigateur (sans serveur, sans Internet).

La page est un seul fichier : les offres sont incluses en JSON, et un petit
programme JavaScript fait la recherche, les filtres, le tri et l'export CSV.
"""

from __future__ import annotations

from datetime import date
import html
import json
from pathlib import Path

from modele import AggregatedOffer


STAGE_LABELS = {"confirmed_stage": "Stage", "possible_stage": "Stage possible"}
# Types d'emploi de Remotive, écrits en anglais dans l'API.
JOB_TYPE_LABELS = {
    "full_time": "Temps plein",
    "part_time": "Temps partiel",
    "contract": "Contrat",
    "freelance": "Travail autonome",
    "internship": "Stage",
    "other": "",
}
TEMPLATE_FILE = Path(__file__).with_name("interface_modele.html")
CV_SCRIPT_FILE = Path(__file__).with_name("interface_cv.js")


def browser_rules() -> dict[str, object]:
    """Les expressions de competences.py et candidature.py, copiées telles quelles dans la page.

    Ainsi la comparaison avec un CV dans le navigateur utilise exactement les mêmes règles
    que `main.py --cv` (vérifié par test_interface_cv.py).
    """
    from candidature import LANGUAGE_WORDS, STAGE_WANTED_PATTERN, STUDENT_PATTERN
    from competences import DESCRIPTION_EXPERIENCE, SKILL_PATTERNS, TECHNOLOGY_PATTERNS

    return {
        "technologies": TECHNOLOGY_PATTERNS,
        "competences": SKILL_PATTERNS,
        "experienceDescription": DESCRIPTION_EXPERIENCE.pattern,
        "etudiant": STUDENT_PATTERN.pattern,
        "stageRecherche": STAGE_WANTED_PATTERN.pattern,
        "langues": LANGUAGE_WORDS,
    }


def offer_to_row(offer: AggregatedOffer, number: int) -> dict[str, object]:
    """Garde seulement ce que la page affiche ou filtre."""
    first = offer.source_records[0] if offer.source_records else None
    return {
        "id": number,
        "titre": offer.original_title or offer.title,
        "titreCnp": offer.title if offer.original_title and offer.original_title != offer.title else "",
        "titreTri": offer.title,  # même ordre qu'en Python quand deux notes sont égales
        "employeur": offer.employer,
        "ville": offer.city,
        "region": offer.region,
        "lieu": offer.location,
        "salMin": offer.salary_min,
        "salMax": offer.salary_max,
        "unite": offer.salary_unit,
        "devise": offer.salary_currency,
        "negocier": offer.salary_negotiable,
        "niveau": offer.level,
        "experience": offer.experience,
        "technos": offer.technologies,
        "competences": offer.skills,
        "stage": STAGE_LABELS.get(offer.stage_status, ""),
        "type": JOB_TYPE_LABELS.get(offer.job_type, offer.job_type),
        "mode": offer.work_mode,
        "publiee": offer.published_at,
        "expire": offer.expires_at,
        "resume": offer.summary,
        "etudes": offer.education,
        "langues": offer.languages,
        "sites": [record.origin_site or record.source for record in offer.source_records],
        "lien": first.url if first else "",
        "lienOrigine": offer.original_url,
    }


def _json_for_html(rows: object) -> str:
    """JSON sûr à placer dans une balise <script> (« </ » ne peut pas fermer la balise)."""
    return json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")


def build_html(offers: list[AggregatedOffer], generated_on: str | None = None) -> str:
    rows = [offer_to_row(offer, number) for number, offer in enumerate(offers, start=1)]
    generated_on = generated_on or date.today().isoformat()
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    cv_script = CV_SCRIPT_FILE.read_text(encoding="utf-8").replace("</", "<\\/")
    return (
        template.replace("{{DATE}}", html.escape(generated_on))
        .replace("{{NOMBRE}}", str(len(rows)))
        .replace("{{REGLES}}", _json_for_html(browser_rules()))
        .replace("{{SCRIPT_CV}}", cv_script)
        .replace("{{DONNEES}}", _json_for_html(rows))
    )


def write_html(offers: list[AggregatedOffer], path: Path, generated_on: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(offers, generated_on), encoding="utf-8")
