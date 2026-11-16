"""
scrapers/remotive.py - Connecteur Remotive bonifié (API REST + télétravail / stages TI).

Reprend et perfectionne la contribution de Kandet :
1. Intégration du client API REST publique Remotive (endpoint /api/remote-jobs).
2. Politique stricte de cache local 24 h (respect scrupuleux de la limite de 4 requêtes/jour de Remotive).
3. Découplage réseau complet avec support d'un mode hors ligne garanti (offline_mode).
4. Moteur de classification géographique multi-niveaux ciblant le Canada, le Québec et le télétravail éligible pour les étudiants TI.
5. Détection native des stages via job_type == 'internship' complétée par un classifieur sémantique contextuel.
6. Extraction et normalisation des compétences clés TI (fusion des tags API et de la détection lexicale).
7. Alignement strict sur le schéma Pydantic unifié JobOffer (models.py).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import html
import json
import logging
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import urlencode
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

try:
    from models import JobOffer
except ImportError:
    from ..models import JobOffer

try:
    from .guichet_emplois import (
        TECH_PATTERNS,
        classify_stage,
        clean_text as shared_clean_text,
        extract_tech_skills as shared_extract_tech_skills,
    )
except ImportError:
    try:
        from scrapers.guichet_emplois import (
            TECH_PATTERNS,
            classify_stage,
            clean_text as shared_clean_text,
            extract_tech_skills as shared_extract_tech_skills,
        )
    except ImportError:
        TECH_PATTERNS = None
        classify_stage = None
        shared_clean_text = None
        shared_extract_tech_skills = None


logger = logging.getLogger("RemotiveScraper")

# --- Paramètres et constantes Remotive ---------------------------------------

REMOTIVE_BASE_URL = "https://remotive.com"
REMOTIVE_API_BASE_URL = "https://remotive.com/api"
REMOTIVE_JOBS_ENDPOINT = f"{REMOTIVE_API_BASE_URL}/remote-jobs"
REMOTIVE_CATEGORIES_ENDPOINT = f"{REMOTIVE_API_BASE_URL}/remote-jobs/categories"

# Règles éthiques et limites d'utilisation de l'API Remotive
REMOTIVE_CACHE_HOURS = 24  # Cache obligatoire 24h (données mises à jour lentement)
REMOTIVE_MAX_REQUESTS_PER_DAY = 4  # Recommandation formelle des créateurs de Remotive
REMOTIVE_DELAY_SECONDS = 1.0  # Temporisation éthique

USER_AGENT = (
    "jobs-insights-atelier/1.0 "
    "(Projet etudiant DEC Informatique College O'Sullivan de Quebec; "
    "contact: gregory@jobs-insights.local)"
)

# Catégories TI reconnues par Remotive et filtrables
REMOTIVE_TI_CATEGORIES = {
    "software development",
    "software-development",
    "software-dev",
    "data and analytics",
    "data",
    "devops",
    "devops / sysadmin",
    "quality assurance",
    "qa",
    "information technology",
    "it",
    "artificial intelligence",
    "ai",
    "engineering",
    "product management",
    "product",
    "design",
    "research",
    "cybersecurity",
    "security",
}

# Rôles / Mots-clés TI pour validation de secours
TI_ROLE_PATTERNS = re.compile(
    r"\b(?:developer|developpeur|developpeuse|engineer|ingenieur|ingenieure|"
    r"programmer|programmeur|architect|architecte|devops|sysadmin|"
    r"full[\s-]?stack|front[\s-]?end|back[\s-]?end|software|logiciel|"
    r"data|donnees|analyst|analyste|qa|tester|testeur|cloud|ia|ai|machine\s+learning)\b",
    re.IGNORECASE,
)

# Dictionnaire de normalisation des tags techniques Remotive vers libellés officiels
TAG_TECH_MAPPING: Dict[str, str] = {
    "python": "Python",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "es6": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "angular": "Angular",
    "angularjs": "Angular",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "java": "Java",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "c#": "C#",
    "csharp": "C#",
    "c++": "C++",
    "cpp": "C++",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "git": "Git",
    "github": "Git",
    "gitlab": "Git",
    "linux": "Linux",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "agile": "Agile",
    "scrum": "Scrum",
    "qa": "QA",
    "testing": "QA",
    "php": "PHP",
    "ruby": "Ruby",
    "ror": "Ruby on Rails",
    "ruby/rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
}

# Motifs de compétences techniques de repli si le module guichet_emplois n'est pas chargé
FALLBACK_TECH_PATTERNS = [
    ("Python", re.compile(r"\bpython\b", re.IGNORECASE)),
    ("Java", re.compile(r"\bjava\b(?!script)", re.IGNORECASE)),
    ("JavaScript", re.compile(r"\b(?:javascript|js)\b", re.IGNORECASE)),
    ("TypeScript", re.compile(r"\btypescript\b", re.IGNORECASE)),
    ("C#", re.compile(r"\bc#(?=[^\w#]|$)", re.IGNORECASE)),
    ("C++", re.compile(r"\bc\+\+(?=[^\w\+]|$)", re.IGNORECASE)),
    ("C", re.compile(r"(?:\blangage\s+c\b|\bprog(?:rammation)?\s+c\b|\bc\s*\/\s*c\+\+|\bansi\s+c\b)", re.IGNORECASE)),
    ("React", re.compile(r"\breact(?:\.js)?\b", re.IGNORECASE)),
    ("Angular", re.compile(r"\bangular(?:\.js)?\b", re.IGNORECASE)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|vuejs|framework\s+vue)\b", re.IGNORECASE)),
    ("Node.js", re.compile(r"\bnode(?:\.js)?\b", re.IGNORECASE)),
    ("PHP", re.compile(r"\bphp\b", re.IGNORECASE)),
    ("SQL", re.compile(r"\bsql\b", re.IGNORECASE)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.IGNORECASE)),
    ("MySQL", re.compile(r"\bmysql\b", re.IGNORECASE)),
    ("MongoDB", re.compile(r"\bmongodb\b", re.IGNORECASE)),
    ("Docker", re.compile(r"\bdocker\b", re.IGNORECASE)),
    ("Kubernetes", re.compile(r"\b(?:kubernetes|k8s)\b", re.IGNORECASE)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", re.IGNORECASE)),
    ("Azure", re.compile(r"\bazure\b", re.IGNORECASE)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", re.IGNORECASE)),
    ("Git", re.compile(r"\bgit\b(?!e)", re.IGNORECASE)),
    ("Linux", re.compile(r"\blinux\b", re.IGNORECASE)),
    ("Spring Boot", re.compile(r"\bspring\s*boot\b", re.IGNORECASE)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.IGNORECASE)),
    ("Django", re.compile(r"\bdjango\b", re.IGNORECASE)),
    ("CI/CD", re.compile(r"\bci[\/\-]cd\b", re.IGNORECASE)),
    ("Agile", re.compile(r"\bagile\b", re.IGNORECASE)),
    ("Scrum", re.compile(r"\bscrum\b", re.IGNORECASE)),
    ("QA", re.compile(r"\b(?:assurance\s+qualit[eé]|qa)\b", re.IGNORECASE)),
]


# --- Exceptions personnalisées -----------------------------------------------

class RemotiveError(Exception):
    """Exception de base pour les erreurs du module Remotive."""
    pass


class OfflineModeError(RemotiveError):
    """Exception levée lorsqu'une requête réseau est requise en mode hors ligne sans cache."""
    pass


