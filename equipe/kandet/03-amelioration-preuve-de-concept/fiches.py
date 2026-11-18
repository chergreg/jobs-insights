"""Guichet-Emplois : lecture des fiches d'offres (balises RDFa) avec un cache.

Chaque fiche contient des attributs property="..." (vocabulaire Schema.org
JobPosting) : description, validThrough, minValue, employmentType, etc.
L'idée de lire ces balises vient des essais de Mamadou et de Hugo ; ici elle
est réécrite avec html.parser pour rester sans dépendance externe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import html as html_module
from html.parser import HTMLParser
from pathlib import Path
import re
import time

from collecte import fetch_url
from guichet import GUICHET_DELAY_SECONDS
from modele import SourceRecord
from texte import clean, plain_text


START_DATE_PATTERN = re.compile(r"Débute\s+dès\s+le\s*(\d{4}-\d{2}-\d{2})")
# Certaines fiches contiennent « Général » écrit tel quel dans le HTML.
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")


def _text(value: str) -> str:
    """Nettoie les espaces et remplace les séquences \\uXXXX par le vrai caractère."""
    return clean(UNICODE_ESCAPE_PATTERN.sub(lambda match: chr(int(match.group(1), 16)), value))
# Propriétés dont les morceaux de texte sont des éléments d'une liste.
LIST_PROPERTIES = {"employmentType", "educationRequirements"}


@dataclass
class JobPostingDetails:
    """Ce qu'on a pu lire sur une fiche. Un champ absent reste vide."""

    title: str = ""
    original_title: str = ""  # titre de l'employeur, affiché pour les offres des partenaires
    employer: str = ""
    description: str = ""
    tasks: list[str] = field(default_factory=list)
    published_text: str = ""
    expires_at: str = ""
    start_date: str = ""
    job_type: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""
    salary_min: str = ""
    salary_max: str = ""
    salary_unit: str = ""
    education: str = ""
    experience: str = ""
    conditions: str = ""
    languages: list[str] = field(default_factory=list)
    original_url: str = ""


