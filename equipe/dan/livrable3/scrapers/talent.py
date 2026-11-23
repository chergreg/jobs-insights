"""Talent.com Canada : recherche TI au Québec (liste JSON-LD ItemList + fiches JSON-LD JobPosting).

Code et observations repris de Mamadou (L3, ``poc_guichet_cnp_v2.py``, essai réel du 2026-11-16) :
- recherche ``https://ca.talent.com/fr/jobs?k=<mot-clé>&l=<lieu>`` ;
- la page de résultats contient un JSON-LD ``ItemList`` dont chaque ``itemListElement`` donne l'URL d'une fiche ;
- fiche ``/fr/view?id=<numéro>`` avec un JSON-LD ``JobPosting`` (``@graph``) : GPS, ``employmentType`` en texte,
  région en anglais (« Quebec »), ville « Québec City ».

Bonifications :
- **porte d'entrée** : ``outils.Client`` lit d'abord robots.txt ; si la page est interdite ou si le serveur
  répond 401/403/429, la collecte s'arrête proprement (message clair, aucun contournement) ;
- aucune valeur devinée (Mamadou mettait « QC » et « Temps plein » par défaut) ; ``id`` = ``tc-<numéro>``
  seulement si l'URL contient ``id=`` (pas d'identifiant fabriqué avec ``hash()``) ;
- lecture JSON-LD partagée avec Jobboom (``scrapers/jsonld.py``).

À vérifier au premier lancement (non observé par l'équipe) : le paramètre de pagination ``p``.
S'il n'est pas reconnu, la page 2 renvoie les mêmes offres et la collecte s'arrête d'elle-même.

Usage (depuis equipe/dan/livrable3) :
    python -m scrapers.talent --pages 1 --fiches 10
    python -m scrapers.talent --mot-cle "stage informatique" --lieu "Montréal, QC"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

if __package__ in (None, ""):                       # lancé comme « python scrapers/talent.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modele import Offre, exporter_csv, exporter_json
from outils import AccesRefuse, Client
from scrapers.commun import espaces
from scrapers.jsonld import champs_jobposting, est_du_type, jobposting, objets_jsonld

SOURCE = "talent"
BASE_URL = "https://ca.talent.com"
URL_RECHERCHE = BASE_URL + "/fr/jobs"
MOT_CLE = "informatique"
LIEU = "Québec, QC"
PARAM_PAGE = "p"                                    # 🔍 à confirmer sur le site
SORTIE_JSON = Path(__file__).resolve().parents[1] / "data" / "offres_talent.json"


# --- Page de résultats -----------------------------------------------------------------

def url_recherche(page: int = 1, mot_cle: str = MOT_CLE, lieu: str = LIEU) -> str:
    parametres = [("k", mot_cle), ("l", lieu)]
    if page > 1:
        parametres.append((PARAM_PAGE, str(page)))
    return f"{URL_RECHERCHE}?{urlencode(parametres)}"


def identifiant(url: str) -> str | None:
    """« https://ca.talent.com/fr/view?id=640918690502021004 » → « 640918690502021004 »."""
    valeurs = parse_qs(urlsplit(url).query).get("id")
    numero = valeurs[0].strip() if valeurs else ""
    return numero if numero.isalnum() else None


def nettoyer_lien(url: str) -> str:
    """Lien absolu vers la fiche, avec seulement le paramètre ``id`` (pas de suivi)."""
    absolu = urljoin(BASE_URL, url)
    numero = identifiant(absolu)
    morceaux = urlsplit(absolu)
    return f"{morceaux.scheme}://{morceaux.netloc}{morceaux.path}?id={numero}" if numero else absolu


