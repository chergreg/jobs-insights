import json
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.jobboom.com"


def get_job_links(keyword: str = "informatique") -> list[str]:
    """Récupère les URLs des offres depuis la page de résultats Jobboom."""
    search_url = f"{BASE_URL}/fr/emploi/{keyword.replace(' ', '-')}/_lfrk"
    params = {"dk": keyword}

    response = requests.get(search_url, params=params, headers=HEADERS, timeout=15)
    print(f"      -> Code HTTP : {response.status_code} | Taille HTML : {len(response.text)}")
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/offre-emploi/" in href:
            full_url = urljoin(BASE_URL, href.split("?")[0])
            links.add(full_url)

    return list(links)


def extract_job_posting_json(job_url: str) -> dict | None:
    """Extrait l'objet JSON-LD (@type == 'JobPosting') d'une page d'offre."""
    response = requests.get(job_url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                data["url_offre"] = job_url
                return data
        except json.JSONDecodeError:
            continue

    return None


def main():
    keyword = "informatique"
    print(f"[1/3] Recherche des offres pour '{keyword}' sur Jobboom...")
    job_links = get_job_links(keyword)
    print(f"      -> {len(job_links)} offres trouvées sur la 1re page.")

    results = []
    for idx, url in enumerate(job_links[:5], start=1):
        print(f"[2/3] ({idx}/5) Extraction JSON de : {url}")
        job_data = extract_job_posting_json(url)
        if job_data:
            results.append({
                "titre": job_data.get("title"),
                "entreprise": job_data.get("hiringOrganization", {}).get("name"),
                "date_publication": job_data.get("datePosted"),
                "url": url,
                "raw_json_ld": job_data,
            })
        time.sleep(1)

    output_file = "offres_jobboom.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[3/3] Terminé ! {len(results)} offres sauvegardées dans {output_file}.")


if __name__ == "__main__":
    main()