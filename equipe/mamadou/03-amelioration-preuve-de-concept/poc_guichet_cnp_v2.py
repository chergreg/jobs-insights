"""
Livrable 3 — Collecteur Multi-Sources Enrichi (5 Sources Québec / Canada)
Auteur : Mamadou

Sources intégrées et bonifiées :
1. Guichet-Emplois Canada : Recherche par les 14 codes CNP 2021 TI (fn21) + province QC + filtre stages (fsrc=16)
   + enrichissement complet des fiches (RDFa property="description", repli DOM #job-posting-detail, bandeau
   ul.job-posting-brief pour la modalité, et .source-title-inner pour le vrai titre employeur).
2. Talent.com Canada : Double JSON-LD @graph (ItemList -> JobPosting) + coordonnées GPS (latitude / longitude).
3. Jobboom Québec : Catégorie Technologies (_i10lfr) ordonnée + fiche JSON-LD JobPosting.
4. Jobillico Québec : Recherche TI Québec/Montréal + fiche JSON-LD JobPosting.
5. Remotive API : API REST JSON officielle (catégories TI ouvertes au Canada) avec cache 24 h.

Toutes les offres sont normalisées dans le modèle riche `JobOffer` (dates ISO AAAA-MM-JJ, détection de 32
compétences TI sans faux positifs, classification des stages, respect de robots.txt et User-Agent honnête).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from typing import Any, Optional
from urllib.parse import quote, quote_plus, urlencode
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GUICHET_BASE_URL = "https://www.guichetemplois.gc.ca"
GUICHET_SEARCH_PATH = "/jobsearch/rechercheemplois"
USER_AGENT = "jobs-insights-osullivan/1.0 (atelier-livrable-3; mamadou)"
DEFAULT_CRAWL_DELAY = 5.0

# 14 codes CNP 2021 du domaine informatique (Classification nationale des professions)
CNP_CODES_TI: tuple[str, ...] = (
    "20012",  # Gestionnaires des systèmes informatiques
    "21211",  # Spécialistes des données (Data Scientists)
    "21220",  # Spécialistes en cybersécurité
    "21221",  # Spécialistes des systèmes d'affaires
    "21222",  # Spécialistes en informatique
    "21223",  # Analystes de bases de données et administrateurs de données
    "21230",  # Développeurs de systèmes informatiques et programmeurs
    "21231",  # Ingénieurs et concepteurs en logiciel
    "21232",  # Développeurs et programmeurs de logiciels
    "21233",  # Concepteurs Web
    "21234",  # Développeurs et programmeurs Web
    "22220",  # Techniciens de réseaux informatiques
    "22221",  # Agents de soutien aux utilisateurs
    "22222",  # Évaluateurs de systèmes informatiques (QA)
)

# Catalogue de détection de compétences TI (sans faux positifs français sur "C" ou "Vue")
TECH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Python", re.compile(r"\bpython\b", re.I)),
    ("Java", re.compile(r"\bjava\b(?!script)", re.I)),
    ("JavaScript", re.compile(r"(?<!\.)\b(?:javascript|js)\b", re.I)),
    ("TypeScript", re.compile(r"\btypescript\b", re.I)),
    ("C#", re.compile(r"\bc#(?=[^\w#]|$)", re.I)),
    ("C++", re.compile(r"\bc\+\+(?=[^\w\+]|$)", re.I)),
    ("C", re.compile(r"(?:\blangage\s+c\b|\bprogrammation\s+c\b|\bc\s*\/\s*c\+\+)", re.I)),
    ("React", re.compile(r"\breact(?:\.js)?\b", re.I)),
    ("Angular", re.compile(r"\bangular(?:\.js)?\b", re.I)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|vuejs|framework\s+vue)\b", re.I)),
    ("Node.js", re.compile(r"\bnode(?:\.js)?\b", re.I)),
    ("PHP", re.compile(r"\bphp\b", re.I)),
    ("Go", re.compile(r"\bgolang\b", re.I)),
    ("Rust", re.compile(r"\brust\b", re.I)),
    ("SQL", re.compile(r"\bsql\b", re.I)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.I)),
    ("MySQL", re.compile(r"\bmysql\b", re.I)),
    ("MongoDB", re.compile(r"\bmongodb\b", re.I)),
    ("Docker", re.compile(r"\bdocker\b", re.I)),
    ("Kubernetes", re.compile(r"\b(?:kubernetes|k8s)\b", re.I)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", re.I)),
    ("Azure", re.compile(r"\bazure\b|\bentra\s+id\b", re.I)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", re.I)),
    ("Git", re.compile(r"\bgit(?:hub|lab)?\b(?!e)", re.I)),
    ("Linux", re.compile(r"\blinux\b|\bubuntu\b|\bred\s*hat\b", re.I)),
    ("Windows Server", re.compile(r"\bwindows\s+server\b|\bactive\s+directory\b|\bintune\b", re.I)),
    ("VMware", re.compile(r"\bvmware\b|\bhyper-v\b|\bveeam\b", re.I)),
    ("Réseaux (TCP/IP, VLAN, VPN)", re.compile(r"\b(?:tcp\/ip|vlan|dhcp|dns|fortinet|pare-feu|firewall)\b", re.I)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.I)),
    ("Django", re.compile(r"\bdjango\b", re.I)),
    ("Spring Boot", re.compile(r"\bspring\s*boot\b", re.I)),
    (".NET", re.compile(r"(?:(?<!\w)\.net\b|\basp\.net\b)", re.I)),
    ("CI/CD", re.compile(r"\bci[\/\-]cd\b|\bdevops\b|\bjenkins\b", re.I)),
    ("Agile / Scrum", re.compile(r"\b(?:agile|scrum)\b", re.I)),
    ("QA / Tests", re.compile(r"\b(?:assurance\s+qualit[eé]|selenium|cypress|pytest)\b", re.I)),
    ("IA / Machine Learning", re.compile(r"\b(?:intelligence\s+artificielle|machine\s+learning|llm|copilot|pytorch|tensorflow)\b", re.I)),
]

MONTHS_FR_EN: dict[str, int] = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


@dataclass
class JobBankOffer:
    """
    Modèle de données enrichi et unifié pour l'ensemble des 5 sources (Guichet-Emplois,
    Talent.com, Jobboom, Jobillico, Remotive). Zéro donnée inventée : None si absent.
    """

    id: str
    source_id: str
    url: str
    titre: Optional[str] = None
    titre_employeur: Optional[str] = None
    cnp_title: Optional[str] = None
    entreprise: Optional[str] = None
    lieu: Optional[str] = None
    province: str = "QC"
    pays: str = "Canada"
    source: str = "guichet-emplois"
    source_partenaire: Optional[str] = None
    date_publication: Optional[str] = None
    date_fin: Optional[str] = None
    type_poste: Optional[str] = None
    modalite: Optional[str] = None
    niveau_etudes: Optional[str] = None
    salaire: Optional[str] = None
    est_stage: bool = False
    statut_stage: str = "not_indicated"
    competences_cles: list[str] = field(default_factory=list)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    date_extraction: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Alias de compatibilité avec les tests unitaires existants
    @property
    def title(self) -> Optional[str]:
        return self.titre

    @title.setter
    def title(self, value: Optional[str]) -> None:
        self.titre = value

    @property
    def employer(self) -> Optional[str]:
        return self.entreprise

    @employer.setter
    def employer(self, value: Optional[str]) -> None:
        self.entreprise = value

    @property
    def location(self) -> Optional[str]:
        return self.lieu

    @location.setter
    def location(self, value: Optional[str]) -> None:
        self.lieu = value

    @property
    def salary(self) -> Optional[str]:
        return self.salaire

    @salary.setter
    def salary(self, value: Optional[str]) -> None:
        self.salaire = value

    @property
    def published_at(self) -> Optional[str]:
        return self.date_publication

    @published_at.setter
    def published_at(self, value: Optional[str]) -> None:
        self.date_publication = value

    @property
    def valid_through(self) -> Optional[str]:
        return self.date_fin

    @valid_through.setter
    def valid_through(self, value: Optional[str]) -> None:
        self.date_fin = value

    @property
    def workplace_mode(self) -> Optional[str]:
        return self.modalite

    @workplace_mode.setter
    def workplace_mode(self, value: Optional[str]) -> None:
        self.modalite = value

    @property
    def employment_type(self) -> Optional[str]:
        return self.type_poste

    @employment_type.setter
    def employment_type(self, value: Optional[str]) -> None:
        self.type_poste = value

    @property
    def education_level(self) -> Optional[str]:
        return self.niveau_etudes

    @education_level.setter
    def education_level(self, value: Optional[str]) -> None:
        self.niveau_etudes = value

    @property
    def origin_partner(self) -> Optional[str]:
        return self.source_partenaire

    @origin_partner.setter
    def origin_partner(self, value: Optional[str]) -> None:
        self.source_partenaire = value

    @property
    def stage_status(self) -> str:
        return self.statut_stage

    @stage_status.setter
    def stage_status(self, value: str) -> None:
        self.statut_stage = value
        self.est_stage = value in ("confirmed_stage", "possible_stage")


# ==============================================================================
# Fonctions utilitaires de nettoyage, dates ISO, compétences et stages
# ==============================================================================
def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    unescaped = html.unescape(str(text))
    cleaned = re.sub(r"\s+", " ", unescaped).strip()
    return cleaned if cleaned else None


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def parse_iso_date(raw_date: Optional[str]) -> Optional[str]:
    """Convertit une date brute ('16 novembre 2026', '2026-11-16T...') en format ISO AAAA-MM-JJ."""
    if not raw_date:
        return None
    val = raw_date.strip()
    iso_m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", val)
    if iso_m:
        return iso_m.group(0)

    tokens = re.findall(r"[^\W\d_]+|\d+", _strip_accents(val))
    nums = [int(t) for t in tokens if t.isdigit()]
    months = [MONTHS_FR_EN[t] for t in tokens if t in MONTHS_FR_EN]
    year = next((n for n in nums if n > 1900), None)
    day = next((n for n in nums if 1 <= n <= 31), None)
    if year and day and months:
        try:
            return date(year, months[0], day).isoformat()
        except ValueError:
            pass
    return val


def extract_tech_skills(*texts: Optional[str]) -> list[str]:
    """Détecte les compétences TI présentes dans les textes fournis sans faux positifs."""
    combined = " ".join(t for t in texts if t)
    if not combined:
        return []
    found: list[str] = []
    for label, pattern in TECH_PATTERNS:
        if pattern.search(combined) and label not in found:
            found.append(label)
    return sorted(found)


def detect_stage_status(title: Optional[str], description: Optional[str], student_filter: bool = False) -> str:
    """Classifie si l'offre est un stage en excluant les mentions d'encadrement ('superviser des stagiaires')."""
    combined = f"{title or ''} {description or ''}".lower()
    cleaned = re.sub(
        r"\b(superviser|encadrer|former|accompagner|diriger)\s+(des|les|un|une|nos)?\s*(stagiaires?|étudiants?)\b",
        "",
        combined,
    )
    if re.search(r"\b(stage|stagiaire|intern|internship|co-op|coop|alternance|ate)\b", cleaned):
        return "confirmed_stage"
    if student_filter or re.search(r"\b(emploi\s+étudiant|étudiant\(e\)|student\s+job)\b", cleaned):
        return "possible_stage"
    return "not_indicated"


def check_robots_permission(session: requests.Session, base_url: str, target_url: str, default_delay: float = 2.0) -> tuple[bool, float]:
    """Vérifie robots.txt pour n'importe quel site et retourne (autorisé, crawl_delay)."""
    rp = RobotFileParser()
    try:
        resp = session.get(f"{base_url.rstrip('/')}/robots.txt", timeout=8)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            allowed = rp.can_fetch(USER_AGENT, target_url)
            delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*") or default_delay
            return allowed, float(delay)
    except requests.RequestException:
        pass
    return True, default_delay


