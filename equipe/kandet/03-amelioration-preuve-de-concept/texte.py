"""Petits outils de nettoyage et de comparaison de texte."""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import re
import unicodedata


MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean(value: str) -> str:
    """Remplace les suites d'espaces et de retours de ligne par un seul espace."""
    return " ".join(value.split())


def plain_text(value: str) -> str:
    """Retire les balises HTML et garde le texte."""
    parser = _TextExtractor()
    parser.feed(value)
    return clean(" ".join(parser.parts))


def normalize(value: str) -> str:
    """Minuscules sans accents, pour comparer des textes."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


MONTH_NAMES = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
               "septembre", "octobre", "novembre", "décembre"]


def french_date(value: str) -> str:
    """« 2026-11-20 » ou « 2026-11-17T13:53:04+00:00 » -> « 20 novembre 2026 » (heure locale)."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return f"{moment.day} {MONTH_NAMES[moment.month - 1]} {moment.year}"


def parse_display_date(value: str) -> str:
    """Convertit « 12 novembre 2026 » ou « November 12, 2026 » en 2026-11-12.

    Retourne une chaîne vide si le format n'est pas reconnu.
    """
    words = re.findall(r"[^\W\d_]+|\d+", normalize(value))
    numbers = [int(word) for word in words if word.isdigit()]
    months = [MONTHS[word] for word in words if word in MONTHS]
    year = next((number for number in numbers if number > 1900), None)
    day = next((number for number in numbers if 1 <= number <= 31), None)
    if year is None or day is None or not months:
        return ""
    try:
        return datetime(year, months[0], day).date().isoformat()
    except ValueError:
        return ""