# --- Fonctions pures de nettoyage et normalisation ---------------------------

def clean_text(raw_html: str) -> str:
    """Supprime les balises HTML et condense les espaces."""
    if shared_clean_text is not None:
        return shared_clean_text(raw_html)
    if not raw_html:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw_html))
    txt = html.unescape(txt)
    return " ".join(txt.split())


def _normalize(value: str) -> str:
    """Convertit en minuscules sans accents pour les comparaisons textuelles."""
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def parse_remotive_date(raw_date: Optional[str]) -> Optional[str]:
    """Extrait la date au format ISO AAAA-MM-JJ depuis une chaîne Remotive.

    Exemples :
    - '2026-11-14T20:33:53' -> '2026-11-14'
    - '2026-11-09' -> '2026-11-09'
    - 'Invalid' -> None
    """
    if not raw_date:
        return None
    val = str(raw_date).strip()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
    if m:
        return m.group(1)
    return None


def extract_tech_skills(text: str) -> List[str]:
    """Extrait les compétences techniques en éliminant les faux positifs récurrents."""
    if shared_extract_tech_skills is not None:
        return shared_extract_tech_skills(text)
    if not text:
        return []
    found: Set[str] = set()
    patterns = TECH_PATTERNS if TECH_PATTERNS is not None else FALLBACK_TECH_PATTERNS
    for tech_name, pattern in patterns:
        if pattern.search(text):
            found.add(tech_name)
    return sorted(list(found))