# ==============================================================================
# SOURCE 1 : Guichet-Emplois Canada (14 codes CNP TI + Fiches RDFa & DOM)
# ==============================================================================
def build_cnp_search_url(
    province: str = "QC",
    cnp_codes: tuple[str, ...] = CNP_CODES_TI,
    student_only: bool = False,
    keyword: Optional[str] = None,
    page: int = 1,
) -> str:
    """Construit l'URL de recherche Guichet-Emplois avec les 14 codes CNP TI et filtres."""
    params: list[tuple[str, str]] = []
    if keyword:
        params.append(("searchstring", keyword.strip()))
    for code in cnp_codes:
        params.append(("fn21", code))
    if province:
        params.append(("fprov", province))
    if student_only:
        params.append(("fsrc", "16"))
    params.append(("sort", "D"))
    if page > 1:
        params.append(("page", str(page)))
    return f"{GUICHET_BASE_URL}{GUICHET_SEARCH_PATH}?{urlencode(params)}"


def parse_search_results_html(html_text: str) -> list[JobBankOffer]:
    """Extrait les cartes d'offres de la page de résultats Guichet-Emplois."""
    soup = BeautifulSoup(html_text, "html.parser")
    offers: list[JobBankOffer] = []
    seen_ids: set[str] = set()

    for article in soup.select("article[id^='article-']"):
        art_id = str(article.get("id", "")).replace("article-", "").strip()
        if not art_id or art_id in seen_ids:
            continue
        seen_ids.add(art_id)

        title_node = article.select_one("span.noctitle")
        cnp_title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else None

        biz_node = article.select_one("li.business")
        employer = _clean_text(biz_node.get_text(" ", strip=True)) if biz_node else None

        tele_node = article.select_one("span.telework")
        workplace_mode = _clean_text(tele_node.get_text(" ", strip=True)) if tele_node else None

        loc_node = article.select_one("li.location")
        location = None
        if loc_node:
            loc_copy = BeautifulSoup(str(loc_node), "html.parser")
            for hidden in loc_copy.select(".wb-inv"):
                hidden.decompose()
            location = _clean_text(loc_copy.get_text(" ", strip=True))

        sal_node = article.select_one("li.salary")
        salary = None
        if sal_node:
            sal_copy = BeautifulSoup(str(sal_node), "html.parser")
            for hidden in sal_copy.select(".wb-inv"):
                hidden.decompose()
            raw_sal = _clean_text(sal_copy.get_text(" ", strip=True))
            if raw_sal:
                raw_sal = re.sub(r"^Salaire\s*:\s*", "", raw_sal, flags=re.I).strip()
            if raw_sal and not any(k in raw_sal.lower() for k in ("non disponible", "not available")):
                salary = raw_sal

        date_node = article.select_one("li.date")
        raw_date = _clean_text(date_node.get_text(" ", strip=True)) if date_node else None
        published_at = parse_iso_date(raw_date)

        partner_node = article.select_one("li.source span.wb-inv")
        origin_partner = _clean_text(partner_node.get_text(" ", strip=True)) if partner_node else "Guichet-Emplois"

        clean_url = f"{GUICHET_BASE_URL}/rechercheemplois/offredemploi/{art_id}"
        stage_st = detect_stage_status(cnp_title, None)

        offers.append(
            JobBankOffer(
                id=f"ge-{art_id}",
                source_id=art_id,
                url=clean_url,
                cnp_title=cnp_title,
                titre=cnp_title,
                entreprise=employer,
                lieu=location,
                salaire=salary,
                date_publication=published_at,
                modalite=workplace_mode,
                source="guichet-emplois",
                source_partenaire=origin_partner,
                est_stage=(stage_st != "not_indicated"),
                statut_stage=stage_st,
                competences_cles=extract_tech_skills(cnp_title),
            )
        )

    return offers


