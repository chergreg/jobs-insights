"""
POC Atelier 1 — Projet `jobs-insights`
Auteur : El Hadji Konaté

Script de preuve de concept (POC) pour scraper les sites d'offres d'emploi et de stages identifiés dans sites.md :
1. Talent.com Canada (Extraction JSON-LD ItemList -> JobPosting + coordonnées GPS)
2. Jobboom Québec (Catégorie Technologies _i10lfr + JSON-LD JobPosting)
3. Guichet-Emplois Canada (Recherche Ville de Québec mid=22447 + balises RDFa Schema.org)
4. Jobillico Québec (Recherche par mot-clé/ville + JSON-LD JobPosting)
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
}


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw))
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def fetch_html(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


# ==============================================================================
# POC 1 : Talent.com Canada (ca.talent.com/fr) — Double JSON-LD + GPS
# ==============================================================================
def poc_scrape_talent_canada(keyword: str = "stage informatique", location: str = "Québec, QC", max_items: int = 3) -> List[Dict[str, Any]]:
    q_enc = urllib.parse.quote_plus(keyword)
    l_enc = urllib.parse.quote_plus(location)
    search_url = f"https://ca.talent.com/fr/jobs?k={q_enc}&l={l_enc}"
    print(f"\n[POC 1 - Talent.com Canada] Recherche : {search_url}")

    body = fetch_html(search_url)
    ld_blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body, re.S)

    job_urls: List[str] = []
    for block in ld_blocks:
        try:
            data = json.loads(block.strip())
            for node in data.get("@graph", []):
                if node.get("@type") == "ItemList":
                    for el in node.get("itemListElement", []):
                        u = el.get("item", {}).get("url")
                        if u and u not in job_urls:
                            job_urls.append(u)
        except Exception:
            continue

    print(f"  -> {len(job_urls)} URLs d'offres détectées dans l'ItemList JSON-LD.")
    results: List[Dict[str, Any]] = []

    for job_url in job_urls[:max_items]:
        try:
            job_html = fetch_html(job_url)
            job_lds = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', job_html, re.S)
            for j_block in job_lds:
                j_data = json.loads(j_block.strip())
                for node in j_data.get("@graph", []):
                    if node.get("@type") == "JobPosting":
                        org = node.get("hiringOrganization") or {}
                        loc = node.get("jobLocation") or {}
                        addr = loc.get("address") or {}
                        geo = loc.get("geo") or {}
                        item = {
                            "source": "Talent.com Canada",
                            "title": clean_html(node.get("title", "")),
                            "company": clean_html(org.get("name", "Non spécifié")),
                            "city": addr.get("addressLocality", location),
                            "region": addr.get("addressRegion", "QC"),
                            "gps": {
                                "lat": geo.get("latitude"),
                                "lon": geo.get("longitude"),
                            },
                            "date_posted": node.get("datePosted"),
                            "employment_type": node.get("employmentType"),
                            "url": job_url,
                            "description_preview": clean_html(node.get("description", ""))[:220] + "...",
                        }
                        results.append(item)
                        print(f"  ✓ [{item['source']}] {item['title']} — {item['company']} ({item['city']})")
                        break
        except Exception as e:
            print(f"  ! Erreur sur {job_url}: {e}")

    return results


# ==============================================================================
# POC 2 : Jobboom Québec (Secteur Technologies _i10lfr) — HTML + JSON-LD
# ==============================================================================
def poc_scrape_jobboom_ti(max_items: int = 3) -> List[Dict[str, Any]]:
    category_url = "https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1"
    print(f"\n[POC 2 - Jobboom Québec TI] Navigation : {category_url}")

    body = fetch_html(category_url)
    raw_paths = list(dict.fromkeys(re.findall(r'data-url=["\'](/fr/offre-emploi/[^"\']+)["\']', body)))
    print(f"  -> {len(raw_paths)} offres TI trouvées sur la page 1.")

    results: List[Dict[str, Any]] = []
    for path in raw_paths[:max_items]:
        full_url = f"https://www.jobboom.com{path}"
        try:
            job_html = fetch_html(full_url)
            ld_blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', job_html, re.S)
            for block in ld_blocks:
                if "JobPosting" not in block:
                    continue
                data = json.loads(block.strip())
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    org = data.get("hiringOrganization") or {}
                    loc = data.get("jobLocation") or {}
                    if isinstance(loc, list) and loc:
                        loc = loc[0]
                    addr = loc.get("address") or {} if isinstance(loc, dict) else {}
                    item = {
                        "source": "Jobboom Québec (Secteur TI _i10lfr)",
                        "title": clean_html(data.get("title", "")),
                        "company": clean_html(org.get("name", "Employeur Jobboom")) if isinstance(org, dict) else "Employeur Jobboom",
                        "city": addr.get("addressLocality", "Québec"),
                        "region": addr.get("addressRegion", "QC"),
                        "date_posted": data.get("datePosted"),
                        "valid_through": data.get("validThrough"),
                        "url": full_url,
                        "description_preview": clean_html(data.get("description", ""))[:220] + "...",
                    }
                    results.append(item)
                    print(f"  ✓ [{item['source']}] {item['title']} — {item['company']} ({item['city']})")
                    break
        except Exception as e:
            print(f"  ! Erreur sur {full_url}: {e}")

    return results


# ==============================================================================
# POC 3 : Guichet-Emplois Canada (guichetemplois.gc.ca) — RDFa Schema.org
# ==============================================================================
def poc_scrape_guichet_emplois(keyword: str = "développeur", mid: str = "22447", max_items: int = 2) -> List[Dict[str, Any]]:
    q_enc = urllib.parse.quote(keyword)
    search_url = f"https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?searchstring={q_enc}&mid={mid}&sort=M"
    print(f"\n[POC 3 - Guichet-Emplois Canada] Recherche : {search_url}")

    body = fetch_html(search_url)
    ids = list(dict.fromkeys(re.findall(r"/offredemploi/(\d+)", body)))
    print(f"  -> {len(ids)} offres détectées sur Guichet-Emplois.")

    results: List[Dict[str, Any]] = []
    for job_id in ids[:max_items]:
        posting_url = f"https://www.guichetemplois.gc.ca/jobsearch/pers/offredemploi/{job_id}"
        try:
            job_html = fetch_html(posting_url)
            title_m = re.search(r'property=["\']title["\'][^>]*>(.*?)</', job_html, re.S)
            org_m = re.search(r'property=["\']hiringOrganization["\'].*?property=["\']name["\'][^>]*>(.*?)</', job_html, re.S)
            city_m = re.search(r'property=["\']addressLocality["\'][^>]*>(.*?)</', job_html, re.S)
            desc_m = re.search(r'property=["\']description["\'][^>]*>(.*?)</div>', job_html, re.S)

            item = {
                "source": "Guichet-Emplois Canada",
                "title": clean_html(title_m.group(1)) if title_m else keyword,
                "company": clean_html(org_m.group(1)) if org_m else "Employeur vérifié",
                "city": clean_html(city_m.group(1)) if city_m else "Québec",
                "url": posting_url,
                "description_preview": (clean_html(desc_m.group(1))[:220] + "...") if desc_m else "",
            }
            results.append(item)
            print(f"  ✓ [{item['source']}] {item['title']} — {item['company']} ({item['city']})")
        except Exception as e:
            print(f"  ! Erreur sur {posting_url}: {e}")

    return results


# ==============================================================================
# POC 4 : Jobillico Québec (jobillico.com) — JSON-LD JobPosting
# ==============================================================================
def poc_scrape_jobillico(keyword: str = "développeur", city: str = "Québec, QC", max_items: int = 2) -> List[Dict[str, Any]]:
    q_enc = urllib.parse.quote(keyword)
    c_enc = urllib.parse.quote(city)
    search_url = f"https://www.jobillico.com/recherche-emploi?skwd={q_enc}&scty={c_enc}"
    print(f"\n[POC 4 - Jobillico Québec] Recherche : {search_url}")

    body = fetch_html(search_url)
    paths = list(dict.fromkeys(re.findall(r'href=["\'](/fr/offre-d-emploi/[^"\'?#]+)', body)))
    print(f"  -> {len(paths)} offres détectées sur Jobillico.")

    results: List[Dict[str, Any]] = []
    for path in paths[:max_items]:
        full_url = f"https://www.jobillico.com{path}"
        try:
            job_html = fetch_html(full_url)
            ld_blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', job_html, re.S)
            for block in ld_blocks:
                if "JobPosting" not in block:
                    continue
                data = json.loads(block.strip())
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    org = data.get("hiringOrganization") or {}
                    loc = data.get("jobLocation") or {}
                    if isinstance(loc, list) and loc:
                        loc = loc[0]
                    addr = loc.get("address") or {} if isinstance(loc, dict) else {}
                    item = {
                        "source": "Jobillico Québec",
                        "title": clean_html(data.get("title", "")),
                        "company": clean_html(org.get("name", "Employeur Jobillico")) if isinstance(org, dict) else "Employeur Jobillico",
                        "city": addr.get("addressLocality", "Québec"),
                        "url": full_url,
                        "description_preview": clean_html(data.get("description", ""))[:220] + "...",
                    }
                    results.append(item)
                    print(f"  ✓ [{item['source']}] {item['title']} — {item['company']} ({item['city']})")
                    break
        except Exception as e:
            print(f"  ! Erreur sur {full_url}: {e}")

    return results


if __name__ == "__main__":
    print("=" * 75)
    print(" DÉMONSTRATION POC ATELIER 1 — PROJET JOBS-INSIGHTS")
    print("=" * 75)

    all_scraped: List[Dict[str, Any]] = []
    all_scraped.extend(poc_scrape_talent_canada(keyword="stage informatique", location="Québec, QC", max_items=3))
    all_scraped.extend(poc_scrape_jobboom_ti(max_items=3))
    all_scraped.extend(poc_scrape_guichet_emplois(keyword="développeur", mid="22447", max_items=2))
    all_scraped.extend(poc_scrape_jobillico(keyword="développeur", city="Québec, QC", max_items=2))

    out_path = Path(__file__).parent / "sample_scraped_jobs.json"
    out_path.write_text(json.dumps(all_scraped, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 75)
    print(f" TOTAL : {len(all_scraped)} offres réelles extraites et sauvegardées dans {out_path.name}")
    print("=" * 75)
