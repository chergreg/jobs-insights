"""
parsers.py - Logique pure de parsing et de filtrage strict TI pour l'API Remotive.
Inspiré des travaux de Kandet et aligné sur les exigences du cours (Livrable 3).
Totalement découplé du réseau et testable hors ligne.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any, Dict, List, Optional
from models import JobOffer

# Dictionnaire des compétences technologiques TI
TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP", "Go", "Rust",
    "SQL", "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Django", "Flask",
    "FastAPI", "Spring", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "Jira", "PostgreSQL", "MySQL", "MongoDB", "DevOps", "Ruby", "Rails",
    "CI/CD", "Agile", "Scrum", "QA", "SysAdmin"
]

# Lieux ouverts au Canada ou internationaux compatibles
ELIGIBLE_CANADA_KEYWORDS = [
    "canada", "worldwide", "anywhere", "north america", "americas", "quebec", "montreal", "remote"
]

# Motifs de titres indiquant EXPLICITEMENT un poste HORS informatique / TI (Anglais & Français)
IT_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"content\s+reviewer|content\s+creator|office\s+assistant|customer\s+service|"
    r"patient\s+care|freelance\s+writer|copywriter|inside\s+sales|sales\s+contractor|"
    r"video\s+annotation|virtual\s+assistant|data\s+entry|telemarketing|recruiter|"
    r"marketing|sales|writer|receptionist|accountant|plombier|caissier|magasinier|"
    r"commis|chauffeur|livreur|cuisinier|serveur|barista"
    r")\b",
    flags=re.IGNORECASE
)

# Motifs de titres confirmant un poste du domaine TI / Informatique (Anglais & Français)
IT_POSITIVE_PATTERNS = re.compile(
    r"\b(?:"
    r"developer|developpeur|programmer|programmeur|engineer|ingenieur|"
    r"software|logiciel|full[\s-]?stack|frontend|front[\s-]?end|backend|back[\s-]?end|"
    r"web|mobile|ios|android|devops|cloud|infrastructure|sysadmin|"
    r"system(?:s)?\s+administrator|administrateur\s+systeme|network|reseau|"
    r"data|donnees|database|base\s+de\s+donnees|dba|bi\b|"
    r"qa\b|quality\s+assurance|testeur|test\s+engineer|assurance\s+qualite|"
    r"tech\s+lead|technical\s+lead|architect|architecte|service\s+desk|support\s+engineer|"
    r"it\b|ti\b|information\s+technology|informatique|cybersecurity|cybersecurite|"
    r"security|securite|scrum\s+master|product\s+owner|machine\s+learning|ai\s+engineer"
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
        return True  # Par défaut accessible mondialement
    return any(keyword in location for keyword in ELIGIBLE_CANADA_KEYWORDS)


def is_it_offer(titre: str, description: str = "", competences: Optional[List[str]] = None) -> bool:
    """
    Filtre strict de validation informatique pour Remotive :
    1. Écarte formellement les postes hors-TI (Marketing, Service Client, Rédaction, Content Reviewer).
    2. Valide si le titre contient un métier TI ou si des compétences technologiques sont présentes.
    """
    titre_norm = normalize_text(titre)

    # 1. Règle d'exclusion stricte
    if IT_EXCLUSION_PATTERNS.search(titre_norm):
        return False

    # 2. Règle positive de validation TI
    if IT_POSITIVE_PATTERNS.search(titre_norm):
        return True

    # 3. Validation par la présence de compétences technologiques reconnues
    if competences and len(competences) > 0:
        return True

    # 4. Examen de secours dans la description
    desc_norm = normalize_text(description[:400])
    if any(k in desc_norm for k in ["software development", "web development", "cloud infrastructure", "database"]):
        return True

    return False


def matches_keyword(titre: str, description: str, tags: List[str], keyword: Optional[str]) -> bool:
    """
    Vérifie si une offre correspond à un mot-clé recherché avec équivalences bilingues (FR/EN).
    Ex: 'programmeur' ou 'developpeur' correspondra à 'developer', 'software', etc.
    """
    if not keyword or not keyword.strip():
        return True

    kw = normalize_text(keyword.strip())

    # Dictionnaire d'équivalences FR -> EN pour Remotive
    equivalences = {
        "programmeur": ["programmer", "developer", "development", "software"],
        "programmeuse": ["programmer", "developer", "development", "software"],
        "developpeur": ["developer", "development", "software", "programmer"],
        "developpeuse": ["developer", "development", "software", "programmer"],
        "logiciel": ["software"],
        "donnees": ["data", "analytics"],
        "reseau": ["network", "sysadmin", "infrastructure"],
        "securite": ["security", "cybersecurity"],
        "stage": ["intern", "internship", "junior"],
        "informatique": ["developer", "engineer", "software", "it", "tech", "computer"]
    }

    cibles = equivalences.get(kw, [kw])

    texte_global = normalize_text(f"{titre} {' '.join(tags)} {description[:600]}")
    return any(c in texte_global for c in cibles)


def parse_remotive_job(raw_job: Dict[str, Any]) -> JobOffer:
    """
    Convertit un dictionnaire d'offre Remotive API en modèle standardisé JobOffer.
    """
    job_id = f"rem-{raw_job.get('id', abs(hash(raw_job.get('url', ''))))}"
    titre = raw_job.get("title") or "Titre non spécifié"
    entreprise = raw_job.get("company_name") or "Non spécifié"
    location_str = raw_job.get("candidate_required_location") or "Télétravail (Canada / Mondial)"

    # Description nettoyée
    clean_desc = clean_html(raw_job.get("description") or "")

    # Date de publication
    date_pub = raw_job.get("publication_date")

    # Salaire
    salaire = raw_job.get("salary") or "Non spécifié"

    # Type d'emploi
    raw_type = (raw_job.get("job_type") or "full_time").lower()
    if "intern" in raw_type or "intern" in titre.lower() or "stage" in titre.lower():
        type_poste = "Stage"
    elif "part" in raw_type:
        type_poste = "Temps partiel"
    elif "contract" in raw_type:
        type_poste = "Contractuel"
    else:
        type_poste = "Temps plein"

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
