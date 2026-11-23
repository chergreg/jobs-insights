"""Convertit mes offres (offres.json) vers le format commun de la classe.

Le format commun est le modèle JobOffer proposé par Gregory dans son plan du
livrable 3 (equipe/gregory/livrable3/plan.md, section 4, et models.py) :
18 champs en français (id, titre, entreprise, lieu, province, competences_cles...).

Ce dossier est indépendant de mon projet : il lit seulement le fichier
offres.json produit par 03-amelioration-preuve-de-concept/main.py.
On peut le supprimer sans rien casser.

    python convertir.py                      # écrit offres_format_commun.json
    python convertir.py --csv                # et aussi offres_format_commun.csv (Excel)
    python convertir.py --echantillon 10     # petit fichier d'exemple

Règle suivie : une information absente n'est pas devinée. Le modèle de
Gregory met « QC » et « Canada » par défaut ; ici, une offre Remotive sans
province connue reçoit « Non spécifié ».
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import unicodedata


DOSSIER = Path(__file__).resolve().parent
ENTREE_PAR_DEFAUT = DOSSIER.parent / "03-amelioration-preuve-de-concept" / "offres.json"
NON_SPECIFIE = "Non spécifié"
# Source de mon projet -> (nom dans le format commun, préfixe de l'identifiant)
SOURCES = {"Guichet-Emplois": ("guichet-emplois", "ge"), "Remotive": ("remotive", "rem")}
CHAMPS = [
    "id", "titre", "entreprise", "lieu", "province", "pays", "url", "source", "source_partenaire",
    "date_publication", "type_poste", "modalite", "est_stage", "statut_stage", "description",
    "competences_cles", "salaire", "date_extraction",
]


def _plat(texte: str) -> str:
    """Minuscules sans accents."""
    texte = unicodedata.normalize("NFKD", (texte or "").casefold())
    return "".join(c for c in texte if not unicodedata.combining(c))


def type_poste(offre: dict) -> str | None:
    """Valeurs du format commun : Temps plein, Temps partiel, Contrat, Stage, Pigiste / Freelance.

    None si l'offre ne le dit pas (le modèle de Gregory mettrait « Temps plein » par défaut).
    """
    if offre.get("stage_status") == "confirmed_stage":
        return "Stage"
    texte = _plat(offre.get("job_type", "")).replace("_", " ")
    if "freelance" in texte or "pigiste" in texte:
        return "Pigiste / Freelance"
    if "contrat" in texte or "contract" in texte or "duree fixe" in texte:
        return "Contrat"
    if "partiel" in texte or "part time" in texte:
        return "Temps partiel"
    if "plein" in texte or "full time" in texte or "permanent" in texte:
        return "Temps plein"
    return None


def convertir_offre(offre: dict, date_extraction: str) -> dict:
    """Une offre de mon offres.json -> une offre au format commun."""
    premiere = offre["source_records"][0]
    nom_source, prefixe = SOURCES.get(premiere["source"], (_plat(premiere["source"]).replace(" ", "-"), "x"))
    origine = premiere.get("origin_site") or ""
    est_guichet = premiere["source"] == "Guichet-Emplois"
    # Technologies puis compétences générales, sans doublon.
    competences = list(dict.fromkeys(list(offre.get("technologies") or []) + list(offre.get("skills") or [])))
    return {
        "id": f"{prefixe}-{premiere['source_id']}",
        "titre": offre.get("title") or NON_SPECIFIE,
        "entreprise": offre.get("employer") or NON_SPECIFIE,
        "lieu": offre.get("location") or NON_SPECIFIE,
        "province": offre.get("province") or NON_SPECIFIE,
        "pays": "Canada" if est_guichet else NON_SPECIFIE,  # le Guichet-Emplois ne publie que des offres au Canada
        "url": premiere.get("url", ""),
        "source": nom_source,
        "source_partenaire": origine if est_guichet and origine and origine != "Guichet-Emplois" else None,
        "date_publication": (offre.get("published_at") or "")[:10] or None,
        "type_poste": type_poste(offre),
        "modalite": offre.get("work_mode") or None,
        "est_stage": offre.get("stage_status") == "confirmed_stage",
        "statut_stage": offre.get("stage_status") or "not_indicated",
        "description": offre.get("description") or None,
        "competences_cles": competences,
        "salaire": offre.get("salary") or None,
        "date_extraction": date_extraction,
    }


def convertir(document: dict) -> list[dict]:
    """Toutes les offres d'un offres.json."""
    if not isinstance(document, dict) or not isinstance(document.get("offers"), list):
        raise ValueError("Ce fichier ne ressemble pas à un offres.json produit par main.py.")
    return [convertir_offre(offre, str(document.get("generated_at", ""))) for offre in document["offers"]]


def ecrire_csv(offres: list[dict], chemin: Path) -> None:
    """CSV pour Excel (utf-8-sig, séparateur « ; »), compétences séparées par des virgules."""
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=CHAMPS, delimiter=";")
        writer.writeheader()
        for offre in offres:
            ligne = dict(offre)
            ligne["competences_cles"] = ", ".join(offre["competences_cles"])
            ligne["est_stage"] = "oui" if offre["est_stage"] else "non"
            writer.writerow({cle: "" if valeur is None else valeur for cle, valeur in ligne.items()})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convertir offres.json vers le format commun de la classe.")
    parser.add_argument("--entree", type=Path, default=ENTREE_PAR_DEFAUT, help="offres.json produit par main.py.")
    parser.add_argument("--sortie", type=Path, default=DOSSIER / "offres_format_commun.json")
    parser.add_argument("--csv", type=Path, nargs="?", const=DOSSIER / "offres_format_commun.csv",
                        help="Écrire aussi un CSV pour Excel.")
    parser.add_argument("--echantillon", type=int, metavar="N",
                        help="Écrire aussi echantillon_format_commun.json avec les N premières offres.")
    args = parser.parse_args(argv)

    try:
        offres = convertir(json.loads(args.entree.read_text(encoding="utf-8")))
    except (OSError, ValueError) as erreur:
        raise SystemExit(f"Impossible de lire {args.entree} : {erreur}\n"
                         "Lancez d'abord la collecte : python ..\\03-amelioration-preuve-de-concept\\main.py")

    args.sortie.write_text(json.dumps(offres, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(offres)} offres converties : {args.sortie}")
    if args.csv:
        ecrire_csv(offres, args.csv)
        print(f"CSV pour Excel : {args.csv}")
    if args.echantillon:
        chemin = DOSSIER / "echantillon_format_commun.json"
        chemin.write_text(json.dumps(offres[: args.echantillon], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Échantillon ({min(args.echantillon, len(offres))} offres) : {chemin}")


if __name__ == "__main__":
    main()
