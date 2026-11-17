"""Déduplication : regroupe les annonces qui décrivent la même offre."""

from __future__ import annotations

from modele import AggregatedOffer, SourceRecord
from texte import normalize


def _publisher(record: SourceRecord) -> tuple[str, str]:
    """Qui a publié l'annonce : la source et, s'il est connu, le site d'origine."""
    return record.source, normalize(record.origin_site)


def _same_source_record(left: SourceRecord, right: SourceRecord) -> bool:
    """Même annonce sur la même source (même identifiant ou même lien)."""
    if left.source != right.source:
        return False
    if left.source_id and right.source_id and left.source_id == right.source_id:
        return True
    return bool(left.url and right.url and left.url.casefold() == right.url.casefold())


def _identity(record: SourceRecord) -> tuple[str, str, str]:
    return (
        normalize(record.title),
        normalize(record.employer),
        normalize(record.location),
    )


def _republished_match(left: SourceRecord, right: SourceRecord) -> bool:
    """Même offre publiée par deux sites différents (ex. Jobillico et Talent.com).

    Deux annonces d'un même site ne sont jamais fusionnées sur le titre seul :
    un employeur peut afficher plusieurs postes identiques.
    """
    if _publisher(left) == _publisher(right):
        return False
    identity = _identity(left)
    return all(identity) and identity == _identity(right)


def _new_aggregated_offer(record: SourceRecord) -> AggregatedOffer:
    return AggregatedOffer(
        title=record.title,
        employer=record.employer,
        location=record.location,
        salary=record.salary,
        published_at=record.published_at,
        work_mode=record.work_mode,
        job_type=record.job_type,
        category=record.category,
        tags=list(record.tags),
        description=record.description,
        stage_status=record.stage_status,
        stage_signals=list(record.stage_signals),
        search_terms=list(record.search_terms),
        source_records=[record],
    )


def _merge_record(offer: AggregatedOffer, record: SourceRecord) -> None:
    """Complète les champs vides de l'offre avec ceux de la nouvelle annonce."""
    for field_name in (
        "title", "employer", "location", "salary", "published_at",
        "work_mode", "job_type", "category", "description",
    ):
        if not getattr(offer, field_name) and getattr(record, field_name):
            setattr(offer, field_name, getattr(record, field_name))
    offer.tags = list(dict.fromkeys(offer.tags + record.tags))
    offer.stage_signals = list(dict.fromkeys(offer.stage_signals + record.stage_signals))
    offer.search_terms = list(dict.fromkeys(offer.search_terms + record.search_terms))
    priority = {"not_indicated": 0, "possible_stage": 1, "confirmed_stage": 2}
    if priority.get(record.stage_status, 0) > priority.get(offer.stage_status, 0):
        offer.stage_status = record.stage_status
    offer.source_records.append(record)


def aggregate_records(records: list[SourceRecord]) -> list[AggregatedOffer]:
    """Regroupe les annonces répétées en offres uniques."""
    grouped: list[AggregatedOffer] = []
    for record in records:
        duplicate = next(
            (
                prior
                for offer in grouped
                for prior in offer.source_records
                if _same_source_record(prior, record)
            ),
            None,
        )
        if duplicate is not None:
            duplicate.search_terms = list(
                dict.fromkeys(duplicate.search_terms + record.search_terms)
            )
            continue

        republished = next(
            (
                offer
                for offer in grouped
                if all(_publisher(prior) != _publisher(record) for prior in offer.source_records)
                and any(_republished_match(prior, record) for prior in offer.source_records)
            ),
            None,
        )
        if republished is None:
            grouped.append(_new_aggregated_offer(record))
        else:
            _merge_record(republished, record)
    return grouped
