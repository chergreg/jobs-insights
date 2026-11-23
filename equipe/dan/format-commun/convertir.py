"""Convertit mes offres du livrable 3 vers le format commun de la classe (modèle ``JobOffer`` du prof).

Format commun : ``equipe/gregory/livrable3/models.py`` (18 champs : id, titre, entreprise, lieu,
province, pays, url, source, source_partenaire, date_publication, type_poste, modalite, est_stage,
statut_stage, description, competences_cles, salaire, date_extraction). Même démarche que Kandet
et Ferdinand : un petit dossier à part qui lit mon fichier, sans rien changer à mon code.

Règles (aucune valeur devinée) :
- ``province`` nettoyée (« , QC » → « QC ») ; texte non reconnu → « Non spécifié » ;
- ``entreprise``, ``lieu``, ``province`` absents → « Non spécifié » (la valeur « absent » du modèle),
  jamais « QC » par défaut ;
- ``pays`` = « Canada » seulement si la province est un code canadien connu, sinon « Non spécifié » ;
- ``type_poste`` absent → ``None`` (le modèle mettrait « Temps plein » par défaut) ;
- ``statut_stage`` et ``competences_cles`` : lus dans le titre et la description (``livrable3/competences.py``) ;
  ``est_stage`` vaut ``True`` pour un stage confirmé ou possible, comme dans le modèle du prof ;
- ``date_extraction`` = date d'export de mon fichier ;
- mes champs en plus (GPS, ``doublons``) ne font pas partie du format commun : ils restent dans
  ``livrable3/data/offres_unifiees.json``.

Usage (depuis equipe/dan/format-commun) :
    python convertir.py                      # écrit offres_format_commun.json
    python convertir.py --csv                # et aussi offres_format_commun.csv (Excel)
    python convertir.py --echantillon 10     # et echantillon_format_commun.json (10 offres)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
LIVRABLE3 = DOSSIER.parent / "livrable3"
sys.path.insert(0, str(LIVRABLE3))

from competences import CONFIRME, NON_INDIQUE, detecter_competences, statut_stage  # noqa: E402
from scrapers.jsonld import CODES_PROVINCES, province as code_province  # noqa: E402

ENTREE_PAR_DEFAUT = LIVRABLE3 / "data" / "offres_unifiees.json"
NON_SPECIFIE = "Non spécifié"
CHAMPS = [
    "id", "titre", "entreprise", "lieu", "province", "pays", "url", "source", "source_partenaire",
    "date_publication", "type_poste", "modalite", "est_stage", "statut_stage", "description",
    "competences_cles", "salaire", "date_extraction",
]


def convertir_offre(offre: dict, date_extraction: str) -> dict:
    """Une offre de ``offres_unifiees.json`` → une offre au format commun."""
    # Nettoyée ici aussi : les fichiers produits avant le lot 9 peuvent contenir « , QC ».
    province = code_province((offre.get("province") or "").strip(" ,;"))
    statut = statut_stage(offre.get("titre"), offre.get("description"), offre.get("est_stage"))
    competences = list(offre.get("competences") or []) or detecter_competences(
        offre.get("titre"), offre.get("description"))
    return {
        "id": offre["id"],
        "titre": offre["titre"],
        "entreprise": offre.get("entreprise") or NON_SPECIFIE,
        "lieu": offre.get("lieu") or NON_SPECIFIE,
        "province": province or NON_SPECIFIE,
        "pays": "Canada" if province in CODES_PROVINCES else NON_SPECIFIE,
        "url": offre["url"],
        "source": offre["source"],
        "source_partenaire": offre.get("source_partenaire") or None,
        "date_publication": offre.get("date_publication") or None,
        "type_poste": offre.get("type_poste") or None,
        "modalite": offre.get("modalite") or None,
        "est_stage": statut != NON_INDIQUE,
        "statut_stage": statut,
        "description": offre.get("description") or None,
        "competences_cles": competences,
        "salaire": offre.get("salaire") or None,
        "date_extraction": date_extraction,
    }


def convertir(document: dict) -> list[dict]:
    """Toutes les offres d'un fichier produit par ``livrable3/main.py`` (ou par un scraper)."""
    if not isinstance(document, dict) or not isinstance(document.get("offres"), list):
        raise ValueError("ce fichier ne ressemble pas à un fichier d'offres produit par livrable3/main.py")
    date = str(document.get("date_export") or "")
    return [convertir_offre(offre, date) for offre in document["offres"]]


def ecrire_json(offres: list[dict], chemin: Path) -> Path:
    chemin.write_text(json.dumps(offres, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def ecrire_csv(offres: list[dict], chemin: Path) -> Path:
    """CSV pour Excel (utf-8-sig, « ; »), compétences séparées par des virgules, est_stage oui/non."""
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=CHAMPS, delimiter=";")
        ecrivain.writeheader()
        for offre in offres:
            ligne = dict(offre, competences_cles=", ".join(offre["competences_cles"]),
                         est_stage="oui" if offre["est_stage"] else "non")
            ecrivain.writerow({cle: "" if valeur is None else valeur for cle, valeur in ligne.items()})
    return chemin


def bilan(offres: list[dict]) -> str:
    confirmes = sum(o["statut_stage"] == CONFIRME for o in offres)
    possibles = sum(o["est_stage"] for o in offres) - confirmes
    avec_competences = sum(bool(o["competences_cles"]) for o in offres)
    return (f"{len(offres)} offres converties : {avec_competences} avec compétences, "
            f"{confirmes} stages confirmés, {possibles} stages possibles")


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(description="Convertit mes offres vers le format commun JobOffer.")
    analyseur.add_argument("--entree", type=Path, default=ENTREE_PAR_DEFAUT, help="offres_unifiees.json du livrable 3")
    analyseur.add_argument("--sortie", type=Path, default=DOSSIER / "offres_format_commun.json")
    analyseur.add_argument("--csv", action="store_true", help="écrire aussi le CSV pour Excel à côté du JSON")
    analyseur.add_argument("--echantillon", type=int, metavar="N",
                           help="écrire aussi echantillon_format_commun.json avec les N premières offres")
    args = analyseur.parse_args(arguments)

    try:
        offres = convertir(json.loads(args.entree.read_text(encoding="utf-8")))
    except (OSError, ValueError) as erreur:
        raise SystemExit(f"Impossible de lire {args.entree} : {erreur}\n"
                         "Lancez d'abord la collecte : cd ../livrable3 puis python main.py")

    print(bilan(offres))
    print(f"JSON : {ecrire_json(offres, args.sortie)}")
    if args.csv:
        print(f"CSV  : {ecrire_csv(offres, args.sortie.with_suffix('.csv'))}")
    if args.echantillon:
        chemin = ecrire_json(offres[: args.echantillon], args.sortie.with_name("echantillon_format_commun.json"))
        print(f"Échantillon ({min(args.echantillon, len(offres))} offres) : {chemin}")


if __name__ == "__main__":
    main()
