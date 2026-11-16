"""
Deuxième test de l'API Adzuna — Canada / Québec / IT

Objectifs :
1. Comparer la recherche à Montréal et à Québec (ville).
2. Tester plusieurs mots-clés informatiques en français et en anglais.
3. Inspecter les champs réellement présents dans les annonces.
4. Examiner les descriptions, salaires, contrats, catégories et localisations.
5. Mesurer les doublons entre les recherches.
6. Tester la pagination de façon contrôlée.

Identifiants requis dans les variables d'environnement :
    ADZUNA_APP_ID
    ADZUNA_APP_KEY

Installation :
    pip install requests

Lancement :
    python adzuna_test_2.py

Le script affiche un résumé et sauvegarde les réponses JSON brutes dans
un dossier adzuna_test_output. Ne partage jamais les identifiants API.
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests


BASE_URL = "https://api.adzuna.com/v1/api/jobs/ca"
TIMEOUT = 20

# Paramètres faciles à ajuster
CATEGORY = "it-jobs"
RESULTS_PER_PAGE = 20

# Pour limiter les appels API, le script récupère au maximum deux pages
# pour chaque recherche. Mets MAX_PAGES = 1 pour un test plus léger.
MAX_PAGES = 2

LOCATIONS = [
    "Québec, Québec",
    "Montréal, Québec",
]

KEYWORDS = [
    "développeur logiciel",
    "développeur web",
    "programmeur",
    "technicien informatique",
    "administrateur système",
    "DevOps",
]

OUTPUT_DIR = Path("adzuna_test_output")


def get_credentials():
    """Lit les identifiants sans les inscrire dans le code."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        sys.exit(
            "Identifiants manquants. Définis ADZUNA_APP_ID et "
            "ADZUNA_APP_KEY dans les variables d'environnement."
        )

    return {"app_id": app_id, "app_key": app_key}


