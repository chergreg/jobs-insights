"""Filtres pour choisir les offres à afficher et à exporter.

Les comparaisons ignorent les majuscules et les accents :
« montreal » trouve « Montréal », « debutant » trouve « débutant ».
"""

from __future__ import annotations

from dataclasses import dataclass

from modele import AggregatedOffer
from texte import normalize


@dataclass
class Filters:
    city: str = ""
    technology: str = ""
    level: str = ""
    stages_only: bool = False
    salary_min: float | None = None
    salary_unit: str = "année"
    employer: str = ""

    def is_empty(self) -> bool:
        return not (self.city or self.technology or self.level or self.stages_only
                    or self.salary_min is not None or self.employer)

    def describe(self) -> str:
        parts = []
        if self.city:
            parts.append(f"ville = {self.city}")
        if self.technology:
            parts.append(f"technologie = {self.technology}")
        if self.level:
            parts.append(f"niveau = {self.level}")
        if self.stages_only:
            parts.append("stages seulement")
        if self.salary_min is not None:
            parts.append(f"salaire minimum ≥ {self.salary_min:g} $ / {self.salary_unit}")
        if self.employer:
            parts.append(f"employeur contient « {self.employer} »")
        return ", ".join(parts) or "aucun filtre"


def matches(offer: AggregatedOffer, filters: Filters) -> bool:
    """Vrai si l'offre respecte tous les filtres demandés."""
    if filters.city and normalize(offer.city) != normalize(filters.city):
        return False
    if filters.technology and normalize(filters.technology) not in {
        normalize(name) for name in offer.technologies
    }:
        return False
    if filters.level and normalize(offer.level) != normalize(filters.level):
        return False
    if filters.stages_only and offer.stage_status == "not_indicated":
        return False
    if filters.salary_min is not None:
        # Le bas de la fourchette doit atteindre le montant, dans la même unité.
        # Une offre sans salaire ou dans une autre unité est écartée.
        if offer.salary_min is None or normalize(offer.salary_unit) != normalize(filters.salary_unit):
            return False
        if offer.salary_min < filters.salary_min:
            return False
    if filters.employer and normalize(filters.employer) not in normalize(offer.employer):
        return False
    return True


def filter_offers(offers: list[AggregatedOffer], filters: Filters) -> list[AggregatedOffer]:
    return [offer for offer in offers if matches(offer, filters)]
