"""
Scraper.py — Collecteur et normalisateur d'offres TI sur Jobboom Québec.
Auteure : Elvira (Projet jobs-insights)

Fonctionnalités :
1. Recherche multi-mots-clés TI sur Jobboom (tri par pertinence + secteur Technologies `_i10lfr`).
2. Filtrage strict de pertinence TI sur le titre du poste (`is_it_job`) pour exclure les offres hors-sujet
   (ex. postes de vente, comptabilité ou construction qui mentionnent seulement "outils informatiques").
3. Déduplication automatique des URLs d'offres.
4. Extraction du bloc structuré Schema.org (`application/ld+json` -> `@type == "JobPosting"`).
5. Nettoyage du HTML de la description et normalisation des champs (ville, province, code postal, GPS, contrat).
6. Détection précise de la modalité (Télétravail / Hybride / Sur place), des stages et des compétences TI
   (sans faux positifs sur les mots français comme "soins de la vue").
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.jobboom.com"
DEFAULT_KEYWORDS = [
    "informatique",
    "developpeur web",
    "programmeur",
    "stage informatique",
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
    r"support\s+technique|soutien\s+technique|helpdesk|help\s+desk|technicien(?:ne)?\s+informatique|"
    r"end\s+user\s+computing|euc\b|"
    r"analyste\s+fonctionnel|analyste\s+ti|analyste[\s-]programmeur|architecte\s+ti|architecte\s+logiciel|"
    r"qa\b|assurance\s+qualite\s+logiciel|testeur(?:euse)?\s+logiciel|"
    r"scrum\s+master|product\s+owner|integrateur(?:trice)?\s+web"
    r")\b",
    flags=re.IGNORECASE,
)

# Mots-clés dans le titre qui indiquent clairement un poste HORS informatique (même s'il contient "programmeur CVC" ou "technicien")
IT_TITLE_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"cvc|cvac|hvac|batiment(?:s)?|construction|mecanicien|electromecanicien|usinage|cnc|"
    r"comptable|comptabilite|accounting|accounts\s+receivable|accounts\s+payable|controleur|"
    r"succursale|sqdc|vendeur|vente(?:s)?|sales\s+representative|service\s+a\s+la\s+clientele|"
    r"deductions|claims|reclamations|soumissions|inspecteur|travaux|loans|journalier|desassemblage"
    r")\b",
    flags=re.IGNORECASE,
)

MIN_PUBLICATION_YEAR = 2026
REFERENCE_TODAY_ISO = "2026-11-18"

# Catalogue de compétences techniques TI (patterns stricts pour éviter les faux positifs en français/anglais)
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


def strip_accents(text: str) -> str:
    """Supprime les accents d'une chaîne pour faciliter les comparaisons regex."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_it_job(title: str, url: str = "") -> bool:
    """
    Vérifie que l'offre est réellement un poste en Informatique / TI
    d'après son titre (et son slug d'URL), en excluant les postes hors-sujet
    (ex: CVC/bâtiment, comptabilité, ventes, succursales).
    """
    normalized_title = strip_accents(title or "").lower()
    normalized_url = strip_accents(url or "").lower()
    target = f"{normalized_title} {normalized_url}"

    if IT_TITLE_EXCLUSION_PATTERNS.search(target):
        return False

    return bool(IT_TITLE_POSITIVE_PATTERNS.search(target))


def is_recent_and_valid_offer(
    date_publication: str | None,
    date_expiration: str | None = None,
    min_year: int = MIN_PUBLICATION_YEAR,
    today_iso: str = REFERENCE_TODAY_ISO,
) -> bool:
    """
    Vérifie que l'offre est récente (publiée en `min_year` ou après, aucune offre des années passées)
    et qu'elle est toujours valide (`date_expiration` absente ou >= `today_iso`).
    """
    if not date_publication or len(str(date_publication)) < 4:
        return False
    try:
        pub_year = int(str(date_publication)[:4])
    except ValueError:
        return False
    if pub_year < min_year:
        return False
    if date_expiration:
        exp_str = str(date_expiration)[:10]
        if len(exp_str) == 10 and exp_str < today_iso:
            return False
    return True


