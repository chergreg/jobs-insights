"""
POC — Scraping des résultats de recherche du Guichet-Emplois (Québec, domaine TI).

Ce que le script fait :
  1. vérifie que robots.txt autorise la page de recherche ;
  2. télécharge une page de résultats filtrée sur le Québec (fprov=QC)
     et sur les codes CNP du domaine informatique (fn21=...) ;
  3. extrait le titre, l'employeur, le lieu, la date, le salaire et le lien de chaque offre ;
  4. enregistre le tout dans offres_guichetemplois.csv.

Les sélecteurs CSS et les paramètres d'URL viennent du POC de Kandet
(equipe/kandet/02-preuve-de-concept-scraping/poc_multi_source.py), qui les a vérifiés.

Utilisation :
    pip install -r requirements.txt
    python poc_guichetemplois.py                  # tous les postes TI au Québec
    python poc_guichetemplois.py "developpeur"    # avec un mot-clé
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
    "User-Agent": "jobs-insights-dan/0.2 (projet etudiant)",
    "Accept-Language": "fr-CA,fr;q=0.9",
}
DELAI = 5  # robots.txt du Guichet-Emplois : « Crawl-delay: 5 »

# Cible : Québec + codes CNP 2021 du domaine informatique (liste reprise de Kandet)
PROVINCE = "QC"
CODES_CNP_TI = [
    "21211", "21220", "21221", "21222", "21223", "21230", "21231",
    "21232", "21233", "21234", "21311", "22220", "22221", "22222",
]

# Sélecteurs vérifiés dans le POC de Kandet (balisage de novembre 2026)
SELECTEURS = {
    "offre": "article[id^='article-']",   # un bloc par offre : <article id="article-50684844">
    "lien": "a.resultJobItem",            # lien vers la fiche
    "titre": ".noctitle",
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
    """Lit robots.txt avec NOTRE User-Agent.

    RobotFileParser.read() se présenterait comme « Python-urllib » : si le serveur
    refuse ce nom, Python conclut à tort que tout est interdit.
    """
    reponse = requests.get(SITE + "/robots.txt", headers=ENTETES, timeout=20)
    if reponse.status_code in (401, 403):
        print("Le serveur refuse de donner robots.txt.")
        return False
    robots = RobotFileParser()
    robots.parse(reponse.text.splitlines())
    return robots.can_fetch(ENTETES["User-Agent"], url)


def chercher(mots_cles):
    parametres = [("fn21", code) for code in CODES_CNP_TI]
    parametres += [("fprov", PROVINCE), ("sort", "D")]   # Québec, plus récentes d'abord
    if mots_cles:
        parametres.append(("searchstring", mots_cles))

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
            "lieu": texte(bloc, SELECTEURS["lieu"]).replace("Emplacement ", ""),
            "date": texte(bloc, SELECTEURS["date"]),
            "salaire": texte(bloc, SELECTEURS["salaire"]).replace("Salaire : ", ""),
            # Le lien contient un identifiant de session (;jsessionid=...) : on le retire.
            "lien": urljoin(SITE, lien.get("href", "").split(";")[0]),
        })
    return offres


def enregistrer_csv(offres, fichier):
    if not offres:
        return
    # utf-8-sig : les accents s'affichent correctement dans Excel
    with open(fichier, "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.DictWriter(f, fieldnames=offres[0].keys())
        ecrivain.writeheader()
        ecrivain.writerows(offres)
    print("Fichier :", fichier)


def main():
    mots_cles = sys.argv[1] if len(sys.argv) > 1 else ""

    if not robots_autorise(PAGE_RECHERCHE):
        sys.exit("robots.txt n'autorise pas cette page : arrêt.")
    time.sleep(DELAI)  # délai entre la lecture de robots.txt et la recherche

    offres = chercher(mots_cles)
    print(len(offres), "offres trouvées")
    for o in offres[:10]:
        print(f"- {o['titre']} | {o['employeur']} | {o['lieu']} | {o['date']}")
        print(f"  {o['lien']}")

    if not offres:
        print("0 offre : vérifier les SELECTEURS avec l'outil Inspecter du navigateur.")

    enregistrer_csv(offres, "offres_guichetemplois.csv")


if __name__ == "__main__":
    main()
