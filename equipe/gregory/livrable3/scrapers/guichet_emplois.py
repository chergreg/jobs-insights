"""
scrapers/guichet_emplois.py - Connecteur Guichet-Emplois Canada fusionné et enrichi.

Combine :
1. La pagination exhaustive multi-pages par codes CNP TI (approche Kandet - 191 offres).
2. L'enrichissement sémantique RDFa / Schema.org et le repli DOM (approche Hugo).
3. L'extraction de compétences techniques contextuelle sans faux positifs (Hugo).
4. Le découplage strict du réseau avec gestionnaire de cache local et respect de robots.txt (5 s).
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
from urllib.parse import urlencode, urljoin, urlsplit
import xml.etree.ElementTree as ET
from typing import Callable, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

try:
    from models import JobOffer
except ImportError:
    from ..models import JobOffer


logger = logging.getLogger("GuichetEmploisScraper")

# --- Paramètres et constantes ------------------------------------------------

GUICHET_BASE_URL = "https://www.guichetemplois.gc.ca"
GUICHET_SEARCH_URL = f"{GUICHET_BASE_URL}/jobsearch/rechercheemplois"
GUICHET_FEED_URL = "https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"

# Crawl-delay spécifié par robots.txt pour Guichet-Emplois
GUICHET_DELAY_SECONDS = 5.0
USER_AGENT = (
    "jobs-insights-atelier/1.0 "
    "(Projet etudiant DEC Informatique College O'Sullivan de Quebec; "
    "contact: gregory@jobs-insights.local)"
)

# 14 codes de la Classification Nationale des Professions (CNP 2021) pour les TI
CNP_CODES_TI = {
    "21211": "Scientifiques de données",
    "21220": "Spécialistes de la cybersécurité",
    "21221": "Spécialistes des systèmes d'affaires",
    "21222": "Spécialistes des systèmes d'information",
    "21223": "Analystes de bases de données",
    "21230": "Développeurs et programmeurs de systèmes informatiques",
    "21231": "Ingénieurs et concepteurs en logiciel",
    "21232": "Développeurs et programmeurs de logiciels",
    "21233": "Concepteurs Web",
    "21234": "Développeurs Web et programmeurs",
    "21311": "Ingénieurs informaticiens",
    "22220": "Techniciens de réseau informatique",
    "22221": "Agents de soutien aux utilisateurs",
    "22222": "Évaluateurs de systèmes d'information",
}

# Dictionnaire de motifs stricts pour compétences TI (sans faux positifs français)
# Note : C++ et C# utilisent (?=[^\w#+]|$) pour préserver le symbole.
TECH_PATTERNS = [
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

STAGE_PATTERN = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|work[\s-]?terms?)\b",
    flags=re.IGNORECASE,
)

STAGE_DESCRIPTION_PATTERN = re.compile(
    r"\b(?:internship|intern|co[\s-]?op|work[\s-]?term)\s+"
    r"(?:position|role|program|opportunity|placement)\b"
    r"|\b(?:student|students)\s+(?:intern|position|role|placement)\b"
    r"|\b(?:stage|stagiaire)\s+(?:en|de|du|d['’]|remunere)\b",
    flags=re.IGNORECASE,
)

STUDENT_ELIGIBILITY_PATTERN = re.compile(
    r"\b(?:currently\s+enrolled|enrolled\s+(?:in|at)|"
    r"must\s+be\s+(?:a\s+)?student|student\s+status|required\s+to\s+be\s+enrolled|"
    r"etre\s+(?:inscrit|inscrite|etudiant|etudiante)|"
    r"doit\s+etre\s+(?:inscrit|inscrite|etudiant|etudiante))\b",
    flags=re.IGNORECASE,
)

MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
    "janv": 1, "fevr": 2, "avr": 4, "juil": 7, "sept": 9, "oct": 10,
    "nov": 11, "dec": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
}


# --- Fonctions pures de nettoyage et normalisation ---------------------------

def clean_text(raw_html: str) -> str:
    """Supprime les balises HTML et condense les espaces."""
    if not raw_html:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw_html))
    txt = html.unescape(txt)
    return " ".join(txt.split())


def _normalize(value: str) -> str:
    """Convertit en minuscules sans accents pour les comparaisons textuelles."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def parse_display_date(value: str) -> Optional[str]:
    """Convertit une date textuelle (fr/en) en format ISO AAAA-MM-JJ.

    Exemples :
    - '12 novembre 2026' -> '2026-11-12'
    - 'November 10, 2026' -> '2026-11-10'
    - '2026-11-12' -> '2026-11-12'
    """
    if not value or not value.strip():
        return None
    val_clean = value.strip()
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", val_clean)
    if iso_match:
        return iso_match.group(0)

    words = re.findall(r"[^\W\d_]+|\d+", _normalize(val_clean))
    numbers = [int(w) for w in words if w.isdigit()]
    months_found = [MONTHS[w] for w in words if w in MONTHS]
    year = next((n for n in numbers if n > 1900), None)
    day = next((n for n in numbers if 1 <= n <= 31), None)

    if year is None or day is None or not months_found:
        return None
    try:
        from datetime import date
        return date(year, months_found[0], day).isoformat()
    except ValueError:
        return None


