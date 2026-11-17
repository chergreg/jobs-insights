"""Guichet-Emplois : lecture des pages de résultats de recherche (HTML)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
import re
import time
from urllib.parse import urlencode, urlsplit

from analyse import classify_stage
from collecte import fetch_url
from modele import SourceRecord
from texte import clean, parse_display_date


GUICHET_BASE_URL = "https://www.guichetemplois.gc.ca"
GUICHET_SEARCH_URL = f"{GUICHET_BASE_URL}/jobsearch/rechercheemplois"
# robots.txt du Guichet-Emplois : « Crawl-delay: 5 ».
GUICHET_DELAY_SECONDS = 5

# Codes CNP 2021 retenus pour le domaine informatique.
CNP_CODES_TI = {
    "21211": "Scientifiques de données",
    "21220": "Spécialistes de la cybersécurité",
    "21221": "Spécialistes des systèmes d'affaires",
    "21222": "Spécialistes des systèmes d'information",
    "21223": "Analystes de bases de données",
    "21230": "Développeurs et programmeurs de systèmes informatiques",
    "21231": "Ingénieurs et concepteurs en logiciel",
    "21232": "Développeurs et programmeurs de logiciels",
    "21233": "Concepteurs Web",
    "21234": "Développeurs Web et programmeurs",
    "21311": "Ingénieurs informaticiens",
    "22220": "Techniciens de réseau informatique",
    "22221": "Agents de soutien aux utilisateurs",
    "22222": "Évaluateurs de systèmes d'information",
}


@dataclass
class SearchPage:
    """Résultat d'une page de recherche du Guichet-Emplois."""

    records: list[SourceRecord]
    announced_total: int | None


def build_search_url(
    page: int = 1,
    term: str = "",
    province: str | None = "QC",
    cnp_codes: tuple[str, ...] | None = tuple(CNP_CODES_TI),
) -> str:
    """Construit l'URL d'une page de résultats (25 offres par page)."""
    params: list[tuple[str, str]] = []
    if term:
        params.append(("searchstring", term))
    params.extend(("fn21", code) for code in cnp_codes or ())
    if province:
        params.append(("fprov", province))
    params.append(("sort", "D"))  # plus récentes d'abord
    if page > 1:
        params.append(("page", str(page)))
    return f"{GUICHET_SEARCH_URL}?{urlencode(params)}"


