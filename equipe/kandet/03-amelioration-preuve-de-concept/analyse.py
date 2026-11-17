"""Analyse des offres : détection des stages et statistiques."""

from __future__ import annotations

from collections import Counter
import re

from modele import AggregatedOffer
from texte import normalize


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


def build_summary(offers: list[AggregatedOffer]) -> dict[str, object]:
    """Compte les offres par source, site d'origine, stage et mode de travail."""
    records = [record for offer in offers for record in offer.source_records]
    return {
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
    }
