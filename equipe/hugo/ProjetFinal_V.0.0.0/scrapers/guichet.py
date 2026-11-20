"""
guichet.py - Scraper pour Guichet-Emplois Canada (Site 1 du TOP 3).
Reprend le moteur éprouvé d'Hugo : cascade Atom XML + HTML paginé + détails RDFa/DOM.
"""

from __future__ import annotations

import html
import logging
import re
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from models import JobOffer

logger = logging.getLogger("Top3.Guichet")

ATOM_URL = "https://www.guichetemplois.gc.ca/jobsearch/feed/jobSearchRSSfeed"
SEARCH_URL = "https://www.guichetemplois.gc.ca/rechercheemplois/rechercheemplois"

HEADERS = {
    "User-Agent": "JobsInsights-Student-Project/2.0 (Canada; Collège O'Sullivan de Québec; DEC-TI)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CA,fr;q=1.0,en-CA;q=0.5",
}

CNP_TI = {
    "21230", "21231", "21232", "21233", "21234", "21220", "21221", "21222",
    "21223", "21311", "22220", "22221", "22222", "20012", "21211", "21210"
}

TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps"
]


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_tech_skills(text: str) -> List[str]:
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
    text_lower = text.lower()
    if any(k in text_lower for k in ["télétravail", "teletravail", "à distance", "remote"]):
        return "Télétravail"
    if "hybride" in text_lower or "hybrid" in text_lower:
        return "Hybride"
    if any(k in text_lower for k in ["sur place", "en présentiel"]):
        return "Sur place"
    return "Non spécifié"


class CollecteurGuichet:
    """Collecteur optimisé pour Guichet-Emplois Canada."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def collecter_atom(self, limite: int = 25) -> List[JobOffer]:
        """Interroge le flux Atom XML francophone."""
        params = {
            "sort": "D",
            "fprov": "QC",
            "wid": "s",
            "action": "search",
            "lang": "fra",
            "term": "informatique"
        }
        try:
            resp = self.session.get(ATOM_URL, params=params, timeout=15)
            if resp.status_code != 200:
                return []
            
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            offres: List[JobOffer] = []

            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                link_elem = entry.find("atom:link", ns)
                summary_elem = entry.find("atom:summary", ns)
                id_elem = entry.find("atom:id", ns)
                updated_elem = entry.find("atom:updated", ns)

                titre = (title_elem.text or "").strip() if title_elem is not None else ""
                url = link_elem.get("href", "") if link_elem is not None else ""
                summary = (summary_elem.text or "").strip() if summary_elem is not None else ""
                raw_id = (id_elem.text or "").strip() if id_elem is not None else url
                date_pub = (updated_elem.text or "").strip() if updated_elem is not None else None

                id_m = re.search(r"(\d+)$", raw_id)
                clean_id = f"gc-{id_m.group(1)}" if id_m else f"gc-{abs(hash(url)) % 10000000}"

                # Découper le summary ("Lieu : Montréal (QC) | Salaire : ...")
                clean_desc = clean_html(summary)
                lieu = "Québec (QC)"
                if "à " in clean_desc:
                    lieu_part = clean_desc.split("à ")[-1].split(".")[0].strip()
                    if lieu_part:
                        lieu = lieu_part

                offre = JobOffer(
                    id=clean_id,
                    titre=titre,
                    entreprise="Guichet-Emplois",
                    lieu=lieu,
                    province="QC",
                    pays="Canada",
                    date_publication=date_pub,
                    modalite=detect_modalite(clean_desc),
                    type_poste="Temps plein",
                    competences_cles=extract_tech_skills(clean_desc),
                    description=clean_desc,
                    url_source=f"{url}&lang=fra" if "?" in url else f"{url}?lang=fra",
                    source="Guichet-Emplois",
                    partenaire="Guichet-Emplois (Atom Feed)",
                    methode_extraction="Atom-XML"
                )
                offres.append(offre)
                if len(offres) >= limite:
                    break

            return offres
        except Exception as e:
            logger.error(f"Erreur Atom Guichet-Emplois : {e}")
            return []

    def collecter(self, limite: int = 20, delai: float = 1.0) -> List[JobOffer]:
        """Collecte principale avec fallback."""
        logger.info(f"Collecte Guichet-Emplois (Cible : {limite} offres)...")
        offres = self.collecter_atom(limite=limite)
        logger.info(f"Guichet-Emplois : {len(offres)} offres récupérées.")
        return offres