def extract_tech_skills(text: str) -> List[str]:
    """Extrait les compétences techniques en éliminant les faux positifs récurrents en français."""
    if not text:
        return []
    found: Set[str] = set()
    for tech_name, pattern in TECH_PATTERNS:
        if pattern.search(text):
            found.add(tech_name)
    return sorted(list(found))


def classify_stage(title: str, job_type: str = "", description: str = "") -> Tuple[bool, str, List[str]]:
    """Détecte et qualifie le statut de stage d'une offre.

    Retourne : (est_stage, statut_stage, signaux)
    statut_stage peut valoir : 'confirmed_stage', 'possible_stage', 'not_indicated'.
    """
    norm_job_type = _normalize(job_type).replace("_", " ")
    if norm_job_type in {"internship", "intern", "co op", "stage", "stagiaire"}:
        return True, "confirmed_stage", ["explicit_internship_job_type"]

    norm_title = _normalize(title)
    if STAGE_PATTERN.search(norm_title):
        return True, "confirmed_stage", ["stage_term_in_title"]

    norm_desc = _normalize(description)
    signals: List[str] = []
    if STAGE_DESCRIPTION_PATTERN.search(norm_desc):
        signals.append("stage_role_in_description")
    if STUDENT_ELIGIBILITY_PATTERN.search(norm_desc):
        signals.append("student_eligibility_in_description")

    if signals:
        return True, "possible_stage", signals

    return False, "not_indicated", []


def clean_posting_url(href: str, base_url: str = GUICHET_BASE_URL) -> str:
    """Nettoie l'URL d'une offre en retirant ;jsessionid et les paramètres de session."""
    if not href:
        return ""
    path = urlsplit(href).path.split(";")[0]
    if path.startswith("/"):
        return f"{base_url}{path}"
    return path if path.startswith("http") else urljoin(base_url, path)


def build_search_url(
    page: int = 1,
    term: str = "",
    province: str | None = "QC",
    cnp_codes: Optional[Tuple[str, ...]] = tuple(CNP_CODES_TI),
    base_url: str = GUICHET_SEARCH_URL,
) -> str:
    """Construit l'URL d'une page de recherche avec filtres CNP et province."""
    params: List[Tuple[str, str]] = []
    if term:
        params.append(("searchstring", term))
    if cnp_codes:
        for code in cnp_codes:
            params.append(("fn21", str(code)))
    if province:
        params.append(("fprov", province))
    params.append(("sort", "D"))  # Plus récentes en premier
    if page > 1:
        params.append(("page", str(page)))
    return f"{base_url}?{urlencode(params)}"


# --- Parseurs HTML / XML (100 % hors ligne) ----------------------------------