def api_get(endpoint, credentials, **params):
    """Effectue un appel GET et affiche les erreurs API de façon lisible."""
    query = {
        **credentials,
        "content-type": "application/json",
        **params,
    }

    try:
        response = requests.get(
            f"{BASE_URL}/{endpoint}",
            params=query,
            timeout=TIMEOUT,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Erreur réseau : {exc}") from exc

    if response.status_code == 429:
        raise RuntimeError(
            "Quota ou limite de requêtes atteint (HTTP 429). "
            "Arrête le test et vérifie les limites de ton compte Adzuna."
        )

    if response.status_code in (401, 403):
        raise RuntimeError(
            f"Accès refusé (HTTP {response.status_code}). "
            "Vérifie ADZUNA_APP_ID et ADZUNA_APP_KEY."
        )

    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("La réponse reçue n'est pas un JSON valide.") from exc


def save_json(filename, data):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def safe_text(value):
    if value is None:
        return "n/d"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def inspect_job(job):
    """Affiche les champs utiles d'une annonce sans supposer qu'ils existent."""
    company = job.get("company") or {}
    location = job.get("location") or {}
    category = job.get("category") or {}

    print(f"    ID             : {safe_text(job.get('id'))}")
    print(f"    Titre          : {safe_text(job.get('title'))}")
    print(f"    Employeur      : {safe_text(company.get('display_name'))}")
    print(f"    Lieu           : {safe_text(location.get('display_name'))}")
    print(f"    Détail lieu    : {safe_text(location.get('area'))}")
    print(f"    Publiée        : {safe_text(job.get('created'))}")
    print(f"    Salaire min    : {safe_text(job.get('salary_min'))}")
    print(f"    Salaire max    : {safe_text(job.get('salary_max'))}")
    print(f"    Salaire prédit : {safe_text(job.get('salary_is_predicted'))}")
    print(f"    Contrat        : {safe_text(job.get('contract_type'))}")
    print(f"    Temps          : {safe_text(job.get('contract_time'))}")
    print(f"    Catégorie      : {safe_text(category.get('label'))}")
    print(f"    Tag catégorie  : {safe_text(category.get('tag'))}")
    print(f"    Latitude       : {safe_text(job.get('latitude'))}")
    print(f"    Longitude      : {safe_text(job.get('longitude'))}")
    print(f"    Description    : {safe_text(job.get('description'))[:700]}")
    print(f"    redirect_url   : {safe_text(job.get('redirect_url'))}")


def run_search(credentials, keyword, location):
    """Récupère jusqu'à MAX_PAGES pages pour une combinaison mot-clé/lieu."""
    all_jobs = []
    page_summaries = []

    print("\n" + "=" * 88)
    print(f"RECHERCHE : {keyword!r} | LIEU : {location!r} | CATÉGORIE : {CATEGORY}")
    print("=" * 88)

    for page in range(1, MAX_PAGES + 1):
        data = api_get(
            f"search/{page}",
            credentials,
            what=keyword,
            where=location,
            category=CATEGORY,
            results_per_page=RESULTS_PER_PAGE,
            sort_by="date",
        )

        jobs = data.get("results") or []
        total_count = data.get("count")
        all_jobs.extend(jobs)

        page_summaries.append({
            "page": page,
            "returned": len(jobs),
            "total_count": total_count,
        })

        print(
            f"\nPage {page} — {len(jobs)} annonce(s) reçue(s) "
            f"| total annoncé par Adzuna : {total_count}"
        )

        if not jobs:
            print("Aucun résultat sur cette page : arrêt de la pagination.")
            break

        # Affiche les trois premières annonces de la première page.
        # Les autres restent disponibles dans le JSON brut sauvegardé.
        if page == 1:
            for index, job in enumerate(jobs[:3], start=1):
                print(f"\n  --- Annonce détaillée {index} ---")
                inspect_job(job)

        # Petite pause entre les pages pour éviter d'enchaîner inutilement.
        if page < MAX_PAGES:
            time.sleep(0.4)

    filename = (
        f"{slugify(location)}__{slugify(keyword)}.json"
    )
    saved_path = save_json(filename, {
        "search": {
            "keyword": keyword,
            "location": location,
            "category": CATEGORY,
            "results_per_page": RESULTS_PER_PAGE,
            "max_pages": MAX_PAGES,
        },
        "pages": page_summaries,
        "results": all_jobs,
    })

    print(f"\nJSON brut sauvegardé : {saved_path}")

    return {
        "keyword": keyword,
        "location": location,
        "total_count": page_summaries[0]["total_count"] if page_summaries else 0,
        "jobs": all_jobs,
        "pages": page_summaries,
    }


def slugify(value):
    """Produit un nom de fichier simple à partir d'un texte."""
    import re
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def summarize(results):
    """Compare les volumes et repère les annonces répétées."""
    print("\n\n" + "#" * 88)
    print("SYNTHÈSE DES RECHERCHES")
    print("#" * 88)

    ids_by_search = {}
    occurrences = defaultdict(list)
    all_jobs_by_id = {}

    for result in results:
        label = f"{result['keyword']} | {result['location']}"
        ids = set()

        print(f"\n{label}")
        print(f"  Total annoncé par Adzuna : {result['total_count']}")
        print(f"  Annonces récupérées      : {len(result['jobs'])}")
        print(f"  Pages examinées          : {len(result['pages'])}")

        for job in result["jobs"]:
            job_id = str(job.get("id", "")).strip()
            if not job_id:
                continue
            ids.add(job_id)
            occurrences[job_id].append(label)
            all_jobs_by_id[job_id] = job

        ids_by_search[label] = ids

    print("\n--- Doublons entre les recherches ---")
    duplicates = {
        job_id: labels
        for job_id, labels in occurrences.items()
        if len(labels) > 1
    }

    if not duplicates:
        print("Aucun doublon détecté dans les pages récupérées.")
    else:
        for job_id, labels in sorted(duplicates.items()):
            job = all_jobs_by_id[job_id]
            print(
                f"- ID {job_id} | {safe_text(job.get('title'))} "
                f"| présent dans {len(labels)} recherches"
            )
            for label in labels:
                print(f"    • {label}")

    print("\n--- Champs présents dans les annonces ---")
    field_counts = Counter()
    nested_counts = Counter()
    total_jobs = len(all_jobs_by_id)

    for job in all_jobs_by_id.values():
        for key, value in job.items():
            if value is not None and value != "":
                field_counts[key] += 1

        for parent in ("company", "location", "category"):
            nested = job.get(parent)
            if isinstance(nested, dict):
                for key, value in nested.items():
                    if value is not None and value != "":
                        nested_counts[f"{parent}.{key}"] += 1

    print(f"Nombre d'annonces uniques examinées : {total_jobs}")
    if total_jobs:
        print("\nChamps principaux (nombre d'annonces où le champ est renseigné) :")
        for field, count in field_counts.most_common():
            print(f"  {field:<25} {count}/{total_jobs}")

        print("\nChamps imbriqués :")
        for field, count in nested_counts.most_common():
            print(f"  {field:<25} {count}/{total_jobs}")

    summary = {
        "unique_jobs_examined": total_jobs,
        "duplicate_ids": duplicates,
        "field_presence": dict(field_counts),
        "nested_field_presence": dict(nested_counts),
    }
    save_json("summary.json", summary)
    print(f"\nSynthèse sauvegardée : {OUTPUT_DIR / 'summary.json'}")


def main():
    credentials = get_credentials()
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("TEST APPROFONDI DE L'API ADZUNA — CANADA / QUÉBEC")
    print(f"Catégorie : {CATEGORY}")
    print(f"Résultats par page : {RESULTS_PER_PAGE}")
    print(f"Nombre maximal de pages par recherche : {MAX_PAGES}")
    print(f"Nombre de combinaisons : {len(LOCATIONS) * len(KEYWORDS)}")
    print(
        "Nombre maximal d'appels de recherche prévu : "
        f"{len(LOCATIONS) * len(KEYWORDS) * MAX_PAGES}"
    )
    print(f"Dossier de sortie : {OUTPUT_DIR.resolve()}")

    results = []

    try:
        for location in LOCATIONS:
            for keyword in KEYWORDS:
                result = run_search(credentials, keyword, location)
                results.append(result)
                time.sleep(0.4)

        summarize(results)

    except (RuntimeError, requests.HTTPError) as exc:
        print(f"\nARRÊT DU TEST : {exc}", file=sys.stderr)
        print(
            "Les fichiers JSON des recherches déjà terminées sont conservés.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nTest terminé.")
    print("N'oublie pas : afficher « Jobs by Adzuna » et utiliser redirect_url.")


if __name__ == "__main__":
    main()