def normalize_remotive_tags(raw_tags: Optional[List[Any]]) -> List[str]:
    """Convertit et normalise la liste brute de tags de l'API Remotive."""
    if not raw_tags or not isinstance(raw_tags, list):
        return []
    normalized: Set[str] = set()
    for tag in raw_tags:
        if not tag:
            continue
        tag_str = str(tag).strip()
        tag_lower = tag_str.lower()
        if tag_lower in TAG_TECH_MAPPING:
            normalized.add(TAG_TECH_MAPPING[tag_lower])
        else:
            # Si le tag n'est pas dans le mapping, on vérifie si un pattern technique le reconnaît
            for tech_name, pattern in (TECH_PATTERNS or FALLBACK_TECH_PATTERNS):
                if pattern.fullmatch(tag_str) or pattern.search(tag_str):
                    normalized.add(tech_name)
                    break
    return sorted(list(normalized))


# --- Moteur de classification géographique -----------------------------------

def classify_remotive_location(raw_location: Optional[str]) -> Dict[str, Any]:
    """Analyse et classifie la localisation exigée par l'offre Remotive.

    Détermine :
    - is_canada_eligible : True si accessible aux résidents du Canada / Québec (télétravail éligible).
    - geo_level : 'quebec', 'canada', 'north_america', 'worldwide', 'other'
    - lieu : Libellé synthétique normalisé (ex: 'Québec (Télétravail)', 'Canada (Télétravail)', etc.)
    - province : 'QC' par défaut pour les offres ouvertes aux Québécois, ou code de province spécifique.
    - pays : 'Canada' si éligible, ou nom de la région/pays sinon.

    Règles :
    1. Si vide ou 'Worldwide' / 'Anywhere' -> Télétravail mondial ouvert à tous (Canada inclus).
    2. Si mention explicite de Québec / Montréal -> Niveau québécois ciblé.
    3. Si mention de 'Canada' ou ville/province canadienne -> Niveau canadien direct.
    4. Si mention de 'USA, Canada' / 'North America' / 'Americas' -> Niveau nord-américain (ouvert au Canada).
    5. Si mention exclusive d'un autre pays sans Canada ('USA only', 'Europe only', 'LATAM') -> Hors cible Canada.
    """
    if not raw_location or not str(raw_location).strip():
        return {
            "is_canada_eligible": True,
            "geo_level": "worldwide",
            "lieu": "Télétravail mondial",
            "province": "QC",
            "pays": "Canada",
        }

    loc_str = str(raw_location).strip()
    norm_loc = _normalize(loc_str)

    # 1. Vérification spécifique Québec
    quebec_indicators = [
        "quebec", "montreal", "laval", "gatineau", "sherbrooke",
        "trois-rivieres", "levis", "saguenay", "longueuil", "qc"
    ]
    # On recherche les mots ou séquences
    if any(re.search(rf"\b{re.escape(k)}\b", norm_loc) for k in quebec_indicators):
        return {
            "is_canada_eligible": True,
            "geo_level": "quebec",
            "lieu": "Québec (Télétravail)",
            "province": "QC",
            "pays": "Canada",
        }

    # 2. Vérification Provinces canadiennes spécifiques
    provinces_map = {
        "ontario": "ON", "toronto": "ON", "ottawa": "ON",
        "british columbia": "BC", "colombie-britannique": "BC", "vancouver": "BC",
        "alberta": "AB", "calgary": "AB", "edmonton": "AB",
        "manitoba": "MB", "winnipeg": "MB",
        "saskatchewan": "SK", "regina": "SK", "saskatoon": "SK",
        "nova scotia": "NS", "nouvelle-ecosse": "NS", "halifax": "NS",
        "new brunswick": "NB", "nouveau-brunswick": "NB", "fredericton": "NB", "moncton": "NB",
    }
    for prov_name, prov_code in provinces_map.items():
        if re.search(rf"\b{re.escape(prov_name)}\b", norm_loc):
            return {
                "is_canada_eligible": True,
                "geo_level": "canada",
                "lieu": f"Canada [{prov_code}] (Télétravail)",
                "province": prov_code,
                "pays": "Canada",
            }

    # 3. Mention Amérique du Nord / Amériques (ouvert au Canada)
    north_america_indicators = [
        "north america", "americas", "amerique du nord",
        "usa, canada", "canada, usa", "usa or canada", "canada or usa",
        "usa/canada", "us/canada", "latam, europe, usa, canada", "europe, usa, canada"
    ]
    if any(k in norm_loc for k in north_america_indicators):
        return {
            "is_canada_eligible": True,
            "geo_level": "north_america",
            "lieu": "Amérique du Nord (Télétravail)",
            "province": "QC",
            "pays": "Canada",
        }

    # 4. Mention directe du Canada
    if re.search(r"\bcanada\b", norm_loc):
        return {
            "is_canada_eligible": True,
            "geo_level": "canada",
            "lieu": "Canada (Télétravail)",
            "province": "QC",
            "pays": "Canada",
        }

    # 5. Mention Télétravail mondial (Worldwide, Anywhere)
    worldwide_indicators = [
        "worldwide", "anywhere", "global", "remote worldwide", "anywhere in the world"
    ]
    if any(k in norm_loc for k in worldwide_indicators):
        return {
            "is_canada_eligible": True,
            "geo_level": "worldwide",
            "lieu": "Télétravail mondial",
            "province": "QC",
            "pays": "Canada",
        }

    # 6. Autres localisations (ex: USA only, Europe only, UK, LATAM sans mention Canada)
    return {
        "is_canada_eligible": False,
        "geo_level": "other",
        "lieu": f"{loc_str} (Télétravail)",
        "province": "Hors Canada",
        "pays": loc_str,
    }


