"""Guichet-Emplois : offres TI au Québec (liste paginée + fiches RDFa).

Code et observations repris :
- Dan (L2, ``poc_guichetemplois.py``) et Kandet (L2/L3) : filtres ``fprov=QC`` + codes CNP TI
  ``fn21`` + ``sort=D``, sélecteurs de la page de résultats, pagination ``page``, site d'origine ;
- Hugo (L2), Mamadou (L3) et Gregory (démo L3) : description par RDFa ``property="description"``
  avec repli DOM ``#job-posting-detail`` ;
- Kandet (L3) : la description RDFa des offres partenaires contient du HTML encodé deux fois.

Bonifications par rapport aux versions précédentes :
- aucune valeur devinée : un champ absent reste ``None`` (pas de « Non spécifié »,
  pas de « Québec (QC) » ni de « Temps plein » par défaut) ;
- réseau délégué à ``outils.Client`` : délai fixe de 5 s (valeur du ``Crawl-delay`` du site),
  cache 24 h, arrêt propre sur 401/403/429 ; robots.txt vérifié seulement avec ``--respecter-robots`` ;
- description en texte propre qui garde les paragraphes et les puces (une ligne par élément).

Usage (depuis equipe/dan/livrable3) :
    python -m scrapers.guichet_emplois --pages 2 --fiches 5
    python -m scrapers.guichet_emplois --mot-cle stage --pages 1 --fiches 10 --csv
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

if __package__ in (None, ""):                       # lancé comme « python scrapers/guichet_emplois.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modele import Offre, exporter_csv, exporter_json
from outils import AccesRefuse, Client
from scrapers.jsonld import province
from scrapers.commun import (UNITES_SALAIRE, date_iso, espaces, est_un_stage,
                             texte_multiligne)

SOURCE = "guichet-emplois"
BASE_URL = "https://www.guichetemplois.gc.ca"
URL_RECHERCHE = BASE_URL + "/jobsearch/rechercheemplois"
PROVINCE = "QC"
# Codes CNP 2021 du domaine informatique (liste de Kandet, reprise dans mon POC L2).
CODES_CNP_TI = (
    "21211", "21220", "21221", "21222", "21223", "21230", "21231",
    "21232", "21233", "21234", "21311", "22220", "22221", "22222",
)
SORTIE_JSON = Path(__file__).resolve().parents[1] / "data" / "offres_guichet_emplois.json"

MODALITES = {
    "sur place": "Sur place", "on site": "Sur place",
    "hybride": "Hybride", "hybrid": "Hybride",
    "télétravail": "Télétravail", "teletravail": "Télétravail", "remote": "Télétravail",
}
PARTENAIRES_IGNORES = {"guichet-emplois", "job bank"}     # l'offre est publiée sur le site lui-même


# --- Petits outils propres au Guichet-Emplois (les autres sont dans scrapers/commun.py) ------

def _est_cache(noeud: Tag, racine: Tag) -> bool:
    """Vrai si le texte est dans un ``.wb-inv`` (texte pour lecteur d'écran) ou ``.hidden``."""
    parent = noeud.parent
    while parent is not None and parent is not racine.parent:
        classes = parent.get("class") or []
        if "wb-inv" in classes or ("hidden" in classes and parent is not racine):
            return True
        parent = parent.parent
    return False


def texte_visible(balise: Tag | None) -> str | None:
    """Texte d'une balise sans ses parties invisibles, espaces normalisés. ``None`` si vide."""
    if balise is None:
        return None
    morceaux = [s for s in balise.find_all(string=True) if not _est_cache(s, balise)]
    texte = espaces(" ".join(morceaux))
    return texte or None






def province_de(lieu: str | None) -> str | None:
    """« Québec (QC) » → « QC ». ``None`` si la province n'est pas écrite."""
    if not lieu:
        return None
    trouve = re.search(r"\(([A-Z]{2})\)\s*$", lieu) or re.search(r",\s*([A-Z]{2})\s*$", lieu)
    return trouve.group(1) if trouve else None


def modalite_de(texte: str | None) -> str | None:
    if not texte:
        return None
    return MODALITES.get(texte.strip().casefold())




def nettoyer_lien(href: str) -> str:
    """Lien absolu sans ``;jsessionid=…`` ni paramètres de suivi."""
    chemin = urlsplit(href).path.split(";")[0]
    return urljoin(BASE_URL, chemin)


# --- Page de résultats -----------------------------------------------------------------

def url_recherche(page: int = 1, mot_cle: str = "") -> str:
    """URL d'une page de résultats : Québec, codes CNP TI, plus récentes d'abord."""
    parametres = [("searchstring", mot_cle)] if mot_cle else []
    parametres += [("fn21", code) for code in CODES_CNP_TI]
    parametres += [("fprov", PROVINCE), ("sort", "D")]
    if page > 1:
        parametres.append(("page", str(page)))
    return f"{URL_RECHERCHE}?{urlencode(parametres)}"


def lire_resultats(html: str) -> tuple[list[Offre], int | None]:
    """Offres d'une page de résultats et nombre total annoncé par le site (``None`` s'il manque)."""
    soupe = BeautifulSoup(html, "html.parser")

    total = None
    compteur = soupe.find(id="results-count")
    if compteur:
        chiffres = "".join(c for c in compteur.get_text() if c.isdigit())
        total = int(chiffres) if chiffres else None

    offres = []
    for article in soupe.select("article[id^='article-']"):
        numero = article["id"].removeprefix("article-")
        lien = article.select_one("a.resultJobItem")
        titre = texte_visible(article.select_one(".noctitle"))
        if not (numero.isdigit() and lien and lien.get("href") and titre):
            continue

        lieu = texte_visible(article.select_one("li.location"))
        salaire = texte_visible(article.select_one("li.salary"))
        if salaire:
            salaire = re.sub(r"^(salaire|salary)\s*:\s*", "", salaire, flags=re.IGNORECASE) or None

        origine = article.select_one(".job-source .wb-inv")
        partenaire = espaces(origine.get_text()) if origine else None
        if partenaire and partenaire.casefold() in PARTENAIRES_IGNORES:
            partenaire = None

        teletravail = article.select_one(".telework")
        offres.append(Offre(
            id=f"ge-{numero}",
            source=SOURCE,
            titre=titre,
            url=nettoyer_lien(lien["href"]),
            source_partenaire=partenaire,
            entreprise=texte_visible(article.select_one("li.business")),
            lieu=lieu,
            province=province_de(lieu),
            date_publication=date_iso(texte_visible(article.select_one("li.date"))),
            modalite=modalite_de(teletravail.get_text()) if teletravail else None,
            est_stage=est_un_stage(titre),
            salaire=salaire,
        ))
    return offres, total


# --- Fiche d'une offre ---------------------------------------------------------------

def _description_rdfa(soupe: BeautifulSoup) -> str | None:
    """Description RDFa. Si elle contient du HTML encodé (offres partenaires), on le relit."""
    balise = soupe.find(attrs={"property": "description"})
    if balise is None:
        return None
    contenu = balise.get_text()
    if "<" in contenu and ">" in contenu:               # « &lt;p&gt; » devenu « <p> » à la 1re lecture
        return texte_multiligne(BeautifulSoup(contenu, "html.parser"))
    return texte_multiligne(balise)


def _salaire_rdfa(soupe: BeautifulSoup) -> str | None:
    valeur = soupe.find(attrs={"property": "baseSalary"})
    if valeur is None:
        return None
    mini = valeur.find(attrs={"property": "minValue"})
    maxi = valeur.find(attrs={"property": "maxValue"})
    unite = valeur.find(attrs={"property": "unitText"})
    if mini is None:
        return texte_visible(valeur)
    texte = f"{espaces(mini.get_text())} $"
    if maxi is not None:
        texte += f" à {espaces(maxi.get_text())} $"
    if unite is not None and unite.get_text().strip() in UNITES_SALAIRE:
        texte += " " + UNITES_SALAIRE[unite.get_text().strip()]
    return texte


def lire_fiche(html: str) -> dict:
    """Champs trouvés sur la fiche. Une clé n'est présente que si la valeur existe vraiment."""
    soupe = BeautifulSoup(html, "html.parser")
    trouve: dict = {}

    def prop(nom: str) -> Tag | None:
        return soupe.find(attrs={"property": nom})

    # 1. Description : RDFa, puis repli DOM.
    description = _description_rdfa(soupe)
    if not description:
        description = texte_multiligne(soupe.find(id="job-posting-detail"))
    if description:
        trouve["description"] = description

    # 2. Autres métadonnées RDFa.
    organisation = prop("hiringOrganization")
    entreprise = texte_visible(organisation.find(attrs={"property": "name"}) if organisation else None)
    ville = texte_visible(prop("addressLocality"))
    # Le site écrit parfois la région « , QC » (offre « Différentes régions ») : on la nettoie,
    # et un texte qui n'est pas une province reconnue donne None (rien d'inventé).
    region_brute = texte_visible(prop("addressRegion"))
    region = province(region_brute.strip(" ,;")) if region_brute else None
    type_poste = prop("employmentType")
    valeurs = {
        "entreprise": entreprise,
        "lieu": f"{ville} ({region})" if ville and region else ville,
        "province": region,
        "date_publication": date_iso(texte_visible(prop("datePosted"))),
        "type_poste": ", ".join(type_poste.stripped_strings) if type_poste else None,
        "salaire": _salaire_rdfa(soupe),
    }
    trouve.update({cle: v for cle, v in valeurs.items() if v})

    # 3. Modalité dans le bandeau résumé (« Sur place », « Hybride », « Télétravail »).
    bandeau = soupe.find("ul", class_="job-posting-brief")
    for valeur in (bandeau.select(".attribute-value") if bandeau else []):
        modalite = modalite_de(valeur.get_text())
        if modalite:
            trouve["modalite"] = modalite
            break

    # 4. Stage : titre de la fiche, titre d'origine du partenaire ou type de poste.
    origine = soupe.find(class_="source-title-inner")
    titre_origine = None
    if origine:
        etiquette = origine.find(class_="orig-title-label")
        titre_origine = origine.get_text().replace(etiquette.get_text() if etiquette else "", "")
    if est_un_stage(texte_visible(prop("title")), titre_origine, trouve.get("type_poste")):
        trouve["est_stage"] = True
    return trouve


def completer(offre: Offre, fiche: dict) -> Offre:
    """Ajoute les champs de la fiche. La description vient toujours de la fiche ;
    les autres champs ne remplacent qu'une valeur absente (``None``) de la liste."""
    for cle, valeur in fiche.items():
        if cle == "description" or getattr(offre, cle) is None:
            setattr(offre, cle, valeur)
    return offre


# --- Collecte ----------------------------------------------------------------------------

def collecter(client: Client, pages: int = 1, fiches: int = 5, mot_cle: str = "") -> list[Offre]:
    """Lit jusqu'à ``pages`` pages de résultats, puis complète les ``fiches`` premières offres.

    S'arrête proprement (sans exception) si le site refuse l'accès : on garde ce qui est déjà lu.
    """
    offres: list[Offre] = []
    vus: set[str] = set()
    total = None
    for page in range(1, pages + 1):
        try:
            html = client.telecharger(url_recherche(page, mot_cle))
        except AccesRefuse as refus:
            print(refus)
            break
        nouvelles, total_page = lire_resultats(html)
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
            break                                          # le site refuse : on n'insiste pas
        except Exception as erreur:                        # une fiche illisible n'arrête pas les autres
            print(f"  Fiche ignorée ({offre.url}) : {erreur}")
    return offres


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(description="Guichet-Emplois : offres TI au Québec.")
    analyseur.add_argument("--pages", type=int, default=1, help="pages de résultats à lire (défaut : 1)")
    analyseur.add_argument("--fiches", type=int, default=5, help="fiches à ouvrir pour la description (défaut : 5)")
    analyseur.add_argument("--mot-cle", default="", help="mot-clé ajouté à la recherche (défaut : aucun)")
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_JSON, help="fichier JSON produit")
    analyseur.add_argument("--csv", action="store_true", help="écrire aussi un CSV à côté du JSON")
    analyseur.add_argument("--sans-cache", action="store_true", help="ignorer le cache disque")
    analyseur.add_argument("--respecter-robots", action="store_true",
                           help="lire et appliquer robots.txt (désactivé par défaut)")
    args = analyseur.parse_args(arguments)

    client = Client(respecter_robots=args.respecter_robots, **({"cache_dossier": None} if args.sans_cache else {}))
    offres = collecter(client, pages=args.pages, fiches=args.fiches, mot_cle=args.mot_cle)

    chemin = exporter_json(offres, args.sortie)
    print(f"\n{len(offres)} offres, {sum(o.description is not None for o in offres)} avec description")
    print(f"JSON : {chemin}")
    if args.csv:
        print(f"CSV  : {exporter_csv(offres, args.sortie.with_suffix('.csv'))}")


if __name__ == "__main__":
    main()
