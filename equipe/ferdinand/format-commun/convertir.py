"""Convertit mes offres Welcome to the Jungle vers le format commun de la classe.

Le format commun est le modèle JobOffer proposé par Gregory
(equipe/gregory/livrable3/models.py et plan.md, section 4) : 18 champs en
français (id, titre, entreprise, lieu, province, pays, url, source...).

Ce dossier réutilise la collecte de mon livrable 3
(03-amelioration-preuve-de-concept/poc_wttj_v2.py) sans la modifier.
On peut le supprimer sans rien casser.

    python convertir.py                                  # 4 mots-clés, Québec
    python convertir.py --mot-cle stage --mot-cle data   # mots-clés choisis
    python convertir.py --csv                            # + CSV pour Excel
    python convertir.py --echantillon 10                 # + petit fichier d'exemple

Règle suivie : une information absente n'est pas devinée. Le modèle de Gregory
met « QC », « Canada » et « Temps plein » par défaut ; ici, chaque champ est
rempli explicitement, avec « Non spécifié » ou None quand l'API ne le donne pas.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
DOSSIER_L3 = DOSSIER.parent / "03-amelioration-preuve-de-concept"

NON_SPECIFIE = "Non spécifié"
SOURCE = "welcome-to-the-jungle"
MOTS_CLES_PAR_DEFAUT = ["stage", "développeur", "data", "informatique"]

CHAMPS = [
    "id", "titre", "entreprise", "lieu", "province", "pays", "url", "source", "source_partenaire",
    "date_publication", "type_poste", "modalite", "est_stage", "statut_stage", "description",
    "competences_cles", "salaire", "date_extraction",
]

# Valeurs de l'API (contract_type) -> valeurs du format commun.
TYPES_POSTE = {
    "full_time": "Temps plein",
    "part_time": "Temps partiel",
    "internship": "Stage",
    "apprenticeship": "Alternance",
    "temporary": "Contrat",
    "freelance": "Pigiste / Freelance",
}
# Valeurs de l'API (remote) -> modalité du format commun.
MODALITES = {
    "no": "Sur place",
    "punctual": "Télétravail occasionnel",
    "partial": "Hybride",
    "fulltime": "Télétravail",
}
PERIODES = {"hourly": "de l'heure", "daily": "par jour", "weekly": "par semaine",
            "monthly": "par mois", "yearly": "par an"}
PAYS = {"CA": "Canada", "FR": "France", "US": "États-Unis", "GB": "Royaume-Uni",
        "BE": "Belgique", "CH": "Suisse", "ES": "Espagne", "DE": "Allemagne"}
# Villes connues du Québec : sert seulement à remplir « province ».
# Une ville absente de cette liste donne « Non spécifié » (pas de supposition).
VILLES_QUEBEC = {"montreal", "quebec", "laval", "gatineau", "longueuil", "sherbrooke",
                 "levis", "trois-rivieres", "saguenay", "terrebonne", "brossard"}
MOTS_STAGE = ("stage", "stagiaire", "intern", "internship", "alternance")


def _plat(texte: str | None) -> str:
    """Minuscules sans accents (« Montréal » -> « montreal »)."""
    texte = unicodedata.normalize("NFKD", (texte or "").casefold())
    return "".join(c for c in texte if not unicodedata.combining(c))


def _bureaux(offre: dict) -> list[dict]:
    """Bureaux de l'offre : `offices`, sinon `office`."""
    bureaux = offre.get("offices") or ([offre["office"]] if offre.get("office") else [])
    return [b for b in bureaux if isinstance(b, dict)]


def lieu_province_pays(offre: dict) -> tuple[str, str, str]:
    """Garde en priorité les bureaux au Canada (le projet vise le Québec)."""
    bureaux = _bureaux(offre)
    canadiens = [b for b in bureaux if b.get("country_code") == "CA"]
    choisis = canadiens or bureaux
    if not choisis:
        return NON_SPECIFIE, NON_SPECIFIE, NON_SPECIFIE

    villes = list(dict.fromkeys(b["city"] for b in choisis if b.get("city")))
    lieu = ", ".join(villes) or NON_SPECIFIE

    code = choisis[0].get("country_code")
    pays = PAYS.get(code, code) if code else NON_SPECIFIE

    province = NON_SPECIFIE
    if canadiens and villes and all(_plat(v) in VILLES_QUEBEC for v in villes):
        province = "QC"
    return lieu, province, pays


def statut_stage(offre: dict) -> str:
    """confirmed_stage si le contrat est un stage, possible_stage si le titre en parle."""
    if offre.get("contract_type") in ("internship", "apprenticeship"):
        return "confirmed_stage"
    titre = _plat(offre.get("name"))
    if any(mot in titre for mot in MOTS_STAGE):
        return "possible_stage"
    return "not_indicated"