def lire_resultats(html: str) -> list[Offre]:
    """Offres annoncées dans le JSON-LD ``ItemList`` de la page de résultats, dans l'ordre.

    Une offre n'a ici que son ``id``, son ``url`` et, si l'ItemList le donne, son titre.
    """
    offres, vus = [], set()
    for liste in (o for o in objets_jsonld(html) if est_du_type(o, "ItemList")):
        elements = liste.get("itemListElement") or []
        for element in elements if isinstance(elements, list) else [elements]:
            if not isinstance(element, dict):
                continue
            item = element.get("item") if isinstance(element.get("item"), dict) else {}
            url = item.get("url") or element.get("url")
            if not isinstance(url, str):
                continue
            url = nettoyer_lien(url)
            numero = identifiant(url)
            if numero is None or numero in vus:
                continue                                # pas d'identifiant inventé, pas de doublon
            vus.add(numero)
            titre = item.get("title") or item.get("name") or element.get("name") or ""
            offres.append(Offre(id=f"tc-{numero}", source=SOURCE, titre=espaces(str(titre)), url=url))
    return offres


# --- Fiche d'une offre -----------------------------------------------------------------

def lire_fiche(html: str) -> dict:
    """Champs du JSON-LD ``JobPosting`` de la fiche. ``{}`` s'il n'y en a pas."""
    job = jobposting(html)
    return champs_jobposting(job) if job else {}


def completer(offre: Offre, fiche: dict) -> Offre:
    """La fiche est plus complète que la liste : ses valeurs remplacent celles de la liste."""
    for cle, valeur in fiche.items():
        setattr(offre, cle, valeur)
    return offre


# --- Collecte ----------------------------------------------------------------------------

def collecter(client: Client, pages: int = 1, fiches: int = 10,
              mot_cle: str = MOT_CLE, lieu: str = LIEU) -> list[Offre]:
    """Lit jusqu'à ``pages`` pages de résultats, puis les ``fiches`` premières fiches.

    La 1re requête sert de porte d'entrée : si Talent.com refuse (robots.txt, 401, 403, 429),
    on affiche le refus et on rend une liste vide, sans réessayer autrement.
    """
    offres: list[Offre] = []
    vus: set[str] = set()
    for page in range(1, pages + 1):
        try:
            html = client.telecharger(url_recherche(page, mot_cle, lieu))
        except AccesRefuse as refus:
            print(refus)
            if page == 1:
                print("Talent.com refuse notre robot : utiliser le plan B (Remotive), voir plan.md.")
            break
        nouvelles = [o for o in lire_resultats(html) if o.id not in vus]
        print(f"Page {page} : {len(nouvelles)} nouvelles offres")
        if not nouvelles:                               # page vide ou pagination non reconnue
            break
        offres += nouvelles
        vus.update(o.id for o in nouvelles)

    for i, offre in enumerate(offres[:fiches], start=1):
        try:
            completer(offre, lire_fiche(client.telecharger(offre.url)))
            print(f"  Fiche {i}/{min(fiches, len(offres))} : {offre.titre}")
        except AccesRefuse as refus:
            print(refus)
            break
        except Exception as erreur:                     # une fiche illisible n'arrête pas les autres
            print(f"  Fiche ignorée ({offre.url}) : {erreur}")
    return [o for o in offres if o.titre]


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(description="Talent.com : offres TI au Québec.")
    analyseur.add_argument("--pages", type=int, default=1, help="pages de résultats à lire (défaut : 1)")
    analyseur.add_argument("--fiches", type=int, default=10, help="fiches à ouvrir (défaut : 10)")
    analyseur.add_argument("--mot-cle", default=MOT_CLE, help=f"mots-clés (défaut : « {MOT_CLE} »)")
    analyseur.add_argument("--lieu", default=LIEU, help=f"lieu (défaut : « {LIEU} »)")
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_JSON, help="fichier JSON produit")
    analyseur.add_argument("--csv", action="store_true", help="écrire aussi un CSV à côté du JSON")
    analyseur.add_argument("--sans-cache", action="store_true", help="ignorer le cache disque")
    args = analyseur.parse_args(arguments)

    client = Client(cache_dossier=None) if args.sans_cache else Client()
    offres = collecter(client, pages=args.pages, fiches=args.fiches, mot_cle=args.mot_cle, lieu=args.lieu)

    chemin = exporter_json(offres, args.sortie)
    print(f"\n{len(offres)} offres, {sum(o.description is not None for o in offres)} avec description")
    print(f"JSON : {chemin}")
    if args.csv:
        print(f"CSV  : {exporter_csv(offres, args.sortie.with_suffix('.csv'))}")


if __name__ == "__main__":
    main()