# --- Détection de stage et normalisation du contrat --------------------------

def parse_remotive_employment_and_stage(
    raw_job: Dict[str, Any],
    clean_description: str
) -> Tuple[str, bool, str]:
    """Détermine le type de poste, l'indicateur de stage et le statut de stage.

    Retourne : (type_poste, est_stage, statut_stage)
    """
    job_type_raw = str(raw_job.get("job_type") or "").strip().lower()
    title_raw = str(raw_job.get("title") or "").strip()

    # Détection native prioritaire via l'attribut officiel Remotive job_type == 'internship'
    if job_type_raw in {"internship", "intern", "stage", "coop", "co-op"}:
        return "Stage", True, "confirmed_stage"

    # Mappage des types de contrats standards
    if job_type_raw in {"full_time", "fulltime", "full-time"}:
        type_poste = "Temps plein"
    elif job_type_raw in {"part_time", "parttime", "part-time"}:
        type_poste = "Temps partiel"
    elif job_type_raw in {"contract"}:
        type_poste = "Contrat"
    elif job_type_raw in {"freelance"}:
        type_poste = "Pigiste / Freelance"
    else:
        type_poste = "Temps plein"

    # Affinement contextuel du stage via classifieur sémantique si non confirmé
    est_stage = False
    statut_stage = "not_indicated"
    if classify_stage is not None:
        is_st, st_stat, _ = classify_stage(title_raw, type_poste, clean_description)
        if is_st:
            est_stage = True
            statut_stage = st_stat
            if type_poste == "Temps plein" and st_stat == "confirmed_stage":
                type_poste = "Stage"
    else:
        # Repli basique si classify_stage non importé
        norm_t = _normalize(title_raw)
        if any(w in norm_t for w in ["stage", "stagiaire", "intern", "internship", "coop"]):
            est_stage = True
            statut_stage = "confirmed_stage"
            type_poste = "Stage"

    return type_poste, est_stage, statut_stage


