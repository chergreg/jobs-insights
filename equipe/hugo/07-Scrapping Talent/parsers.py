"""
parsers.py - Logique pure d'extraction et de parsing pour Talent.com Canada.
Inspiré des travaux de Mamadou (Atelier 1) et aligné sur les exigences du cours (Livrable 3).
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

# Dictionnaire des compétences technologiques TI
TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps", "Ruby", "Rails",
    "CI/CD", "Agile", "Scrum", "QA", "SysAdmin", "VMware", "Power BI"
]

# Motifs de titres indiquant EXPLICITEMENT un poste HORS informatique / TI
IT_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"content\s+reviewer|office\s+assistant|customer\s+service|patient\s+care|"
    r"freelance\s+writer|copywriter|inside\s+sales|sales\s+contractor|video\s+annotation|"
    r"virtual\s+assistant|data\s+entry|telemarketing|recruiter|receptionist|accountant|"
    r"plombier|caissier|caissiere|magasinier|commis|chauffeur|livreur|cuisinier|"
    r"serveur|barista|assembleur|assembleuse|menuisier|mecanicien|soudeur|"
    r"manoeuvre|securite\s+gardien|agent\s+d'entretien|concierge"
    r")\b",
    flags=re.IGNORECASE
)

# Motifs de titres confirmant un poste du domaine TI / Informatique
IT_POSITIVE_PATTERNS = re.compile(
    r"\b(?:"
    r"developer|developpeur|developpeuse|programmer|programmeur|programmeuse|"
    r"engineer|ingenieur|ingenieure|software|logiciel|full[\s-]?stack|frontend|"
    r"front[\s-]?end|backend|back[\s-]?end|web|mobile|ios|android|devops|cloud|"
    r"infrastructure|sysadmin|administrateur\s+systeme|administrateur\s+des\s+systemes|"
    r"reseau|reseaux|network|data|donnees|database|base\s+de\s+donnees|dba|bi\b|"
    r"qa\b|quality\s+assurance|testeur|test\s+engineer|assurance\s+qualite|"
    r"tech\s+lead|technical\s+lead|architect|architecte|service\s+desk|support\s+technique|"
    r"technicien\s+informatique|technicienne\s+informatique|technicien\s+reseau|"
    r"it\b|ti\b|technologies\s+de\s+l'information|informatique|cybersecurity|"
    r"cybersecurite|securite\s+informatique|analyste\s+programmeur|analyste\s+en\s+informatique|"
    r"analyste\s+fonctionnel|analyste\s+affaires\s+ti|scrum\s+master|product\s+owner|"
    r"machine\s+learning|intelligence\s+artificielle"
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
    """Détecte les compétences techniques clés dans le texte."""
    if not text:
        return []
    found = set()
    text_lower = text.lower()
    for skill in TECH_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return sorted(list(found))


def detect_modalite(text: str) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    text_lower = (text or "").lower()
    if any(k in text_lower for k in ["télétravail", "teletravail", "à distance", "remote", "100% à distance"]):
        return "Télétravail"
    if "hybride" in text_lower or "hybrid" in text_lower:
        return "Hybride"
    if any(k in text_lower for k in ["sur place", "en présentiel", "sur site"]):
        return "Sur place"
    return "Non spécifié"


def format_salary(base_sal: Any) -> str:
    """Formate proprement la structure de salaire JSON-LD de Talent.com."""
    if not base_sal or not isinstance(base_sal, dict):
        return "Non spécifié"
    currency = base_sal.get("currency") or "CAD"
    val = base_sal.get("value")
    unit = ""
    if isinstance(val, dict):
        unit_text = val.get("unitText")
        if unit_text:
            u_upper = unit_text.upper()
            if u_upper in ["HOUR", "HEURE", "H"]:
                unit = "/ heure"
            elif u_upper in ["YEAR", "AN", "ANNÉE", "ANNEE"]:
                unit = "/ an"
            elif u_upper in ["MONTH", "MOIS"]:
                unit = "/ mois"
            else:
                unit = f"/ {unit_text.lower()}"

        v_min = val.get("minValue")
        v_max = val.get("maxValue")
        if v_min is not None and v_max is not None and v_min != v_max:
            return f"{v_min} $ - {v_max} $ {currency} {unit}".strip()
        elif v_min is not None:
            return f"{v_min} $ {currency} {unit}".strip()
        elif v_max is not None:
            return f"{v_max} $ {currency} {unit}".strip()
    elif isinstance(val, (int, float, str)):
        return f"{val} $ {currency}".strip()
    return "Non spécifié"


def is_it_offer(titre: str, description: str = "", competences: Optional[List[str]] = None) -> bool:
    """
    Filtre strict de validation informatique :
    1. Écarte formellement les postes hors-TI (magasinier, commis, caissier, service client, etc.).
    2. Valide si le titre correspond à un métier TI reconnu.
    3. Valide si au moins 2 compétences techniques reconnues sont présentes.
    """
    titre_norm = normalize_text(titre)

    # 1. Règle d'exclusion stricte
    if IT_EXCLUSION_PATTERNS.search(titre_norm):
        return False

    # 2. Règle positive de validation TI
    if IT_POSITIVE_PATTERNS.search(titre_norm):
        return True

    # 3. Compétences techniques identifiées
    if competences and len(competences) >= 2:
        return True

    # 4. Examen du résumé de la description
    desc_norm = normalize_text(description[:400])
    if any(k in desc_norm for k in ["programmation", "developpement logiciel", "infrastructure reseau", "base de donnees"]):
        return True

    return False


def matches_keyword(titre: str, description: str, keyword: Optional[str]) -> bool:
    """Vérifie si une offre correspond à un mot-clé recherché."""
    if not keyword or not keyword.strip():
        return True
    kw = normalize_text(keyword.strip())
    texte = normalize_text(f"{titre} {description[:600]}")
    return kw in texte


def extract_job_urls_from_search_html(search_html: str, base_url: str = "https://ca.talent.com") -> List[str]:
    """
    Extrait les URLs uniques d'offres d'emploi à partir de la page de résultats Talent.com.
    Combine la lecture de l'ItemList JSON-LD (@graph) et les balises <a> HTML.
    """
    if not search_html:
        return []

    urls: List[str] = []
    seen = set()

    # 1. Extraction depuis les blocs JSON-LD @graph -> ItemList
    soup = BeautifulSoup(search_html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for el in node.get("itemListElement", []):
                        if isinstance(el, dict):
                            item_obj = el.get("item")
                            url_target = None
                            if isinstance(item_obj, dict):
                                url_target = item_obj.get("url")
                            elif isinstance(item_obj, str):
                                url_target = item_obj
                            elif "url" in el:
                                url_target = el.get("url")

                            if url_target:
                                abs_url = urljoin(base_url, url_target)
                                if abs_url not in seen and "/view?id=" in abs_url:
                                    seen.add(abs_url)
                                    urls.append(abs_url)
        except (json.JSONDecodeError, Exception):
            continue

    # 2. Complément depuis les liens HTML <a> href="/fr/view?id=..."
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "/view?id=" in href:
            abs_url = urljoin(base_url, href)
            if abs_url not in seen:
                seen.add(abs_url)
                urls.append(abs_url)

    return urls


def extract_json_ld_job_posting_from_detail_html(detail_html: str) -> Optional[Dict[str, Any]]:
    """
    Extrait le dictionnaire JobPosting du bloc JSON-LD de la page de détail d'une offre Talent.com.
    """
    if not detail_html:
        return None

    soup = BeautifulSoup(detail_html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "JobPosting":
                    return node
        except (json.JSONDecodeError, Exception):
            continue

    return None


def parse_talent_job_posting(data: Dict[str, Any], url_source: str) -> JobOffer:
    """
    Convertit un dictionnaire JSON-LD JobPosting issu de Talent.com en modèle JobOffer standardisé.
    """
    # Identifiant unique
    id_match = re.search(r"id=([a-zA-Z0-9]+)", url_source)
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

    # Salaire
    salaire = format_salary(data.get("baseSalary"))

    # Description et compétences
    clean_desc = clean_html(data.get("description") or "")
    skills = extract_tech_skills(clean_desc)
    modalite = detect_modalite(f"{titre} {clean_desc}")

    # Type de poste
    employment_type = data.get("employmentType")
    type_poste = "Temps plein"
    if isinstance(employment_type, list):
        emp_str = " ".join(str(x) for x in employment_type).lower()
    else:
        emp_str = str(employment_type or "").lower()

    if "intern" in emp_str or "stage" in titre.lower() or "stage" in clean_desc[:200].lower():
        type_poste = "Stage"
    elif "part" in emp_str or "temps partiel" in emp_str:
        type_poste = "Temps partiel"
    elif "contract" in emp_str or "temporaire" in clean_desc[:200].lower():
        type_poste = "Contractuel"
    elif "full" in emp_str or "permanent" in clean_desc[:200].lower():
        type_poste = "Temps plein"

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
