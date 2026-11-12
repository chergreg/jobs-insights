"""Collecte d'offres d'emploi et de stage en informatique (livrable 2).

Deux sources :
- Guichet-Emplois : pages de résultats de recherche (HTML), filtrées par codes
  CNP du domaine TI et par province. Toutes les pages sont parcourues.
- Remotive : API JSON publique d'emplois à distance.

Le script n'utilise que la bibliothèque standard de Python.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


# --- Paramètres des sources -------------------------------------------------

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

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_MAX_REQUESTS_PER_DAY = 4
REMOTIVE_CACHE_HOURS = 24
REMOTIVE_ALLOWED_CATEGORIES = {
    "software development",
    "information technology",
    "artificial intelligence",
    "data and analytics",
    "devops",
    "quality assurance",
    "engineering",
    "product management",
    "design",
    "research",
}
REMOTIVE_CANADA_TERMS = ("canada", "quebec", "montreal", "north america", "worldwide")

USER_AGENT = "jobs-insights-atelier/1.0 (educational project)"
MAX_RESPONSE_BYTES = 10_000_000
RETRY_STATUS_CODES = {429, 503}
RETRY_WAIT_SECONDS = 30


# --- Détection des stages ---------------------------------------------------

STAGE_PATTERN = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|work[\s-]?terms?)\b",
    flags=re.IGNORECASE,
)
STAGE_DESCRIPTION_PATTERN = re.compile(
    r"\b(?:internship|intern|co[\s-]?op|work[\s-]?term)\s+"
    r"(?:position|role|program|opportunity|placement)\b"
    r"|\b(?:student|students)\s+(?:intern|position|role|placement)\b"
    r"|\b(?:stage|stagiaire)\s+(?:en|de|du|d['’]|remunere)\b",
    flags=re.IGNORECASE,
)
STUDENT_ELIGIBILITY_PATTERN = re.compile(
    r"\b(?:currently\s+enrolled|enrolled\s+(?:in|at)|"
    r"must\s+be\s+(?:a\s+)?student|student\s+status|required\s+to\s+be\s+enrolled|"
    r"etre\s+(?:inscrit|inscrite|etudiant|etudiante)|"
    r"doit\s+etre\s+(?:inscrit|inscrite|etudiant|etudiante))\b",
    flags=re.IGNORECASE,
)

MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


# --- Modèle de données ------------------------------------------------------

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


@dataclass
class SearchPage:
    """Résultat d'une page de recherche du Guichet-Emplois."""

    records: list[SourceRecord]
    announced_total: int | None


# --- Outils texte ------------------------------------------------------------

class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return _clean(" ".join(parser.parts))


def _clean(value: str) -> str:
    return " ".join(value.split())


def _normalize(value: str) -> str:
    """Minuscules sans accents, pour comparer des textes."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def parse_display_date(value: str) -> str:
    """Convertit « 12 novembre 2026 » ou « November 12, 2026 » en 2026-11-12.

    Retourne une chaîne vide si le format n'est pas reconnu.
    """
    words = re.findall(r"[^\W\d_]+|\d+", _normalize(value))
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


def classify_stage(title: str, job_type: str, description: str) -> tuple[str, list[str]]:
    """Classe une offre : stage confirmé, stage possible ou non indiqué."""
    normalized_job_type = _normalize(job_type).replace("_", " ")
    if normalized_job_type in {"internship", "intern", "co op", "stage", "stagiaire"}:
        return "confirmed_stage", ["explicit_internship_job_type"]
    if STAGE_PATTERN.search(_normalize(title)):
        return "confirmed_stage", ["stage_term_in_title"]
    normalized_description = _normalize(description)
    if STAGE_DESCRIPTION_PATTERN.search(normalized_description):
        return "possible_stage", ["stage_role_in_description"]
    if STUDENT_ELIGIBILITY_PATTERN.search(normalized_description):
        return "possible_stage", ["student_eligibility_in_description"]
    return "not_indicated", []


# --- Réseau --------------------------------------------------------------------

def fetch_url(url: str, accept: str) -> bytes:
    """Télécharge une URL. Réessaie une fois après 30 s sur HTTP 429 ou 503."""
    request = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except HTTPError as error:
            if attempt == 1 and error.code in RETRY_STATUS_CODES:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            raise

    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Réponse trop volumineuse (plus de {MAX_RESPONSE_BYTES} octets).")
    return content


# --- Guichet-Emplois -----------------------------------------------------------

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
        values = {key: _clean(value) for key, value in article.items()}
        title = values.get("title", "")
        if not title:
            continue
        origin_site = values.get("origin", "")
        stage_status, stage_signals = classify_stage(title, "", "")
        records.append(
            SourceRecord(
                source="Guichet-Emplois",
                source_id=values["id"],
                url=_posting_url(values.get("href", "")),
                title=title,
                origin_site=origin_site,
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


# --- Remotive ------------------------------------------------------------------

def parse_remotive_payload(
    payload: dict[str, object],
    location_filter: bool = False,
) -> list[SourceRecord]:
    """Garde les offres Remotive des catégories liées à l'informatique."""
    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("La réponse Remotive ne contient pas de liste 'jobs'.")

    records: list[SourceRecord] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue
        category = str(raw_job.get("category") or "")
        if _normalize(category) not in REMOTIVE_ALLOWED_CATEGORIES:
            continue
        required_location = str(raw_job.get("candidate_required_location") or "")
        if location_filter and not any(
            term in _normalize(required_location) for term in REMOTIVE_CANADA_TERMS
        ):
            continue

        title = str(raw_job.get("title") or "")
        job_type = str(raw_job.get("job_type") or "")
        description = _plain_text(str(raw_job.get("description") or ""))
        raw_tags = raw_job.get("tags")
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        stage_status, stage_signals = classify_stage(title, job_type, description)
        records.append(
            SourceRecord(
                source="Remotive",
                source_id=str(raw_job.get("id") or raw_job.get("url") or ""),
                url=str(raw_job.get("url") or ""),
                title=title,
                origin_site="Remotive",
                employer=str(raw_job.get("company_name") or ""),
                location=required_location,
                salary=str(raw_job.get("salary") or ""),
                published_at=str(raw_job.get("publication_date") or ""),
                work_mode="Télétravail",
                job_type=job_type,
                category=category,
                tags=tags,
                description=description,
                stage_status=stage_status,
                stage_signals=stage_signals,
                source_data={
                    key: value for key, value in raw_job.items() if key != "description"
                },
            )
        )
    return records