def salaire(offre: dict) -> str | None:
    """Texte lisible à partir de salary_min / salary_max, sinon None."""
    mini, maxi = offre.get("salary_min"), offre.get("salary_max")
    if mini is None and maxi is None:
        return None
    devise = offre.get("salary_currency") or ""
    if mini is not None and maxi is not None:
        montant = f"{mini:g} à {maxi:g}"
    elif maxi is not None:
        montant = f"jusqu'à {maxi:g}"
    else:
        montant = f"à partir de {mini:g}"
    periode = PERIODES.get(offre.get("salary_period"), "")
    return " ".join(p for p in (montant, devise, periode) if p)


def convertir_offre(offre: dict, date_extraction: str) -> dict | None:
    """Une offre brute de l'API -> une offre au format commun.

    Renvoie None si l'offre n'a pas les champs obligatoires du modèle (id, titre, url).
    """
    entreprise = offre.get("organization") or {}
    identifiant = offre.get("reference") or offre.get("slug")
    titre = offre.get("name")
    if not (identifiant and titre and entreprise.get("slug") and offre.get("slug")):
        return None

    lieu, province, pays = lieu_province_pays(offre)
    statut = statut_stage(offre)
    date_pub = offre.get("published_at")
    return {
        "id": f"wttj-{identifiant}",
        "titre": titre,
        "entreprise": entreprise.get("name") or NON_SPECIFIE,
        "lieu": lieu,
        "province": province,
        "pays": pays,
        "url": ("https://www.welcometothejungle.com/fr/companies/"
                f"{entreprise['slug']}/jobs/{offre['slug']}"),
        "source": SOURCE,
        "source_partenaire": None,
        "date_publication": date_pub[:10] if date_pub else None,
        "type_poste": TYPES_POSTE.get(offre.get("contract_type")),
        "modalite": MODALITES.get(offre.get("remote")),
        "est_stage": statut == "confirmed_stage",
        "statut_stage": statut,
        "description": None,       # absente de la liste de résultats de l'API
        "competences_cles": [],    # pas de description -> pas de compétences détectées
        "salaire": salaire(offre),
        "date_extraction": date_extraction,
    }


def convertir(offres_brutes: list[dict], date_extraction: str,
              canada_seulement: bool = True) -> list[dict]:
    """Convertit, retire les doublons (même id) et garde le Canada si demandé."""
    resultat, vus = [], set()
    for brute in offres_brutes:
        offre = convertir_offre(brute, date_extraction)
        if offre is None or offre["id"] in vus:
            continue
        if canada_seulement and offre["pays"] != "Canada":
            continue
        vus.add(offre["id"])
        resultat.append(offre)
    return resultat


def ecrire_json(offres: list[dict], chemin: Path) -> None:
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)


def ecrire_csv(offres: list[dict], chemin: Path) -> None:
    """CSV pour Excel en français (utf-8-sig, séparateur `;`)."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        writer.writeheader()
        for offre in offres:
            ligne = dict(offre)
            ligne["competences_cles"] = ", ".join(offre["competences_cles"])
            writer.writerow(ligne)


def collecter_brutes(mots_cles: list[str], max_pages: int) -> list[dict]:
    """Réutilise la collecte de mon livrable 3 pour chaque mot-clé (Québec)."""
    sys.path.insert(0, str(DOSSIER_L3))
    import poc_wttj_v2  # import ici : les tests hors ligne n'en ont pas besoin

    brutes = []
    for i, mot in enumerate(mots_cles):
        if i:
            time.sleep(poc_wttj_v2.PAUSE_SECONDES)
        print(f"\nMot-clé « {mot} »")
        brutes.extend(poc_wttj_v2.collecter(mot, poc_wttj_v2.LIEUX_QUEBEC, max_pages))
    return brutes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Offres WTTJ au format commun JobOffer")
    parser.add_argument("--mot-cle", action="append", dest="mots_cles",
                        help="répétable ; par défaut : " + ", ".join(MOTS_CLES_PAR_DEFAUT))
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--csv", action="store_true", help="écrit aussi le CSV")
    parser.add_argument("--echantillon", type=int, default=0,
                        help="écrit aussi un échantillon de N offres")
    args = parser.parse_args(argv)

    mots_cles = args.mots_cles or MOTS_CLES_PAR_DEFAUT
    brutes = collecter_brutes(mots_cles, args.max_pages)
    date_extraction = datetime.now(timezone.utc).isoformat()
    offres = convertir(brutes, date_extraction)

    print(f"\n{len(brutes)} offres reçues, {len(offres)} offres uniques au Canada")
    stages = sum(o["est_stage"] for o in offres)
    print(f"dont {stages} stage(s) confirmé(s)")

    ecrire_json(offres, DOSSIER / "offres_format_commun.json")
    print("Fichier créé :", DOSSIER / "offres_format_commun.json")
    if args.csv:
        ecrire_csv(offres, DOSSIER / "offres_format_commun.csv")
        print("Fichier créé :", DOSSIER / "offres_format_commun.csv")
    if args.echantillon:
        ecrire_json(offres[:args.echantillon], DOSSIER / "echantillon_format_commun.json")
        print("Fichier créé :", DOSSIER / "echantillon_format_commun.json")


if __name__ == "__main__":
    main()