# --- Parseur d'offre individuelle Remotive ------------------------------------

def parse_remotive_job(raw_job: Dict[str, Any]) -> Optional[JobOffer]:
    """Convertit un dictionnaire d'offre brute issu de l'API Remotive en un objet JobOffer typé.

    Conforme aux règles de AGENTS.md :
    - Zéro hallucination : salaire laissé à None si absent ou vide.
    - URL direct propre pointant vers Remotive.
    - Modalité fixée à 'Télétravail' (nature intrinsèque de Remotive).
    - Compétences techniques fusionnant tags et extraction lexicale.
    """
    if not isinstance(raw_job, dict):
        return None

    raw_id = raw_job.get("id")
    url = raw_job.get("url")
    if not raw_id and not url:
        return None

    job_id = f"rem-{raw_id}" if raw_id is not None else f"rem-{hash(str(url)) % 10000000}"
    titre = clean_text(str(raw_job.get("title") or ""))
    if not titre:
        return None

    entreprise = clean_text(str(raw_job.get("company_name") or "")) or "Non spécifié"
    raw_desc = str(raw_job.get("description") or "")
    description = clean_text(raw_desc) if raw_desc else None

    # Classification géographique
    raw_loc = raw_job.get("candidate_required_location")
    geo_info = classify_remotive_location(raw_loc)

    # Type de poste et détection de stage
    type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(
        raw_job,
        description or ""
    )

    # Date de publication ISO AAAA-MM-JJ
    date_pub = parse_remotive_date(raw_job.get("publication_date"))

    # Salaire (sans aucune invention)
    raw_salary = str(raw_job.get("salary") or "").strip()
    salaire = raw_salary if raw_salary else None

    # Extraction et consolidation des compétences techniques
    tags_skills = normalize_remotive_tags(raw_job.get("tags"))
    text_to_scan = f"{titre} {description or ''}"
    text_skills = extract_tech_skills(text_to_scan)
    competences_combinees = sorted(list(set(tags_skills + text_skills)))

    return JobOffer(
        id=job_id,
        titre=titre,
        entreprise=entreprise,
        lieu=geo_info["lieu"],
        province=geo_info["province"],
        pays=geo_info["pays"],
        url=str(url or f"{REMOTIVE_BASE_URL}/job/{raw_id}"),
        source="remotive",
        source_partenaire=None,
        date_publication=date_pub,
        type_poste=type_poste,
        modalite="Télétravail",
        est_stage=est_stage,
        statut_stage=statut_stage,
        description=description,
        competences_cles=competences_combinees,
        salaire=salaire,
    )


# --- Parseur de payload global Remotive ---------------------------------------

