"""
scraper_jobboom_v2.py — Livrable 3 : Collecteur et normalisateur amélioré pour Jobboom Québec.
Auteure : Elvira (Projet jobs-insights)

Améliorations par rapport au Livrable 2 (Scraper.py d'Elvira et poc_scrapers_atelier1.py de Mamadou) :
1. Fusion des deux stratégies de découverte sur Jobboom :
   - Catégorie Secteur Technologies (`_i10lfr?sortBy=date&page=N`, approche de Mamadou) ;
   - Recherche par mots-clés ciblés (`/fr/emploi/<slug>/_lfrk?dk=...`, approche d'Elvira).
2. Déduplication par identifiant Jobboom (`jb-<id>`) avec traçabilité des canaux de découverte (`origines_decouverte`).
3. Conformité et respect du site :
   - Vérification automatique de `robots.txt` via `urllib.robotparser` avant les requêtes ;
   - `User-Agent` honnête identifiant le projet étudiant du Collège O'Sullivan de Québec.
4. Enrichissement du schéma normalisé :
   - Extraction du salaire (`salaire`) depuis `baseSalary` du JSON-LD lorsqu'il est renseigné (`None` sinon, sans deviner) ;
   - Détection affinée des stages, de la modalité et des compétences TI sans faux positifs.
5. Architecture modulaire et testable hors ligne (voir `test_scraper_jobboom_v2.py`).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.robotparser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models import is_recent_and_valid_offer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://www.jobboom.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
CATEGORY_TI_PATH = "/fr/technologies-medias-numeriques/_i10lfr"

USER_AGENT = "jobs-insights-osullivan/1.0 (Projet etudiant TI; College O'Sullivan de Quebec)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

DEFAULT_KEYWORDS = [
    "stage informatique",
    "developpeur web",
    "programmeur",
    "informatique",
]

# Mots-clés confirmant qu'un titre d'offre appartient bien au domaine TI / Informatique
IT_TITLE_POSITIVE_PATTERNS = re.compile(
    r"\b(?:"
    r"informatique|informaticien(?:ne)?|ti\b|it\b|"
    r"developpeur(?:euse)?|developer|programmeur(?:euse)?|programmer|"
    r"logiciel(?:s)?|software|web|fullstack|full[\s-]?stack|frontend|front[\s-]?end|backend|back[\s-]?end|"
    r"devops|cloud|cybersecurite|cybersecurity|securite\s+informatique|"
    r"data|donnees|base(?:s)?\s+de\s+donnees|dba|bi\b|intelligence\s+d['’]affaires|"
    r"reseau(?:x)?|network|systeme(?:s)?\s+informatique|administrateur(?:trice)?\s+systeme|sysadmin|"
    r"support\s+technique|soutien\s+technique|soutien\s+informatique|helpdesk|help\s+desk|"
    r"technicien(?:ne)?\s+informatique|technicien(?:ne)?\s+ti|"
    r"end\s+user\s+computing|euc\b|configuration\s+informatique|"
    r"analyste\s+fonctionnel|analyste\s+ti|analyste[\s-]programmeur|architecte\s+ti|architecte\s+logiciel|"
    r"specialiste\s+d['’]?application|"
    r"qa\b|assurance\s+qualite\s+logiciel|testeur(?:euse)?\s+logiciel|"
    r"scrum\s+master|product\s+owner|integrateur(?:trice)?\s+web"
    r")\b",
    flags=re.IGNORECASE,
)

# Mots-clés dans le titre qui indiquent clairement un poste HORS informatique
IT_TITLE_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"cvc|cvac|hvac|batiment(?:s)?|construction|mecanicien|electromecanicien|usinage|cnc|"
    r"comptable|comptabilite|accounting|accounts\s+receivable|accounts\s+payable|controleur|"
    r"succursale|sqdc|vendeur|vente(?:s)?|sales\s+representative|service\s+a\s+la\s+clientele|"
    r"deductions|claims|reclamations|soumissions|inspecteur|travaux|loans"
    r")\b",
    flags=re.IGNORECASE,
)

TECH_SKILLS_PATTERNS: list[tuple[str, str]] = [
    ("Python", r"\bpython\b"),
    ("Java", r"\bjava\b"),
    ("C#", r"\bc#|\bc\s*sharp\b"),
    (".NET", r"(?:^|[\s,;(/])\.net\b|\basp\.net\b"),
    ("C++", r"\bc\+\+"),
    ("JavaScript", r"\bjavascript\b|\bjs\b"),
    ("TypeScript", r"\btypescript\b"),
    ("React", r"\breact(?:\.js|js)?\b"),
    ("Angular", r"\bangular(?:\.js|js)?\b"),
    ("Vue.js", r"\bvue\.js\b|\bvuejs\b"),
    ("Node.js", r"\bnode\.js\b|\bnodejs\b"),
    ("jQuery", r"\bjquery\b"),
    ("HTML", r"\bhtml5?\b"),
    ("CSS", r"\bcss3?\b|\bsass\b|\bscss\b"),
    ("PHP", r"\bphp\b|\blaravel\b|\bsymfony\b"),
    ("SQL", r"\bsql\b"),
    ("T-SQL", r"\bt-sql\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("MongoDB", r"\bmongodb\b"),
    ("SSIS", r"\bssis\b"),
    ("SSRS", r"\bssrs\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("AWS", r"\baws\b|\bamazon\s+web\s+services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle\s+cloud\b"),
    ("Git", r"\bgit\b|\bgithub\b|\bgitlab\b"),
    ("Jira", r"\bjira\b"),
    ("Confluence", r"\bconfluence\b"),
    ("CI/CD", r"\bci\s*/\s*cd\b"),
    ("DevOps", r"\bdevops\b"),
    ("Linux", r"\blinux\b"),
    ("Windows", r"\bwindows\b"),
    ("ITIL", r"\bitil\b"),
    ("Agile", r"\bagile\b|\bscrum\b"),
    ("REST API", r"\brest\s*api\b|\bapi\s*rest\b|\brestful\b|\bapi\b"),
    ("AJAX", r"\bajax\b"),
    ("XML", r"\bxml\b"),
    ("JSON", r"\bjson\b"),
    ("VBA", r"\bvba\b"),
]

STAGE_REGEX = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op)\b",
    flags=re.IGNORECASE,
)

UNIT_LABELS = {
    "HOUR": "heure",
    "DAY": "jour",
    "WEEK": "semaine",
    "MONTH": "mois",
    "YEAR": "an",
}


def strip_accents(text: str) -> str:
    """Supprime les accents d'une chaîne pour faciliter les comparaisons regex."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_it_job(title: str, url: str = "") -> bool:
    """
    Vérifie que l'offre est réellement un poste en Informatique / TI
    d'après son titre (et son slug d'URL), en excluant les postes hors-sujet.
    """
    normalized_title = strip_accents(title or "").lower()
    normalized_url = strip_accents(url or "").lower()
    target = f"{normalized_title} {normalized_url}"

    if IT_TITLE_EXCLUSION_PATTERNS.search(target):
        return False

    return bool(IT_TITLE_POSITIVE_PATTERNS.search(target))