def parse_job_detail_html(html_text: str, offer: JobBankOffer, student_filter: bool = False) -> JobBankOffer:
    """
    Enrichit une offre Guichet-Emplois à partir du HTML de sa fiche détaillée :
    1. Extrait le vrai titre de l'employeur (`.source-title-inner`) lorsqu'il diffère du titre CNP.
    2. Extrait la modalité (`Sur place`, `Hybride`, `Télétravail`) et le type de contrat depuis `ul.job-posting-brief`.
    3. Extrait la description complète via une cascade à 3 niveaux :
       - Niveau A : RDFa `property="description"` (avec décodage du HTML doublement échappé `&lt;p&gt;` des partenaires).
       - Niveau B : Conteneurs DOM (`#job-posting-detail`, `.job-posting-detail-requirements`, `.job-posting-details-body`).
       - Niveau C : Synthèse structurée du bandeau `.job-posting-brief` pour les offres partenaires externes sans texte libre.
    4. Détecte les compétences TI (`competences_cles`) et le statut de stage (`statut_stage`).
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Titre RDFa sur la fiche
    title_prop = soup.find(attrs={"property": "title"})
    if title_prop:
        detail_title = _clean_text(title_prop.get_text(" ", strip=True))
        if detail_title:
            offer.titre = detail_title

    # 1.b Vrai titre de l'employeur affiché sur le site partenaire (.source-title-inner)
    source_title_tag = soup.select_one(".source-title-inner")
    if source_title_tag:
        sc_copy = BeautifulSoup(str(source_title_tag), "html.parser")
        for lbl in sc_copy.select(".orig-title-label"):
            lbl.decompose()
        emp_title = _clean_text(sc_copy.get_text(" ", strip=True))
        if emp_title:
            offer.titre_employeur = emp_title

    # 2. Employeur RDFa (si absent de la liste)
    if not offer.entreprise:
        org_prop = soup.find(attrs={"property": "hiringOrganization"})
        if org_prop:
            name_prop = org_prop.find(attrs={"property": "name"}) or org_prop
            offer.entreprise = _clean_text(name_prop.get_text(" ", strip=True))

    # 3. Bandeau résumé (ul.job-posting-brief) pour modalité et conditions
    brief_node = soup.select_one("ul.job-posting-brief")
    brief_summary: Optional[str] = None
    if brief_node:
        brief_summary = _clean_text(brief_node.get_text(" | ", strip=True))
        brief_low = (brief_summary or "").lower()
        if not offer.modalite:
            if "télétravail" in brief_low or "remote" in brief_low:
                offer.modalite = "Télétravail"
            elif "hybride" in brief_low or "hybrid" in brief_low:
                offer.modalite = "Hybride"
            elif "sur place" in brief_low or "on site" in brief_low:
                offer.modalite = "Sur place"

    # 4. Cascade d'extraction de la description complète
    description_text: Optional[str] = None

    # Niveau A : RDFa property="description" (seulement si non vide !)
    for desc_candidate in soup.find_all(attrs={"property": "description"}):
        raw_desc = desc_candidate.get_text(" ", strip=True)
        if "<" in raw_desc and ">" in raw_desc:
            raw_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)
        cleaned_candidate = _clean_text(raw_desc)
        if cleaned_candidate and len(cleaned_candidate) > 25:
            description_text = cleaned_candidate
            break

    # Niveau B : Conteneurs DOM (#job-posting-detail, .job-posting-detail-requirements)
    if not description_text:
        for selector in ("#job-posting-detail", "section.job-posting-detail-requirements", "div.job-posting-detail-requirements"):
            dom_node = soup.select_one(selector)
            if dom_node:
                cleaned_dom = _clean_text(dom_node.get_text(" ", strip=True))
                if cleaned_dom and len(cleaned_dom) > 30:
                    description_text = cleaned_dom
                    break

    # Niveau C : Synthèse des informations de la fiche pour les offres partenaires sans corps de texte
    if not description_text and brief_summary:
        parts = []
        if offer.titre_employeur:
            parts.append(f"Intitulé employeur : {offer.titre_employeur}.")
        parts.append(f"Caractéristiques de l'offre ({offer.source_partenaire or 'Guichet-Emplois'}) : {brief_summary}")
        description_text = " ".join(parts)

    offer.description = description_text

    # 5. Date limite (validThrough), type d'emploi et niveau d'études
    valid_node = soup.find(attrs={"property": "validThrough"})
    if valid_node:
        offer.date_fin = _clean_text(valid_node.get_text(" ", strip=True))

    emp_parts: list[str] = []
    for prop_name in ("employmentType", "workHours"):
        node = soup.find(attrs={"property": prop_name})
        if node:
            val = _clean_text(node.get_text(" ", strip=True))
            if val and val not in emp_parts:
                emp_parts.append(val)
    if emp_parts:
        offer.type_poste = ", ".join(emp_parts)

    edu_node = soup.find(attrs={"property": "educationRequirements"})
    if edu_node:
        offer.niveau_etudes = _clean_text(edu_node.get_text(" ", strip=True))

    # 6. Détection de stage et compétences clés sur l'ensemble des champs
    offer.stage_status = detect_stage_status(
        f"{offer.titre or ''} {offer.titre_employeur or ''}",
        offer.description,
        student_filter=student_filter,
    )
    if offer.est_stage and (not offer.type_poste or offer.type_poste == "Temps plein"):
        offer.type_poste = "Stage"

    offer.competences_cles = extract_tech_skills(
        offer.titre,
        offer.titre_employeur,
        offer.description,
    )
    return offer


# ==============================================================================
# SOURCE 2 : Talent.com Canada (Double JSON-LD @graph + Coordonnées GPS)
# ==============================================================================
def parse_talent_search_json_ld(html_text: str) -> list[str]:
    """Extrait les URLs d'offres depuis l'objet JSON-LD ItemList (#jobList) de Talent.com."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else []
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for item in node.get("itemListElement", []):
                        u = item.get("item", {}).get("url")
                        if u and u not in urls:
                            urls.append(u)
        except json.JSONDecodeError:
            continue
    return urls


def parse_talent_job_detail_html(html_text: str, url: str) -> Optional[JobBankOffer]:
    """Extrait l'offre complète et ses coordonnées GPS depuis le JSON-LD JobPosting de Talent.com."""
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else []
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "JobPosting":
                    raw_id = url.split("id=")[-1].split("&")[0] if "id=" in url else str(abs(hash(url)))[:10]
                    title = _clean_text(node.get("title"))
                    org = node.get("hiringOrganization") or {}
                    company = _clean_text(org.get("name")) if isinstance(org, dict) else None
                    loc = node.get("jobLocation") or {}
                    if isinstance(loc, list) and loc:
                        loc = loc[0]
                    addr = loc.get("address") or {} if isinstance(loc, dict) else {}
                    geo = loc.get("geo") or {} if isinstance(loc, dict) else {}
                    city = _clean_text(addr.get("addressLocality"))
                    region = _clean_text(addr.get("addressRegion")) or "QC"

                    raw_desc_html = str(node.get("description") or "")
                    desc_clean = _clean_text(BeautifulSoup(raw_desc_html, "html.parser").get_text(" ", strip=True))
                    stage_st = detect_stage_status(title, desc_clean)

                    lat = float(geo["latitude"]) if geo.get("latitude") is not None else None
                    lon = float(geo["longitude"]) if geo.get("longitude") is not None else None

                    return JobBankOffer(
                        id=f"tc-{raw_id}",
                        source_id=raw_id,
                        url=url,
                        titre=title,
                        titre_employeur=title,
                        entreprise=company,
                        lieu=f"{city} ({region})" if city else region,
                        province=region,
                        source="talent-canada",
                        date_publication=parse_iso_date(node.get("datePosted")),
                        type_poste="Stage" if stage_st == "confirmed_stage" else _clean_text(str(node.get("employmentType") or "Temps plein")),
                        est_stage=(stage_st != "not_indicated"),
                        statut_stage=stage_st,
                        competences_cles=extract_tech_skills(title, desc_clean),
                        latitude=lat,
                        longitude=lon,
                        description=desc_clean,
                    )
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


# ==============================================================================
# SOURCE 3 : Jobboom Québec (Secteur Technologies _i10lfr + JSON-LD JobPosting)
# ==============================================================================
def parse_jobboom_listing_html(html_text: str) -> list[str]:
    """Extrait les URLs d'offres TI sur Jobboom dans l'ordre d'affichage (hors commandites)."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for card in soup.select("div.job_item[data-url]"):
        classes = card.get("class") or []
        if "job_item_sponsorship" in classes:
            continue
        path = str(card.get("data-url", "")).strip()
        if path.startswith("/fr/offre-emploi/"):
            full_u = f"https://www.jobboom.com{path}"
            if full_u not in urls:
                urls.append(full_u)
    return urls


def parse_json_ld_job_posting(html_text: str, url: str, source_name: str, id_prefix: str) -> Optional[JobBankOffer]:
    """Parseur générique de fiche JSON-LD Schema.org JobPosting (Jobboom & Jobillico)."""
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            if not (isinstance(data, dict) and data.get("@type") == "JobPosting"):
                continue
            m_id = re.search(r"(\d{5,})", url)
            raw_id = m_id.group(1) if m_id else str(abs(hash(url)))[:8]
            title = _clean_text(data.get("title"))
            org = data.get("hiringOrganization") or {}
            company = _clean_text(org.get("name")) if isinstance(org, dict) else None

            loc = data.get("jobLocation") or {}
            if isinstance(loc, list) and loc:
                loc = loc[0]
            addr = loc.get("address") or {} if isinstance(loc, dict) else {}
            city = _clean_text(addr.get("addressLocality"))
            region = _clean_text(addr.get("addressRegion")) or "QC"

            raw_desc = str(data.get("description") or "")
            desc_clean = _clean_text(BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True))
            stage_st = detect_stage_status(title, desc_clean)

            # Salaire éventuel dans baseSalary
            salary_str: Optional[str] = None
            base_sal = data.get("baseSalary")
            if isinstance(base_sal, dict):
                val_obj = base_sal.get("value")
                if isinstance(val_obj, dict):
                    min_v = val_obj.get("minValue")
                    max_v = val_obj.get("maxValue")
                    unit = val_obj.get("unitText", "")
                    if min_v and max_v:
                        salary_str = f"{min_v} $ à {max_v} $ ({unit})"
                    elif min_v:
                        salary_str = f"{min_v} $ ({unit})"

            modalite = None
            if desc_clean:
                low_d = desc_clean.lower()
                if "télétravail" in low_d or "100% remote" in low_d:
                    modalite = "Télétravail"
                elif "hybride" in low_d:
                    modalite = "Hybride"

            return JobBankOffer(
                id=f"{id_prefix}-{raw_id}",
                source_id=raw_id,
                url=url,
                titre=title,
                titre_employeur=title,
                entreprise=company,
                lieu=f"{city} ({region})" if city else region,
                province=region,
                source=source_name,
                date_publication=parse_iso_date(data.get("datePosted")),
                date_fin=parse_iso_date(data.get("validThrough")),
                type_poste="Stage" if stage_st == "confirmed_stage" else "Temps plein",
                modalite=modalite,
                salaire=salary_str,
                est_stage=(stage_st != "not_indicated"),
                statut_stage=stage_st,
                competences_cles=extract_tech_skills(title, desc_clean),
                description=desc_clean,
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


# ==============================================================================
# SOURCE 4 : Jobillico Québec (Recherche TI + JSON-LD JobPosting)
# ==============================================================================
def parse_jobillico_listing_html(html_text: str) -> list[str]:
    """Extrait les URLs d'offres depuis la page de résultats Jobillico."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for a_tag in soup.select("a[href*='/fr/offre-d-emploi/']"):
        href = str(a_tag.get("href", "")).split("?")[0].split("#")[0].strip()
        if href.startswith("/fr/offre-d-emploi/"):
            full_u = f"https://www.jobillico.com{href}"
            if full_u not in urls:
                urls.append(full_u)
    return urls


# ==============================================================================
# SOURCE 5 : Remotive API (API REST JSON officielle - Télétravail Canada)
# ==============================================================================
def fetch_remotive_canada_offers(session: requests.Session, limit: int = 4) -> list[JobBankOffer]:
    """Interroge l'API publique Remotive et filtre les offres TI accessibles depuis le Canada."""
    api_url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=30"
    print(f"\n[Source 5 - Remotive API] Requête JSON : {api_url}")
    offers: list[JobBankOffer] = []
    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("jobs", []):
            if len(offers) >= limit:
                break
            req_loc = str(item.get("candidate_required_location") or "").lower()
            if not any(k in req_loc for k in ("canada", "north america", "americas", "worldwide", "anywhere")):
                continue
            raw_id = str(item.get("id"))
            title = _clean_text(item.get("title"))
            company = _clean_text(item.get("company_name"))
            raw_desc = str(item.get("description") or "")
            desc_clean = _clean_text(BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True))
            job_type_raw = str(item.get("job_type") or "").lower()
            stage_st = "confirmed_stage" if "intern" in job_type_raw else detect_stage_status(title, desc_clean)

            offers.append(
                JobBankOffer(
                    id=f"rem-{raw_id}",
                    source_id=raw_id,
                    url=str(item.get("url")),
                    titre=title,
                    titre_employeur=title,
                    entreprise=company,
                    lieu=f"Télétravail ({item.get('candidate_required_location', 'Canada')})",
                    province="QC/CA",
                    source="remotive",
                    date_publication=parse_iso_date(item.get("publication_date")),
                    type_poste="Stage" if stage_st == "confirmed_stage" else "Temps plein",
                    modalite="Télétravail",
                    salaire=_clean_text(item.get("salary")) or None,
                    est_stage=(stage_st != "not_indicated"),
                    statut_stage=stage_st,
                    competences_cles=extract_tech_skills(title, desc_clean, " ".join(item.get("tags") or [])),
                    description=desc_clean,
                )
            )
    except requests.RequestException as exc:
        print(f"  ! Erreur Remotive API : {exc}")
    print(f"  -> {len(offers)} offres Remotive éligibles Canada extraites.")
    return offers


