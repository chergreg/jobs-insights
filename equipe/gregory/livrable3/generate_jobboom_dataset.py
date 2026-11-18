"""
generate_jobboom_dataset.py - Génération du jeu d'essai data/offres_jobboom.json.

Intègre et consolide :
1. Les 5 offres réelles de la contribution d'Elvira (avec extraction complète de raw_json_ld).
2. Les 3 offres réelles de la contribution de Mamadou.
3. La collecte en direct / en cache de la catégorie TI de Jobboom Québec (pages 1 et 2).
4. Le respect du modèle pivot Pydantic v2 JobOffer.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from scrapers.jobboom import (
    JobboomScraper,
    clean_jobboom_url,
    clean_text,
    extract_jobboom_id,
    extract_tech_skills,
    parse_date_iso,
    parse_jobboom_detail_html,
    parse_jobboom_employment_type,
    parse_jobboom_location,
    parse_jobboom_salary,
)


def load_elvira_offers(elvira_file: Path) -> list[JobOffer]:
    """Convertit les offres collectées par Elvira dans le modèle unifié JobOffer."""
    offers: list[JobOffer] = []
    if not elvira_file.is_file():
        return offers

    data = json.loads(elvira_file.read_text(encoding="utf-8"))
    for item in data:
        raw_ld = item.get("raw_json_ld")
        url = item.get("url") or (raw_ld.get("url_offre") if raw_ld else "")
        if not url:
            continue

        clean_url = clean_jobboom_url(url)
        job_id = extract_jobboom_id(clean_url)

        if raw_ld:
            # Reconstitution via notre fonction de parsing pour garantir la rigueur
            html_synth = f"""
            <html><head><script type="application/ld+json">
            {json.dumps(raw_ld, ensure_ascii=False)}
            </script></head><body><h1>{raw_ld.get('title', '')}</h1></body></html>
            """
            offer = parse_jobboom_detail_html(html_synth, clean_url)
            if offer:
                offers.append(offer)
        else:
            titre = item.get("titre", "Titre non spécifié")
            offers.append(JobOffer(
                id=job_id,
                titre=titre,
                entreprise=item.get("entreprise", "Non spécifié"),
                lieu="Montréal, QC",
                province="QC",
                pays="Canada",
                url=clean_url,
                source="jobboom",
                date_publication=parse_date_iso(item.get("date_publication")),
                type_poste="Temps plein",
                description=None,
                competences_cles=extract_tech_skills(titre),
            ))

    return offers


def load_mamadou_offers(mamadou_file: Path) -> list[JobOffer]:
    """Convertit les offres Jobboom collectées par Mamadou dans le modèle unifié JobOffer."""
    offers: list[JobOffer] = []
    if not mamadou_file.is_file():
        return offers

    data = json.loads(mamadou_file.read_text(encoding="utf-8"))
    for item in data:
        if "Jobboom" not in item.get("source", ""):
            continue
        url = item.get("url", "")
        if not url:
            continue

        clean_url = clean_jobboom_url(url)
        job_id = extract_jobboom_id(clean_url)
        titre = item.get("title", "Titre non spécifié")
        desc = item.get("description_preview") or ""
        city = item.get("city") or "Québec"
        region = item.get("region") or "QC"

        offers.append(JobOffer(
            id=job_id,
            titre=titre,
            entreprise=item.get("company", "Non spécifié"),
            lieu=f"{city}, {region}",
            province=region,
            pays="Canada",
            url=clean_url,
            source="jobboom",
            date_publication=parse_date_iso(item.get("date_posted")),
            type_poste="Temps plein",
            description=clean_text(desc) if desc else None,
            competences_cles=extract_tech_skills(f"{titre} {desc}"),
        ))

    return offers


def main() -> None:
    data_dir = CUR_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_file = data_dir / "offres_jobboom.json"

    offers_by_id: dict[str, JobOffer] = {}

    # 1. Chargement des contributions d'Elvira
    elvira_path = CUR_DIR.parent.parent / "elvira" / "02-preuve-de-concept-scraping" / "offres_jobboom.json"
    elvira_offers = load_elvira_offers(elvira_path)
    for off in elvira_offers:
        offers_by_id[off.id] = off
    print(f" • {len(elvira_offers)} offre(s) intégrée(s) depuis les travaux d'Elvira.")

    # 2. Chargement des contributions de Mamadou (v1 et v2 si disponible)
    mamadou_path = CUR_DIR.parent.parent / "mamadou" / "02-preuve-de-concept-scraping" / "sample_scraped_jobs.json"
    mamadou_offers = load_mamadou_offers(mamadou_path)
    mamadou_v2_path = CUR_DIR.parent.parent / "mamadou" / "03-amelioration-preuve-de-concept" / "echantillon_v2.json"
    if mamadou_v2_path.is_file():
        mamadou_offers.extend(load_mamadou_offers(mamadou_v2_path))
    for off in mamadou_offers:
        if off.id not in offers_by_id:
            offers_by_id[off.id] = off
    print(f" • {len(offers_by_id)} offre(s) intégrée(s) après contributions étudiantes (Elvira + Mamadou).")

    # 3. Collecte via le connecteur Jobboom fiabilisé (toutes les pages en cache ou direct, sans limite)
    print(" • Exécution du connecteur JobboomScraper sur la catégorie TI...")
    scraper = JobboomScraper(delai_secondes=2.0)
    try:
        live_offers = scraper.search(keyword="", max_pages=0, limit=0, use_cache=True)
        print(f"   -> {len(live_offers)} offre(s) récupérée(s) via JobboomScraper.")
        for off in live_offers:
            offers_by_id[off.id] = off
    except Exception as e:
        print(f"   ! Attention : collecte réseau interrompue ({e}), maintien des offres déjà chargées.")

    final_offers = list(offers_by_id.values())
    # Tri par date de publication décroissante puis par ID
    final_offers.sort(key=lambda o: (o.date_publication or "", o.id), reverse=True)

    # Export JSON
    payload = [o.model_dump() for o in final_offers]
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] {len(final_offers)} offres Jobboom consolidées et exportées dans {output_file}")


if __name__ == "__main__":
    main()
