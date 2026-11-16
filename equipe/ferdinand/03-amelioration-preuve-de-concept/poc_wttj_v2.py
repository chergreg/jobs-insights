"""Collecte d'offres Welcome to the Jungle - version 2 (Livrable 3).

Reprend le POC du livrable 2 (equipe/ferdinand/02-preuve-de-concept-scraping/poc_wttj.py)
et corrige les limites relevées dans la synthèse :
- ajout de la localisation (ville, pays) à partir de `office` / `offices` ;
- recherche ciblée sur le Québec (Montréal, Québec) + filtre local sur le Canada ;
- `raise_for_status()` avant `.json()` et User-Agent honnête ;
- plus d'appel à `os.startfile()` (Windows seulement) ;
- code découpé en fonctions testables hors ligne.

Lancer :
    python poc_wttj_v2.py
    python poc_wttj_v2.py --mot-cle "développeur"
    python poc_wttj_v2.py --partout          # sans filtre de lieu (comme la v1)
"""

import argparse
import csv
import json
import time
from pathlib import Path

import requests

URL_API = "https://api.welcometothejungle.com/api/v3/public/jobs"
HEADERS = {
    "User-Agent": "jobs-insights-atelier/1.0 (projet etudiant)",
    "Accept": "application/json",
}
PAUSE_SECONDES = 2
MAX_PAGES = 5

# Lieux envoyés à l'API, au format observé dans l'onglet Réseau du site.
LIEUX_QUEBEC = [
    {
        "country": "Canada",
        "country_code": "CA",
        "district": "Montréal",
        "label": "Montréal, Québec, Canada",
        "latitude": 45.50008,
        "longitude": -73.68248,
        "state": "Québec",
    },
    {
        "country": "Canada",
        "country_code": "CA",
        "district": "Québec",
        "label": "Québec, Québec, Canada",
        "latitude": 46.81228,
        "longitude": -71.21454,
        "state": "Québec",
    },
]

COLONNES = [
    "source", "id_source", "titre", "entreprise", "secteur", "contrat",
    "teletravail", "villes", "pays", "au_canada", "salaire_min", "salaire_max",
    "devise", "periode_salaire", "date_publication", "lien",
]

DOSSIER = Path(__file__).resolve().parent


# ---------- Collecte réseau ----------

def recuperer_page(mot_cle: str, page: int, lieux: list | None) -> dict:
    """Appelle l'API pour une page de résultats et renvoie le JSON."""
    params = {"job_title": mot_cle, "include_empty_salary": "true", "page": page}
    if lieux:
        params["locations"] = json.dumps(lieux, ensure_ascii=False)
    reponse = requests.get(URL_API, params=params, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    return reponse.json()


def collecter(mot_cle: str, lieux: list | None, max_pages: int = MAX_PAGES) -> list[dict]:
    """Parcourt les pages de résultats et renvoie les offres brutes."""
    offres_brutes = []
    page = 1
    while True:
        resultat = recuperer_page(mot_cle, page, lieux)
        meta = resultat.get("metadata", {})
        print(f"Page {page}/{meta.get('page_count', '?')} - {meta.get('total', '?')} offres au total")
        offres_brutes.extend(resultat.get("data", []))
        if page >= meta.get("page_count", 1) or page >= max_pages:
            break
        page += 1
        time.sleep(PAUSE_SECONDES)
    return offres_brutes


# ---------- Parsing / normalisation (testé hors ligne) ----------

def extraire_bureaux(offre: dict) -> list[dict]:
    """Renvoie la liste des bureaux de l'offre (`offices`, sinon `office`)."""
    bureaux = offre.get("offices") or []
    if not bureaux and offre.get("office"):
        bureaux = [offre["office"]]
    return [b for b in bureaux if isinstance(b, dict)]


def normaliser(offre: dict) -> dict:
    """Transforme une offre brute de l'API en ligne du format commun.

    Les champs absents restent vides : on ne devine jamais une information.
    """
    entreprise = offre.get("organization") or {}
    bureaux = extraire_bureaux(offre)
    villes = sorted({b.get("city") for b in bureaux if b.get("city")})
    pays = sorted({b.get("country_code") for b in bureaux if b.get("country_code")})

    lien = None
    if entreprise.get("slug") and offre.get("slug"):
        lien = (
            "https://www.welcometothejungle.com/fr/companies/"
            f"{entreprise['slug']}/jobs/{offre['slug']}"
        )

    return {
        "source": "welcome_to_the_jungle",
        "id_source": offre.get("reference"),
        "titre": offre.get("name"),
        "entreprise": entreprise.get("name"),
        "secteur": entreprise.get("industry"),
        "contrat": offre.get("contract_type"),
        "teletravail": offre.get("remote"),
        "villes": ", ".join(villes) or None,
        "pays": ", ".join(pays) or None,
        "au_canada": "CA" in pays,
        "salaire_min": offre.get("salary_min"),
        "salaire_max": offre.get("salary_max"),
        "devise": offre.get("salary_currency"),
        "periode_salaire": offre.get("salary_period"),
        "date_publication": offre.get("published_at"),
        "lien": lien,
    }


def dedupliquer(offres: list[dict]) -> list[dict]:
    """Retire les doublons (même identifiant ou même lien), en gardant l'ordre."""
    vues = set()
    uniques = []
    for offre in offres:
        cle = offre.get("id_source") or offre.get("lien")
        if cle in vues:
            continue
        vues.add(cle)
        uniques.append(offre)
    return uniques


# ---------- Export ----------

def exporter_csv(offres: list[dict], chemin: Path) -> None:
    """Écrit le CSV (séparateur `;` et utf-8-sig pour Excel en français)."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        writer.writeheader()
        writer.writerows(offres)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte d'offres Welcome to the Jungle")
    parser.add_argument("--mot-cle", default="stage", help='ex. "stage", "développeur", "data"')
    parser.add_argument("--partout", action="store_true", help="ne pas filtrer sur le Québec")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args()

    lieux = None if args.partout else LIEUX_QUEBEC
    brutes = collecter(args.mot_cle, lieux, args.max_pages)
    offres = dedupliquer([normaliser(o) for o in brutes])

    if not args.partout:
        # L'API peut renvoyer des offres proches mais hors Canada : on garde seulement le Canada.
        offres = [o for o in offres if o["au_canada"]]

    print(f"\n{len(brutes)} offres reçues, {len(offres)} gardées")
    for o in offres[:5]:
        print(f"- {o['titre']} | {o['entreprise']} | {o['villes']} | {o['contrat']}")

    if offres:
        chemin = DOSSIER / "offres_wttj_v2.csv"
        exporter_csv(offres, chemin)
        print("\nFichier créé :", chemin)
    else:
        print("Aucune offre : essaie un autre --mot-cle ou --partout.")


if __name__ == "__main__":
    main()