def parse_remotive_payload(
    payload: Dict[str, Any],
    geo_filter: str = "canada_eligible",
    category_filter: bool = True,
    stage_only: bool = False,
    limit: Optional[int] = None,
) -> List[JobOffer]:
    """Parse un payload JSON Remotive complet et retourne une liste filtrée de JobOffer.

    Filtres :
    - geo_filter :
        'canada_eligible' (défaut) : offres ouvertes au Canada / Québec (QC, CA, Amérique du Nord, Worldwide).
        'canada_only' : restreint strictement au Canada ou Québec.
        'quebec_only' : restreint strictement au Québec.
        'all' : aucune restriction géographique.
    - category_filter :
        True (défaut) : ne retient que les métiers TI (catégorie TI ou compétences/rôle TI détectés).
        False : retient toutes les offres sans filtrage par métier.
    - stage_only :
        True : retient uniquement les offres qualifiées de stages.
        False : retient toutes les offres.
    - limit :
        Nombre maximal d'offres à retourner (ou None pour la totalité).
    """
    if not isinstance(payload, dict):
        raise ValueError("Le payload Remotive doit être un dictionnaire JSON.")

    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("La réponse Remotive ne contient pas de liste 'jobs' valide.")

    offers: List[JobOffer] = []
    seen_ids: Set[str] = set()

    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue

        category = str(raw_job.get("category") or "")
        norm_cat = _normalize(category)

        # 1. Filtre par catégorie TI
        if category_filter:
            is_cat_ti = norm_cat in REMOTIVE_TI_CATEGORIES
            raw_title = str(raw_job.get("title") or "")
            is_role_ti = bool(TI_ROLE_PATTERNS.search(raw_title))
            if not is_cat_ti and not is_role_ti:
                continue

        # 2. Filtre géographique
        raw_loc = raw_job.get("candidate_required_location")
        geo_info = classify_remotive_location(raw_loc)

        if geo_filter == "canada_eligible" and not geo_info["is_canada_eligible"]:
            continue
        elif geo_filter == "canada_only" and geo_info["geo_level"] not in ("quebec", "canada"):
            continue
        elif geo_filter == "quebec_only" and geo_info["geo_level"] != "quebec":
            continue

        # 3. Conversion en JobOffer
        offer = parse_remotive_job(raw_job)
        if not offer or offer.id in seen_ids:
            continue

        # 4. Filtre stage optionnel
        if stage_only and not offer.est_stage:
            continue

        seen_ids.add(offer.id)
        offers.append(offer)

        if limit is not None and len(offers) >= limit:
            break

    return offers


# --- Classe Collecteur Remotive avec Cache 24 h Découplé ---------------------

