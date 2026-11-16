"""
scrapers/jobboom.py - Connecteur Jobboom Québec fiabilisé.

Reprend et fiabilise les contributions d'Elvira et Mamadou :
1. Remplace le parcours partiel de 5 offres par une pagination ordonnée et paramétrable.
2. Extrait proprement le bloc JSON-LD schema.org/JobPosting via json.loads (élimination des regex fragiles).
3. Intègre la temporisation éthique conforme (délai de 2.0 secondes entre les requêtes).
4. Découple strictement le réseau via un gestionnaire de cache local avec mode hors ligne.
5. Aligne les sorties sur le modèle unifié JobOffer (Pydantic v2).
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import quote_plus, urljoin, urlsplit
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

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
        parse_display_date as shared_parse_display_date,
    )
except ImportError:
    try:
        from scrapers.guichet_emplois import (
            TECH_PATTERNS,
            classify_stage,
            clean_text as shared_clean_text,
            extract_tech_skills as shared_extract_tech_skills,
            parse_display_date as shared_parse_display_date,
        )
    except ImportError:
        TECH_PATTERNS = None
        classify_stage = None
        shared_clean_text = None
        shared_extract_tech_skills = None
        shared_parse_display_date = None


logger = logging.getLogger("JobboomScraper")

# --- Paramètres et constantes ------------------------------------------------

JOBBOOM_BASE_URL = "https://www.jobboom.com"
# Catégorie standard Technologies et Médias Numériques au Québec (_i10lfr)
JOBBOOM_TECH_CATEGORY_URL = f"{JOBBOOM_BASE_URL}/fr/technologies-medias-numeriques/_i10lfr"
JOBBOOM_SEARCH_URL = f"{JOBBOOM_BASE_URL}/fr/emploi"

# Temporisation éthique recommandée pour Jobboom (2.0 secondes)
JOBBOOM_DELAY_SECONDS = 2.0
USER_AGENT = (
    "jobs-insights-atelier/1.0 "
    "(Projet etudiant DEC Informatique College O'Sullivan de Quebec; "
    "contact: gregory@jobs-insights.local)"
)

# Motifs de compétences techniques de repli si le module partagé n'est pas importé
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
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def clean_jobboom_url(raw_url: str, base_url: str = JOBBOOM_BASE_URL) -> str:
    """Nettoie l'URL d'une offre en retirant query parameters et fragments."""
    if not raw_url:
        return ""
    clean = raw_url.strip()
    path = urlsplit(clean).path
    if path.startswith("/"):
        return f"{base_url}{path}"
    if clean.startswith("http"):
        base_domain = f"{urlsplit(clean).scheme}://{urlsplit(clean).netloc}"
        return f"{base_domain}{path}"
    return urljoin(base_url, path)


def extract_jobboom_id(url: str) -> str:
    """Extrait un identifiant normalisé depuis l'URL de l'offre Jobboom.

    Exemples :
    - ..._services-plus_p3132854 -> 'jb-3132854'
    - .../offre-emploi/dev-python_p3718101 -> 'jb-3718101'
    - .../offre-emploi/slug-sans-p -> 'jb-slug-sans-p'
    """
    if not url:
        return f"jb-{int(time.time())}"
    m = re.search(r"[_-]p(\d+)(?:[/?#]|$)", url)
    if m:
        return f"jb-{m.group(1)}"
    m2 = re.search(r"/p(\d+)(?:[/?#]|$)", url)
    if m2:
        return f"jb-{m2.group(1)}"
    slug = urlsplit(url).path.rstrip("/").split("/")[-1]
    safe_slug = re.sub(r"[^\w\-]", "", slug)
    return f"jb-{safe_slug[:40]}" if safe_slug else f"jb-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def parse_date_iso(raw_date: Optional[str]) -> Optional[str]:
    """Extrait la date au format ISO AAAA-MM-JJ."""
    if not raw_date:
        return None
    val = str(raw_date).strip()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
    if m:
        return m.group(1)
    if shared_parse_display_date is not None:
        return shared_parse_display_date(val)
    return None


def extract_tech_skills(text: str) -> List[str]:
    """Extrait les compétences techniques en éliminant les faux positifs."""
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


def build_category_url(page: int = 1, sort_by: str = "date", base_url: str = JOBBOOM_BASE_URL) -> str:
    """Construit l'URL de la catégorie TI et médias numériques avec pagination ordonnée."""
    base = f"{base_url}/fr/technologies-medias-numeriques/_i10lfr"
    params = [("sortBy", sort_by)]
    if page > 1:
        params.append(("page", str(page)))
    query = "&".join(f"{k}={v}" for k, v in params)
    return f"{base}?{query}"


