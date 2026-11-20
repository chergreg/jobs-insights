"""
collecteurs.py — Les 4 collecteurs spécialisés du pipeline Multi-Sources.
Auteure : Elvira (Projet jobs-insights — Livrable 3 Multi-Sources)

Sources couvertes :
1. `JobboomCollector` (Jobboom Québec : Catégorie TI `_i10lfr` + Mots-clés + JSON-LD `JobPosting`).
2. `GuichetEmploisCollector` (Guichet-Emplois Canada : 14 codes CNP TI au Québec + fiches RDFa/DOM).
3. `JobillicoCollector` (Jobillico Québec : Recherche TI Québec + JSON-LD `JobPosting`).
4. `RemotiveCollector` (API REST JSON publique Remotive + cache 24 h + filtrage TI Canada).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models import (
    JobOffer,
    clean_html_text,
    detect_is_internship,
    detect_work_mode,
    extract_salary,
    extract_skills,
    is_it_job,
    is_recent_and_valid_offer,
    normalize_city_name,
    normalize_iso_date,
)

USER_AGENT = "jobs-insights-osullivan/1.0 (Projet etudiant TI; College O'Sullivan de Quebec)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
}

# Les 14 codes CNP 2021 du domaine informatique (repris de Kandet & Mamadou)
CNP_CODES_TI = (
    "20012",
    "21211",
    "21220",
    "21221",
    "21222",
    "21223",
    "21230",
    "21231",
    "21232",
    "21233",
    "21234",
    "22220",
    "22221",
    "22222",
)


class RobotGuard:
    """Gestionnaire de conformité `robots.txt` avec mise en cache par domaine."""

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self.user_agent = user_agent
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def get_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser | None:
        if base_url in self._parsers:
            return self._parsers[base_url]
        robots_url = f"{base_url.rstrip('/')}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            resp = requests.get(robots_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                self._parsers[base_url] = rp
                return rp
        except requests.RequestException:
            pass
        self._parsers[base_url] = None
        return None

    def is_allowed(self, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        rp = self.get_parser(base_url)
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)


# ==============================================================================
# 1. Collecteur Jobboom Québec (Elvira + Mamadou `_i10lfr`)
# ==============================================================================
class JobboomCollector:
    """Collecteur pour Jobboom Québec (Catégorie TI `_i10lfr` + Mots-clés + JSON-LD `JobPosting`)."""

    BASE_URL = "https://www.jobboom.com"
    CATEGORY_TI_PATH = "/fr/technologies-medias-numeriques/_i10lfr"

    def __init__(self, robot_guard: RobotGuard | None = None, delay: float = 1.5) -> None:
        self.robot_guard = robot_guard or RobotGuard()
        self.delay = delay

    @staticmethod
    def extract_job_id(url: str) -> str:
        match = re.search(r"_p(\d+)(?:$|[/?#])", url)
        if match:
            return f"jb-{match.group(1)}"
        return f"jb-{abs(hash(url)) % 10_000_000}"

    @staticmethod
    def parse_links_from_html(html_content: str, base_url: str = BASE_URL) -> tuple[list[str], int]:
        """Extrait les liens d'offres TI pertinentes depuis `<a href>` et `data-url` (hors commandites)."""
        soup = BeautifulSoup(html_content, "html.parser")
        links: list[str] = []
        seen_it: set[str] = set()
        all_raw_urls: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag["href"])
            if "/offre-emploi/" in href:
                full_url = urljoin(base_url, href.split("?")[0])
                all_raw_urls.add(full_url)
                link_text = clean_html_text(a_tag.get_text())
                if full_url not in seen_it and is_it_job(link_text, full_url):
                    seen_it.add(full_url)
                    links.append(full_url)

        for tag in soup.find_all(attrs={"data-url": True}):
            classes = " ".join(tag.get("class") or [])
            if "job_item_sponsorship" in classes:
                continue
            data_url = str(tag["data-url"])
            if "/offre-emploi/" in data_url:
                full_url = urljoin(base_url, data_url.split("?")[0])
                all_raw_urls.add(full_url)
                if full_url not in seen_it and is_it_job("", full_url):
                    seen_it.add(full_url)
                    links.append(full_url)

        return links, len(all_raw_urls)

    @staticmethod
    def parse_job_posting_from_html(
        html_content: str,
        url: str,
        origines_decouverte: list[str] | None = None,
    ) -> JobOffer | None:
        """Extrait et normalise le bloc JSON-LD `JobPosting` d'une fiche Jobboom en `JobOffer`."""
        soup = BeautifulSoup(html_content, "html.parser")
        job_data: dict[str, Any] | None = None
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                parsed = json.loads(raw.strip())
                if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
                    job_data = parsed
                    break
            except json.JSONDecodeError:
                continue

        if not job_data:
            return None

        return JobboomCollector.from_json_ld(job_data, url, origines_decouverte=origines_decouverte)

    @staticmethod
    def from_json_ld(
        job_data: dict[str, Any],
        url: str,
        origines_decouverte: list[str] | None = None,
    ) -> JobOffer:
        title = clean_html_text(job_data.get("title"))
        description_text = clean_html_text(job_data.get("description") or "")

        org = job_data.get("hiringOrganization")
        company = clean_html_text(org.get("name")) if isinstance(org, dict) else "Non spécifié"
        logo = org.get("logo") if isinstance(org, dict) else None

        job_loc = job_data.get("jobLocation")
        if isinstance(job_loc, list) and job_loc:
            job_loc = job_loc[0]
        address = job_loc.get("address", {}) if isinstance(job_loc, dict) else {}
        geo = job_loc.get("geo", {}) if isinstance(job_loc, dict) else {}

        city = normalize_city_name(address.get("addressLocality") or "Québec")
        province = address.get("addressRegion") or "QC"
        country = address.get("addressCountry") or "CA"
        postal_code = address.get("postalCode")

        lat_raw, lon_raw = geo.get("latitude"), geo.get("longitude")
        try:
            coords = (
                {"latitude": float(lat_raw), "longitude": float(lon_raw)}
                if lat_raw is not None and lon_raw is not None
                else None
            )
        except (TypeError, ValueError):
            coords = None

        emp_raw = job_data.get("employmentType")
        if isinstance(emp_raw, list):
            emp_types = [str(x) for x in emp_raw if x]
        elif isinstance(emp_raw, str) and emp_raw:
            emp_types = [emp_raw]
        else:
            emp_types = []

        return JobOffer(
            id=JobboomCollector.extract_job_id(url),
            source="Jobboom",
            titre=title,
            entreprise=company or "Non spécifié",
            logo_entreprise=logo,
            ville=city,
            province=province,
            pays=country,
            code_postal=postal_code,
            coordonnees_gps=coords,
            salaire=extract_salary(job_data),
            type_contrat=emp_types,
            modalite=detect_work_mode(title, description_text, str(job_data.get("jobLocationType") or "")),
            est_stage=detect_is_internship(title, description_text, emp_types),
            competences_cles=extract_skills(title, description_text),
            date_publication=normalize_iso_date(job_data.get("datePosted")),
            date_expiration=normalize_iso_date(job_data.get("validThrough")),
            url=url,
            description_texte=description_text,
            origines_decouverte=origines_decouverte or ["Jobboom"],
        )

    def collect_live(self, keywords: list[str] | None = None, max_offers: int = 8) -> list[JobOffer]:
        """Collecte en direct sur Jobboom (Catégorie `_i10lfr` + Mots-clés)."""
        keywords = keywords or ["stage informatique", "developpeur web"]
        discovered: list[tuple[str, list[str]]] = []

        cat_url = f"{self.BASE_URL}{self.CATEGORY_TI_PATH}?sortBy=date&page=1"
        if self.robot_guard.is_allowed(cat_url):
            try:
                resp = requests.get(cat_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                links, _ = self.parse_links_from_html(resp.text)
                discovered.append(("Jobboom:_i10lfr", links))
                time.sleep(self.delay)
            except requests.RequestException:
                pass

        for kw in keywords:
            slug = kw.strip().replace(" ", "-")
            kw_url = f"{self.BASE_URL}/fr/emploi/{slug}/_lfrk?dk={urllib.parse.quote_plus(kw)}"
            if not self.robot_guard.is_allowed(kw_url):
                continue
            try:
                resp = requests.get(kw_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                links, _ = self.parse_links_from_html(resp.text)
                discovered.append((f"Jobboom:mot_cle:{kw}", links))
                time.sleep(self.delay)
            except requests.RequestException:
                continue

        seen_urls: dict[str, list[str]] = {}
        for origin, urls in discovered:
            for u in urls:
                seen_urls.setdefault(u, [])
                if origin not in seen_urls[u]:
                    seen_urls[u].append(origin)

        offers: list[JobOffer] = []
        for url, origins in list(seen_urls.items())[:max_offers]:
            if not self.robot_guard.is_allowed(url):
                continue
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                offer = self.parse_job_posting_from_html(resp.text, url, origines_decouverte=origins)
                if (
                    offer
                    and is_it_job(offer.titre, offer.url)
                    and is_recent_and_valid_offer(offer.date_publication, offer.date_expiration)
                ):
                    offers.append(offer)
                time.sleep(self.delay)
            except requests.RequestException:
                continue

        return offers


# ==============================================================================
# 2. Collecteur Guichet-Emplois Canada (Kandet CNP + Hugo RDFa/DOM)
# ==============================================================================
class GuichetEmploisCollector:
    """
    Collecteur pour Guichet-Emplois Canada combinant :
    - la recherche par les 14 codes CNP TI au Québec et la détection du site partenaire (Kandet) ;
    - l'enrichissement des fiches détaillées via RDFa `property="description"` et repli DOM (Hugo/Mamadou).
    """

    BASE_URL = "https://www.guichetemplois.gc.ca"
    SEARCH_URL = f"{BASE_URL}/jobsearch/rechercheemplois"

    def __init__(self, robot_guard: RobotGuard | None = None, delay: float = 5.0) -> None:
        self.robot_guard = robot_guard or RobotGuard()
        self.delay = max(delay, 5.0)  # Respect strict du Crawl-delay: 5 de Guichet-Emplois

    @staticmethod
    def parse_search_results_html(html_content: str) -> list[dict[str, Any]]:
        """Extrait les cartes `<article id="article-...">` d'une page de résultats Guichet-Emplois."""
        soup = BeautifulSoup(html_content, "html.parser")
        cards: list[dict[str, Any]] = []

        for article in soup.find_all("article", id=re.compile(r"^article-\d+")):
            art_id = str(article.get("id") or "")
            source_id = art_id.replace("article-", "").strip()
            if not source_id:
                continue

            title_el = article.select_one(".noctitle")
            business_el = article.select_one(".business")
            loc_el = article.select_one(".location")
            sal_el = article.select_one(".salary")
            date_el = article.select_one(".date")
            telework_el = article.select_one(".telework")
            source_li = article.select_one("li.source")

            for hidden in article.select(".location .wb-inv, .salary .wb-inv, .date .wb-inv"):
                hidden.decompose()

            partner = None
            if source_li:
                inv = source_li.select_one("span.wb-inv")
                if inv:
                    partner_raw = clean_html_text(inv.get_text())
                    if partner_raw and "numéro" not in partner_raw.lower():
                        partner = partner_raw

            link_tag = article.find("a", href=True)
            href = str(link_tag["href"]).split(";jsessionid=")[0].split("?")[0] if link_tag else ""
            full_url = urljoin(GuichetEmploisCollector.BASE_URL, href) if href else (
                f"{GuichetEmploisCollector.BASE_URL}/rechercheemplois/offredemploi/{source_id}"
            )

            cards.append(
                {
                    "id": f"ge-{source_id}",
                    "source_id": source_id,
                    "titre": clean_html_text(title_el.get_text()) if title_el else "",
                    "entreprise": clean_html_text(business_el.get_text()) if business_el else "Non spécifié",
                    "ville": normalize_city_name(clean_html_text(loc_el.get_text()) if loc_el else "Québec"),
                    "salaire": clean_html_text(sal_el.get_text()).replace("Salaire :", "").strip() if sal_el else None,
                    "date_publication": normalize_iso_date(clean_html_text(date_el.get_text()) if date_el else None),
                    "telework_hint": clean_html_text(telework_el.get_text()) if telework_el else "",
                    "partenaire_origine": partner,
                    "url": full_url,
                }
            )

        return cards

    @staticmethod
    def enrich_from_detail_html(card: dict[str, Any], detail_html: str) -> JobOffer:
        """Enrichit une carte Guichet-Emplois avec le HTML de sa fiche détaillée (RDFa + repli DOM)."""
        soup = BeautifulSoup(detail_html, "html.parser")

        # Vrai titre employeur s'il est affiché
        emp_title_el = soup.select_one(".source-title-inner") or soup.find(attrs={"property": "title"})
        real_title = clean_html_text(emp_title_el.get_text()) if emp_title_el else card.get("titre", "")
        title = real_title or card.get("titre", "")

        # Cascade description : 1. RDFa property="description", 2. #job-posting-detail, 3. ul.job-posting-brief
        desc_el = (
            soup.find(attrs={"property": "description"})
            or soup.select_one("#job-posting-detail")
            or soup.select_one("ul.job-posting-brief")
        )
        description_text = clean_html_text(str(desc_el)) if desc_el else ""

        hint = f"{card.get('telework_hint', '')} {description_text}"
        modalite = detect_work_mode(title, description_text, hint)
        est_stage = detect_is_internship(title, description_text, [])
        skills = extract_skills(title, description_text)

        return JobOffer(
            id=card["id"],
            source="Guichet-Emplois",
            partenaire_origine=card.get("partenaire_origine"),
            origines_decouverte=["Guichet-Emplois:CNP_TI"],
            titre=title,
            entreprise=card.get("entreprise") or "Non spécifié",
            ville=card.get("ville") or "Québec",
            province="QC",
            pays="CA",
            salaire=card.get("salaire"),
            type_contrat=["FULL_TIME"],
            modalite=modalite,
            est_stage=est_stage,
            competences_cles=skills,
            date_publication=card.get("date_publication"),
            date_expiration=None,
            url=card["url"],
            description_texte=description_text,
        )


# ==============================================================================
# 3. Collecteur Jobillico Québec (Mamadou + Hugo JSON-LD)
# ==============================================================================
class JobillicoCollector:
    """Collecteur pour Jobillico Québec (Recherche TI + JSON-LD `JobPosting`)."""

    BASE_URL = "https://www.jobillico.com"

    @staticmethod
    def extract_job_id(url: str) -> str:
        match = re.search(r"/(\d+)(?:$|[/?#])", url)
        if match:
            return f"ji-{match.group(1)}"
        return f"ji-{abs(hash(url)) % 10_000_000}"

    @staticmethod
    def parse_links_from_html(html_content: str, base_url: str = BASE_URL) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag["href"])
            if "/fr/offre-d-emploi/" in href:
                full_url = urljoin(base_url, href.split("?")[0].split("#")[0])
                if full_url not in seen:
                    seen.add(full_url)
                    links.append(full_url)
        return links

    @staticmethod
    def parse_job_posting_from_html(html_content: str, url: str) -> JobOffer | None:
        soup = BeautifulSoup(html_content, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw or "JobPosting" not in raw:
                continue
            try:
                data = json.loads(raw.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                title = clean_html_text(data.get("title"))
                desc = clean_html_text(data.get("description") or "")
                org = data.get("hiringOrganization")
                company = clean_html_text(org.get("name")) if isinstance(org, dict) else "Non spécifié"
                loc = data.get("jobLocation")
                if isinstance(loc, list) and loc:
                    loc = loc[0]
                addr = loc.get("address", {}) if isinstance(loc, dict) else {}
                city = normalize_city_name(addr.get("addressLocality") or "Québec")
                emp_raw = data.get("employmentType")
                emp_types = [emp_raw] if isinstance(emp_raw, str) else list(emp_raw or [])

                return JobOffer(
                    id=JobillicoCollector.extract_job_id(url),
                    source="Jobillico",
                    origines_decouverte=["Jobillico:recherche_ti"],
                    titre=title,
                    entreprise=company or "Non spécifié",
                    ville=city,
                    province=addr.get("addressRegion") or "QC",
                    pays="CA",
                    code_postal=addr.get("postalCode"),
                    salaire=extract_salary(data),
                    type_contrat=emp_types,
                    modalite=detect_work_mode(title, desc),
                    est_stage=detect_is_internship(title, desc, emp_types),
                    competences_cles=extract_skills(title, desc),
                    date_publication=normalize_iso_date(data.get("datePosted")),
                    date_expiration=normalize_iso_date(data.get("validThrough")),
                    url=url,
                    description_texte=desc,
                )
        return None


# ==============================================================================
# 4. Collecteur Remotive API REST (Kandet + Gregory)
# ==============================================================================
class RemotiveCollector:
    """Collecteur pour l'API REST publique Remotive (postes et stages TI en télétravail ouverts au Canada)."""

    API_URL = "https://remotive.com/api/remote-jobs"
    CANADA_PATTERNS = re.compile(
        r"\b(?:canada|quebec|québec|north\s+america|americas|worldwide|anywhere)\b",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def parse_api_jobs(payload: dict[str, Any]) -> list[JobOffer]:
        jobs = payload.get("jobs") or []
        offers: list[JobOffer] = []

        for job in jobs:
            if not isinstance(job, dict):
                continue
            title = clean_html_text(job.get("title"))
            url = str(job.get("url") or "")
            req_loc = str(job.get("candidate_required_location") or "Worldwide")

            if not RemotiveCollector.CANADA_PATTERNS.search(req_loc):
                continue
            if not is_it_job(title, url):
                continue

            pub_date = normalize_iso_date(job.get("publication_date"))
            if not is_recent_and_valid_offer(pub_date, None):
                continue

            desc = clean_html_text(job.get("description") or "")
            job_type = str(job.get("job_type") or "").upper()
            emp_types = [job_type] if job_type else ["FULL_TIME"]
            est_stage = job_type == "INTERNSHIP" or detect_is_internship(title, desc, emp_types)
            tags = [str(t) for t in (job.get("tags") or [])]
            skills = extract_skills(f"{title} {' '.join(tags)}", desc)
            salary = clean_html_text(job.get("salary")) or None

            offers.append(
                JobOffer(
                    id=f"rem-{job.get('id')}",
                    source="Remotive",
                    origines_decouverte=["Remotive:api_rest"],
                    titre=title,
                    entreprise=clean_html_text(job.get("company_name")) or "Non spécifié",
                    logo_entreprise=job.get("company_logo"),
                    ville=f"Télétravail ({req_loc})",
                    province="QC",
                    pays="CA",
                    salaire=salary,
                    type_contrat=emp_types,
                    modalite="Télétravail",
                    est_stage=est_stage,
                    competences_cles=skills,
                    date_publication=pub_date,
                    date_expiration=None,
                    url=url,
                    description_texte=desc,
                )
            )

        return offers
