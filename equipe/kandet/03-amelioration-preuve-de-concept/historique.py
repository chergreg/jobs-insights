"""Collecte régulière : ce qui a changé depuis la collecte précédente.

Les offres changent vite : entre le 17 et le 20 novembre 2026, 24 offres sur
197 étaient nouvelles et 24 avaient disparu. Ce module :

- compare la nouvelle collecte avec le offres.json précédent (avant qu'il soit remplacé) ;
- marque les offres nouvelles (badge « Nouvelle » dans offres.html) ;
- ajoute une ligne par collecte dans historique-collectes.csv ;
- retire du cache les fiches des offres qui ne sont plus en ligne (--nettoyer-cache).

Une annonce est reconnue par sa source et son numéro (ex. Guichet-Emplois 50585958).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from modele import AggregatedOffer


Key = tuple[str, str]


def offer_keys(records: list[dict] | list) -> set[Key]:
    """Clés (source, numéro) des annonces d'une offre, qu'elle vienne d'un JSON ou du programme."""
    keys = set()
    for record in records:
        if isinstance(record, dict):
            keys.add((str(record.get("source", "")), str(record.get("source_id", ""))))
        else:
            keys.add((record.source, record.source_id))
    return keys


@dataclass
class GoneOffer:
    title: str
    employer: str
    expires_at: str
    url: str


@dataclass
class Changes:
    previous_date: str
    previous_count: int
    new_count: int
    kept_count: int
    gone: list[GoneOffer] = field(default_factory=list)

    @property
    def gone_before_expiry(self) -> int:
        """Offres retirées avant leur date limite (souvent : poste déjà pourvu)."""
        today = datetime.now().date().isoformat()
        return sum(1 for offer in self.gone if offer.expires_at and offer.expires_at >= today)

    def as_dict(self) -> dict[str, object]:
        return {
            "previous_generated_at": self.previous_date,
            "previous_offer_count": self.previous_count,
            "new_offers": self.new_count,
            "kept_offers": self.kept_count,
            "gone_offers": len(self.gone),
            "gone": [vars(offer) for offer in self.gone],
        }


def load_previous(path: Path) -> dict | None:
    """Le offres.json précédent, ou None s'il n'existe pas ou n'est pas lisible."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict) or not isinstance(document.get("offers"), list):
        return None
    return document


def compare_with_previous(previous: dict, offers: list[AggregatedOffer]) -> Changes:
    """Compare et marque les offres nouvelles (offer.new_since_previous)."""
    previous_keys: set[Key] = set()
    for raw in previous["offers"]:
        previous_keys |= offer_keys(raw.get("source_records", []))

    current_keys: set[Key] = set()
    new_count = kept_count = 0
    for offer in offers:
        keys = offer_keys(offer.source_records)
        current_keys |= keys
        offer.new_since_previous = not (keys & previous_keys)
        if offer.new_since_previous:
            new_count += 1
        else:
            kept_count += 1

    gone = []
    for raw in previous["offers"]:
        records = raw.get("source_records", [])
        if records and not (offer_keys(records) & current_keys):
            gone.append(
                GoneOffer(
                    title=str(raw.get("original_title") or raw.get("title") or ""),
                    employer=str(raw.get("employer") or ""),
                    expires_at=str(raw.get("expires_at") or ""),
                    url=str(records[0].get("url", "")),
                )
            )
    return Changes(
        previous_date=str(previous.get("generated_at", "")),
        previous_count=len(previous["offers"]),
        new_count=new_count,
        kept_count=kept_count,
        gone=gone,
    )


HISTORY_COLUMNS = ["date", "offres", "nouvelles", "disparues", "retirees_avant_expiration", "fiches_lues", "erreurs"]


def append_history(path: Path, offers_count: int, changes: Changes | None, postings_read: int, errors: int,
                   when: datetime | None = None) -> None:
    """Ajoute une ligne à l'historique (CSV pour Excel : utf-8-sig, séparateur « ; »)."""
    when = when or datetime.now()
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        if new_file:
            writer.writerow(HISTORY_COLUMNS)
        writer.writerow([
            when.strftime("%Y-%m-%d %H:%M"),
            offers_count,
            "" if changes is None else changes.new_count,
            "" if changes is None else len(changes.gone),
            "" if changes is None else changes.gone_before_expiry,
            postings_read,
            errors,
        ])


def clean_cache(cache_dir: Path, current_ids: set[str]) -> int:
    """Supprime les fiches en cache des offres qui ne sont plus dans les résultats. Retourne le nombre retiré."""
    removed = 0
    if not cache_dir.is_dir():
        return 0
    for path in cache_dir.glob("*.html"):
        if path.stem not in current_ids:
            path.unlink()
            removed += 1
    return removed