def _extract_text_excluding_wb_inv(tag) -> str:
    """Extrait le texte d'une balise BeautifulSoup en ignorant les balises .wb-inv."""
    if not tag:
        return ""
    parts = []
    for elem in tag.descendants:
        if isinstance(elem, str):
            cur = elem.parent
            is_inv = False
            while cur and cur != tag:
                classes = cur.get("class", [])
                if isinstance(classes, str):
                    classes = classes.split()
                if "wb-inv" in classes:
                    is_inv = True
                    break
                cur = cur.parent
            if not is_inv:
                parts.append(elem)
    return " ".join(" ".join(parts).split())


def parse_search_page_html(
    html_str: str,
    base_url: str = GUICHET_BASE_URL,
    search_term: str = ""
) -> Tuple[List[JobOffer], Optional[int]]:
    """Parse une page HTML de résultats de recherche Guichet-Emplois.

    Retourne :
        (liste_offres, total_annonce_par_le_site)
    """
    if not html_str:
        return [], None

    soup = BeautifulSoup(html_str, "html.parser")

    announced_total: Optional[int] = None
    count_el = soup.find(id="results-count")
    if count_el:
        digits = re.sub(r"\D", "", count_el.get_text())
        if digits:
            try:
                announced_total = int(digits)
            except ValueError:
                pass

    offers: List[JobOffer] = []
    articles = soup.find_all("article")

    for article in articles:
        raw_article_id = article.get("id", "")
        if not raw_article_id.startswith("article-"):
            continue

        raw_id = raw_article_id.removeprefix("article-").strip()
        job_id = f"ge-{raw_id}"

        link_tag = article.find("a", class_="resultJobItem")
        raw_href = link_tag.get("href", "") if link_tag else ""
        url_propre = clean_posting_url(raw_href, base_url=base_url)

        title_tag = article.find("span", class_="noctitle")
        titre = " ".join(title_tag.get_text().split()) if title_tag else "Titre non spécifié"

        # Entreprise
        business_tag = article.find("li", class_="business")
        entreprise = _extract_text_excluding_wb_inv(business_tag) or "Non spécifié"

        # Localisation
        loc_tag = article.find("li", class_="location")
        lieu_brut = _extract_text_excluding_wb_inv(loc_tag)
        lieu = re.sub(r"^(?:emplacement|location)\s*:?\s*", "", lieu_brut, flags=re.IGNORECASE).strip()
        if not lieu:
            lieu = "Québec (QC)"

        province = "QC"
        for prov in ["QC", "ON", "BC", "AB", "MB", "NB", "NS", "PE", "NL", "SK", "YT", "NT", "NU"]:
            if f"({prov})" in lieu or f", {prov}" in lieu or lieu.endswith(f" {prov}"):
                province = prov
                break

        # Salaire
        salary_tag = article.find("li", class_="salary")
        sal_brut = _extract_text_excluding_wb_inv(salary_tag)
        salaire = re.sub(r"^(?:salaire|salary)\s*:?\s*", "", sal_brut, flags=re.IGNORECASE).strip() if sal_brut else None

        # Date de publication
        date_tag = article.find("li", class_="date")
        date_brute = _extract_text_excluding_wb_inv(date_tag)
        date_iso = parse_display_date(date_brute)

        # Modalité (Badge télétravail)
        modalite = None
        telework_tag = article.find("span", class_="telework")
        if telework_tag:
            modalite = telework_tag.get_text(strip=True)

        # Partenaire d'origine
        partenaire: Optional[str] = None
        source_tag = article.find("span", class_="job-source")
        if source_tag:
            orig_text = source_tag.get_text(" ", strip=True)
            if orig_text:
                if any(x in orig_text for x in ["Guichet-Emplois", "Job Bank"]):
                    partenaire = None
                else:
                    partenaire = orig_text.replace(".com", "").strip()

        # Classification du stage
        est_stage, statut_stage, _ = classify_stage(titre, modalite or "")
        type_poste = "Stage" if est_stage else "Temps plein"

        # Compétences extraites de l'intitulé
        competences = extract_tech_skills(titre)

        offer = JobOffer(
            id=job_id,
            titre=titre,
            entreprise=entreprise,
            lieu=lieu,
            province=province,
            pays="Canada",
            url=url_propre,
            source="guichet-emplois",
            source_partenaire=partenaire,
            date_publication=date_iso,
            type_poste=type_poste,
            modalite=modalite,
            est_stage=est_stage,
            statut_stage=statut_stage,
            description=None,
            competences_cles=competences,
            salaire=salaire,
        )
        offers.append(offer)

    return offers, announced_total


