
import requests
from bs4 import BeautifulSoup

# URL de l'offre d'emploi sur Guichet-Emplois
url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50703263"

try:
    # Étape 1 : Récupérer le HTML du site
    response = requests.get(url, timeout=15)

    # Vérifier la réponse du serveur
    print("Statut HTTP :", response.status_code)
    print("Type de contenu :", response.headers.get("Content-Type"))
    print("Taille de la réponse :", len(response.content), "octets")

    # Vérifier si la requête a réussi
    response.raise_for_status()

    # Étape 2 : Analyser le HTML avec BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    # Étape 3 : Extraire le titre de l'offre
    titre = soup.find(
        "span",
        attrs={"property": "title"}
    )

    if titre:
        print("Titre extrait du site :", titre.get_text(strip=True))
    else:
        print("Titre introuvable dans le HTML reçu.")

    # Étape 4 : Extraire l'employeur
    employeur = soup.find(
        "strong",
        string=lambda texte: texte and "imperial truck" in texte.lower()
    )

    if employeur:
        print("Employeur extrait du site :", employeur.get_text(strip=True))
    else:
        print("Employeur introuvable dans le HTML reçu.")

    # Étape 5 : Afficher le lien de l'offre
    print("Lien de l'offre :", response.url)

except requests.RequestException as erreur:
    print("Erreur lors de la récupération :", erreur)
