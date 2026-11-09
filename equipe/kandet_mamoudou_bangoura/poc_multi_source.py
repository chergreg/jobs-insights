"""Local multi-source jobs and internships aggregator POC."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


JOB_BANK_FEED_URL = "https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"
REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
SEARCH_CATEGORY_CODES = ("21230", "21232", "21234")
REMOTIVE_ALLOWED_CATEGORIES = {"software development", "information technology"}
JOB_BANK_TERMS = ("developpeur", "programmeur", "stage informatique", "internship")
JOB_BANK_CRAWL_DELAY_SECONDS = 5
REMOTIVE_MAX_REQUESTS_PER_DAY = 4
ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "jobs-insights-atelier/1.0 (educational project)"
MAX_RESPONSE_BYTES = 10_000_000
STAGE_PATTERN = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|work[\s-]?terms?)\b",
    flags=re.IGNORECASE,
)
STUDENT_PATTERN = re.compile(r"\b(?:student|étudiant|etudiante|étudiante)\b", flags=re.IGNORECASE)


@dataclass
class SourceRecord:
    source: str
    source_id: str
    url: str
    title: str
    employer: str = ""
    location: str = ""
    salary: str = ""
    published_at: str = ""
    job_type: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    stage_status: str = "not_indicated"
    stage_signals: list[str] = field(default_factory=list)
    source_data: dict[str, object] = field(default_factory=dict)


@dataclass
class AggregatedOffer:
    title: str
    employer: str
    location: str
    salary: str
    published_at: str
    job_type: str
    category: str
    tags: list[str]
    description: str
    stage_status: str
    stage_signals: list[str]
    source_records: list[SourceRecord]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def _field(summary: str, label: str) -> str:
    pattern = rf"(?:^|\s){re.escape(label)}:\s*(.*?)(?=\s+(?:Job number|Location|Employer|Salary):|$)"
    match = re.search(pattern, summary, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def classify_stage(title: str, job_type: str, description: str) -> tuple[str, list[str]]:
    title_type = f"{title} {job_type}"
    signals = []
    if STAGE_PATTERN.search(title_type):
        signals.append("stage_term_in_title_or_job_type")
        return "likely_stage", signals
    if STAGE_PATTERN.search(description):
        signals.append("stage_term_in_description")
        return "possible_stage", signals
    if STUDENT_PATTERN.search(f"{title} {job_type} {description}"):
        signals.append("student_term")
        return "possible_stage", signals
    return "not_indicated", signals


def build_feed_url(term: str, rows: int) -> str:
    params = [("fn21", code) for code in SEARCH_CATEGORY_CODES]
    params.extend((("term", term), ("sort", "D"), ("rows", str(rows))))
    return f"{JOB_BANK_FEED_URL}?{urlencode(params)}"


def parse_feed(
    xml_content: bytes,
    location: str | None = "QC",
) -> list[SourceRecord]:
    """Parse Job Bank's Atom feed into normalized source records."""
    root = ET.fromstring(xml_content)
    jobs: list[SourceRecord] = []

    for entry in root.findall(f"{ATOM}entry"):
        title_element = entry.find(f"{ATOM}title")
        link_element = entry.find(f"{ATOM}link")
        summary_element = entry.find(f"{ATOM}summary")
        updated_element = entry.find(f"{ATOM}updated")

        title = _plain_text("".join(title_element.itertext())) if title_element is not None else ""
        summary = _plain_text("".join(summary_element.itertext())) if summary_element is not None else ""
        link = link_element.get("href", "") if link_element is not None else ""
        job_location = _field(summary, "Location")
        job_number = _field(summary, "Job number")

        if location and _normalize(location) not in _normalize(job_location):
            continue

        published_at = (
            updated_element.text.strip()
            if updated_element is not None and updated_element.text
            else ""
        )
        employer = _field(summary, "Employer")
        salary = _field(summary, "Salary")
        stage_status, stage_signals = classify_stage(title, "", summary)
        jobs.append(
            SourceRecord(
                source="Guichet-Emplois",
                source_id=job_number or link,
                url=link,
                title=title,
                employer=employer,
                location=job_location,
                salary=salary,
                published_at=published_at,
                description=summary,
                stage_status=stage_status,
                stage_signals=stage_signals,
                source_data={
                    "job_number": job_number,
                    "summary": summary,
                },
            )
        )

    return jobs


