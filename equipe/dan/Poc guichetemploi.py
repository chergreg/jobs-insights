"""
POC 1 — Scraping des résultats de recherche du Guichet-Emplois.

Ce que le script fait :
  1. vérifie que robots.txt autorise la page de recherche ;
  2. télécharge la page de résultats pour des mots-clés et un lieu ;
  3. extrait le titre, l'employeur, le lieu, la date, le salaire et le lien de chaque offre ;
  4. enregistre le tout dans offres_guichetemplois.csv.

IMPORTANT : les sélecteurs CSS (SELECTEURS ci-dessous) doivent être vérifiés
avec « clic droit → Inspecter » sur la vraie page, car le site peut changer.

Utilisation :
    pip install -r requirements.txt
    python poc_guichetemplois.py "technicien" "Moncton, NB"
"""

import csv
import sys
import time
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

SITE = "https://www.guichetemplois.gc.ca"
PAGE_RECHERCHE = SITE + "/jobsearch/rechercheemplois"
ENTETES = {
    "User-Agent": "ProjetEtudiantUMoncton-RechercheEmploi/0.1",
    "Accept-Language": "fr-CA,fr;q=0.9",
}

# À VÉRIFIER avec l'outil Inspecter : balise de chaque offre et de ses champs.
SELECTEURS = {
    "offre": "article",               # un bloc par offre
    "lien": "a",                      # lien vers la fiche
    "titre": ".noctitle",             # titre du poste
    "employeur": ".business",
    "lieu": ".location",
    "date": ".date",
    "salaire": ".salary",
}


def texte(bloc, selecteur):
    """Renvoie le texte nettoyé d'un sous-élément, ou une chaîne vide s'il n'existe pas."""
    element = bloc.select_one(selecteur)
    return " ".join(element.get_text(" ", strip=True).split()) if element else ""


def robots_autorise(url):
    robots = RobotFileParser(SITE + "/robots.txt")
    try:
        robots.read()
    except Exception as erreur:
        print("Impossible de lire robots.txt :", erreur)
        return False
    return robots.can_fetch(ENTETES["User-Agent"], url)


def chercher(mots_cles, lieu):
    parametres = {"searchstring": mots_cles, "locationstring": lieu}
    reponse = requests.get(PAGE_RECHERCHE, params=parametres, headers=ENTETES, timeout=20)
    reponse.raise_for_status()
    print("Page téléchargée :", reponse.url)

    soupe = BeautifulSoup(reponse.text, "html.parser")
    offres = []
    for bloc in soupe.select(SELECTEURS["offre"]):
        lien = bloc.select_one(SELECTEURS["lien"])
        titre = texte(bloc, SELECTEURS["titre"])
        if not lien or not titre:
            continue  # ce bloc n'est pas une offre
        offres.append({
            "source": "guichetemplois",
            "titre": titre,
            "employeur": texte(bloc, SELECTEURS["employeur"]),
            "lieu": texte(bloc, SELECTEURS["lieu"]),
            "date": texte(bloc, SELECTEURS["date"]),
            "salaire": texte(bloc, SELECTEURS["salaire"]),
            "lien": urljoin(SITE, lien.get("href", "")),
        })
    return offres


def enregistrer_csv(offres, fichier):
    if not offres:
        return
    with open(fichier, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=offres[0].keys())
        ecrivain.writeheader()
        ecrivain.writerows(offres)


def main():
    mots_cles = sys.argv[1] if len(sys.argv) > 1 else "technicien"
    lieu = sys.argv[2] if len(sys.argv) > 2 else "Moncton, NB"

    if not robots_autorise(PAGE_RECHERCHE):
        sys.exit("robots.txt n'autorise pas cette page (ou il est illisible) : arrêt.")

    offres = chercher(mots_cles, lieu)
    print(len(offres), "offres trouvées")
    for o in offres[:10]:
        print(f"- {o['titre']} | {o['employeur']} | {o['lieu']} | {o['date']}")
        print(f"  {o['lien']}")

    if not offres:
        print("0 offre : vérifier les SELECTEURS avec l'outil Inspecter du navigateur.")

    enregistrer_csv(offres, "offres_guichetemplois.csv")
    time.sleep(2)  # pause polie avant toute autre requête


if __name__ == "__main__":
    main()