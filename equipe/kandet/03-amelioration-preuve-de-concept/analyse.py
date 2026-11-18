"""Analyse des offres : détection des stages et statistiques."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import re
from statistics import median

from modele import AggregatedOffer
from texte import normalize


TOP_SIZE = 10
EXPIRING_DAYS = 7


STAGE_PATTERN = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|work[\s-]?terms?)\b",
    flags=re.IGNORECASE,
)
STAGE_DESCRIPTION_PATTERN = re.compile(
    r"\b(?:internship|intern|co[\s-]?op|work[\s-]?term)\s+"
    r"(?:position|role|program|opportunity|placement)\b"
    r"|\b(?:student|students)\s+(?:intern|position|role|placement)\b"
    r"|\b(?:stage|stagiaire)\s+(?:en|de|du|d['’]|remunere)\b",
    flags=re.IGNORECASE,
)
STUDENT_ELIGIBILITY_PATTERN = re.compile(
    r"\b(?:currently\s+enrolled|enrolled\s+(?:in|at)|"
    r"must\s+be\s+(?:a\s+)?student|student\s+status|required\s+to\s+be\s+enrolled|"
    r"etre\s+(?:inscrit|inscrite|etudiant|etudiante)|"
    r"doit\s+etre\s+(?:inscrit|inscrite|etudiant|etudiante))\b",
    flags=re.IGNORECASE,
)


def classify_stage(title: str, job_type: str, description: str) -> tuple[str, list[str]]:
    """Classe une offre : stage confirmé, stage possible ou non indiqué."""
    normalized_job_type = normalize(job_type).replace("_", " ")
    if normalized_job_type in {"internship", "intern", "co op", "stage", "stagiaire"}:
        return "confirmed_stage", ["explicit_internship_job_type"]
    if STAGE_PATTERN.search(normalize(title)):
        return "confirmed_stage", ["stage_term_in_title"]
    normalized_description = normalize(description)
    if STAGE_DESCRIPTION_PATTERN.search(normalized_description):
        return "possible_stage", ["stage_role_in_description"]
    if STUDENT_ELIGIBILITY_PATTERN.search(normalized_description):
        return "possible_stage", ["student_eligibility_in_description"]
    return "not_indicated", []


def salary_statistics(offers: list[AggregatedOffer]) -> dict[str, dict[str, object]]:
    """Statistiques de salaire, séparées par devise et par unité (« CAD / année »).

    On ne mélange jamais un taux horaire et un salaire annuel. Pour chaque offre :
    - la valeur basse est salary_min ;
    - la valeur haute est salary_max, ou salary_min s'il n'y a pas de maximum.
    """
    groups: dict[str, list[AggregatedOffer]] = {}
    for offer in offers:
        if offer.salary_min is None or not offer.salary_unit:
            continue
        key = f"{offer.salary_currency or 'devise non précisée'} / {offer.salary_unit}"
        groups.setdefault(key, []).append(offer)

    result: dict[str, dict[str, object]] = {}
    for key, group in sorted(groups.items(), key=lambda item: -len(item[1])):
        lows = [offer.salary_min for offer in group if offer.salary_min is not None]
        highs = [offer.salary_max if offer.salary_max is not None else offer.salary_min for offer in group]
        result[key] = {
            "offers": len(group),
            "lowest": min(lows),
            "highest": max(value for value in highs if value is not None),
            "median_low": round(median(lows), 2),
        }
    return result


def expiring_soon(offers: list[AggregatedOffer], today: date, days: int = EXPIRING_DAYS) -> list[dict[str, str]]:
    """Offres dont la date d'expiration tombe dans les prochains jours (aujourd'hui compris)."""
    limit = today + timedelta(days=days)
    soon = []
    for offer in offers:
        try:
            expires = date.fromisoformat(offer.expires_at)
        except ValueError:
            continue
        if today <= expires <= limit:
            soon.append({"expires_at": offer.expires_at, "title": offer.title, "employer": offer.employer})
    return sorted(soon, key=lambda item: item["expires_at"])


def _top(values: list[str], size: int = TOP_SIZE) -> dict[str, int]:
    return dict(Counter(value for value in values if value).most_common(size))


def build_summary(offers: list[AggregatedOffer], today: date | None = None) -> dict[str, object]:
    """Statistiques sur les offres : sources, stages, technologies, salaires, villes..."""
    today = today or date.today()
    records = [record for offer in offers for record in offer.source_records]
    return {
        "top_technologies": _top([name for offer in offers for name in offer.technologies]),
        "top_skills": _top([name for offer in offers for name in offer.skills]),
        "salaries": salary_statistics(offers),
        "top_cities": _top([offer.city for offer in offers]),
        "levels": dict(Counter(offer.level or "Non précisé" for offer in offers).most_common()),
        "job_types": dict(Counter(offer.job_type or "Non précisé" for offer in offers).most_common()),
        "expiring_within_7_days": expiring_soon(offers, today),
        "offers_by_source": dict(Counter(record.source for record in records)),
        "guichet_by_origin_site": dict(
            Counter(
                record.origin_site or "Non précisé"
                for record in records
                if record.source == "Guichet-Emplois"
            ).most_common()
        ),
        "merged_offers": sum(len(offer.source_records) > 1 for offer in offers),
        "stage_classification": dict(Counter(offer.stage_status for offer in offers)),
        "work_mode": dict(Counter(offer.work_mode or "Non précisé" for offer in offers)),
        "with_salary": sum(bool(offer.salary) for offer in offers),
        # Nombre d'offres où chaque champ est rempli (pour comparer avant/après).
        "filled_fields": {
            name: sum(getattr(offer, name) not in (None, "", []) for offer in offers)
            for name in FILLED_FIELDS
        },
    }


FILLED_FIELDS = (
    "original_title", "description", "tasks", "expires_at", "job_type", "city", "province",
    "postal_code", "salary_min", "salary_unit", "education", "experience", "languages",
    "original_url", "technologies", "skills", "experience_years_min", "level", "summary",
)