def clean_html_text(raw_html: str | None) -> str:
    """Nettoie une chaîne HTML pour obtenir un texte brut lisible."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_job_id(url: str) -> str:
    """Extrait l'identifiant numérique Jobboom depuis l'URL (ex: jb-3698100)."""
    match = re.search(r"_p(\d+)(?:$|[/?#])", url)
    if match:
        return f"jb-{match.group(1)}"
    return f"jb-{abs(hash(url)) % 10_000_000}"


def detect_work_mode(title: str, description_text: str, job_location_type: str | None = None) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    combined = f"{title} {description_text}".lower()
    if any(term in combined for term in ("hybride", "hybrid", "mode hybride", "télétravail partiel")):
        return "Hybride"
    if (job_location_type and "TELECOMMUTE" in str(job_location_type).upper()) or any(
        term in combined
        for term in ("télétravail", "teletravail", "100% à distance", "remote", "travail à distance")
    ):
        return "Télétravail"
    return "Sur place"


def detect_is_internship(title: str, description_text: str, employment_types: list[str]) -> bool:
    """Détecte si l'offre correspond à un stage."""
    emp_upper = {t.upper() for t in employment_types}
    if "INTERN" in emp_upper or "INTERNSHIP" in emp_upper:
        return True
    if STAGE_REGEX.search(title):
        return True
    if re.search(r"\b(?:offre de stage|stage rémunéré|stagiaire en|stage offert)\b", description_text, re.IGNORECASE):
        return True
    return False


def extract_skills(title: str, description_text: str) -> list[str]:
    """Extrait la liste des compétences techniques TI mentionnées dans l'offre."""
    combined = f"{title} {description_text}"
    found: list[str] = []
    for label, pattern in TECH_SKILLS_PATTERNS:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            found.append(label)
    return found


