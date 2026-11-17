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
    stage_status: str = "not_indicated"
    stage_signals: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    source_data: dict[str, object] = field(default_factory=dict)


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