def clean_html_text(raw_html: str | None) -> str:
    """Nettoie une chaîne HTML pour obtenir un texte brut lisible."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_job_id(url: str) -> str:
    """Extrait l'identifiant numérique Jobboom depuis l'URL (ex: jb-3661921)."""
    match = re.search(r"_p(\d+)(?:$|[/?#])", url)
    if match:
        return f"jb-{match.group(1)}"
    return f"jb-{abs(hash(url)) % 10_000_000}"


def detect_work_mode(title: str, description_text: str) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    combined = f"{title} {description_text}".lower()
    if any(term in combined for term in ("hybride", "hybrid", "mode hybride")):
        return "Hybride"
    if any(
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
    if re.search(r"\b(?:offre de stage|stage rémunéré|stagiaire en)\b", description_text, re.IGNORECASE):
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


def normalize_job_posting(job_data: dict[str, Any], url: str) -> dict[str, Any]:
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

    work_mode = detect_work_mode(title, description_text)
    is_stage = detect_is_internship(title, description_text, employment_types)
    skills = extract_skills(title, description_text)

    return {
        "id": extract_job_id(url),
        "source": "Jobboom",
        "titre": title,
        "entreprise": company,
        "logo_entreprise": logo,
        "ville": city,
        "province": province,
        "pays": country,
        "code_postal": postal_code,
        "coordonnees_gps": coordinates,
        "type_contrat": employment_types,
        "modalite": work_mode,
        "est_stage": is_stage,
        "competences_cles": skills,
        "date_publication": job_data.get("datePosted"),
        "date_expiration": job_data.get("validThrough"),
        "url": url,
        "description_texte": description_text,
    }


def get_job_links(keyword: str = "informatique", page: int = 1) -> list[str]:
    """
    Récupère les URLs des offres TI pertinentes depuis la page de résultats Jobboom.
    IMPORTANT : On n'utilise PAS `sortBy=date` sur la recherche par mot-clé car Jobboom
    remonterait alors n'importe quelle offre récente contenant les mots "outils informatiques"
    dans sa description (ex: vendeur, comptable). Le tri par défaut de Jobboom est par pertinence.
    De plus, on pré-filtre les liens d'offres avec `is_it_job` sur le texte/URL du lien.
    """
    slug = keyword.strip().replace(" ", "-")
    search_url = f"{BASE_URL}/fr/emploi/{slug}/_lfrk"
    params: dict[str, str | int] = {"dk": keyword}
    if page > 1:
        params["page"] = page

    response = requests.get(search_url, params=params, headers=HEADERS, timeout=15)
    print(f"      -> [{keyword} | p.{page}] Code HTTP : {response.status_code} | Taille HTML : {len(response.text)}")
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    seen_it: set[str] = set()
    all_raw_urls: set[str] = set()

    # 1. Attributs href sur les balises <a>
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/offre-emploi/" in href:
            full_url = urljoin(BASE_URL, href.split("?")[0])
            all_raw_urls.add(full_url)
            link_text = clean_html_text(a_tag.get_text())
            if full_url not in seen_it and is_it_job(link_text, full_url):
                seen_it.add(full_url)
                links.append(full_url)

    # 2. Attributs data-url utilisés sur les cartes d'offres Jobboom
    for tag in soup.find_all(attrs={"data-url": True}):
        data_url = str(tag["data-url"])
        if "/offre-emploi/" in data_url:
            full_url = urljoin(BASE_URL, data_url.split("?")[0])
            all_raw_urls.add(full_url)
            if full_url not in seen_it and is_it_job("", full_url):
                seen_it.add(full_url)
                links.append(full_url)

    print(
        f"         ({len(links)} offres TI pertinentes retenues sur {len(all_raw_urls)} annonces brutes de la page {page})"
    )
    return links


def extract_job_posting_json(job_url: str) -> dict[str, Any] | None:
    """Extrait l'objet JSON-LD (@type == 'JobPosting') d'une page d'offre."""
    response = requests.get(job_url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
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


def normalize_existing_file(file_path: Path) -> list[dict[str, Any]]:
    """Re-normalise et filtre les offres TI d'un fichier JSON existant (sans conserver `raw_json_ld`)."""
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    existing_items = json.loads(file_path.read_text(encoding="utf-8"))
    normalized_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in existing_items:
        raw_ld = item.get("raw_json_ld")
        url = item.get("url") or (raw_ld.get("url_offre") if isinstance(raw_ld, dict) else None)
        if not url or url in seen_urls:
            continue
        if isinstance(raw_ld, dict):
            title = clean_html_text(raw_ld.get("title") or item.get("titre"))
            if not is_it_job(title, url):
                continue
            normalized = normalize_job_posting(raw_ld, url)
        else:
            title = clean_html_text(item.get("titre"))
            if not is_it_job(title, url):
                continue
            cleaned_item = dict(item)
            cleaned_item.pop("raw_json_ld", None)
            normalized = cleaned_item
        if not is_recent_and_valid_offer(
            normalized.get("date_publication"),
            normalized.get("date_expiration"),
        ):
            continue
        seen_urls.add(url)
        normalized_results.append(normalized)

    file_path.write_text(json.dumps(normalized_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized_results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collecteur et normalisateur d'offres TI sur Jobboom.")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="Mots-clés TI à rechercher sur Jobboom.",
    )
    parser.add_argument(
        "--max-per-keyword",
        type=int,
        default=5,
        help="Nombre maximal d'offres à extraire par mot-clé (défaut: 5).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Nombre maximal de pages à parcourir par mot-clé (défaut: 3).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Délai en secondes entre deux requêtes de fiches d'emploi (défaut: 1.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "offres_jobboom.json",
        help="Chemin du fichier JSON de sortie.",
    )
    parser.add_argument(
        "--normalize-existing",
        action="store_true",
        help="Re-normalise et filtre uniquement le fichier offres_jobboom.json existant sans requêtes HTTP.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.normalize_existing:
        print(f"[*] Normalisation et filtrage TI du fichier existant : {args.output}")
        normalized = normalize_existing_file(args.output)
        print(f"[OK] {len(normalized)} offres TI normalisées et sauvegardées dans {args.output.name}.")
        return

    print("[1/3] Recherche des offres TI sur Jobboom (tri par pertinence + filtre métier TI)...")
    candidate_urls: list[str] = []
    seen_urls: set[str] = set()

    for keyword in args.keywords:
        collected_for_kw = 0
        for page in range(1, args.pages + 1):
            try:
                links = get_job_links(keyword, page=page)
            except requests.RequestException as exc:
                print(f"      [!] Erreur lors de la recherche '{keyword}' (p.{page}) : {exc}")
                break

            for link in links:
                if link not in seen_urls:
                    seen_urls.add(link)
                    candidate_urls.append(link)
                    collected_for_kw += 1
                    if collected_for_kw >= args.max_per_keyword:
                        break
            if collected_for_kw >= args.max_per_keyword:
                break

    print(f"      -> {len(candidate_urls)} offres TI uniques retenues après filtrage et déduplication.")

    results: list[dict[str, Any]] = []
    total = len(candidate_urls)
    for idx, url in enumerate(candidate_urls, start=1):
        print(f"[2/3] ({idx}/{total}) Extraction & normalisation : {url}")
        try:
            job_data = extract_job_posting_json(url)
            if job_data:
                normalized = normalize_job_posting(job_data, url)
                if not is_it_job(normalized["titre"], url):
                    print(f"      [-] Ignorée (hors TI) : {normalized['titre']}")
                    continue
                if not is_recent_and_valid_offer(
                    normalized.get("date_publication"),
                    normalized.get("date_expiration"),
                ):
                    print(
                        f"      [-] Ignorée (ancienne ou expirée : {normalized.get('date_publication')}) : {normalized['titre']}"
                    )
                    continue
                results.append(normalized)
                print(
                    f"      ✓ {normalized['titre']} — {normalized['entreprise']} "
                    f"({normalized['ville']}, {normalized['modalite']}) | "
                    f"Compétences: {', '.join(normalized['competences_cles']) or 'Aucune détectée'}"
                )
        except requests.RequestException as exc:
            print(f"      [!] Erreur HTTP sur {url} : {exc}")
        if idx < total and args.delay > 0:
            time.sleep(args.delay)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[3/3] Terminé ! {len(results)} offres TI sauvegardées dans {args.output}.")


if __name__ == "__main__":
    main()