def extract_salary(job_data: dict[str, Any]) -> str | None:
    """
    Extrait le salaire depuis le champ `baseSalary` du JSON-LD JobPosting s'il existe.
    Retourne `None` si aucun salaire n'est renseigné (sans jamais inventer de valeur).
    """
    base_salary = job_data.get("baseSalary")
    if base_salary is None:
        return None
    if isinstance(base_salary, (int, float)):
        return f"{base_salary} $"
    if isinstance(base_salary, str):
        cleaned = base_salary.strip()
        return cleaned or None
    if isinstance(base_salary, dict):
        currency = base_salary.get("currency") or "CAD"
        val = base_salary.get("value")
        if isinstance(val, dict):
            min_v = val.get("minValue")
            max_v = val.get("maxValue")
            exact_v = val.get("value")
            unit_raw = str(val.get("unitText") or "").upper()
            unit = UNIT_LABELS.get(unit_raw, unit_raw.lower())
            suffix = f" / {unit}" if unit else ""
            if min_v is not None and max_v is not None:
                return f"{min_v} à {max_v} {currency}{suffix}"
            if exact_v is not None:
                return f"{exact_v} {currency}{suffix}"
        elif isinstance(val, (int, float, str)) and str(val).strip():
            return f"{val} {currency}"
    return None


def parse_job_links_from_html(html_content: str, base_url: str = BASE_URL) -> tuple[list[str], int]:
    """
    Extrait de façon déterministe les liens d'offres TI pertinentes depuis une page HTML Jobboom.
    Combine l'inspection des balises `<a href="...">` (Elvira v1) et des attributs `data-url` (Mamadou).
    Retourne `(liens_ti_retenus, total_liens_bruts)`.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links: list[str] = []
    seen_it: set[str] = set()
    all_raw_urls: set[str] = set()

    # 1. Balises <a href="/fr/offre-emploi/...">
    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"])
        if "/offre-emploi/" in href:
            full_url = urljoin(base_url, href.split("?")[0])
            all_raw_urls.add(full_url)
            link_text = clean_html_text(a_tag.get_text())
            if full_url not in seen_it and is_it_job(link_text, full_url):
                seen_it.add(full_url)
                links.append(full_url)

    # 2. Attributs data-url="/fr/offre-emploi/..." sur les cartes d'offres (approche Mamadou)
    for tag in soup.find_all(attrs={"data-url": True}):
        data_url = str(tag["data-url"])
        if "/offre-emploi/" in data_url:
            full_url = urljoin(base_url, data_url.split("?")[0])
            all_raw_urls.add(full_url)
            if full_url not in seen_it and is_it_job("", full_url):
                seen_it.add(full_url)
                links.append(full_url)

    return links, len(all_raw_urls)


def parse_job_posting_json_from_html(html_content: str) -> dict[str, Any] | None:
    """Extrait l'objet JSON-LD (@type == 'JobPosting') du HTML d'une fiche d'offre."""
    soup = BeautifulSoup(html_content, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        raw_content = script.string or script.get_text()
        if not raw_content:
            continue
        try:
            data = json.loads(raw_content.strip())
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                return data
        except json.JSONDecodeError:
            continue

    return None


def normalize_job_posting(
    job_data: dict[str, Any],
    url: str,
    origines_decouverte: list[str] | None = None,
) -> dict[str, Any]:
    """Transforme le bloc JSON-LD JobPosting brut en un dictionnaire normalisé et enrichi."""
    title = clean_html_text(job_data.get("title"))
    raw_description = job_data.get("description") or ""
    description_text = clean_html_text(raw_description)

    org = job_data.get("hiringOrganization")
    if isinstance(org, dict):
        company = clean_html_text(org.get("name")) or "Non spécifié"
        logo = org.get("logo")
    else:
        company = "Non spécifié"
        logo = None

    job_location = job_data.get("jobLocation")
    if isinstance(job_location, list) and job_location:
        job_location = job_location[0]
    address = job_location.get("address", {}) if isinstance(job_location, dict) else {}
    geo = job_location.get("geo", {}) if isinstance(job_location, dict) else {}

    city = address.get("addressLocality") or "Non spécifié"
    province = address.get("addressRegion") or "QC"
    country = address.get("addressCountry") or "CA"
    postal_code = address.get("postalCode")

    lat_raw = geo.get("latitude")
    lon_raw = geo.get("longitude")
    try:
        coordinates = (
            {"latitude": float(lat_raw), "longitude": float(lon_raw)}
            if lat_raw is not None and lon_raw is not None
            else None
        )
    except (TypeError, ValueError):
        coordinates = None

    emp_type_raw = job_data.get("employmentType")
    if isinstance(emp_type_raw, list):
        employment_types = [str(item) for item in emp_type_raw if item]
    elif isinstance(emp_type_raw, str) and emp_type_raw:
        employment_types = [emp_type_raw]
    else:
        employment_types = []

    work_mode = detect_work_mode(title, description_text, job_data.get("jobLocationType"))
    is_stage = detect_is_internship(title, description_text, employment_types)
    skills = extract_skills(title, description_text)
    salary = extract_salary(job_data)

    return {
        "id": extract_job_id(url),
        "source": "Jobboom",
        "origines_decouverte": origines_decouverte or ["non_specifie"],
        "titre": title,
        "entreprise": company,
        "logo_entreprise": logo,
        "ville": city,
        "province": province,
        "pays": country,
        "code_postal": postal_code,
        "coordonnees_gps": coordinates,
        "salaire": salary,
        "type_contrat": employment_types,
        "modalite": work_mode,
        "est_stage": is_stage,
        "competences_cles": skills,
        "date_publication": job_data.get("datePosted"),
        "date_expiration": job_data.get("validThrough"),
        "url": url,
        "description_texte": description_text,
    }


def load_robot_parser(robots_url: str = ROBOTS_URL) -> urllib.robotparser.RobotFileParser | None:
    """Charge et analyse le fichier robots.txt de Jobboom."""
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp
    except requests.RequestException:
        pass
    return None


def is_url_allowed(
    rp: urllib.robotparser.RobotFileParser | None,
    url: str,
    user_agent: str = USER_AGENT,
) -> bool:
    """Vérifie si l'URL est autorisée par le robots.txt (autorisé par défaut si robots.txt est inaccessible)."""
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)


