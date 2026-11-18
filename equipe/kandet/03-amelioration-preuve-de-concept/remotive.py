"""Remotive : API JSON publique d'emplois à distance, avec cache de 24 h."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from analyse import classify_stage
from collecte import fetch_url
from modele import SourceRecord
from texte import normalize, plain_text


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
        if normalize(category) not in REMOTIVE_ALLOWED_CATEGORIES:
            continue
        required_location = str(raw_job.get("candidate_required_location") or "")
        if location_filter and not any(
            term in normalize(required_location) for term in REMOTIVE_CANADA_TERMS
        ):
            continue

        title = str(raw_job.get("title") or "")
        job_type = str(raw_job.get("job_type") or "")
        description = plain_text(str(raw_job.get("description") or ""))
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