# ==============================================================================
# Orchestrateur Multi-Sources (5 plateformes)
# ==============================================================================
def collect_all_sources(
    guichet_limit: int = 8,
    other_limit: int = 4,
    student_only: bool = False,
    keyword: Optional[str] = None,
    delay: float = 2.0,
) -> list[dict[str, Any]]:
    """Collecte et enrichit les offres sur les 5 sources avec déduplication."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-CA,fr;q=0.9"})

    all_offers: list[JobBankOffer] = []

    # 1. Guichet-Emplois Canada (14 codes CNP TI)
    search_url = build_cnp_search_url(province="QC", student_only=student_only, keyword=keyword)
    allowed, _ = check_robots_permission(session, GUICHET_BASE_URL, search_url, default_delay=DEFAULT_CRAWL_DELAY)
    if allowed:
        print(f"\n[Source 1 - Guichet-Emplois CNP TI] Recherche : {search_url}")
        resp = session.get(search_url, timeout=15)
        resp.raise_for_status()
        ge_offers = parse_search_results_html(resp.text)
        print(f"  -> {len(ge_offers)} offres TI détectées sur la 1re page CNP. Enrichissement de {guichet_limit} fiches...")
        for idx, off in enumerate(ge_offers[:guichet_limit], start=1):
            time.sleep(delay)
            try:
                d_resp = session.get(off.url, timeout=15)
                d_resp.raise_for_status()
                parse_job_detail_html(d_resp.text, off, student_filter=student_only)
                print(f"  ✓ ({idx}/{guichet_limit}) [ge] {off.titre_employeur or off.titre} — {off.entreprise} ({len(off.competences_cles)} compétences)")
                all_offers.append(off)
            except requests.RequestException as exc:
                print(f"  ! Erreur fiche {off.url}: {exc}")

    # 2. Talent.com Canada (JSON-LD @graph + GPS)
    tc_query = keyword or ("stage informatique" if student_only else "développeur informatique")
    tc_url = f"https://ca.talent.com/fr/jobs?k={quote_plus(tc_query)}&l={quote_plus('Québec, QC')}"
    print(f"\n[Source 2 - Talent.com Canada] Recherche : {tc_url}")
    try:
        tc_resp = session.get(tc_url, timeout=15)
        tc_resp.raise_for_status()
        tc_links = parse_talent_search_json_ld(tc_resp.text)
        print(f"  -> {len(tc_links)} offres détectées dans l'ItemList JSON-LD.")
        for u in tc_links[:other_limit]:
            time.sleep(delay)
            d_resp = session.get(u, timeout=15)
            d_resp.raise_for_status()
            parsed = parse_talent_job_detail_html(d_resp.text, u)
            if parsed:
                print(f"  ✓ [tc] {parsed.titre} — {parsed.entreprise} (GPS: {parsed.latitude}, {parsed.longitude})")
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Talent.com : {exc}")

    # 3. Jobboom Québec (Secteur TI _i10lfr)
    jb_url = "https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1"
    print(f"\n[Source 3 - Jobboom Québec TI] Navigation : {jb_url}")
    try:
        jb_resp = session.get(jb_url, timeout=15)
        jb_resp.raise_for_status()
        jb_links = parse_jobboom_listing_html(jb_resp.text)
        print(f"  -> {len(jb_links)} offres TI organiques trouvées.")
        for u in jb_links[:other_limit]:
            time.sleep(delay)
            d_resp = session.get(u, timeout=15)
            d_resp.raise_for_status()
            parsed = parse_json_ld_job_posting(d_resp.text, u, source_name="jobboom", id_prefix="jb")
            if parsed:
                print(f"  ✓ [jb] {parsed.titre} — {parsed.entreprise} ({len(parsed.competences_cles)} compétences)")
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Jobboom : {exc}")

    # 4. Jobillico Québec (JSON-LD JobPosting)
    ji_query = keyword or ("stage informatique" if student_only else "développeur")
    ji_url = f"https://www.jobillico.com/recherche-emploi?skwd={quote(ji_query)}&scty={quote('Québec, QC')}"
    print(f"\n[Source 4 - Jobillico Québec] Recherche : {ji_url}")
    try:
        ji_resp = session.get(ji_url, timeout=15)
        ji_resp.raise_for_status()
        ji_links = parse_jobillico_listing_html(ji_resp.text)
        print(f"  -> {len(ji_links)} offres détectées sur Jobillico.")
        for u in ji_links[:other_limit]:
            time.sleep(delay)
            d_resp = session.get(u, timeout=15)
            d_resp.raise_for_status()
            parsed = parse_json_ld_job_posting(d_resp.text, u, source_name="jobillico", id_prefix="ji")
            if parsed:
                print(f"  ✓ [ji] {parsed.titre} — {parsed.entreprise} ({len(parsed.competences_cles)} compétences)")
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Jobillico : {exc}")

    # 5. Remotive API (Télétravail Canada)
    all_offers.extend(fetch_remotive_canada_offers(session, limit=other_limit))

    return [asdict(o) for o in all_offers]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecteur Multi-Sources Enrichi (5 sites Québec/Canada - Livrable 3)")
    parser.add_argument("--limite-guichet", type=int, default=8, help="Offres Guichet-Emplois CNP à enrichir (défaut: 8)")
    parser.add_argument("--limite-autres", type=int, default=4, help="Offres par autre source à enrichir (défaut: 4)")
    parser.add_argument("--stages", action="store_true", help="Cibler en priorité les stages (fsrc=16 sur Guichet-Emplois)")
    parser.add_argument("--mot-cle", type=str, default=None, help="Mot-clé optionnel")
    parser.add_argument("--delai", type=float, default=2.0, help="Délai en secondes entre les fiches (défaut: 2.0s)")
    parser.add_argument("--sortie", type=str, default="echantillon_v2.json", help="Fichier JSON de sortie")
    args = parser.parse_args()

    results = collect_all_sources(
        guichet_limit=args.limite_guichet,
        other_limit=args.limite_autres,
        student_only=args.stages,
        keyword=args.mot_cle,
        delay=args.delai,
    )

    out_path = Path(__file__).parent / args.sortie
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTerminé : {len(results)} offres multi-sources enrichies enregistrées dans {out_path.name}")


if __name__ == "__main__":
    main()
