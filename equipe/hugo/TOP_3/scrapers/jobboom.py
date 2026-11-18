"""
jobboom.py - Scraper pour Jobboom Québec (Site 2 du TOP 3).
Extraction directe par balises sémantiques Schema.org (<script type="application/ld+json">).
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from models import JobOffer

logger = logging.getLogger("Top3.Jobboom")

BASE_URL = "https://www.jobboom.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (ProjetEtudiant-JobsInsights-Sullivan)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
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
    if any(k in text_lower for k in ["sur place", "en présentiel", "sur site"]):
        return "Sur place"
    return "Non spécifié"


class CollecteurJobboom:
    """Collecteur structuré pour Jobboom."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def obtenir_liens(self, mot_cle: str = "informatique", max_pages: int = 2) -> List[str]:
        slug = quote(mot_cle.strip().replace(" ", "-"))
        liens = set()

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/fr/emploi/{slug}/_lfrk"
            params = {"dk": mot_cle}
            if page > 1:
                params["page"] = str(page)

            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/offre-emploi/" in href:
                        liens.add(urljoin(BASE_URL, href.split("?")[0]))
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Erreur recherche Jobboom page {page} : {e}")
                break

        return sorted(list(liens))

    def collecter_fiche(self, url: str) -> Optional[JobOffer]:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            data = None
            for script in soup.find_all("script", type="application/ld+json"):
                if not script.string:
                    continue
                try:
                    parsed = json.loads(script.string.strip())
                    if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
                        data = parsed
                        break
                except json.JSONDecodeError:
                    continue

            if not data:
                return None

            id_m = re.search(r"_p(\d+)$", url)
            job_id = f"jb-{id_m.group(1)}" if id_m else f"jb-{abs(hash(url)) % 10000000}"

            titre = data.get("title") or "Titre non spécifié"
            h_org = data.get("hiringOrganization")
            entreprise = h_org.get("name") if isinstance(h_org, dict) else "Non spécifié"

            lieu = "Québec"
            province = "QC"
            loc = data.get("jobLocation")
            if isinstance(loc, dict):
                addr = loc.get("address")
                if isinstance(addr, dict):
                    lieu = addr.get("addressLocality") or lieu
                    province = addr.get("addressRegion") or province

            clean_desc = clean_html(data.get("description") or "")

            return JobOffer(
                id=job_id,
                titre=titre,
                entreprise=entreprise,
                lieu=lieu,
                province=province,
                pays="Canada",
                salaire="Non spécifié",
                date_publication=data.get("datePosted"),
                modalite=detect_modalite(clean_desc),
                type_poste="Temps plein",
                competences_cles=extract_tech_skills(clean_desc),
                description=clean_desc,
                url_source=url,
                source="Jobboom",
                partenaire="Jobboom Québec",
                methode_extraction="HTML+JSON-LD"
            )
        except Exception as e:
            logger.error(f"Erreur extraction fiche Jobboom {url} : {e}")
            return None

    def collecter(self, mot_cle: str = "informatique", limite: int = 15, delai: float = 1.0) -> List[JobOffer]:
        logger.info(f"Collecte Jobboom (Cible : {limite} offres)...")
        liens = self.obtenir_liens(mot_cle=mot_cle, max_pages=max(1, (limite // 15) + 1))
        offres: List[JobOffer] = []

        for idx, url in enumerate(liens[:limite], start=1):
            offre = self.collecter_fiche(url)
            if offre:
                offres.append(offre)
            time.sleep(delai)

        logger.info(f"Jobboom : {len(offres)} offres récupérées.")
        return offres