def build_search_url(
    keyword: str,
    page: int = 1,
    sort_by: str = "date",
    base_url: str = JOBBOOM_BASE_URL
) -> str:
    """Construit l'URL d'une recherche par mot-clé avec pagination."""
    slug = re.sub(r"[^\w]+", "-", _normalize(keyword).strip()).strip("-")
    base = f"{base_url}/fr/emploi/{slug}/_lfrk"
    params = [("dk", keyword), ("sortBy", sort_by)]
    if page > 1:
        params.append(("page", str(page)))
    query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params)
    return f"{base}?{query}"


# --- Parseurs HTML et JSON-LD (100 % hors ligne) -----------------------------

def parse_listing_page_html(
    html_str: str,
    base_url: str = JOBBOOM_BASE_URL
) -> Tuple[List[str], Optional[int]]:
    """Parse une page HTML de listing Jobboom (catégorie ou recherche).

    Extrait :
    1. La liste ordonnée et dédupliquée des URLs complètes des offres (/fr/offre-emploi/...).
    2. Le nombre total d'offres annoncé dans la pagination (ex : '1 - 15 de 131 résultats').

    Retourne : (urls_offres, total_annonce)
    """
    if not html_str:
        return [], None

    soup = BeautifulSoup(html_str, "html.parser")
    found_urls: List[str] = []
    seen: Set[str] = set()

    # 1. Extraction des URLs via balises <a> avec href="/fr/offre-emploi/..."
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/offre-emploi/" in href:
            clean_url = clean_jobboom_url(href, base_url=base_url)
            if clean_url and clean_url not in seen:
                seen.add(clean_url)
                found_urls.append(clean_url)

    # 2. Complément d'extraction via attributs data-url (pattern de Mamadou)
    for tag in soup.find_all(attrs={"data-url": True}):
        data_url = tag["data-url"]
        if "/offre-emploi/" in data_url:
            clean_url = clean_jobboom_url(data_url, base_url=base_url)
            if clean_url and clean_url not in seen:
                seen.add(clean_url)
                found_urls.append(clean_url)

    # 3. Extraction du total d'offres annoncé par le site
    total_annonces: Optional[int] = None
    # Recherche dans le bloc de pagination (ex: "1 - 15 de 131 résultats")
    pagination_tag = soup.find(class_=re.compile(r"paginat", re.I))
    text_to_search = pagination_tag.get_text() if pagination_tag else soup.get_text()

    total_match = re.search(r"de\s+([\d\s\xa0]+)\s+r[eé]sultats", text_to_search, re.IGNORECASE)
    if not total_match:
        total_match = re.search(r"([\d\s\xa0]+)\s+offres?\s+d'emploi", text_to_search, re.IGNORECASE)

    if total_match:
        digits = re.sub(r"\D", "", total_match.group(1))
        if digits:
            try:
                total_annonces = int(digits)
            except ValueError:
                total_annonces = None

    return found_urls, total_annonces