def enrich_job_offer_from_detail(offer: JobOffer, html_str: str) -> JobOffer:
    """Enrichit une offre à partir du HTML de sa fiche détaillée.

    Stratégie en cascade :
    1. Modalité et type de poste via le bandeau résumé `.job-posting-brief`.
    2. Description intégrale via métadonnées sémantiques RDFa (`property="description"`),
       avec repli DOM (`#job-posting-detail`, etc.).
    3. Détection contextuelle des compétences sans faux positifs.
    4. Affinement du statut de stage sur le texte intégral.
    """
    if not html_str:
        return offer

    soup = BeautifulSoup(html_str, "html.parser")
    description_trouvee: Optional[str] = None
    blocs_exigences: List[str] = []

    # 1. Analyse du bandeau résumé
    brief = soup.find("ul", class_="job-posting-brief")
    if brief:
        brief_text = brief.get_text(" ", strip=True).lower()
        if "télétravail" in brief_text or "remote" in brief_text:
            offer.modalite = "Télétravail"
        elif "hybride" in brief_text or "hybrid" in brief_text:
            offer.modalite = "Hybride"
        elif "sur place" in brief_text or "on site" in brief_text:
            offer.modalite = "Sur place"

        if any(k in brief_text for k in ["stage", "stagiaire", "intern", "coop", "co-op"]):
            offer.type_poste = "Stage"
            offer.est_stage = True
            offer.statut_stage = "confirmed_stage"
        elif "temps partiel" in brief_text:
            offer.type_poste = "Temps partiel"

    # 1.1 Récupération de l'intitulé brut employeur (sur offres partenaires agrégées)
    source_title_tag = soup.find(class_="source-title-inner")
    if source_title_tag:
        label_tag = source_title_tag.find(class_="orig-title-label")
        label_text = label_tag.get_text() if label_tag else ""
        raw_emp_title = source_title_tag.get_text().replace(label_text, "").strip()
        if raw_emp_title:
            blocs_exigences.append(raw_emp_title)
            est_st, st_stat, _ = classify_stage(raw_emp_title)
            if est_st:
                offer.est_stage = True
                offer.statut_stage = st_stat
                offer.type_poste = "Stage"

    # 2. Description - Étape RDFa / Schema.org
    rdfa_desc = soup.find(attrs={"property": "description"})
    if rdfa_desc:
        cleaned_desc = clean_text(rdfa_desc.get_text(separator="\n", strip=True))
        if len(cleaned_desc) > 30:
            description_trouvee = cleaned_desc
            blocs_exigences.append(cleaned_desc)

    # Repli DOM si non trouvé par RDFa
    if not description_trouvee:
        conteneurs_candidats = [
            soup.find("div", id="job-posting-detail"),
            soup.find("section", class_="job-posting-detail-requirements"),
            soup.find("div", class_="job-posting-details-body"),
            soup.find("div", class_="cmp-content"),
        ]
        for c in conteneurs_candidats:
            if c:
                txt = clean_text(c.get_text(separator="\n", strip=True))
                if len(txt) > 40:
                    description_trouvee = txt
                    blocs_exigences.append(txt)
                    break

    if not description_trouvee:
        sections = soup.find_all("div", class_="job-posting-detail-requirements")
        if sections:
            txt_assembled = "\n".join(clean_text(s.get_text(separator=" ", strip=True)) for s in sections)
            if len(txt_assembled) > 30:
                description_trouvee = txt_assembled
                blocs_exigences.append(txt_assembled)

    if description_trouvee:
        offer.description = description_trouvee

    # 3. Extraction des compétences techniques
    texte_competences = " ".join(blocs_exigences) if blocs_exigences else (offer.description or "")
    nouvelles_competences = extract_tech_skills(texte_competences)
    offer.competences_cles = sorted(list(set(offer.competences_cles + nouvelles_competences)))

    # 4. Affinement du statut de stage sur le texte complet
    if not offer.est_stage:
        est_stage, statut_stage, _ = classify_stage(
            offer.titre,
            offer.type_poste or "",
            offer.description or ""
        )
        if est_stage:
            offer.est_stage = True
            offer.statut_stage = statut_stage
            if offer.type_poste == "Temps plein" and statut_stage == "confirmed_stage":
                offer.type_poste = "Stage"

    return offer


