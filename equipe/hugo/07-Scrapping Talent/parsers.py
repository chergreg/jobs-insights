"""
parsers.py - Logique pure d'extraction et de parsing pour Talent.com Canada.
Inspiré des travaux d'El Hadji Konaté.
Totalement découplé du réseau et testable hors ligne.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from models import JobOffer

TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps"
]


def clean_html(raw_html: str) -> str:
    """Supprime les balises HTML et normalise les espaces."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_tech_skills(text: str) -> List[str]:
    """Détecte les compétences techniques clés dans le texte."""
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for skill in TECH_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return sorted(list(set(found)))


def detect_modalite(text: str) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["télétravail", "teletravail", "à distance", "remote", "100% à distance"]):
        return "Télétravail"
    if "hybride" in text_lower or "hybrid" in text_lower:
        return "Hybride"
    if any(k in text_lower for k in ["sur place", "en présentiel", "sur site"]):
        return "Sur place"
    return "Non spécifié"


def extract_json_ld_job_postings_from_html(search_html: str) -> List[Dict[str, Any]]:
    """
    Extrait tous les objets JobPosting présents dans les blocs JSON-LD de la page de recherche Talent.com.
    Talent.com structure souvent ses offres dans un objet racine `@graph` contenant une `ItemList` ou directement des `JobPosting`.
    """
    if not search_html:
        return []
    soup = BeautifulSoup(search_html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    job_postings: List[Dict[str, Any]] = []

    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            items_to_check = []
            if isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items_to_check.extend(data["@graph"])
                else:
                    items_to_check.append(data)
            elif isinstance(data, list):
                items_to_check.extend(data)

            for item in items_to_check:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "JobPosting":
                    job_postings.append(item)
                elif item.get("@type") == "ItemList" and "itemListElement" in item:
                    for sub in item["itemListElement"]:
                        if isinstance(sub, dict):
                            sub_item = sub.get("item")
                            if isinstance(sub_item, dict) and sub_item.get("@type") == "JobPosting":
                                job_postings.append(sub_item)
        except json.JSONDecodeError:
            continue

    return job_postings


def parse_talent_job_posting(data: Dict[str, Any], default_url: str = "https://ca.talent.com") -> JobOffer:
    """
    Convertit un dictionnaire JSON-LD JobPosting issu de Talent.com en modèle JobOffer standardisé.
    """
    url_source = data.get("url") or default_url
    id_match = re.search(r"id=(\w+)", url_source)
    if id_match:
        job_id = f"tal-{id_match.group(1)}"
    else:
        job_id = f"tal-{abs(hash(url_source + str(data.get('title')))) % 10000000}"

    titre = data.get("title") or "Titre non spécifié"
    
    # Entreprise
    hiring_org = data.get("hiringOrganization")
    entreprise = "Non spécifié"
    if isinstance(hiring_org, dict):
        entreprise = hiring_org.get("name") or "Non spécifié"
    elif isinstance(hiring_org, str):
        entreprise = hiring_org

    # Localisation
    lieu = "Québec"
    province = "QC"
    job_loc = data.get("jobLocation")
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            lieu = addr.get("addressLocality") or lieu
            province = addr.get("addressRegion") or province

    # Date
    date_pub = data.get("datePosted")

    # Type de poste
    employment_type = data.get("employmentType")
    type_poste = "Non spécifié"
    if isinstance(employment_type, list):
        type_poste = ", ".join(employment_type)
    elif isinstance(employment_type, str):
        type_poste = employment_type

    # Description
    clean_desc = clean_html(data.get("description") or "")
    skills = extract_tech_skills(clean_desc)
    modalite = detect_modalite(clean_desc)

    # Salaire
    salaire = "Non spécifié"
    base_sal = data.get("baseSalary")
    if isinstance(base_sal, dict):
        val = base_sal.get("value")
        currency = base_sal.get("currency", "$")
        if isinstance(val, dict):
            v_min = val.get("minValue")
            v_max = val.get("maxValue")
            if v_min and v_max:
                salaire = f"{v_min} - {v_max} {currency}"
            elif v_min:
                salaire = f"{v_min} {currency}"
        elif isinstance(val, (int, float, str)):
            salaire = f"{val} {currency}"

    return JobOffer(
        id=job_id,
        titre=titre,
        entreprise=entreprise,
        lieu=lieu,
        province=province,
        pays="Canada",
        salaire=salaire,
        date_publication=date_pub,
        modalite=modalite,
        type_poste=type_poste,
        competences_cles=skills,
        description=clean_desc,
        url_source=url_source,
        source="Talent.com",
        partenaire="Talent.com Canada",
        methode_extraction="HTML+JSON-LD-Graph"
    )