def merge_discovered_urls(
    discovered_batches: list[tuple[str, list[str]]],
    max_per_channel: int | None = None,
) -> list[tuple[str, list[str]]]:
    """
    Fusionne et déduplique les URLs d'offres issues de plusieurs canaux
    (catégorie TI `_i10lfr` de Mamadou + mots-clés d'Elvira) en conservant
    l'ordre de découverte et la liste des canaux (`origines_decouverte`) pour chaque offre.
    """
    ordered_ids: list[str] = []
    id_to_url: dict[str, str] = {}
    id_to_origins: dict[str, list[str]] = {}

    for origin_label, urls in discovered_batches:
        count = 0
        for url in urls:
            job_id = extract_job_id(url)
            if job_id not in id_to_url:
                ordered_ids.append(job_id)
                id_to_url[job_id] = url
                id_to_origins[job_id] = [origin_label]
            elif origin_label not in id_to_origins[job_id]:
                id_to_origins[job_id].append(origin_label)
            count += 1
            if max_per_channel is not None and count >= max_per_channel:
                break

    return [(id_to_url[jid], id_to_origins[jid]) for jid in ordered_ids]


def fetch_category_ti_links(
    page: int = 1,
    rp: urllib.robotparser.RobotFileParser | None = None,
) -> list[str]:
    """
    Récupère les liens d'offres depuis la catégorie Secteur Technologies (`_i10lfr`)
    avec tri par date (approche de Mamadou combinée au filtre TI d'Elvira).
    """
    url = f"{BASE_URL}{CATEGORY_TI_PATH}"
    params: dict[str, str | int] = {"sortBy": "date", "page": page}
    if not is_url_allowed(rp, url):
        print(f"      [!] URL bloquée par robots.txt : {url}")
        return []

    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    links, raw_count = parse_job_links_from_html(response.text)
    print(f"      -> [Catégorie TI _i10lfr | p.{page}] {len(links)} offres TI retenues sur {raw_count} annonces")
    return links


def fetch_keyword_links(
    keyword: str,
    page: int = 1,
    rp: urllib.robotparser.RobotFileParser | None = None,
) -> list[str]:
    """Récupère les liens d'offres TI pour un mot-clé donné (approche d'Elvira)."""
    slug = keyword.strip().replace(" ", "-")
    url = f"{BASE_URL}/fr/emploi/{slug}/_lfrk"
    params: dict[str, str | int] = {"dk": keyword}
    if page > 1:
        params["page"] = page

    if not is_url_allowed(rp, url):
        print(f"      [!] URL bloquée par robots.txt : {url}")
        return []

    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    links, raw_count = parse_job_links_from_html(response.text)
    print(f"      -> [Mot-clé '{keyword}' | p.{page}] {len(links)} offres TI retenues sur {raw_count} annonces")
    return links


