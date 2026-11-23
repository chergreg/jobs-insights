"""Point d'entrée CLI pour le Livrable 3 — Enrichissement et normalisation du POC Adzuna Canada.

Fonctionne par défaut 100 % hors ligne (`--from-l2`) à partir des 10 fichiers JSON collectés
lors du Livrable 2 dans `../02-preuve-de-concept-scraping/adzuna_test_output/`.
Permet également une collecte en direct (`--live`) si les variables d'environnement
`ADZUNA_APP_ID` et `ADZUNA_APP_KEY` sont configurées.

Génère trois fichiers d'export dans `data/` :
- `offres_adzuna_v3.json` : offres enrichies avec provenance (API vs description) et statistiques ;
- `offres_adzuna_v3.csv` : tableau complet encodé en `utf-8-sig` (séparateur `;`) pour Excel sous Windows ;
- `offres_format_commun.json` : les mêmes offres converties dans les 18 champs du format commun de la classe.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from collecteur import (
    ClientAdzuna,
    DOSSIER_SORTIE_L2,
    charger_reponses_locales,
    obtenir_identifiants_env,
)
from pipeline import (
    exporter_csv_enrichi,
    exporter_format_commun_json,
    exporter_json_enrichi,
    executer_pipeline_documents,
)


DOSSIER_COURANT = Path(__file__).resolve().parent
DOSSIER_DATA = DOSSIER_COURANT / "data"

VILLES_DEFAUT = ["Québec, Québec", "Montréal, Québec"]
MOTS_CLES_DEFAUT = [
    "développeur logiciel",
    "développeur web",
    "programmeur",
    "technicien informatique",
    "administrateur système",
    "DevOps",
]


def construire_parseur() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Livrable 3 — Enrichissement des offres Adzuna Canada depuis les descriptions."
    )
    parser.add_argument(
        "--dossier-entree",
        type=Path,
        default=DOSSIER_SORTIE_L2,
        help="Dossier contenant les fichiers JSON de recherche Adzuna (défaut: adzuna_test_output du L2).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Interroge l'API Adzuna en direct au lieu de lire les fichiers JSON locaux du Livrable 2.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=2,
        help="Nombre maximal de pages par recherche en mode --live (défaut: 2).",
    )
    parser.add_argument(
        "--filtrer-ti-format-commun",
        action="store_true",
        help="Exclut les offres signalées hors-TI uniquement dans l'export offres_format_commun.json.",
    )
    parser.add_argument(
        "--dossier-sortie",
        type=Path,
        default=DOSSIER_DATA,
        help="Dossier de destination pour les exports JSON et CSV (défaut: data/).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construire_parseur()
    args = parser.parse_args(argv)

    erreurs_collecte: list[str] = []
    if args.live:
        creds = obtenir_identifiants_env()
        client = ClientAdzuna(credentials=creds)
        dossier_cache = args.dossier_sortie / "cache_raw"
        documents, erreurs_collecte = client.collecter_campagne(
            locations=VILLES_DEFAUT,
            keywords=MOTS_CLES_DEFAUT,
            max_pages=args.max_pages,
            dossier_cache=dossier_cache,
        )
        if erreurs_collecte:
            print(f"[Avertissement] {len(erreurs_collecte)} recherche(s) ont rencontré une erreur :", file=sys.stderr)
            for err in erreurs_collecte:
                print(f"  - {err}", file=sys.stderr)
    else:
        documents = charger_reponses_locales(args.dossier_entree)

    offres, stats = executer_pipeline_documents(documents)

    chemin_json = exporter_json_enrichi(offres, stats, args.dossier_sortie / "offres_adzuna_v3.json")
    chemin_csv = exporter_csv_enrichi(offres, args.dossier_sortie / "offres_adzuna_v3.csv")
    chemin_commun = exporter_format_commun_json(
        offres,
        args.dossier_sortie / "offres_format_commun.json",
        filtrer_ti=args.filtrer_ti_format_commun,
    )

    print(stats.formater_rapport_console())
    print("\nFichiers générés :")
    print(f"  - JSON enrichi (avec provenance) : {chemin_json}")
    print(f"  - CSV Excel (utf-8-sig, ';')     : {chemin_csv}")
    print(f"  - JSON Format commun (18 champs) : {chemin_commun}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
