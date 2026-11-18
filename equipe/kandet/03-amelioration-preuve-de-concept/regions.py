"""Région administrative du Québec à partir du nom de la ville.

Source : Répertoire des municipalités du Québec, ministère des Affaires
municipales et de l'Habitation (MAMH), licence CC-BY 4.0.
https://www.donneesquebec.ca/recherche/dataset/repertoire-des-municipalites-du-quebec

Le fichier regions_quebec.csv garde seulement 3 colonnes (nom, type, région).
Il est créé par preparer_regions.py à partir des listes officielles des
municipalités (MUN.csv) et des arrondissements (ARR.csv). Les arrondissements
servent pour les offres situées par exemple à « Saint-Laurent » ou « Lachine »
(Montréal).

Règle : si un nom n'est pas trouvé, ou s'il correspond à des municipalités de
régions différentes, la région reste vide. Elle n'est jamais devinée.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import re

from texte import normalize


REGIONS_FILE = Path(__file__).resolve().parent / "regions_quebec.csv"
REGION_CODE = re.compile(r"\s*\(\d+\)\s*$")


def clean_region(value: str) -> str:
    """« Montérégie (16) » -> « Montérégie »."""
    return REGION_CODE.sub("", value).strip()


def build_region_index(rows: list[dict[str, str]]) -> dict[str, str]:
    """Nom normalisé -> région. Les municipalités passent avant les arrondissements.

    Un nom présent dans deux régions différentes est retiré de l'index.
    """
    index: dict[str, str] = {}
    ambiguous: set[str] = set()
    for kind in ("municipalité", "arrondissement"):
        seen_now: dict[str, set[str]] = {}
        for row in rows:
            if row.get("type") != kind or not row.get("nom") or not row.get("region"):
                continue
            seen_now.setdefault(normalize(row["nom"]), set()).add(clean_region(row["region"]))
        for name, regions in seen_now.items():
            if name in index or name in ambiguous:
                continue  # déjà connu comme municipalité
            if len(regions) == 1:
                index[name] = regions.pop()
            else:
                ambiguous.add(name)
    return index


@lru_cache(maxsize=1)
def _default_index() -> dict[str, str]:
    if not REGIONS_FILE.exists():
        return {}
    with REGIONS_FILE.open(encoding="utf-8-sig", newline="") as file:
        return build_region_index(list(csv.DictReader(file, delimiter=";")))


def region_of(city: str, index: dict[str, str] | None = None) -> str:
    """Région administrative d'une ville du Québec, ou « » si inconnue."""
    if not city:
        return ""
    return (index if index is not None else _default_index()).get(normalize(city), "")