def load_remotive_payload(cache_path: Path, refresh: bool = False) -> dict[str, object]:
    """Réutilise la réponse en cache pendant 24 h (l'API demande 4 appels/jour max)."""
    if not refresh and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict) or not isinstance(cached.get("payload"), dict):
            raise ValueError(f"Cache Remotive invalide : {cache_path}")
        if cached.get("request_url") == REMOTIVE_API_URL:
            fetched_at = datetime.fromisoformat(str(cached.get("fetched_at", "")))
            age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if 0 <= age_seconds < REMOTIVE_CACHE_HOURS * 3600:
                return cached["payload"]

    try:
        payload = json.loads(fetch_url(REMOTIVE_API_URL, "application/json"))
    except json.JSONDecodeError as error:
        raise ValueError("La réponse Remotive n'est pas un JSON valide.") from error
    if not isinstance(payload, dict):
        raise ValueError("La réponse Remotive doit être un objet JSON.")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "request_url": REMOTIVE_API_URL,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


# --- Déduplication -------------------------------------------------------------

def _publisher(record: SourceRecord) -> tuple[str, str]:
    """Qui a publié l'annonce : la source et, s'il est connu, le site d'origine."""
    return record.source, _normalize(record.origin_site)


def _same_source_record(left: SourceRecord, right: SourceRecord) -> bool:
    """Même annonce sur la même source (même identifiant ou même lien)."""
    if left.source != right.source:
        return False
    if left.source_id and right.source_id and left.source_id == right.source_id:
        return True
    return bool(left.url and right.url and left.url.casefold() == right.url.casefold())