def extract_json_ld_job_posting(html_str: str) -> Optional[Dict[str, Any]]:
    """Extrait le bloc JSON-LD schema.org/JobPosting d'une page d'offre HTML.

    Parcourt l'ensemble des balises <script type="application/ld+json"> en utilisant
    json.loads natif (sans expressions régulières fragiles). Supporte les objets directs,
    les listes et les graphes Schema.org (@graph).
    """
    if not html_str:
        return None

    soup = BeautifulSoup(html_str, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        if not script.string or not script.string.strip():
            continue
        try:
            payload = json.loads(script.string.strip())
        except (json.JSONDecodeError, ValueError):
            continue

        candidates: List[Any] = []
        if isinstance(payload, dict):
            if "@graph" in payload and isinstance(payload["@graph"], list):
                candidates.extend(payload["@graph"])
            else:
                candidates.append(payload)
        elif isinstance(payload, list):
            candidates.extend(payload)

        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
                return item

    return None


def parse_jobboom_location(job_data: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extrait et normalise le lieu, la province et le pays depuis le bloc jobLocation JSON-LD.

    Retourne : (lieu, province, pays)
    """
    loc_entry = job_data.get("jobLocation")
    if isinstance(loc_entry, list) and loc_entry:
        loc_entry = loc_entry[0]

    city = "Québec"
    region = "QC"
    country = "Canada"

    if isinstance(loc_entry, dict):
        addr = loc_entry.get("address")
        if isinstance(addr, dict):
            c_cand = addr.get("addressLocality")
            if c_cand:
                city = str(c_cand).strip()

            r_cand = addr.get("addressRegion")
            if r_cand:
                r_str = str(r_cand).strip().upper()
                region = r_str if len(r_str) == 2 else ("QC" if "QUEBEC" in _normalize(r_str) else region)

            country_cand = addr.get("addressCountry")
            if country_cand:
                country_str = str(country_cand).strip()
                country = "Canada" if country_str.upper() in {"CA", "CAN", "CANADA"} else country_str

    lieu = f"{city}, {region}" if city else f"Québec ({region})"
    return lieu, region, country


def parse_jobboom_employment_type(job_data: Dict[str, Any], title: str, description: str) -> Tuple[str, bool, str]:
    """Détermine le type de poste et le statut de stage à partir de employmentType JSON-LD et du texte.

    Retourne : (type_poste, est_stage, statut_stage)
    """
    raw_type = job_data.get("employmentType")
    types_list: List[str] = []
    if isinstance(raw_type, list):
        types_list = [str(x).upper() for x in raw_type]
    elif isinstance(raw_type, str):
        types_list = [raw_type.upper()]

    type_poste = "Temps plein"
    est_stage = False
    statut_stage = "not_indicated"

    # Vérification explicite du statut de stage dans le schéma Schema.org
    if any(k in types_list for k in ["INTERN", "INTERNSHIP", "STAGE", "COOP"]):
        est_stage = True
        statut_stage = "confirmed_stage"
        type_poste = "Stage"
    elif any(k in types_list for k in ["PART_TIME", "TEMPS_PARTIEL"]):
        type_poste = "Temps partiel"
    elif any(k in types_list for k in ["CONTRACTOR", "CONTRACT", "TEMPORARY", "TEMPORAIRE"]):
        type_poste = "Contrat"
    elif any(k in types_list for k in ["FULL_TIME", "PERMANENT", "TEMPS_PLEIN"]):
        type_poste = "Temps plein"

    # Affinement contextuel du stage via classifieur sémantique si non confirmé
    if not est_stage and classify_stage is not None:
        is_st, st_stat, _ = classify_stage(title, type_poste, description)
        if is_st:
            est_stage = True
            statut_stage = st_stat
            if type_poste == "Temps plein" and st_stat == "confirmed_stage":
                type_poste = "Stage"

    return type_poste, est_stage, statut_stage


def parse_jobboom_salary(job_data: Dict[str, Any]) -> Optional[str]:
    """Extrait le salaire déclaré depuis le bloc baseSalary JSON-LD (MonetaryAmount).

    Conforme à AGENTS.md : zéro hallucination ou estimation, retourne None si non spécifié.
    """
    base_sal = job_data.get("baseSalary")
    if not base_sal:
        return None

    if isinstance(base_sal, dict):
        val = base_sal.get("value")
        unit = base_sal.get("unitText") or (val.get("unitText") if isinstance(val, dict) else "") or ""
        unit_suffix = ""
        if unit:
            u_clean = str(unit).upper()
            if u_clean in {"YEAR", "ANNUAL", "YEARLY"}:
                unit_suffix = " par an"
            elif u_clean in {"HOUR", "HOURLY"}:
                unit_suffix = " de l'heure"
            elif u_clean in {"MONTH", "MONTHLY"}:
                unit_suffix = " par mois"
            else:
                unit_suffix = f" /{unit.lower()}"

        if isinstance(val, dict):
            min_v = val.get("minValue")
            max_v = val.get("maxValue")
            exact_v = val.get("value")
            if min_v is not None and max_v is not None:
                return f"{min_v} $ à {max_v} ${unit_suffix}".strip()
            elif exact_v is not None:
                return f"{exact_v} ${unit_suffix}".strip()
            elif min_v is not None:
                return f"À partir de {min_v} ${unit_suffix}".strip()
        elif val is not None:
            return f"{val} ${unit_suffix}".strip()

    elif isinstance(base_sal, (str, int, float)):
        sal_str = str(base_sal).strip()
        if sal_str:
            return sal_str

    return None


def parse_jobboom_detail_html(html_str: str, url: str) -> Optional[JobOffer]:
    """Parse une page d'offre Jobboom et retourne un objet JobOffer typé.

    Stratégie :
    1. Extraction prioritaire du bloc JSON-LD schema.org/JobPosting.
    2. Nettoyage de la description HTML.
    3. Extraction des compétences clés TI sans faux positifs.
    4. Détection fine de la modalité (télétravail, hybride, sur place).
    5. Repli DOM élégant si le bloc JSON-LD est absent ou incomplet.
    """
    if not html_str:
        return None

    job_data = extract_json_ld_job_posting(html_str)
    job_id = extract_jobboom_id(url)
    clean_url = clean_jobboom_url(url)

    if job_data:
        raw_title = job_data.get("title") or "Titre non spécifié"
        titre = html.unescape(str(raw_title)).strip()

        # Employeur
        hiring_org = job_data.get("hiringOrganization")
        entreprise = "Non spécifié"
        if isinstance(hiring_org, dict):
            org_name = hiring_org.get("name")
            if org_name:
                entreprise = clean_text(str(org_name))
        elif isinstance(hiring_org, str) and hiring_org.strip():
            entreprise = clean_text(hiring_org)

        # Lieu, région, pays
        lieu, province, pays = parse_jobboom_location(job_data)

        # Date de publication
        date_pub = parse_date_iso(job_data.get("datePosted"))

        # Description
        desc_html = job_data.get("description", "")
        description = clean_text(desc_html) if desc_html else None

        # Type de contrat et détection de stage
        type_poste, est_stage, statut_stage = parse_jobboom_employment_type(
            job_data,
            title=titre,
            description=description or ""
        )

        # Modalité de travail
        modalite: Optional[str] = None
        loc_type = str(job_data.get("jobLocationType", "")).upper()
        if loc_type in {"TELECOMMUTE", "REMOTE"}:
            modalite = "Télétravail"
        else:
            texte_modalite = f"{titre} {description or ''}".lower()
            if "télétravail" in texte_modalite or "full remote" in texte_modalite:
                modalite = "Télétravail"
            elif "hybride" in texte_modalite:
                modalite = "Hybride"
            elif "sur place" in texte_modalite or "présentiel" in texte_modalite:
                modalite = "Sur place"

        # Salaire
        salaire = parse_jobboom_salary(job_data)

        # Compétences clés TI
        competences = extract_tech_skills(f"{titre} {description or ''}")

        return JobOffer(
            id=job_id,
            titre=titre,
            entreprise=entreprise,
            lieu=lieu,
            province=province,
            pays=pays,
            url=clean_url,
            source="jobboom",
            source_partenaire=None,
            date_publication=date_pub,
            type_poste=type_poste,
            modalite=modalite,
            est_stage=est_stage,
            statut_stage=statut_stage,
            description=description,
            competences_cles=competences,
            salaire=salaire,
        )

    # Repli DOM si aucun bloc JSON-LD n'est présent
    soup = BeautifulSoup(html_str, "html.parser")
    title_el = soup.find("h1")
    if not title_el:
        return None

    titre = clean_text(title_el.get_text())
    desc_el = soup.find(class_=re.compile(r"description|job-details", re.I))
    description = clean_text(desc_el.get_text()) if desc_el else None

    emp_el = soup.find(class_=re.compile(r"company|employer", re.I))
    entreprise = clean_text(emp_el.get_text()) if emp_el else "Non spécifié"

    competences = extract_tech_skills(f"{titre} {description or ''}")
    est_st = False
    st_stat = "not_indicated"
    if classify_stage is not None:
        est_st, st_stat, _ = classify_stage(titre, "Temps plein", description or "")

    return JobOffer(
        id=job_id,
        titre=titre,
        entreprise=entreprise,
        lieu="Québec, QC",
        province="QC",
        pays="Canada",
        url=clean_url,
        source="jobboom",
        source_partenaire=None,
        date_publication=None,
        type_poste="Stage" if est_st else "Temps plein",
        modalite=None,
        est_stage=est_st,
        statut_stage=st_stat,
        description=description,
        competences_cles=competences,
        salaire=None,
    )


# --- Classe collecteur avec cache local et découplage réseau -----------------

class JobboomScraper:
    """Collecteur Jobboom Québec conforme, avec pagination ordonnée et cache local.

    Caractéristiques :
    - Temporisation éthique de 2.0 s entre chaque requête HTTP directe.
    - User-Agent honnête et transparent.
    - Découplage strict via cache disque (search et details) avec support du mode hors ligne.
    - Extraction JSON-LD robuste schema.org/JobPosting via json.loads natif.
    - Export aligné sur le modèle commun JobOffer.
    """

    def __init__(
        self,
        cache_dir: Optional[Path | str] = None,
        delai_secondes: float = JOBBOOM_DELAY_SECONDS,
        user_agent: str = USER_AGENT,
        offline_mode: bool = False,
        timeout: int = 15,
    ):
        self.delai_secondes = delai_secondes
        self.user_agent = user_agent
        self.offline_mode = offline_mode
        self.timeout = timeout
        self.last_request_time: float = 0.0

        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).resolve().parent.parent / "cache" / "jobboom"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "search").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "details").mkdir(parents=True, exist_ok=True)

        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
            })
        return self._session

    def _get_cache_path(self, category: str, key: str, extension: str = "html") -> Path:
        safe_key = re.sub(r"[^\w\-.]", "_", key)
        if len(safe_key) > 100:
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            safe_key = f"{safe_key[:80]}_{digest}"
        return self.cache_dir / category / f"{safe_key}.{extension}"

    def read_cache(
        self,
        category: str,
        key: str,
        max_age_hours: Optional[float] = 24.0,
        extension: str = "html"
    ) -> Optional[str]:
        """Lit une entrée du cache si elle existe et n'est pas expirée."""
        path = self._get_cache_path(category, key, extension)
        if not path.is_file():
            return None
        if max_age_hours is not None:
            age_seconds = time.time() - path.stat().st_mtime
            if age_seconds > max_age_hours * 3600:
                return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Échec lecture cache %s : %s", path, e)
            return None

    def write_cache(self, category: str, key: str, content: str, extension: str = "html") -> Path:
        """Écrit une entrée dans le cache local."""
        path = self._get_cache_path(category, key, extension)
        path.write_text(content, encoding="utf-8")
        return path

    def _respect_rate_limit(self) -> None:
        """Applique le délai d'attente éthique (2.0 s) entre requêtes réseau consécutives."""
        if self.delai_secondes <= 0:
            return
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delai_secondes and self.last_request_time > 0:
            sleep_time = self.delai_secondes - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def fetch_url(
        self,
        url: str,
        category: str = "search",
        cache_key: Optional[str] = None,
        use_cache: bool = True,
        max_age_hours: Optional[float] = 24.0,
        extension: str = "html"
    ) -> str:
        """Récupère une page HTML en vérifiant le cache en premier."""
        key = cache_key or url
        if use_cache:
            cached = self.read_cache(category, key, max_age_hours=max_age_hours, extension=extension)
            if cached is not None:
                return cached

        if self.offline_mode:
            raise RuntimeError(f"Mode hors ligne actif : aucun cache trouvé pour l'URL '{url}'.")

        self._respect_rate_limit()

        for attempt in (1, 2):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code in {429, 503} and attempt == 1:
                    time.sleep(10.0)
                    continue
                resp.raise_for_status()
                content = resp.text
                if use_cache:
                    self.write_cache(category, key, content, extension=extension)
                return content
            except Exception as e:
                if attempt == 2:
                    logger.error("Erreur HTTP lors de la récupération de %s : %s", url, e)
                    raise

        return ""

    def scrape_job_urls(
        self,
        category_url: str = JOBBOOM_TECH_CATEGORY_URL,
        keyword: str = "",
        max_pages: int = 1,
        limit: int = 0,
        use_cache: bool = True,
        progress: Optional[Callable[[int, int, Optional[int]], None]] = None,
    ) -> Tuple[List[str], Optional[int]]:
        """Parcourt les pages de résultats Jobboom et extrait la liste ordonnée des URLs d'offres."""
        job_urls: List[str] = []
        seen_urls: Set[str] = set()
        announced_total: Optional[int] = None
        page = 1

        while True:
            if max_pages > 0 and page > max_pages:
                break
            if limit > 0 and len(job_urls) >= limit:
                break

            if keyword:
                url = build_search_url(keyword=keyword, page=page)
                cache_key = f"search_{_normalize(keyword)}_page_{page}"
            else:
                url = build_category_url(page=page)
                cache_key = f"category_ti_page_{page}"

            html_content = self.fetch_url(
                url,
                category="search",
                cache_key=cache_key,
                use_cache=use_cache
            )

            page_urls, total = parse_listing_page_html(html_content, base_url=JOBBOOM_BASE_URL)
            if announced_total is None and total is not None:
                announced_total = total

            new_on_page = 0
            for u in page_urls:
                if u not in seen_urls:
                    seen_urls.add(u)
                    job_urls.append(u)
                    new_on_page += 1
                    if limit > 0 and len(job_urls) >= limit:
                        break

            if progress is not None:
                progress(page, len(job_urls), announced_total)

            if new_on_page == 0:
                break

            if announced_total is not None and len(job_urls) >= announced_total:
                break

            page += 1

        return job_urls, announced_total

    def fetch_offer_detail(self, url: str, use_cache: bool = True) -> Optional[JobOffer]:
        """Télécharge la fiche détaillée d'une offre et la convertit en JobOffer."""
        clean_url = clean_jobboom_url(url)
        offer_id = extract_jobboom_id(clean_url)
        cache_key = f"detail_{offer_id.replace('jb-', '')}"

        try:
            detail_html = self.fetch_url(
                clean_url,
                category="details",
                cache_key=cache_key,
                use_cache=use_cache
            )
            return parse_jobboom_detail_html(detail_html, clean_url)
        except Exception as e:
            logger.warning("Échec de récupération de la fiche %s : %s", url, e)
            return None

    def search(
        self,
        keyword: str = "",
        max_pages: int = 1,
        limit: int = 0,
        use_cache: bool = True,
        progress: Optional[Callable[[int, int, Optional[int]], None]] = None,
        progress_detail: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[JobOffer]:
        """Point d'entrée principal : découvre et extrait les offres d'emploi Jobboom complètes."""
        urls, announced_total = self.scrape_job_urls(
            keyword=keyword,
            max_pages=max_pages,
            limit=limit,
            use_cache=use_cache,
            progress=progress
        )

        offers: List[JobOffer] = []
        total_urls = len(urls)

        for idx, u in enumerate(urls, start=1):
            offer = self.fetch_offer_detail(u, use_cache=use_cache)
            if offer is not None:
                offers.append(offer)
                if progress_detail is not None:
                    progress_detail(idx, total_urls, offer.titre)
            else:
                if progress_detail is not None:
                    progress_detail(idx, total_urls, "Échec parsing")

        return offers
