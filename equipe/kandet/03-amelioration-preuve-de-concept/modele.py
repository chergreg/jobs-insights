"""Modèle de données commun à toutes les sources."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceRecord:
    """Une annonce telle que lue sur une source."""

    source: str
    source_id: str
    url: str
    title: str
    origin_site: str = ""  # site qui a publié l'annonce (ex. Jobillico sur le Guichet-Emplois)
    employer: str = ""
    location: str = ""
    salary: str = ""
    published_at: str = ""
    work_mode: str = ""
    job_type: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    # Champs lus sur la fiche de l'offre (vides si la fiche n'a pas été lue)
    original_title: str = ""  # titre écrit par l'employeur (offres des partenaires)
    tasks: list[str] = field(default_factory=list)
    expires_at: str = ""
    start_date: str = ""
    city: str = ""
    province: str = ""
    region: str = ""  # région administrative du Québec (regions.py)
    postal_code: str = ""
    education: str = ""
    experience: str = ""
    conditions: str = ""
    languages: list[str] = field(default_factory=list)
    original_url: str = ""  # lien vers l'annonce sur le site partenaire
    # Salaire en chiffres (rempli par normalisation.py)
    salary_min: float | None = None
    salary_max: float | None = None
    salary_unit: str = ""  # heure, jour, semaine, mois, année
    salary_currency: str = ""
    salary_negotiable: bool = False
    stage_status: str = "not_indicated"
    stage_signals: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    source_data: dict[str, object] = field(default_factory=dict)


# Champs texte et listes copiés d'une annonce vers l'offre regroupée.
DETAIL_TEXT_FIELDS = (
    "original_title", "expires_at", "start_date", "city", "province", "region", "postal_code",
    "education", "experience", "conditions", "original_url",
)
DETAIL_LIST_FIELDS = ("tasks", "languages")
# Copiés ensemble, pour ne pas mélanger le montant d'une annonce et l'unité d'une autre.
SALARY_FIELDS = ("salary_min", "salary_max", "salary_unit", "salary_currency", "salary_negotiable")


@dataclass
class AggregatedOffer:
    """Une offre après déduplication, avec toutes les annonces qui la décrivent."""

    title: str
    employer: str
    location: str
    salary: str
    published_at: str
    work_mode: str
    job_type: str
    category: str
    tags: list[str]
    description: str
    stage_status: str
    stage_signals: list[str]
    search_terms: list[str]
    source_records: list[SourceRecord]
    original_title: str = ""
    tasks: list[str] = field(default_factory=list)
    expires_at: str = ""
    start_date: str = ""
    city: str = ""
    province: str = ""
    region: str = ""
    postal_code: str = ""
    education: str = ""
    experience: str = ""
    conditions: str = ""
    languages: list[str] = field(default_factory=list)
    original_url: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_unit: str = ""
    salary_currency: str = ""
    salary_negotiable: bool = False
    # Calculés par competences.py à partir du titre, de la description et des tâches
    technologies: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    experience_years_min: float | None = None
    level: str = ""  # débutant, intermédiaire, avancé
    summary: str = ""
