"""
parsers.py - Logique pure de parsing et de filtrage pour l'API Remotive.
Inspiré des travaux de Kandet.
Totalement découplé du réseau et testable hors ligne.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from models import JobOffer

TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps"
]

ELIGIBLE_CANADA_KEYWORDS = [
    "canada", "worldwide", "anywhere", "north america", "americas", "quebec", "montreal", "remote"
]


def clean_html(raw_html: str) -> str:
    """Supprime les balises HTML et normalise les espaces."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_tech_skills(text: str, tags: Optional[List[str]] = None) -> List[str]:
    """Détecte les compétences techniques clés dans le texte et les tags d'API."""
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


def is_canada_eligible(raw_job: Dict[str, Any]) -> bool:
    """
    Vérifie si l'offre Remotive est accessible à un candidat résidant au Canada / Québec.
    """
    location = (raw_job.get("candidate_required_location") or "").lower()
    if not location:
        return True  # Par défaut worldwide
    return any(keyword in location for keyword in ELIGIBLE_CANADA_KEYWORDS)


def parse_remotive_job(raw_job: Dict[str, Any]) -> JobOffer:
    """
    Convertit un dictionnaire d'offre Remotive API en modèle standardisé JobOffer.
    """
    job_id = f"rem-{raw_job.get('id', abs(hash(raw_job.get('url', ''))))}"
    titre = raw_job.get("title") or "Titre non spécifié"
    entreprise = raw_job.get("company_name") or "Non spécifié"
    location_str = raw_job.get("candidate_required_location") or "Télétravail (Canada / Mondial)"
    
    # Description
    clean_desc = clean_html(raw_job.get("description") or "")
    
    # Date publication
    date_pub = raw_job.get("publication_date")
    
    # Salaire
    salaire = raw_job.get("salary") or "Non spécifié"
    
    # Type d'emploi
    raw_type = raw_job.get("job_type") or "full_time"
    type_poste = "Temps plein" if "full" in raw_type.lower() else raw_type
    
    # Compétences
    tags = raw_job.get("tags") or []
    skills = extract_tech_skills(clean_desc, tags=tags)

    return JobOffer(
        id=job_id,
        titre=titre,
        entreprise=entreprise,
        lieu=f"Télétravail ({location_str})",
        province="Télétravail",
        pays="Canada / International",
        salaire=salaire,
        date_publication=date_pub,
        modalite="Télétravail",
        type_poste=type_poste,
        competences_cles=skills,
        description=clean_desc,
        url_source=raw_job.get("url") or "https://remotive.com",
        source="Remotive",
        partenaire="Remotive API",
        methode_extraction="REST-API"
    )