def fetch_url(url: str, accept: str) -> bytes:
    request = Request(
        url,
        headers={"Accept": accept, "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        content = response.read(MAX_RESPONSE_BYTES + 1)

    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Le flux dépasse la limite de {MAX_RESPONSE_BYTES} octets.")

    return content


def fetch_job_bank(term: str, rows: int, location: str | None) -> list[SourceRecord]:
    return parse_feed(
        fetch_url(build_feed_url(term, rows), "application/atom+xml"),
        location=location,
    )


def parse_remotive_payload(
    payload: dict[str, object],
    location_filter: bool = True,
) -> list[SourceRecord]:
    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("La réponse Remotive ne contient pas de liste 'jobs'.")

    records: list[SourceRecord] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue

        title = str(raw_job.get("title") or "")
        job_type = str(raw_job.get("job_type") or "")
        category = str(raw_job.get("category") or "")
        description_html = str(raw_job.get("description") or "")
        description = _plain_text(description_html)
        required_location = str(raw_job.get("candidate_required_location") or "")
        normalized_location = _normalize(required_location)
        if _normalize(category) not in REMOTIVE_ALLOWED_CATEGORIES:
            continue
        if location_filter and not any(
            term in normalized_location
            for term in ("canada", "quebec", "montreal", "north america", "worldwide")
        ):
            continue

        raw_tags = raw_job.get("tags")
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        stage_status, stage_signals = classify_stage(title, job_type, description)
        records.append(
            SourceRecord(
                source="Remotive",
                source_id=str(raw_job.get("id") or raw_job.get("url") or ""),
                url=str(raw_job.get("url") or ""),
                title=title,
                employer=str(raw_job.get("company_name") or ""),
                location=required_location,
                salary=str(raw_job.get("salary") or ""),
                published_at=str(raw_job.get("publication_date") or ""),
                job_type=job_type,
                category=category,
                tags=tags,
                description=description,
                stage_status=stage_status,
                stage_signals=stage_signals,
                source_data={
                    key: value
                    for key, value in raw_job.items()
                    if key not in {"description"}
                },
            )
        )
    return records


def load_remotive_payload(cache_path: Path, refresh: bool = False) -> dict[str, object]:
    if not refresh and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict) or not isinstance(cached.get("payload"), dict):
            raise ValueError(f"Le cache Remotive est invalide : {cache_path}")
        fetched_at = datetime.fromisoformat(str(cached.get("fetched_at", "")))
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if 0 <= age_seconds < 24 * 60 * 60:
            return cached["payload"]

    query = urlencode({"category": "software-dev", "limit": 100})
    payload_bytes = fetch_url(
        f"{REMOTIVE_API_URL}?{query}",
        "application/json",
    )
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as error:
        raise ValueError("La réponse Remotive n'est pas un JSON valide.") from error
    if not isinstance(payload, dict):
        raise ValueError("La réponse Remotive doit être un objet JSON.")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def fetch_remotive(
    cache_path: Path,
    location_filter: bool = True,
    refresh: bool = False,
) -> list[SourceRecord]:
    payload = load_remotive_payload(cache_path, refresh=refresh)
    return parse_remotive_payload(payload, location_filter=location_filter)


def _offer_key(record: SourceRecord) -> tuple[str, ...]:
    normalized_title = _normalize(record.title)
    normalized_employer = _normalize(record.employer)
    normalized_location = _normalize(record.location)
    if normalized_title and normalized_employer and normalized_location:
        return normalized_title, normalized_employer, normalized_location
    if record.url:
        return ("url", record.url.casefold())
    return ("source_id", record.source, record.source_id or str(id(record)))


def aggregate_records(records: list[SourceRecord]) -> list[AggregatedOffer]:
    grouped: dict[tuple[str, ...], AggregatedOffer] = {}
    for record in records:
        key = _offer_key(record)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = AggregatedOffer(
                title=record.title,
                employer=record.employer,
                location=record.location,
                salary=record.salary,
                published_at=record.published_at,
                job_type=record.job_type,
                category=record.category,
                tags=list(record.tags),
                description=record.description,
                stage_status=record.stage_status,
                stage_signals=list(record.stage_signals),
                source_records=[record],
            )
            continue

        if any(
            prior.source == record.source
            and (
                (prior.source_id and prior.source_id == record.source_id)
                or (prior.url and prior.url == record.url)
            )
            for prior in existing.source_records
        ):
            continue

        for field_name in (
            "title",
            "employer",
            "location",
            "salary",
            "published_at",
            "job_type",
            "category",
            "description",
        ):
            if not getattr(existing, field_name) and getattr(record, field_name):
                setattr(existing, field_name, getattr(record, field_name))
        existing.tags = list(dict.fromkeys(existing.tags + record.tags))
        existing.stage_signals = list(
            dict.fromkeys(existing.stage_signals + record.stage_signals)
        )
        if record.stage_status == "likely_stage":
            existing.stage_status = "likely_stage"
        elif record.stage_status == "possible_stage" and existing.stage_status == "not_indicated":
            existing.stage_status = "possible_stage"
        existing.source_records.append(record)

    return list(grouped.values())


def print_offer(offer: AggregatedOffer) -> None:
    print(f"{offer.title} — {offer.employer or 'Employeur non précisé'}")
    print(f"  Lieu : {offer.location or 'Non précisé'}")
    print(f"  Stage : {offer.stage_status.replace('_', ' ')}")
    if offer.job_type:
        print(f"  Type : {offer.job_type}")
    if offer.salary:
        print(f"  Salaire : {offer.salary}")
    for record in offer.source_records:
        print(f"  Source : {record.source}")
        print(f"  Offre : {record.url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agréger des offres du Guichet-Emplois et de Remotive."
    )
    parser.add_argument(
        "--jobbank-term",
        action="append",
        help="Mot-clé Guichet-Emplois; répétable. Par défaut : développement et stages.",
    )
    parser.add_argument("--location", default="QC", help="Lieu Guichet-Emplois (défaut : QC).")
    parser.add_argument(
        "--all-jobbank-locations",
        action="store_true",
        help="Ne pas filtrer les résultats du Guichet-Emplois par lieu.",
    )
    parser.add_argument(
        "--all-remotive-locations",
        action="store_true",
        help="Inclure aussi les offres Remotive qui ne ciblent pas le Canada ou le monde entier.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Offres maximum affichées (défaut : 20).")
    parser.add_argument("--rows", type=int, default=100, help="Résultats demandés par flux (1 à 100).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("offres.json"),
        help="Fichier JSON local de sortie.",
    )
    parser.add_argument(
        "--refresh-remotive",
        action="store_true",
        help="Ignorer le cache Remotive (augmente le nombre de requêtes à l'API).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Afficher les résultats sans écrire le fichier JSON.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit doit être supérieur ou égal à 1.")
    if not 1 <= args.rows <= 100:
        parser.error("--rows doit être compris entre 1 et 100.")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    jobbank_location = None if args.all_jobbank_locations else args.location
    jobbank_terms = args.jobbank_term or list(JOB_BANK_TERMS)
    source_records: list[SourceRecord] = []
    errors: list[str] = []
    previous_request = 0.0

    for term in jobbank_terms:
        elapsed = time.monotonic() - previous_request if previous_request else JOB_BANK_CRAWL_DELAY_SECONDS
        if elapsed < JOB_BANK_CRAWL_DELAY_SECONDS:
            time.sleep(JOB_BANK_CRAWL_DELAY_SECONDS - elapsed)
        try:
            source_records.extend(fetch_job_bank(term, args.rows, jobbank_location))
        except (OSError, ET.ParseError, ValueError) as error:
            errors.append(f"Guichet-Emplois ({term}) : {error}")
        previous_request = time.monotonic()

    try:
        source_records.extend(
            fetch_remotive(
                Path(__file__).with_name("remotive-cache.json"),
                location_filter=not args.all_remotive_locations,
                refresh=args.refresh_remotive,
            )
        )
    except (OSError, ValueError) as error:
        errors.append(f"Remotive : {error}")

    for error in errors:
        print(f"AVERTISSEMENT : {error}", file=sys.stderr)

    if not source_records:
        if errors:
            raise RuntimeError("Aucune offre n'a été récupérée; consultez les erreurs ci-dessus.")
        print("Aucune offre ne correspond aux critères.")
        return

    offers = aggregate_records(source_records)
    print(
        f"{len(offers)} offres uniques; "
        f"{sum(offer.stage_status != 'not_indicated' for offer in offers)} stage(s) probable(s) ou à vérifier."
    )
    for offer in offers[: args.limit]:
        print_offer(offer)

    if not args.no_save:
        document = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "Guichet-Emplois": JOB_BANK_FEED_URL,
                "Remotive": REMOTIVE_API_URL,
            },
            "remotive_notice": (
                "Conserver l'attribution Remotive et le lien de chaque offre. "
                "Ne pas republier ces offres sur un site tiers. L'API recommande au plus "
                f"{REMOTIVE_MAX_REQUESTS_PER_DAY} requêtes par jour."
            ),
            "errors": errors,
            "offer_count": len(offers),
            "offers": [asdict(offer) for offer in offers],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nDonnées sauvegardées localement dans : {args.output}")


if __name__ == "__main__":
    main()