def _identity(record: SourceRecord) -> tuple[str, str, str]:
    return (
        _normalize(record.title),
        _normalize(record.employer),
        _normalize(record.location),
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


# --- Programme principal -------------------------------------------------------

def build_summary(offers: list[AggregatedOffer]) -> dict[str, object]:
    records = [record for offer in offers for record in offer.source_records]
    return {
        "offers_by_source": dict(Counter(record.source for record in records)),
        "guichet_by_origin_site": dict(
            Counter(
                record.origin_site or "Non précisé"
                for record in records
                if record.source == "Guichet-Emplois"
            ).most_common()
        ),
        "merged_offers": sum(len(offer.source_records) > 1 for offer in offers),
        "stage_classification": dict(Counter(offer.stage_status for offer in offers)),
        "work_mode": dict(Counter(offer.work_mode or "Non précisé" for offer in offers)),
        "with_salary": sum(bool(offer.salary) for offer in offers),
    }


def print_offer(offer: AggregatedOffer) -> None:
    sites = ", ".join(
        record.origin_site or record.source for record in offer.source_records
    )
    print(
        f"- {offer.published_at or '????-??-??'} | {offer.title} | "
        f"{offer.employer or 'Employeur non précisé'} | {offer.location or 'Lieu non précisé'} | {sites}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collecte d'offres TI : Guichet-Emplois (recherche HTML) et Remotive (API)."
    )
    parser.add_argument(
        "--terme",
        action="append",
        default=[],
        help="Mot-clé Guichet-Emplois (répétable). Par défaut : aucun, seuls les codes CNP TI filtrent.",
    )
    parser.add_argument("--province", default="QC", help="Province Guichet-Emplois (défaut : QC).")
    parser.add_argument(
        "--toutes-provinces",
        action="store_true",
        help="Ne pas filtrer le Guichet-Emplois par province.",
    )
    parser.add_argument(
        "--tous-domaines",
        action="store_true",
        help="Ne pas filtrer par codes CNP (à combiner avec --terme).",
    )
    parser.add_argument(
        "--remotive-canada",
        action="store_true",
        help="Garder seulement les offres Remotive ouvertes au Canada, à l'Amérique du Nord ou au monde entier.",
    )
    parser.add_argument(
        "--rafraichir-remotive",
        action="store_true",
        help="Ignorer le cache Remotive (l'API demande au plus 4 appels par jour).",
    )
    parser.add_argument("--sans-remotive", action="store_true", help="Ne pas interroger Remotive.")
    parser.add_argument(
        "--sortie",
        type=Path,
        default=Path(__file__).with_name("offres.json"),
        help="Fichier JSON de sortie (défaut : offres.json à côté du script).",
    )
    parser.add_argument(
        "--echantillon",
        type=Path,
        help="Écrit aussi un petit fichier avec les 10 premières offres du Guichet-Emplois.",
    )
    parser.add_argument("--sans-sauvegarde", action="store_true", help="Afficher sans écrire de fichier.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    province = None if args.toutes_provinces else args.province
    cnp_codes = None if args.tous_domaines else tuple(CNP_CODES_TI)
    terms = args.terme or [""]
    source_records: list[SourceRecord] = []
    searches: list[dict[str, object]] = []
    errors: list[str] = []

    for index, term in enumerate(terms):
        if index > 0:
            time.sleep(GUICHET_DELAY_SECONDS)
        label = f"« {term} »" if term else "codes CNP TI"
        try:
            records, summary = fetch_guichet(
                term,
                province,
                cnp_codes,
                progress=lambda page, count, total: print(
                    f"Guichet-Emplois ({label}) page {page} : {count} offres"
                    + (f" / {total} annoncées" if total is not None else ""),
                    file=sys.stderr,
                ),
            )
            source_records.extend(records)
            searches.append(summary)
        except (OSError, ValueError) as error:
            errors.append(f"Guichet-Emplois ({label}) : {error}")

    remotive_total: object = None
    if not args.sans_remotive:
        try:
            payload = load_remotive_payload(
                Path(__file__).with_name("remotive-cache.json"),
                refresh=args.rafraichir_remotive,
            )
            remotive_total = payload.get("total-job-count", len(payload.get("jobs") or []))
            source_records.extend(
                parse_remotive_payload(payload, location_filter=args.remotive_canada)
            )
        except (OSError, ValueError) as error:
            errors.append(f"Remotive : {error}")

    for error in errors:
        print(f"AVERTISSEMENT : {error}", file=sys.stderr)
    if not source_records:
        if errors:
            raise SystemExit("Aucune offre récupérée; voir les avertissements ci-dessus.")
        print("Aucune offre ne correspond aux critères.")
        return

    offers = aggregate_records(source_records)
    summary = build_summary(offers)
    print(f"\n{len(offers)} offres uniques ({len(source_records)} annonces lues).")
    for search in searches:
        print(
            f"Guichet-Emplois {search['term'] or '(codes CNP TI)'} : {search['collected']} récupérées"
            f" / {search['announced_total']} annoncées, {search['pages_read']} page(s)"
        )
    if remotive_total is not None:
        print(f"Remotive : {summary['offers_by_source'].get('Remotive', 0)} gardées sur {remotive_total} dans l'API")
    print(f"Sites d'origine (Guichet-Emplois) : {summary['guichet_by_origin_site']}")
    print(f"Offres publiées sur plusieurs sites (fusionnées) : {summary['merged_offers']}")
    print(f"Stages : {summary['stage_classification']}\n")
    for offer in offers:
        print_offer(offer)

    if args.sans_sauvegarde:
        return
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "province": province,
            "cnp_codes": list(cnp_codes or []),
            "terms": [term for term in terms if term],
            "remotive_canada_only": args.remotive_canada,
        },
        "sources": {"Guichet-Emplois": GUICHET_SEARCH_URL, "Remotive": REMOTIVE_API_URL},
        "remotive_notice": (
            "Offres Remotive : garder l'attribution et le lien d'origine, ne pas les republier "
            f"sur un site tiers, au plus {REMOTIVE_MAX_REQUESTS_PER_DAY} appels par jour."
        ),
        "errors": errors,
        "guichet_searches": searches,
        "remotive_total_in_api": remotive_total,
        "offer_count": len(offers),
        "summary": summary,
        "offers": [asdict(offer) for offer in offers],
    }
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nRésultats enregistrés dans : {args.sortie}")

    if args.echantillon:
        sample = [
            asdict(offer)
            for offer in offers
            if offer.source_records[0].source == "Guichet-Emplois"
        ][:10]
        args.echantillon.write_text(
            json.dumps(
                {"generated_at": document["generated_at"], "offers": sample},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Échantillon enregistré dans : {args.echantillon}")


if __name__ == "__main__":
    main()