def parse_atom_feed(xml_content: str | bytes, base_url: str = GUICHET_BASE_URL) -> List[JobOffer]:
    """Parse le flux de syndication officiel Atom XML de Guichet-Emplois."""
    if isinstance(xml_content, str):
        xml_bytes = xml_content.encode("utf-8")
    else:
        xml_bytes = xml_content

    offers: List[JobOffer] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return offers

    atom_ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f"{atom_ns}entry"):
        title_el = entry.find(f"{atom_ns}title")
        titre = title_el.text.strip() if title_el is not None and title_el.text else "Titre non spécifié"

        link_el = entry.find(f"{atom_ns}link")
        raw_href = link_el.attrib.get("href", "") if link_el is not None else ""
        url_propre = clean_posting_url(raw_href, base_url=base_url)

        updated_el = entry.find(f"{atom_ns}updated")
        date_raw = updated_el.text.strip() if updated_el is not None and updated_el.text else None
        date_iso = parse_display_date(date_raw) if date_raw else None

        id_el = entry.find(f"{atom_ns}id")
        raw_id_text = id_el.text.strip() if id_el is not None and id_el.text else raw_href.split("/")[-1].split("?")[0]
        clean_id = raw_id_text.replace("article-", "").replace("gc-", "").replace("ge-", "")
        job_id = f"ge-{clean_id}"

        summary_el = entry.find(f"{atom_ns}summary")
        summary_html = summary_el.text if summary_el is not None and summary_el.text else ""

        entreprise = "Non spécifié"
        lieu = "Québec (QC)"
        province = "QC"
        salaire = None

        if summary_html:
            emp_m = re.search(r"<strong>(?:Employer|Employeur)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if emp_m:
                entreprise = emp_m.group(1).strip()
            loc_m = re.search(r"<strong>(?:Location|Emplacement)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if loc_m:
                lieu = loc_m.group(1).strip()
                for p in ["QC", "ON", "BC", "AB", "MB", "NB", "NS"]:
                    if f"({p})" in lieu or p in lieu:
                        province = p
                        break
            sal_m = re.search(r"<strong>(?:Salary|Salaire)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if sal_m:
                salaire = sal_m.group(1).strip()

        est_stage, statut_stage, _ = classify_stage(titre, "", summary_html)
        type_poste = "Stage" if est_stage else "Temps plein"
        competences = extract_tech_skills(f"{titre} {summary_html}")
        desc = clean_text(summary_html) if summary_html else None

        offer = JobOffer(
            id=job_id,
            titre=titre,
            entreprise=entreprise,
            lieu=lieu,
            province=province,
            pays="Canada",
            url=url_propre,
            source="guichet-emplois",
            source_partenaire=None,
            date_publication=date_iso,
            type_poste=type_poste,
            modalite=None,
            est_stage=est_stage,
            statut_stage=statut_stage,
            description=desc,
            competences_cles=competences,
            salaire=salaire,
        )
        offers.append(offer)

    return offers


# --- Classe collecteur avec cache local et découplage réseau -----------------

class GuichetEmploisScraper:
    """Collecteur Guichet-Emplois conforme, avec pagination CNP et cache local."""

    def __init__(
        self,
        cache_dir: Optional[Path | str] = None,
        delai_secondes: float = GUICHET_DELAY_SECONDS,
        user_agent: str = USER_AGENT,
        offline_mode: bool = False,
        timeout: int = 20,
    ):
        self.delai_secondes = delai_secondes
        self.user_agent = user_agent
        self.offline_mode = offline_mode
        self.timeout = timeout
        self.last_request_time: float = 0.0

        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).resolve().parent.parent / "cache" / "guichet_emplois"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "search").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "details").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "atom").mkdir(parents=True, exist_ok=True)

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
        """Applique le délai d'attente (5 s) entre deux requêtes réseau consécutives."""
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
        """Récupère une page HTML ou flux, en vérifiant le cache en premier."""
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
                    time.sleep(15.0)
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

    def search(
        self,
        term: str = "",
        province: str = "QC",
        cnp_codes: Optional[Tuple[str, ...]] = tuple(CNP_CODES_TI),
        max_pages: int = 0,
        limit: int = 0,
        use_cache: bool = True,
        progress: Optional[Callable[[int, int, Optional[int]], None]] = None,
    ) -> List[JobOffer]:
        """Parcourt exhaustivement les pages de recherche selon les codes CNP et la province."""
        offers: List[JobOffer] = []
        seen_ids: Set[str] = set()
        announced_total: Optional[int] = None
        page = 1

        while True:
            if max_pages > 0 and page > max_pages:
                break
            if limit > 0 and len(offers) >= limit:
                break

            url = build_search_url(page=page, term=term, province=province, cnp_codes=cnp_codes)
            cache_key = f"search_{province}_{term}_page_{page}"

            html_content = self.fetch_url(
                url,
                category="search",
                cache_key=cache_key,
                use_cache=use_cache
            )

            page_offers, total = parse_search_page_html(html_content, base_url=GUICHET_BASE_URL, search_term=term)
            if announced_total is None and total is not None:
                announced_total = total

            new_on_page: List[JobOffer] = []
            for off in page_offers:
                if off.id not in seen_ids:
                    seen_ids.add(off.id)
                    offers.append(off)
                    new_on_page.append(off)
                    if limit > 0 and len(offers) >= limit:
                        break

            if progress is not None:
                progress(page, len(offers), announced_total)

            if not new_on_page:
                break

            if announced_total is not None and len(seen_ids) >= announced_total:
                break

            page += 1

        return offers

    def enrich_offer(self, offer: JobOffer, use_cache: bool = True) -> JobOffer:
        """Télécharge la fiche détaillée d'une offre et applique l'enrichissement en cascade."""
        if not offer.url:
            return offer

        clean_id = offer.id.removeprefix("ge-").removeprefix("gc-")
        cache_key = f"detail_{clean_id}"

        try:
            detail_html = self.fetch_url(
                offer.url,
                category="details",
                cache_key=cache_key,
                use_cache=use_cache
            )
            return enrich_job_offer_from_detail(offer, detail_html)
        except Exception as e:
            logger.warning("Impossible d'enrichir l'offre %s : %s", offer.id, e)
            return offer

    def enrich_offers(
        self,
        offers: List[JobOffer],
        limit: int = 0,
        use_cache: bool = True,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[JobOffer]:
        """Enrichit un lot d'offres en respectant le cache et les délais."""
        to_enrich = offers[:limit] if limit > 0 else offers
        total = len(to_enrich)
        enriched: List[JobOffer] = []

        for idx, off in enumerate(to_enrich, start=1):
            res = self.enrich_offer(off, use_cache=use_cache)
            enriched.append(res)
            if progress is not None:
                progress(idx, total)

        if limit > 0 and len(offers) > limit:
            enriched.extend(offers[limit:])

        return enriched
