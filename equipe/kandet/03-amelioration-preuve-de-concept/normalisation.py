"""Normalisation des champs : ville et province, salaire en chiffres, dates.

Règle : si une valeur n'est pas écrite clairement dans l'offre, on la laisse
vide. Par exemple, un taux horaire n'est jamais converti en salaire annuel
(il faudrait supposer un nombre d'heures), et « $80k - $100k » sans unité
garde une unité vide.
"""

from __future__ import annotations

import re

from modele import SourceRecord
from texte import normalize


PROVINCES = {"QC", "ON", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}
# « Montréal (QC) » sur la liste de résultats, « Longueuil, QC » sur certaines offres.
LOCATION_PATTERNS = (
    re.compile(r"^(?P<city>.+?)\s*\((?P<province>[A-Z]{2})\)$"),
    re.compile(r"^(?P<city>.+?),\s*(?P<province>[A-Z]{2})$"),
)

RDFA_UNITS = {"HOUR": "heure", "DAY": "jour", "WEEK": "semaine", "MONTH": "mois", "YEAR": "année"}
# Ordre important : « de l'heure / 40 heures par semaine » est un taux horaire.
TEXT_UNITS = (
    ("heure", re.compile(r"\b(?:heure|hour|hourly|hr)\b|/\s*h\b")),
    ("jour", re.compile(r"\b(?:jour|day|daily)\b")),
    ("semaine", re.compile(r"\b(?:semaine|week|weekly|wk)\b")),
    ("mois", re.compile(r"\b(?:mois|month|monthly|mo)\b")),
    ("année", re.compile(r"\b(?:annee|annuel|annuelle|year|yearly|annual|annum|yr)\b")),
)
# Un montant : « 52 000,00 », « 123 000 », « 43,27 », « 80,000 », « 3.5k », « 35,3k ».
AMOUNT_PATTERN = re.compile(
    r"(?P<number>\d{1,3}(?:[   ,.]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"\s*(?P<thousands>[kK])?"
)


def split_location(location: str) -> tuple[str, str]:
    """« Montréal (QC) » donne (« Montréal », « QC »). Sinon les deux restent vides."""
    value = " ".join(location.split())
    for pattern in LOCATION_PATTERNS:
        match = pattern.match(value)
        if match and match.group("province") in PROVINCES:
            return match.group("city"), match.group("province")
    return "", ""


def parse_amount(text: str) -> float | None:
    """Convertit un montant écrit en français ou en anglais en nombre."""
    match = AMOUNT_PATTERN.search(text)
    if not match:
        return None
    return _to_number(match.group("number"), bool(match.group("thousands")))


def _to_number(token: str, thousands: bool) -> float:
    token = token.replace(" ", "").replace(" ", "").replace(" ", "")
    decimal = re.search(r"[.,](\d{1,2})$", token)
    if decimal:
        # Le dernier séparateur suivi de 1 ou 2 chiffres est la virgule décimale.
        whole = re.sub(r"[.,]", "", token[: decimal.start()])
        value = float(f"{whole}.{decimal.group(1)}")
    else:
        # « 80,000 » ou « 123.000 » : séparateurs de milliers.
        value = float(re.sub(r"[.,]", "", token))
    return value * 1000 if thousands else value


def parse_salary_text(text: str) -> tuple[float | None, float | None, str]:
    """Lit (minimum, maximum, unité) dans un salaire écrit en texte.

    « 52 000,00 $ à 60 000,00 $ par année » -> (52000.0, 60000.0, "année")
    « $14 - $20/hour » -> (14.0, 20.0, "heure")
    « Competitive » -> (None, None, "")
    """
    # « / 40 heures par semaine » est une précision sur l'horaire, pas un montant.
    salary_part = re.split(r"/\s*\d+\s*heures", text)[0]
    amounts = [
        _to_number(match.group("number"), bool(match.group("thousands")))
        for match in AMOUNT_PATTERN.finditer(salary_part)
    ][:2]
    if not amounts:
        return None, None, ""
    maximum = amounts[1] if len(amounts) > 1 else None
    return amounts[0], maximum, salary_unit_from_text(salary_part)


def salary_unit_from_text(text: str) -> str:
    normalized = normalize(text)
    for unit, pattern in TEXT_UNITS:
        if pattern.search(normalized):
            return unit
    return ""


def normalize_record(record: SourceRecord) -> None:
    """Remplit ville, province, salaire en chiffres et dates au format AAAA-MM-JJ."""
    if not record.city or not record.province:
        city, province = split_location(record.location)
        record.city = record.city or city
        record.province = record.province or province

    posting = record.source_data.get("posting")
    if isinstance(posting, dict) and posting.get("salary_min"):
        # Valeurs RDFa de la fiche : plus fiables que le texte de la liste.
        record.salary_min = parse_amount(str(posting["salary_min"]))
        record.salary_max = parse_amount(str(posting.get("salary_max") or ""))
        record.salary_unit = RDFA_UNITS.get(str(posting.get("salary_unit") or "").upper(), "")
    elif record.salary:
        record.salary_min, record.salary_max, record.salary_unit = parse_salary_text(record.salary)
    if record.salary_min is not None and record.source == "Guichet-Emplois":
        record.salary_currency = "CAD"
    record.salary_negotiable = "negocier" in normalize(record.salary)

    for name in ("published_at", "expires_at", "start_date"):
        value = getattr(record, name)
        match = re.match(r"\d{4}-\d{2}-\d{2}", value)
        setattr(record, name, match.group(0) if match else "")