def upgrade_existing_file(
    source_file: Path,
    output_file: Path,
    mamadou_file: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Re-normalise et fusionne hors ligne le fichier JSON v1 d'Elvira (`offres_jobboom.json`)
    et les offres Jobboom de l'échantillon de Mamadou (`sample_scraped_jobs.json`) vers le schéma v2.
    """
    if not source_file.exists():
        raise FileNotFoundError(f"Fichier introuvable : {source_file}")

    items = json.loads(source_file.read_text(encoding="utf-8"))
    results_by_id: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []

    for item in items:
        raw_ld = item.get("raw_json_ld")
        url = item.get("url") or (raw_ld.get("url_offre") if isinstance(raw_ld, dict) else None)
        if not url:
            continue
        job_id = extract_job_id(url)
        title = clean_html_text((raw_ld.get("title") if isinstance(raw_ld, dict) else None) or item.get("titre"))
        if not is_it_job(title, url):
            continue
        origins = list(item.get("origines_decouverte") or ["mots_cles_elvira"])
        if job_id not in results_by_id:
            ordered_ids.append(job_id)
            if isinstance(raw_ld, dict):
                results_by_id[job_id] = normalize_job_posting(raw_ld, url, origines_decouverte=origins)
            else:
                desc = clean_html_text(item.get("description_texte"))
                emp_types = list(item.get("type_contrat") or [])
                results_by_id[job_id] = {
                    "id": job_id,
                    "source": "Jobboom",
                    "origines_decouverte": origins,
                    "titre": title,
                    "entreprise": item.get("entreprise") or "Non spécifié",
                    "logo_entreprise": item.get("logo_entreprise"),
                    "ville": item.get("ville") or "Non spécifié",
                    "province": item.get("province") or "QC",
                    "pays": item.get("pays") or "CA",
                    "code_postal": item.get("code_postal"),
                    "coordonnees_gps": item.get("coordonnees_gps"),
                    "salaire": item.get("salaire"),
                    "type_contrat": emp_types,
                    "modalite": item.get("modalite") or detect_work_mode(title, desc),
                    "est_stage": bool(item.get("est_stage", detect_is_internship(title, desc, emp_types))),
                    "competences_cles": item.get("competences_cles") or extract_skills(title, desc),
                    "date_publication": item.get("date_publication"),
                    "date_expiration": item.get("date_expiration"),
                    "url": url,
                    "description_texte": desc,
                }
        else:
            existing_origins = results_by_id[job_id]["origines_decouverte"]
            for orig in origins:
                if orig not in existing_origins:
                    existing_origins.append(orig)

    if mamadou_file and mamadou_file.exists():
        mamadou_items = json.loads(mamadou_file.read_text(encoding="utf-8"))
        for m_item in mamadou_items:
            if "jobboom" not in str(m_item.get("source", "")).lower():
                continue
            url = m_item.get("url")
            if not url:
                continue
            title = clean_html_text(m_item.get("title"))
            if not is_it_job(title, url):
                continue
            job_id = extract_job_id(url)
            origin_tag = "categorie_ti:_i10lfr (Mamadou)"
            if job_id in results_by_id:
                existing_origins = results_by_id[job_id]["origines_decouverte"]
                if origin_tag not in existing_origins:
                    existing_origins.append(origin_tag)
                continue

            synthetic_ld = {
                "@context": "http://schema.org/",
                "@type": "JobPosting",
                "title": m_item.get("title"),
                "description": m_item.get("description_preview") or "",
                "datePosted": m_item.get("date_posted"),
                "validThrough": m_item.get("valid_through"),
                "hiringOrganization": {
                    "@type": "Organization",
                    "name": m_item.get("company") or "Non spécifié",
                },
                "jobLocation": {
                    "@type": "Place",
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": m_item.get("city") or "Non spécifié",
                        "addressRegion": m_item.get("region") or "QC",
                        "addressCountry": "CA",
                    },
                },
            }
            ordered_ids.append(job_id)
            results_by_id[job_id] = normalize_job_posting(
                synthetic_ld,
                url,
                origines_decouverte=[origin_tag],
            )

    results = [
        results_by_id[jid]
        for jid in ordered_ids
        if is_recent_and_valid_offer(
            results_by_id[jid].get("date_publication"),
            results_by_id[jid].get("date_expiration"),
        )
    ]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Livrable 3 — Collecteur Jobboom v2 (Catégorie TI _i10lfr + Mots-clés + Conformité robots.txt)."
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="Mots-clés TI à rechercher sur Jobboom.",
    )
    parser.add_argument(
        "--category-pages",
        type=int,
        default=2,
        help="Nombre de pages à parcourir dans la catégorie Secteur Technologies (_i10lfr) (défaut: 2).",
    )
    parser.add_argument(
        "--keyword-pages",
        type=int,
        default=1,
        help="Nombre de pages à parcourir par mot-clé (défaut: 1).",
    )
    parser.add_argument(
        "--max-per-channel",
        type=int,
        default=6,
        help="Nombre maximal d'offres retenues par canal de recherche (défaut: 6).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Délai minimal en secondes entre deux requêtes (défaut: 1.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "offres_jobboom_v2.json",
        help="Chemin du fichier JSON de sortie.",
    )
    parser.add_argument(
        "--from-v1",
        type=Path,
        default=None,
        help="Chemin d'un fichier JSON v1 à migrer hors ligne vers le format v2.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.from_v1 is not None:
        default_mamadou = (
            Path(__file__).resolve().parent.parent.parent
            / "mamadou"
            / "02-preuve-de-concept-scraping"
            / "sample_scraped_jobs.json"
        )
        print(f"[*] Fusion et normalisation hors ligne depuis {args.from_v1} (+ échantillon Mamadou) vers {args.output}...")
        migrated = upgrade_existing_file(args.from_v1, args.output, mamadou_file=default_mamadou)
        print(f"[OK] {len(migrated)} offres TI uniques fusionnées au format v2 dans {args.output.name}.")
        return

    print(f"[0/3] Vérification de {ROBOTS_URL} (User-Agent: {USER_AGENT})...")
    rp = load_robot_parser()
    crawl_delay = rp.crawl_delay(USER_AGENT) if rp else None
    effective_delay = max(args.delay, float(crawl_delay)) if crawl_delay else args.delay
    print(f"      -> Délai appliqué entre requêtes : {effective_delay:.1f} s")

    discovered_batches: list[tuple[str, list[str]]] = []

    print("[1/3] Collecte combinée : Catégorie TI (_i10lfr, Mamadou) + Mots-clés (Elvira)...")
    for page in range(1, args.category_pages + 1):
        try:
            links = fetch_category_ti_links(page=page, rp=rp)
            discovered_batches.append((f"categorie_ti:_i10lfr_p{page}", links))
        except requests.RequestException as exc:
            print(f"      [!] Erreur sur la catégorie TI (p.{page}) : {exc}")
            break
        time.sleep(effective_delay)

    for kw in args.keywords:
        for page in range(1, args.keyword_pages + 1):
            try:
                links = fetch_keyword_links(kw, page=page, rp=rp)
                discovered_batches.append((f"mot_cle:{kw}", links))
            except requests.RequestException as exc:
                print(f"      [!] Erreur sur le mot-clé '{kw}' (p.{page}) : {exc}")
                break
            time.sleep(effective_delay)

    merged_candidates = merge_discovered_urls(discovered_batches, max_per_channel=args.max_per_channel)
    print(f"      -> {len(merged_candidates)} offres TI uniques après fusion et déduplication.")

    results: list[dict[str, Any]] = []
    total = len(merged_candidates)
    for idx, (url, origins) in enumerate(merged_candidates, start=1):
        if not is_url_allowed(rp, url):
            print(f"      [!] Fiche ignorée (robots.txt) : {url}")
            continue
        print(f"[2/3] ({idx}/{total}) Extraction fiche : {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            job_data = parse_job_posting_json_from_html(resp.text)
            if job_data:
                normalized = normalize_job_posting(job_data, url, origines_decouverte=origins)
                if not is_it_job(normalized["titre"], url):
                    print(f"      [-] Ignorée (hors TI) : {normalized['titre']}")
                    continue
                results.append(normalized)
                print(
                    f"      ✓ {normalized['titre']} — {normalized['entreprise']} "
                    f"({normalized['ville']}, {normalized['modalite']}) | "
                    f"Origines: {', '.join(origins)}"
                )
        except requests.RequestException as exc:
            print(f"      [!] Erreur HTTP sur {url} : {exc}")
        if idx < total and effective_delay > 0:
            time.sleep(effective_delay)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[3/3] Terminé ! {len(results)} offres TI sauvegardées dans {args.output}.")


if __name__ == "__main__":
    main()