class RemotiveScraper:
    """Collecteur Remotive avec cache local 24 h et mode hors ligne rigoureux.

    Respecte les conditions d'utilisation de Remotive :
    - Au plus 4 requêtes par jour recommandées par les créateurs de l'API.
    - Cache local de 24 heures pour éviter les appels redondants.
    - Attribution complète vers Remotive et lien direct vers l'offre.
    - Découplage réseau strict pour les tests unitaires et la reproduction hors ligne.
    """

    def __init__(
        self,
        cache_dir: Optional[Path | str] = None,
        cache_hours: float = REMOTIVE_CACHE_HOURS,
        delai_secondes: float = REMOTIVE_DELAY_SECONDS,
        user_agent: str = USER_AGENT,
        offline_mode: bool = False,
        timeout: int = 15,
    ):
        self.cache_hours = cache_hours
        self.delai_secondes = delai_secondes
        self.user_agent = user_agent
        self.offline_mode = offline_mode
        self.timeout = timeout
        self.last_request_time: float = 0.0

        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).resolve().parent.parent / "cache" / "remotive"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_file(self, category: Optional[str] = None) -> Path:
        """Retourne le chemin du fichier de cache associé à une catégorie."""
        if category:
            safe_cat = re.sub(r"[^\w\-]", "_", _normalize(category)).strip("_")
            return self.cache_dir / f"remotive_cache_{safe_cat}.json"
        return self.cache_dir / "remotive_cache.json"

    def is_cache_fresh(self, cache_file: Path) -> bool:
        """Vérifie si le fichier de cache existe et date de moins de `cache_hours` (24 h)."""
        if not cache_file.is_file():
            return False

        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            if not isinstance(cached_data, dict):
                return False

            fetched_at_str = cached_data.get("fetched_at")
            if not fetched_at_str:
                return False

            fetched_at = datetime.fromisoformat(str(fetched_at_str))
            now = datetime.now(timezone.utc)

            # Si l'horodatage est naïf, on l'assume UTC
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)

            age_seconds = (now - fetched_at).total_seconds()
            return 0 <= age_seconds < (self.cache_hours * 3600)
        except Exception as err:
            logger.warning(f"Erreur lors de la lecture du cache {cache_file} : {err}")
            return False

    def load_from_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """Charge le payload contenu dans le cache si valide."""
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached_data, dict) and isinstance(cached_data.get("payload"), dict):
                return cached_data["payload"]
        except Exception as err:
            logger.warning(f"Impossible de décoder le cache {cache_file} : {err}")
        return None

    def save_to_cache(
        self,
        cache_file: Path,
        payload: Dict[str, Any],
        request_url: str,
        category: Optional[str] = None
    ) -> None:
        """Enregistre le payload et ses métadonnées dans le fichier de cache local."""
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        jobs_list = payload.get("jobs", []) if isinstance(payload, dict) else []
        envelope = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "request_url": request_url,
            "category": category,
            "total_jobs_in_payload": len(jobs_list) if isinstance(jobs_list, list) else 0,
            "payload": payload,
        }
        cache_file.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        logger.info(f"Cache Remotive enregistré : {cache_file} ({envelope['total_jobs_in_payload']} offres)")

    def fetch_payload(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        refresh: bool = False,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Récupère le payload JSON de l'API Remotive (via cache 24h prioritaire ou réseau).

        Lève OfflineModeError si un appel réseau est nécessaire en mode hors ligne.
        """
        cache_file = self.get_cache_file(category)

        # 1. Utilisation prioritaire du cache valide
        if use_cache and not refresh and self.is_cache_fresh(cache_file):
            payload = self.load_from_cache(cache_file)
            if payload is not None:
                logger.info(f"Payload Remotive chargé depuis le cache frais : {cache_file}")
                return payload

        # 2. Mode hors ligne : blocage absolu des appels réseau
        if self.offline_mode:
            # Si un cache même expiré existe, on peut l'utiliser en mode offline avec avertissement
            if cache_file.is_file():
                payload = self.load_from_cache(cache_file)
                if payload is not None:
                    logger.warning(f"Mode hors ligne : utilisation du cache local (expiré) : {cache_file}")
                    return payload
            raise OfflineModeError(
                f"Mode hors ligne activé : aucun cache disponible pour {cache_file} "
                "et les requêtes réseau sont interdites."
            )

        # 3. Temporisation éthique avant requête HTTP
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delai_secondes:
            time.sleep(self.delai_secondes - elapsed)

        params: Dict[str, str] = {}
        if category:
            params["category"] = category
        if search:
            params["search"] = search

        request_url = REMOTIVE_JOBS_ENDPOINT
        if params:
            request_url = f"{REMOTIVE_JOBS_ENDPOINT}?{urlencode(params)}"

        logger.info(f"Appel réseau API Remotive : {request_url}")
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            resp = requests.get(request_url, headers=headers, timeout=self.timeout)
            self.last_request_time = time.time()

            if resp.status_code == 429:
                raise RemotiveError(
                    "Limite de requêtes atteinte sur Remotive (HTTP 429). "
                    "Veuillez réutiliser le cache local."
                )
            elif resp.status_code != 200:
                raise RemotiveError(f"Erreur API Remotive (HTTP {resp.status_code}) : {resp.text[:200]}")

            payload = resp.json()
            if not isinstance(payload, dict):
                raise ValueError("La réponse Remotive n'est pas un dictionnaire JSON valide.")

            # Sauvegarde dans le cache local
            if use_cache:
                self.save_to_cache(cache_file, payload, request_url, category=category)

            return payload

        except requests.RequestException as exc:
            raise RemotiveError(f"Échec de la connexion à l'API Remotive : {exc}") from exc

    def scrape_offers(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        geo_filter: str = "canada_eligible",
        category_filter: bool = True,
        stage_only: bool = False,
        limit: Optional[int] = None,
        refresh: bool = False,
        use_cache: bool = True,
    ) -> List[JobOffer]:
        """Exécute la collecte et retourne la liste des offres d'emploi / stage normalisées."""
        payload = self.fetch_payload(
            category=category,
            search=search,
            refresh=refresh,
            use_cache=use_cache
        )
        return parse_remotive_payload(
            payload,
            geo_filter=geo_filter,
            category_filter=category_filter,
            stage_only=stage_only,
            limit=limit,
        )
