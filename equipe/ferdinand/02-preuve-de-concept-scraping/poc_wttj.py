import csv
import json
import os
import time
import requests

URL = "https://api.welcometothejungle.com/api/v3/public/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

MOT_CLE = "stage data"
MAX_PAGES = 3

# Le fichier sera créé dans le même dossier que ce script
DOSSIER = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(DOSSIER, "offres_wttj.csv")

toutes_les_offres = []
page = 1

while True:
    params = {"job_title": MOT_CLE, "include_empty_salary": "true", "page": page}
    response = requests.get(URL, params=params, headers=HEADERS)
    print("Page", page, "- code", response.status_code)
    resultat = response.json()

    for offre in resultat["data"]:
        entreprise = offre.get("organization", {})
        toutes_les_offres.append({
            "titre": offre.get("name"),
            "entreprise": entreprise.get("name"),
            "secteur": entreprise.get("industry"),
            "contrat": offre.get("contract_type"),
            "teletravail": offre.get("remote"),
            "mis_a_jour": offre.get("updated_at"),
            "lien": "https://www.welcometothejungle.com/fr/companies/"
                    f"{entreprise.get('slug', '')}/jobs/{offre.get('slug', '')}",
        })

    if page >= resultat["metadata"]["page_count"] or page >= MAX_PAGES:
        break
    page += 1
    time.sleep(1)

print("Nombre d'offres récupérées :", len(toutes_les_offres))

if len(toutes_les_offres) == 0:
    print("Aucune offre trouvée : change MOT_CLE et relance.")
else:
    with open(FICHIER, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=toutes_les_offres[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(toutes_les_offres)
    print("Fichier créé ici :", FICHIER)
    os.startfile(FICHIER)  # ouvre le fichier dans Excel