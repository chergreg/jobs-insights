"""
remotive.py - Scraper pour Remotive (Site 3 du TOP 3).
Extraction directe via l'API REST publique sans blocage anti-bot.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional

import requests
from models import JobOffer

logger = logging.getLogger("Top3.Remotive")

API_URL = "https://remotive.com/api/remote-jobs"

TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps"
]

ELIGIBLE_CANADA = ["canada", "worldwide", "anywhere", "north america", "americas", "quebec", "montreal"]


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_tech_skills(text: str, tags: Optional[List[str]] = None) -> List[str]:
    found = set()
    if tags:
        for t in tags:
            for s in TECH_SKILLS:
                if s.lower() == t.lower():
                    found.add(s)

    text_lower = (text or "").lower()
    for skill in TECH_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return sorted(list(found))


class CollecteurRemotive:
    """Collecteur officiel API REST pour Remotive."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "JobsInsights-Student-Project/2.0 (Canada; Education)",
            "Accept": "application/json"
        })

    def collecter(
        self,
        categorie: str = "software-dev",
        mot_cle: Optional[str] = None,
        limite: int = 15
    ) -> List[JobOffer]:
        logger.info(f"Collecte Remotive API (Cible : {limite} offres)...")
        params = {}
        if categorie:
            params["category"] = categorie
        if mot_cle:
            params["search"] = mot_cle

        try:
            resp = self.session.get(API_URL, params=params, timeout=20)
            if resp.status_code != 200:
                logger.error(f"HTTP {resp.status_code} sur Remotive API")
                return []

            data = resp.json()
            jobs = data.get("jobs", [])
            offres: List[JobOffer] = []

            for raw_job in jobs:
                loc = (raw_job.get("candidate_required_location") or "").lower()
                # Filtrer l'éligibilité pour les candidats au Canada
                if loc and not any(k in loc for k in ELIGIBLE_CANADA):
                    continue

                clean_desc = clean_html(raw_job.get("description") or "")
                tags = raw_job.get("tags") or []
                skills = extract_tech_skills(clean_desc, tags=tags)

                job_id = f"rem-{raw_job.get('id', abs(hash(raw_job.get('url', ''))))}"
                titre = raw_job.get("title") or "Titre non spécifié"
                entreprise = raw_job.get("company_name") or "Non spécifié"

                offre = JobOffer(
                    id=job_id,
                    titre=titre,
                    entreprise=entreprise,
                    lieu=f"Télétravail ({raw_job.get('candidate_required_location', 'Mondial')})",
                    province="Télétravail",
                    pays="Canada / International",
                    salaire=raw_job.get("salary") or "Non spécifié",
                    date_publication=raw_job.get("publication_date"),
                    modalite="Télétravail",
                    type_poste="Temps plein",
                    competences_cles=skills,
                    description=clean_desc,
                    url_source=raw_job.get("url") or "https://remotive.com",
                    source="Remotive",
                    partenaire="Remotive API",
                    methode_extraction="REST-API"
                )
                offres.append(offre)
                if len(offres) >= limite:
                    break

            logger.info(f"Remotive : {len(offres)} offres récupérées.")
            return offres
        except Exception as e:
            logger.error(f"Erreur API Remotive : {e}")
            return []
