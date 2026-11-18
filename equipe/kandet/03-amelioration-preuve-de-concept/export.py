"""Lecture d'un offres.json existant et export CSV pour Excel."""

from __future__ import annotations

import csv
from dataclasses import fields
import json
from pathlib import Path

from modele import AggregatedOffer, SourceRecord


# Colonnes du CSV : (en-tête, fonction qui donne la valeur)
CSV_COLUMNS = [
    ("titre", lambda o: o.title),
    ("titre_employeur", lambda o: o.original_title),
    ("employeur", lambda o: o.employer),
    ("ville", lambda o: o.city),
    ("province", lambda o: o.province),
    ("salaire_min", lambda o: _number(o.salary_min)),
    ("salaire_max", lambda o: _number(o.salary_max)),
    ("unite_salaire", lambda o: o.salary_unit),
    ("devise", lambda o: o.salary_currency),
    ("a_negocier", lambda o: "oui" if o.salary_negotiable else ""),
    ("niveau", lambda o: o.level),
    ("experience_ans", lambda o: _number(o.experience_years_min)),
    ("technologies", lambda o: ", ".join(o.technologies)),
    ("competences", lambda o: ", ".join(o.skills)),
    ("stage", lambda o: {"confirmed_stage": "confirmé", "possible_stage": "possible"}.get(o.stage_status, "")),
    ("type_emploi", lambda o: o.job_type),
    ("mode_travail", lambda o: o.work_mode),
    ("publiee_le", lambda o: o.published_at),
    ("expire_le", lambda o: o.expires_at),
    ("site_origine", lambda o: ", ".join(r.origin_site or r.source for r in o.source_records)),
    ("lien", lambda o: o.source_records[0].url if o.source_records else ""),
    ("lien_annonce_origine", lambda o: o.original_url),
    ("resume", lambda o: o.summary),
]


def _number(value: float | None) -> str:
    """52000.0 -> « 52000 », 36.5 -> « 36,5 » (virgule décimale pour Excel en français)."""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")


def write_csv(offers: list[AggregatedOffer], path: Path) -> None:
    """CSV en utf-8-sig avec « ; » : s'ouvre directement dans Excel en français."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow([header for header, _value in CSV_COLUMNS])
        for offer in offers:
            writer.writerow([value(offer) for _header, value in CSV_COLUMNS])


def load_offers(path: Path) -> list[AggregatedOffer]:
    """Relit les offres d'un offres.json produit par main.py (sans appel réseau)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("offers"), list):
        raise ValueError(f"{path} ne ressemble pas à un fichier produit par main.py.")

    offer_fields = {item.name for item in fields(AggregatedOffer)}
    record_fields = {item.name for item in fields(SourceRecord)}
    offers = []
    for raw in document["offers"]:
        records = [
            SourceRecord(**{key: value for key, value in record.items() if key in record_fields})
            for record in raw.get("source_records", [])
        ]
        values = {key: value for key, value in raw.items() if key in offer_fields and key != "source_records"}
        offers.append(AggregatedOffer(**values, source_records=records))
    return offers