class _SearchPageParser(HTMLParser):
    """Lit les balises <article> d'une page de résultats du Guichet-Emplois.

    Chaque champ est repéré par sa classe CSS (noctitle, business, location...).
    Les textes cachés pour les lecteurs d'écran (classe wb-inv) sont des
    étiquettes comme « Emplacement » : on les ignore, sauf le nom du site
    d'origine placé dans le bloc job-source.
    """

    FIELD_CLASSES = {
        "noctitle": "title",
        "date": "date",
        "business": "employer",
        "location": "location",
        "salary": "salary",
        "telework": "work_mode",
        "source": "job_number",
    }
    SKIPPED_CLASSES = {"new", "appmethod", "postedonJB", "description"}
    VOID_TAGS = {"br", "img", "input", "hr", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.articles: list[dict[str, str]] = []
        self.announced_total: int | None = None
        self._article: dict[str, str] | None = None
        self._stack: list[tuple[str, str]] = []  # (balise, rôle)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.VOID_TAGS:
            return
        attributes = {name: value or "" for name, value in attrs}
        classes = set(attributes.get("class", "").split())
        role = ""

        if tag == "article" and attributes.get("id", "").startswith("article-"):
            self._article = {"id": attributes["id"].removeprefix("article-")}
            role = "article"
        elif attributes.get("id") == "results-count":
            role = "count"
        elif self._article is not None:
            if tag == "a" and "resultJobItem" in classes:
                self._article["href"] = attributes.get("href", "")
            if "postedonJB" in classes:
                self._article["posted_on_guichet"] = "1"
            if "wb-inv" in classes:
                role = "origin" if self._current_role() == "job-source" else "skip"
            elif "job-source" in classes:
                role = "job-source"
            elif classes & self.SKIPPED_CLASSES:
                role = "skip"
            else:
                role = next(
                    (name for css, name in self.FIELD_CLASSES.items() if css in classes),
                    "",
                )
        self._stack.append((tag, role))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_TAGS:
            return
        # On dépile jusqu'à la balise correspondante (HTML parfois mal fermé).
        while self._stack:
            open_tag, role = self._stack.pop()
            if role == "article" and self._article is not None:
                self.articles.append(self._article)
                self._article = None
            if open_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        role = self._current_role()
        if role == "count":
            digits = re.sub(r"\D", "", data)
            if digits and self.announced_total is None:
                self.announced_total = int(digits)
        elif self._article is not None and role not in {"", "skip", "article", "job-source"}:
            if role == "origin" and self._article.get("origin"):
                return  # le nom du site apparaît deux fois dans l'article
            self._article[role] = self._article.get(role, "") + " " + data

    def _current_role(self) -> str:
        for _tag, role in reversed(self._stack):
            if role:
                return role
        return ""


def _posting_url(href: str) -> str:
    """Retire l'identifiant de session (;jsessionid=...) et les paramètres du lien."""
    path = urlsplit(href).path.split(";")[0]
    return f"{GUICHET_BASE_URL}{path}" if path.startswith("/") else path


def _strip_salary_label(value: str) -> str:
    return re.sub(r"^(?:salaire|salary)\s*:?\s*", "", value, flags=re.IGNORECASE)


def parse_search_page(html: str, search_term: str = "") -> SearchPage:
    """Transforme une page de résultats HTML en annonces normalisées."""
    parser = _SearchPageParser()
    parser.feed(html)
    parser.close()

    records: list[SourceRecord] = []
    for article in parser.articles:
        values = {key: clean(value) for key, value in article.items()}
        title = values.get("title", "")
        if not title:
            continue
        stage_status, stage_signals = classify_stage(title, "", "")
        records.append(
            SourceRecord(
                source="Guichet-Emplois",
                source_id=values["id"],
                url=_posting_url(values.get("href", "")),
                title=title,
                origin_site=values.get("origin", ""),
                employer=values.get("employer", ""),
                location=values.get("location", ""),
                salary=_strip_salary_label(values.get("salary", "")),
                published_at=parse_display_date(values.get("date", "")),
                work_mode=values.get("work_mode", ""),
                stage_status=stage_status,
                stage_signals=stage_signals,
                search_terms=[search_term] if search_term else [],
                source_data={
                    "job_number": values.get("job_number", ""),
                    "displayed_date": values.get("date", ""),
                    "posted_on_guichet": values.get("posted_on_guichet") == "1",
                },
            )
        )
    return SearchPage(records=records, announced_total=parser.announced_total)


def fetch_guichet(
    term: str = "",
    province: str | None = "QC",
    cnp_codes: tuple[str, ...] | None = tuple(CNP_CODES_TI),
    progress: Callable[[int, int, int | None], None] | None = None,
) -> tuple[list[SourceRecord], dict[str, object]]:
    """Parcourt toutes les pages de résultats d'une recherche, sans plafond.

    Arrêt quand une page est vide, quand elle ne contient que des offres déjà
    vues, ou quand le total annoncé par le site est atteint.
    """
    records: list[SourceRecord] = []
    seen_ids: set[str] = set()
    announced_total: int | None = None
    pages_read = 0
    page = 1

    while True:
        if page > 1:
            time.sleep(GUICHET_DELAY_SECONDS)
        html = fetch_url(
            build_search_url(page, term, province, cnp_codes),
            "text/html",
        ).decode("utf-8", errors="replace")
        result = parse_search_page(html, search_term=term)
        pages_read += 1
        if announced_total is None:
            announced_total = result.announced_total

        new_records = [record for record in result.records if record.source_id not in seen_ids]
        if progress is not None:
            progress(page, len(result.records), announced_total)
        if not new_records:
            break
        records.extend(new_records)
        seen_ids.update(record.source_id for record in new_records)
        if announced_total is not None and len(seen_ids) >= announced_total:
            break
        page += 1

    summary = {
        "term": term,
        "announced_total": announced_total,
        "collected": len(records),
        "pages_read": pages_read,
    }
    return records, summary
