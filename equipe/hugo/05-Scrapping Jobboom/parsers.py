"""
parsers.py - Logique pure d'extraction, parsing et filtrage strict TI pour Jobboom.
Inspiré des travaux d'Elvira, d'El Hadji Konaté et de la classe (Livrable 3).
Totalement découplé du réseau et testable hors ligne.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from models import JobOffer

# Dictionnaire de compétences technologiques
TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "Oracle", "DevOps", "CI/CD",
    "Agile", "Scrum", "QA", "SysAdmin"
]

# Motifs de titres indiquant EXPLICITEMENT un poste HORS informatique
IT_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"plombier|plomberie|magasinier|caissier(?:e)?|assembleur(?:se)?|manutentionnaire|"
    r"mecanicien|electromecanicien|usinage|cnc|hvac|ventilation|batiment(?:s)?|construction|"
    r"comptable|comptabilite|receptionniste|cuisinier|serveur(?:se)?|barista|"
    r"vendeur(?:se)?|commis\s+bancaire|caissier\s+en\s+milieu\s+bancaire|"
    r"service\s+a\s+la\s+clientele|associe\s+specialise|associe\s+ventes|"
    r"adjoint(?:e)?\s+administratif(?:ve)?(?!\s+ti)|secretaire|commis\s+d['’]entrepot|"
    r"chauffeur|livreur|operateur\s+de\s+production|agent\s+de\s+securite"
    r")\b",
    flags=re.IGNORECASE
)

# Motifs de titres confirmant un poste du domaine TI / Informatique
IT_POSITIVE_PATTERNS = re.compile(
    r"\b(?:"
    r"informatique|informaticien(?:ne)?|ti\b|it\b|"
    r"developpeur(?:euse)?|developer|programmeur(?:euse)?|programmer|"
    r"logiciel(?:s)?|software|web|fullstack|full[\s-]?stack|frontend|front[\s-]?end|backend|back[\s-]?end|"
    r"devops|cloud|cybersecurite|cybersecurity|securite\s+informatique|"
    r"data|donnees|base(?:s)?\s+de\s+donnees|dba|bi\b|intelligence\s+d['’]affaires|"
    r"reseau(?:x)?|network|systeme(?:s)?|administrateur(?:trice)?\s+systeme|sysadmin|"
    r"support\s+technique|soutien\s+technique|soutien\s+informatique|helpdesk|help\s+desk|"
    r"technicien(?:ne)?\s+informatique|technicien(?:ne)?\s+ti|"
    r"analyste\s+fonctionnel|analyste\s+ti|analyste[\s-]programmeur|analyste|architecte\s+ti|architecte\s+logiciel|architecte|"
    r"specialiste\s+d['’]?application|gestionnaire\s+de\s+projets?\s+ti|"
    r"qa\b|assurance\s+qualite\s+logiciel|testeur(?:euse)?\s+logiciel|qualite\s+logiciel|"
    r"scrum\s+master|product\s+owner|integrateur(?:trice)?\s+web|stage\s+informatique"
    r")\b",
    flags=re.IGNORECASE
)


def normalize_text(text: str) -> str:
    """Supprime les accents et convertit en minuscules pour faciliter les correspondances."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def clean_html(raw_html: str) -> str:
    """Supprime les balises HTML et normalise les espaces."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_tech_skills(text: str) -> List[str]:
    """Détecte les compétences techniques clés dans le texte sans faux positifs."""
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for skill in TECH_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return sorted(list(set(found)))


def detect_modalite(text: str, data: Optional[Dict[str, Any]] = None) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    if data and data.get("jobLocationType") == "TELECOMMUTE":
        return "Télétravail"
    text_lower = text.lower()
    if any(k in text_lower for k in ["télétravail", "teletravail", "à distance", "remote", "100% à distance"]):
        return "Télétravail"
    if "hybride" in text_lower or "hybrid" in text_lower:
        return "Hybride"
    if any(k in text_lower for k in ["sur place", "en présentiel", "sur site"]):
        return "Sur place"
    return "Non spécifié"


def is_it_offer(titre: str, description: str = "", competences: Optional[List[str]] = None) -> bool:
    """
    Filtre strict de validation informatique :
    1. Rejette immédiatement les postes non-informatiques évidents (plomberie, caissier, magasinier, etc.).
    2. Valide si le titre contient un métier TI ou si des compétences technologiques TI sont détectées.
    """
    titre_norm = normalize_text(titre)

    # 1. Règle d'exclusion stricte
    if IT_EXCLUSION_PATTERNS.search(titre_norm):
        return False

    # 2. Règle positive de validation TI
    if IT_POSITIVE_PATTERNS.search(titre_norm):
        return True

    # 3. Validation par les compétences techniques présentes
    if competences and len(competences) > 0:
        return True

    # 4. Examen de secours dans la description normalisée
    desc_norm = normalize_text(description[:500])
    if any(k in desc_norm for k in ["developpement logiciel", "infrastructure ti", "programmation", "base de donnees"]):
        return True

    return False


def extract_job_links_from_html(search_html: str, base_url: str = "https://www.jobboom.com") -> List[str]:
    """
    Extrait les URLs des fiches d'offres depuis le code HTML de la page de recherche Jobboom.
    """
    if not search_html:
        return []
    soup = BeautifulSoup(search_html, "html.parser")
    links: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/offre-emploi/" in href and not href.startswith("javascript"):
            clean_href = href.split("?")[0]
            links.add(urljoin(base_url, clean_href))

    return sorted(list(links))


def extract_json_ld_from_detail_html(detail_html: str) -> Optional[Dict[str, Any]]:
    """
    Extrait le dictionnaire JSON-LD (@type == 'JobPosting') depuis le HTML d'une fiche d'offre Jobboom.
    """
    if not detail_html:
        return None
    soup = BeautifulSoup(detail_html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            if isinstance(data, dict):
                if data.get("@type") == "JobPosting":
                    return data
                if "@graph" in data and isinstance(data["@graph"], list):
                    for item in data["@graph"]:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            return item
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        return item
        except json.JSONDecodeError:
            continue
    return None


def parse_jobboom_json_ld(data: Dict[str, Any], job_url: str) -> JobOffer:
    """
    Convertit un dictionnaire JSON-LD JobPosting issu de Jobboom en modèle JobOffer standardisé.
    """
    id_match = re.search(r"_p(\d+)$", job_url)
    job_id = f"jb-{id_match.group(1)}" if id_match else f"jb-{abs(hash(job_url)) % 10000000}"

    titre = data.get("title") or "Titre non spécifié"
    
    # Entreprise
    hiring_org = data.get("hiringOrganization")
    entreprise = "Non spécifié"
    if isinstance(hiring_org, dict):
        entreprise = hiring_org.get("name") or "Non spécifié"
    elif isinstance(hiring_org, str):
        entreprise = hiring_org

    # Lieu et province
    lieu = "Québec"
    province = "QC"
    job_location = data.get("jobLocation")
    if isinstance(job_location, dict):
        address = job_location.get("address")
        if isinstance(address, dict):
            lieu = address.get("addressLocality") or lieu
            province = address.get("addressRegion") or province

    # Date
    date_pub = data.get("datePosted")

    # Type d'emploi
    type_map = {
        "FULL_TIME": "Temps plein",
        "PART_TIME": "Temps partiel",
        "INTERN": "Stage",
        "CONTRACTOR": "Contractuel",
        "TEMPORARY": "Temporaire"
    }
    employment_type = data.get("employmentType")
    type_poste = "Non spécifié"
    if isinstance(employment_type, list):
        type_poste = ", ".join(type_map.get(t, t) for t in employment_type)
    elif isinstance(employment_type, str):
        type_poste = type_map.get(employment_type, employment_type)

    if any(k in titre.lower() for k in ["stage", "stagiaire", "intern"]):
        type_poste = "Stage"

    # Description
    raw_desc = data.get("description") or ""
    clean_desc = clean_html(raw_desc)

    # Compétences et modalité
    skills = extract_tech_skills(clean_desc)
    modalite = detect_modalite(clean_desc, data=data)

    # Salaire
    salaire = "Non spécifié"
    base_salary = data.get("baseSalary")
    if isinstance(base_salary, dict):
        val = base_salary.get("value")
        currency = base_salary.get("currency", "$")
        if isinstance(val, dict):
            min_v = val.get("minValue")
            max_v = val.get("maxValue")
            if min_v and max_v:
                salaire = f"{min_v} - {max_v} {currency}"
            elif min_v:
                salaire = f"{min_v} {currency}"
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
        url_source=job_url,
        source="Jobboom",
        partenaire="Jobboom Québec",
        methode_extraction="HTML+JSON-LD"
    )