class _PostingParser(HTMLParser):
    """Récupère le texte de chaque élément qui porte un attribut property."""

    VOID_TAGS = {"br", "img", "input", "hr", "meta", "link", "source"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Chaque occurrence : (liste des propriétés de l'élément, morceaux de texte)
        self.occurrences: list[tuple[tuple[str, ...], list[str]]] = []
        self.contents: dict[str, str] = {}
        self.tasks: list[str] = []
        self.original_url = ""
        # (balise, propriétés, texte de la propriété, texte de la tâche)
        self._stack: list[tuple[str, tuple[str, ...], list[str] | None, list[str] | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.VOID_TAGS:
            return
        attributes = {name: value or "" for name, value in attrs}
        if tag == "a" and attributes.get("id") == "externalJobLink":
            self.original_url = attributes.get("href", "")

        parts: list[str] | None = None
        properties = tuple(attributes.get("property", "").split())
        if properties:
            parts = []
            self.occurrences.append((properties, parts))
            if attributes.get("content"):
                for name in properties:
                    self.contents.setdefault(name, attributes["content"])

        # Les tâches sont les éléments <li> du bloc property="responsibilities".
        task: list[str] | None = None
        if tag == "li" and any("responsibilities" in props for _t, props, _p, _k in self._stack):
            task = []
        classes = attributes.get("class", "").split()
        if "source-title-inner" in classes:
            # Titre écrit par l'employeur sur le site partenaire (pas une balise RDFa).
            parts = []
            properties = ("_original_title",)
            self.occurrences.append((properties, parts))
        if "wb-inv" in classes or "orig-title-label" in classes:
            # Texte pour lecteurs d'écran (« Ce lien ouvrira dans une nouvelle fenêtre »)
            # ou étiquette « Appellation affichée sur Jobillico - » : ignoré.
            properties = ("_hidden",)
        self._stack.append((tag, properties, parts, task))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_TAGS:
            return
        while self._stack:
            open_tag, _properties, _parts, task = self._stack.pop()
            if task is not None and _text(" ".join(task)):
                self.tasks.append(_text(" ".join(task)))
            if open_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if any(properties == ("_hidden",) for _tag, properties, _parts, _task in self._stack):
            return
        for _tag, _properties, parts, task in self._stack:
            if parts is not None:
                parts.append(data)
            if task is not None:
                task.append(data)

    def value(self, name: str, exact: bool = False) -> str:
        """Texte de la première occurrence d'une propriété."""
        for properties, parts in self.occurrences:
            if name in properties and (not exact or properties == (name,)):
                if name in LIST_PROPERTIES:
                    return ", ".join(_text(part) for part in parts if _text(part))
                return _text(" ".join(parts))
        return ""

    def values(self, name: str, exact: bool = False) -> list[str]:
        return [
            _text(" ".join(parts))
            for properties, parts in self.occurrences
            if name in properties and (not exact or properties == (name,)) and _text(" ".join(parts))
        ]


def _description_text(raw: str) -> str:
    """Les partenaires envoient une description en HTML encodé deux fois.

    Après décodage des entités, il reste des balises <p>, <strong>... dans le
    texte : on les retire une deuxième fois.
    """
    text = plain_text(raw) if "<" in raw and ">" in raw else raw
    # Il peut rester des entités encodées deux fois, comme « &amp; ».
    return clean(html_module.unescape(text))


def parse_job_posting(html: str) -> JobPostingDetails:
    """Lit les balises RDFa d'une fiche d'offre du Guichet-Emplois."""
    parser = _PostingParser()
    parser.feed(html)
    parser.close()

    start_date = START_DATE_PATTERN.search(html.replace("\xa0", " ").replace("&nbsp;", " "))
    return JobPostingDetails(
        title=parser.value("title"),
        original_title=parser.value("_original_title"),
        employer=parser.value("hiringOrganization"),
        description=_description_text(parser.value("description")),
        tasks=parser.tasks,
        published_text=parser.value("datePosted"),
        expires_at=parser.value("validThrough"),
        start_date=start_date.group(1) if start_date else "",
        job_type=parser.value("employmentType"),
        city=parser.value("addressLocality"),
        province=parser.value("addressRegion"),
        postal_code=parser.value("postalCode"),
        salary_min=clean(parser.contents.get("minValue") or parser.value("minValue")),
        salary_max=clean(parser.contents.get("maxValue") or parser.value("maxValue")),
        salary_unit=parser.value("unitText"),
        education=parser.value("educationRequirements"),
        experience=parser.value("experienceRequirements"),
        conditions=parser.value("specialCommitments"),
        # Les langues sont les éléments qui ont seulement property="qualification".
        languages=parser.values("qualification", exact=True),
        original_url=parser.original_url,
    )


def apply_details(record: SourceRecord, details: JobPostingDetails) -> None:
    """Complète une annonce avec sa fiche, sans écraser ce qui est déjà rempli."""
    for name in (
        "original_title", "description", "expires_at", "start_date", "job_type", "city",
        "province", "postal_code", "education", "experience", "conditions", "original_url",
    ):
        if not getattr(record, name) and getattr(details, name):
            setattr(record, name, getattr(details, name))
    for name in ("tasks", "languages"):
        if not getattr(record, name):
            setattr(record, name, list(getattr(details, name)))
    # Valeurs brutes gardées pour l'étape suivante (salaire en chiffres).
    record.source_data["posting"] = {
        "title": details.title,
        "published_text": details.published_text,
        "salary_min": details.salary_min,
        "salary_max": details.salary_max,
        "salary_unit": details.salary_unit,
    }


def enrich_with_postings(
    records: list[SourceRecord],
    cache_dir: Path,
    max_postings: int | None = None,
    progress: Callable[[int, int, bool], None] | None = None,
) -> dict[str, object]:
    """Lit la fiche de chaque offre du Guichet-Emplois.

    Une fiche déjà dans le cache n'est pas redemandée au site. Sinon, on
    attend 5 s avant chaque téléchargement (Crawl-delay du robots.txt).
    """
    targets = [record for record in records if record.source == "Guichet-Emplois"]
    if max_postings is not None:
        targets = targets[:max_postings]

    cache_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"read": 0, "from_cache": 0, "downloaded": 0, "errors": []}
    errors: list[str] = summary["errors"]  # type: ignore[assignment]

    for index, record in enumerate(targets, start=1):
        cache_path = cache_dir / f"{record.source_id}.html"
        from_cache = cache_path.exists()
        try:
            if from_cache:
                html = cache_path.read_text(encoding="utf-8")
            else:
                time.sleep(GUICHET_DELAY_SECONDS)
                html = fetch_url(record.url, "text/html").decode("utf-8", errors="replace")
            details = parse_job_posting(html)
            if not details.title:
                raise ValueError("fiche sans titre (offre retirée ou page d'erreur)")
            if not from_cache:
                cache_path.write_text(html, encoding="utf-8")
            apply_details(record, details)
        except (OSError, ValueError) as error:
            errors.append(f"{record.source_id} : {error}")
            continue
        finally:
            if progress is not None:
                progress(index, len(targets), from_cache)

        summary["read"] = int(summary["read"]) + 1
        key = "from_cache" if from_cache else "downloaded"
        summary[key] = int(summary[key]) + 1
    return summary
