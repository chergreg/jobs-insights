"""Preuve de concept de collecte des offres Remotive (cache local 24 h)."""

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://remotive.com/api/remote-jobs"
DOSSIER = Path(__file__).resolve().parent
DUREE_CACHE_SECONDES = 24 * 60 * 60


class NettoyeurHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.textes = []
        self.ignorer = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignorer += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignorer = max(0, self.ignorer - 1)

    def handle_data(self, texte):
        if self.ignorer == 0:
            self.textes.append(texte)


def nettoyer_description(html):
    if not html:
        return None
    nettoyeur = NettoyeurHTML()
    nettoyeur.feed(html)
    texte = " ".join(" ".join(nettoyeur.textes).split())
    return texte or None


def normaliser_localisation(localisation: str) -> str:
    """Normalise les accents et espaces pour comparer des mots complets."""
    texte = unicodedata.normalize("NFKD", localisation.casefold())
    texte = "".join(
        caractere for caractere in texte
        if not unicodedata.combining(caractere)
    )
    return " ".join(texte.split())


def extraire_province_code(localisation: str | None) -> str | None:
    """Renseigne une province seulement si la source donne un indice précis.

    « Canada », « Worldwide » et « North America » ne désignent aucune
    province. « Laval » seul reste ambigu (Québec ou France, par exemple).
    Cette preuve de concept ne couvre volontairement que QC et ON.
    """
    if not localisation or not localisation.strip():
        return None

    texte = normaliser_localisation(localisation)
    if re.search(r"\b(?:quebec|montreal|gatineau|sherbrooke|qc)\b", texte):
        return "QC"
    if re.search(r"\b(?:ontario|toronto|ottawa)\b", texte):
        return "ON"
    if re.search(r"\blaval\b", texte) and re.search(r"\bcanada\b", texte):
        return "QC"
    return None


def classifier_localisation(localisation: str | None) -> str:
    """Classe la zone déclarée sans confondre une région avec une province."""
    if not localisation or not localisation.strip():
        return "inconnue"

    texte = normaliser_localisation(localisation)
    usa = bool(re.search(r"\b(?:usa|us|united states|etats[- ]unis)\b", texte))
    canada = bool(re.search(r"\bcanada\b", texte))

    if re.search(r"\b(?:worldwide|anywhere|global)\b", texte):
        return "mondiale"
    if (
        re.search(r"\b(?:north america|amerique du nord|americas)\b", texte)
        or (canada and usa)
    ):
        return "amerique_du_nord"

    province = extraire_province_code(localisation)
    if province == "QC":
        return "quebec"
    if canada or province is not None:
        return "canada"
    if usa:
        return "etats_unis"
    return "autre"


class Offre(TypedDict):
    titre: str | None
    entreprise: str | None
    localisation: str | None
    categorie_localisation: str
    province_code: str | None
    date_publication: str | None
    description: str | None
    salaire: str | None
    url_originale: str | None


def consulter_api(limite: int) -> object:
    url = f"{API_URL}?{urlencode({'limit': limite})}"
    requete = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "jobs-insights-hendrix-livrable3/1.0 (prototype scolaire)",
    })
    with urlopen(requete, timeout=15) as reponse:
        return json.load(reponse)


def charger_reponse_avec_cache(limite: int, chemin: Path) -> object:
    """Réutilise la réponse d'une même requête Remotive pendant 24 h.

    Adaptation du cache de Kandet : la clef inclut ici le paramètre limit.
    Un cache absent, illisible, expiré ou corrompu déclenche une collecte.
    """
    url = f"{API_URL}?{urlencode({'limit': limite})}"

    if chemin.exists():
        try:
            cache = json.loads(chemin.read_text(encoding="utf-8"))
            if (
                isinstance(cache, dict)
                and cache.get("request_url") == url
                and isinstance(cache.get("payload"), dict)
                and isinstance(cache["payload"].get("jobs"), list)
            ):
                date_cache = datetime.fromisoformat(cache["fetched_at"])
                if date_cache.tzinfo is not None:
                    age = (datetime.now(timezone.utc) - date_cache).total_seconds()
                    if 0 <= age < DUREE_CACHE_SECONDES:
                        return cache["payload"]
        except (OSError, ValueError, KeyError, TypeError):
            # Le cache n'est qu'une optimisation, pas une source de vérité.
            pass

    reponse = consulter_api(limite)
    if not isinstance(reponse, dict) or not isinstance(reponse.get("jobs"), list):
        raise ValueError("La réponse Remotive doit contenir une liste 'jobs'.")

    chemin.parent.mkdir(parents=True, exist_ok=True)
    cache = {
        "request_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "payload": reponse,
    }
    chemin.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return reponse


def champ(offre: dict, cle: str) -> str | None:
    valeur = offre.get(cle)
    if valeur is None or isinstance(valeur, str):
        return valeur or None
    raise ValueError(f"Le champ {cle} doit contenir du texte ou être absent.")


def extraire_offres(reponse: object, limite: int) -> list[Offre]:
    if not isinstance(reponse, dict) or not isinstance(reponse.get("jobs"), list):
        raise ValueError("La réponse doit contenir une liste 'jobs'.")

    offres = []
    urls_vues = set()
    for offre in reponse["jobs"][:limite]:
        if not isinstance(offre, dict):
            raise ValueError("Chaque élément de 'jobs' doit être un objet.")
        url = champ(offre, "url")
        if url is not None and url in urls_vues:
            continue
        localisation = champ(offre, "candidate_required_location")
        offres.append(Offre(
            titre=champ(offre, "title"),
            entreprise=champ(offre, "company_name"),
            localisation=localisation,
            categorie_localisation=classifier_localisation(localisation),
            province_code=extraire_province_code(localisation),
            date_publication=champ(offre, "publication_date"),
            description=nettoyer_description(champ(offre, "description")),
            salaire=champ(offre, "salary"),
            url_originale=url,
        ))
        if url is not None:
            urls_vues.add(url)
    return offres


def exporter_json(chemin: Path, offres: list[Offre], simule: bool) -> None:
    export = {
        "source": "Remotive",
        "mode": "simule" if simule else "reel",
        "nombre_offres": len(offres),
        "offres": offres,
    }
    chemin.write_text(
        json.dumps(export, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reel", action="store_true",
                        help="Effectuer une requête à l'API publique.")
    parser.add_argument("--limite", type=int, choices=range(1, 11), default=3,
                        metavar="1-10", help="Nombre maximal d'offres (défaut : 3).")
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.reel:
            reponse = charger_reponse_avec_cache(
                args.limite, DOSSIER / "remotive-cache.json"
            )
        else:
            with (DOSSIER / "fixtures" / "reponse_simulee.json").open(
                encoding="utf-8"
            ) as fichier:
                reponse = json.load(fichier)
        offres = extraire_offres(reponse, args.limite)
        exporter_json(args.sortie, offres, simule=not args.reel)
    except HTTPError as erreur:
        message = f"Remotive a retourné HTTP {erreur.code}."
        if erreur.code == 429:
            message += " Attendez avant un prochain essai."
        print(message, file=sys.stderr)
        return 1
    except (OSError, ValueError) as erreur:
        print(f"Collecte ou export impossible : {erreur}", file=sys.stderr)
        return 1

    mode = "réel" if args.reel else "simulé"
    print(f"{len(offres)} offre(s) exportée(s) en mode {mode} vers {args.sortie}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
