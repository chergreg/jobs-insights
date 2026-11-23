import requests
import json
from pathlib import Path
from bs4 import BeautifulSoup

url = "https://www.guichetemplois.gc.ca/jobsearch/jobsearch?searchstring=informatique&locationstring=&locationparam=&sort=M"

reponse = requests.get(url, timeout=15)

print("Statut HTTP :", reponse.status_code)

if reponse.status_code == 200:
    soup = BeautifulSoup(reponse.text, "html.parser")
    offres = soup.select("article")

    liste_offres = []

    for offre in offres:
        titre = offre.find("span", class_="noctitle")
        entreprise = offre.find("li", class_="business")
        ville = offre.find("li", class_="location")
        salaire = offre.find("li", class_="salary")
        date = offre.find("li", class_="date")

        if titre:
            donnees = {
                "titre": titre.get_text(strip=True),
                "entreprise": entreprise.get_text(strip=True) if entreprise else "",
                "ville": ville.get_text(" ", strip=True).replace("Emplacement", "").strip() if ville else "",
                "salaire": salaire.get_text(strip=True).replace("Salaire :", "").strip() if salaire else "",
                "date": date.get_text(strip=True) if date else ""
            }

            liste_offres.append(donnees)

    chemin = Path(__file__).parent / "offres_guichet.json"

    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(liste_offres, fichier, indent=4, ensure_ascii=False)

    print("Nombre d'offres récupérées :", len(liste_offres))
    print("Fichier JSON créé avec succès.")

else:
    print("Impossible de récupérer la page.")