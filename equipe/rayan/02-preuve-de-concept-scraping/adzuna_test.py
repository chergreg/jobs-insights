"""Test rapide de l'API Adzuna (Canada / Québec / IT).

Lecture des identifiants dans les variables d'environnement
ADZUNA_APP_ID et ADZUNA_APP_KEY (ne jamais les écrire dans le code).

Utilisation :
    pip install requests
    python adzuna_test.py
"""

import os
import sys

import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs/ca"
TIMEOUT = 15


def get_credentials():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        sys.exit("Définis ADZUNA_APP_ID et ADZUNA_APP_KEY dans ton environnement.")
    return {"app_id": app_id, "app_key": app_key}


def call(endpoint, creds, **params):
    """Appelle l'API et renvoie le JSON, ou quitte avec un message clair."""
    params = {**creds, "content-type": "application/json", **params}
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
    if response.status_code == 429:
        sys.exit("Quota atteint (429). Attends un peu avant de relancer.")
    if response.status_code in (401, 403):
        sys.exit(f"Identifiants refusés ({response.status_code}). Vérifie app_id et app_key.")
    response.raise_for_status()
    return response.json()


def show_categories(creds):
    """Affiche les catégories du Canada pour confirmer le tag IT."""
    data = call("categories", creds)
    print("== Catégories du Canada ==")
    for cat in data.get("results", []):
        print(f"  {cat['tag']:<30} {cat['label']}")
    print()


def search(creds, what, where, category="it-jobs", n=5):
    data = call(
        "search/1",
        creds,
        what=what,
        where=where,
        category=category,
        results_per_page=n,
        sort_by="date",
    )
    print(f"== '{what}' à '{where}' (catégorie {category}) : {data.get('count', 0)} offres au total ==")
    for job in data.get("results", []):
        company = (job.get("company") or {}).get("display_name", "n/d")
        location = (job.get("location") or {}).get("display_name", "n/d")
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        salary = f"{salary_min:.0f}-{salary_max:.0f}" if salary_min and salary_max else "n/d"
        print(f"- {job.get('title')}")
        print(f"    employeur : {company}")
        print(f"    lieu      : {location}")
        print(f"    publiée   : {job.get('created')}")
        print(f"    salaire   : {salary} (prédit : {job.get('salary_is_predicted', 'n/d')})")
        print(f"    lien      : {job.get('redirect_url')}")
    print()


def main():
    creds = get_credentials()
    show_categories(creds)
    search(creds, what="développeur", where="Montréal, Québec")
    search(creds, what="developer", where="Québec")
    search(creds, what="devops", where="Montréal, Québec")
    print("Rappel : afficher « Jobs by Adzuna » et utiliser redirect_url pour renvoyer vers l'offre.")


if __name__ == "__main__":
    main()
