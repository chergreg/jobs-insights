"""Jobboom : offres de la catégorie « Technologies et médias numériques » (liste + fiches JSON-LD).

Code et observations repris :
- Mamadou (L2/L3) : catégorie TI ``_i10lfr?sortBy=date&page=N``, cartes ``div.job_item[data-url]``,
  exclusion des offres commanditées (classe ``job_item_sponsorship``), ordre d'affichage gardé ;
- Elvira (L2/L3) : fiche lue par le JSON-LD ``JobPosting`` (un bloc ``Organization`` le précède),
  GPS, code postal, ``employmentType`` en liste, ``baseSalary`` ;
- Gregory (démo L3) : total annoncé « 1 - 15 de 131 résultats », lecture JSON-LD par ``json.loads``.

Bonifications :
- aucune valeur devinée : pas de ville « Québec » ni de « Temps plein » par défaut,
  ``est_stage`` vaut ``True`` ou ``None`` (jamais ``False`` sans preuve) ;
- modalité tirée seulement du champ structuré ``jobLocationType`` (``TELECOMMUTE``), pas du texte libre ;
- aucun identifiant inventé : une URL sans numéro ``_p<chiffres>`` est ignorée ;
- réseau délégué à ``outils.Client`` (délai 2 s, cache 24 h, arrêt propre sur 401/403/429 ;
  robots.txt vérifié seulement avec ``--respecter-robots``).

Usage (depuis equipe/dan/livrable3) :
    python -m scrapers.jobboom --pages 2 --fiches 10
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

if __package__ in (None, ""):                       # lancé comme « python scrapers/jobboom.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modele import Offre, exporter_csv, exporter_json
from outils import AccesRefuse, Client
from scrapers.commun import espaces
from scrapers.jsonld import champs_jobposting, jobposting

SOURCE = "jobboom"
BASE_URL = "https://www.jobboom.com"
URL_CATEGORIE_TI = BASE_URL + "/fr/technologies-medias-numeriques/_i10lfr"
SORTIE_JSON = Path(__file__).resolve().parents[1] / "data" / "offres_jobboom.json"

NUMERO_OFFRE = re.compile(r"_p(\d+)$")              # …/offre-emploi/<slug>_p3698100


# --- Page de la catégorie ---------------------------------------------------------------

def url_categorie(page: int = 1) -> str:
    """URL d'une page de la catégorie TI, offres les plus récentes d'abord."""
    return f"{URL_CATEGORIE_TI}?sortBy=date" + (f"&page={page}" if page > 1 else "")


def nettoyer_lien(href: str) -> str:
    """Lien absolu sans paramètres de suivi (``?track=…``) ni ancre."""
    return urljoin(BASE_URL, urlsplit(href).path)


def numero_offre(url: str) -> str | None:
    """« …/developpeur-python_tech-mtl_p3718101 » → « 3718101 ». ``None`` si absent."""
    trouve = NUMERO_OFFRE.search(urlsplit(url).path)
    return trouve.group(1) if trouve else None


def _titre_carte(carte: Tag) -> str | None:
    # En repli, la « carte » est le lien <a> lui-même (find ne cherche que dans les descendants).
    titre = carte if carte.name == "a" else (carte.find(["h2", "h3"]) or carte.find("a"))
    texte = espaces(titre.get_text()) if titre else ""
    return texte or None


def lire_categorie(html: str) -> tuple[list[Offre], int | None]:
    """Offres d'une page de la catégorie (hors commandites) et total annoncé (``None`` s'il manque).

    À ce stade, une offre n'a que son ``id``, son ``url`` et le titre de sa carte :
    le reste vient de la fiche (``lire_fiche``).
    """
    soupe = BeautifulSoup(html, "html.parser")

    cartes = soupe.select("div.job_item[data-url]")
    liens = [(c, c["data-url"]) for c in cartes if "job_item_sponsorship" not in (c.get("class") or [])]
    if not cartes:                                     # balisage différent : repli sur les liens <a>
        liens = [(a, a["href"]) for a in soupe.select("a[href*='/offre-emploi/']")
                 if not a.find_parent(class_="job_item_sponsorship")]

    offres, vus = [], set()
    for carte, href in liens:
        url = nettoyer_lien(href)
        numero = numero_offre(url)
        if "/offre-emploi/" not in url or numero is None or numero in vus:
            continue
        vus.add(numero)
        offres.append(Offre(id=f"jb-{numero}", source=SOURCE, titre=_titre_carte(carte) or "", url=url))

    total = None
    resume = re.search(r"de\s+([\d\s\xa0]+?)\s+r[ée]sultats", soupe.get_text(" "), re.IGNORECASE)
    if resume:
        chiffres = "".join(c for c in resume.group(1) if c.isdigit())
        total = int(chiffres) if chiffres else None
    return offres, total


# --- Fiche d'une offre (JSON-LD) ---------------------------------------------------------

def lire_fiche(html: str) -> dict:
    """Champs du JSON-LD ``JobPosting`` (lecture commune : ``scrapers/jsonld.py``).

    Une clé n'est présente que si la valeur existe vraiment ; ``{}`` si la page n'a pas de JobPosting.
    """
    job = jobposting(html)
    return champs_jobposting(job) if job else {}


def completer(offre: Offre, fiche: dict) -> Offre:
    """La fiche est la source la plus complète : ses valeurs remplacent celles de la carte."""
    for cle, valeur in fiche.items():
        setattr(offre, cle, valeur)
    return offre


# --- Collecte ------------------------------------------------------------------------------

def collecter(client: Client, pages: int = 1, fiches: int = 10) -> list[Offre]:
    """Lit jusqu'à ``pages`` pages de la catégorie TI, puis les ``fiches`` premières fiches.

    Une offre sans titre (ni sur sa carte ni dans sa fiche) est retirée : elle n'est pas exploitable.
    S'arrête proprement (sans exception) si le site refuse l'accès.
    """
    offres: list[Offre] = []
    vus: set[str] = set()
    total = None
    for page in range(1, pages + 1):
        try:
            html = client.telecharger(url_categorie(page))
        except AccesRefuse as refus:
            print(refus)
            break
        nouvelles, total_page = lire_categorie(html)
        total = total_page or total
        nouvelles = [o for o in nouvelles if o.id not in vus]
        print(f"Page {page} : {len(nouvelles)} offres (total annoncé : {total if total is not None else '?'})")
        if not nouvelles:
            break
        offres += nouvelles
        vus.update(o.id for o in nouvelles)
        if total is not None and len(offres) >= total:
            break

    for i, offre in enumerate(offres[:fiches], start=1):
        try:
            completer(offre, lire_fiche(client.telecharger(offre.url)))
            print(f"  Fiche {i}/{min(fiches, len(offres))} : {offre.titre}")
        except AccesRefuse as refus:
            print(refus)
            break
        except Exception as erreur:                    # une fiche illisible n'arrête pas les autres
            print(f"  Fiche ignorée ({offre.url}) : {erreur}")
    return [o for o in offres if o.titre]


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(description="Jobboom : offres de la catégorie TI.")
    analyseur.add_argument("--pages", type=int, default=1, help="pages de la catégorie à lire (défaut : 1)")
    analyseur.add_argument("--fiches", type=int, default=10, help="fiches à ouvrir (défaut : 10)")
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_JSON, help="fichier JSON produit")
    analyseur.add_argument("--csv", action="store_true", help="écrire aussi un CSV à côté du JSON")
    analyseur.add_argument("--sans-cache", action="store_true", help="ignorer le cache disque")
    analyseur.add_argument("--respecter-robots", action="store_true",
                           help="lire et appliquer robots.txt (désactivé par défaut)")
    args = analyseur.parse_args(arguments)

    client = Client(respecter_robots=args.respecter_robots, **({"cache_dossier": None} if args.sans_cache else {}))
    offres = collecter(client, pages=args.pages, fiches=args.fiches)

    chemin = exporter_json(offres, args.sortie)
    print(f"\n{len(offres)} offres, {sum(o.description is not None for o in offres)} avec description")
    print(f"JSON : {chemin}")
    if args.csv:
        print(f"CSV  : {exporter_csv(offres, args.sortie.with_suffix('.csv'))}")


if __name__ == "__main__":
    main()
