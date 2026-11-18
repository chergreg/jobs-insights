"""
main.py - Point d'entrée unifié et exécutable de la démonstration Livrable 3.

Permet de :
1. Charger ou exécuter la collecte des trois sources d'emplois québécoises et canadiennes
   en informatique (Guichet-Emplois Canada, Jobboom Québec, Remotive).
2. Appliquer le moteur d'unification et de déduplication multi-sources (pipeline.py).
3. Générer les deux fichiers d'export finaux consolidés :
   - data/offres_unifiees.json (format structuré complet indenté).
   - data/offres_unifiees.csv (encodé en utf-8-sig avec séparateur ';' pour compatibilité Excel Windows).
4. Afficher un rapport statistique exhaustif de la collecte et de la fusion.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import time
from typing import List

# Configuration du chemin d'import local
CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from pipeline import (
    export_to_csv,
    export_to_json,
    load_offers_from_json,
    unify_offers,
)
from scrapers.guichet_emplois import GuichetEmploisScraper
from scrapers.jobboom import JobboomScraper
from scrapers.remotive import RemotiveScraper


logger = logging.getLogger("Livrable3Main")


def parse_arguments() -> argparse.Namespace:
    """Analyse les arguments passés en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Pipeline d'unification et de déduplication multi-sources Livrable 3 (jobs-insights)."
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="guichet,jobboom,remotive",
        help="Sources à inclure, séparées par une virgule (ex: 'guichet,jobboom,remotive').",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Exécute les connecteurs de scraping au lieu de charger les jeux d'essai existants.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Désactive le cache local lors de la collecte par scraping (requêtes réelles).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite d'offres à extraire par source lors du scraping.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=str(CUR_DIR / "data" / "offres_unifiees.json"),
        help="Chemin de sortie du fichier JSON unifié (défaut: data/offres_unifiees.json).",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=str(CUR_DIR / "data" / "offres_unifiees.csv"),
        help="Chemin de sortie du fichier CSV unifié (défaut: data/offres_unifiees.csv).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Active l'affichage détaillé des logs d'exécution.",
    )
    return parser.parse_args()


def collect_from_datasets(selected_sources: List[str], data_dir: Path) -> List[JobOffer]:
    """Charge les offres depuis les jeux d'essai préexistants sous data/."""
    offers: List[JobOffer] = []

    file_mapping = {
        "guichet": data_dir / "offres_guichet_emplois.json",
        "jobboom": data_dir / "offres_jobboom.json",
        "remotive": data_dir / "offres_remotive.json",
    }

    for src_key in selected_sources:
        target_file = file_mapping.get(src_key)
        if target_file and target_file.is_file():
            loaded = load_offers_from_json(target_file)
            print(f" [Chargement] {target_file.name:<28} : {len(loaded):>4} offres chargées")
            offers.extend(loaded)
        else:
            print(f" [Avertissement] Fichier {target_file} introuvable.")

    return offers


def collect_from_scrapers(
    selected_sources: List[str],
    cache_root: Path,
    use_cache: bool,
    limit: int | None,
) -> List[JobOffer]:
    """Exécute les connecteurs de scraping pour collecter les offres en direct ou depuis le cache."""
    offers: List[JobOffer] = []

    if "guichet" in selected_sources:
        print("\n--- Collecte Guichet-Emplois Canada ---")
        ge_cache = cache_root / "guichet_emplois"
        scraper_ge = GuichetEmploisScraper(cache_dir=ge_cache, offline_mode=False)
        ge_limit = limit or 10
        try:
            raw_ge = scraper_ge.search(limit=ge_limit, max_pages=1, use_cache=use_cache)
            ge_offers = scraper_ge.enrich_offers(raw_ge, limit=ge_limit, use_cache=use_cache)
            print(f" -> Guichet-Emplois : {len(ge_offers)} offres collectées")
            offers.extend(ge_offers)
        except Exception as err:
            logger.error("Erreur lors de la collecte Guichet-Emplois : %s", err)

    if "jobboom" in selected_sources:
        print("\n--- Collecte Jobboom Québec ---")
        jb_cache = cache_root / "jobboom"
        scraper_jb = JobboomScraper(cache_dir=jb_cache, offline_mode=False)
        jb_limit = limit or 10
        max_p = 2 if (limit is None or limit > 15) else 1
        try:
            jb_offers = scraper_jb.search(limit=jb_limit, max_pages=max_p, use_cache=use_cache)
            print(f" -> Jobboom : {len(jb_offers)} offres collectées")
            offers.extend(jb_offers)
        except Exception as err:
            logger.error("Erreur lors de la collecte Jobboom : %s", err)

    if "remotive" in selected_sources:
        print("\n--- Collecte Remotive ---")
        rem_cache = cache_root / "remotive"
        scraper_rem = RemotiveScraper(cache_dir=rem_cache, offline_mode=False)
        rem_limit = limit or 15
        try:
            rem_offers = scraper_rem.scrape_offers(
                category="software-development",
                geo_filter="canada_eligible",
                limit=rem_limit,
                refresh=not use_cache,
                use_cache=use_cache,
            )
            print(f" -> Remotive : {len(rem_offers)} offres collectées")
            offers.extend(rem_offers)
        except Exception as err:
            logger.error("Erreur lors de la collecte Remotive : %s", err)

    return offers


def main() -> int:
    """Fonction principale orchestrant la collecte, l'unification et les exports."""
    args = parse_arguments()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    print("==================================================================")
    print("      LIVRABLE 3 : PIPELINE D'UNIFICATION & EXPORTS FINAUX       ")
    print("                   Projet jobs-insights                          ")
    print("==================================================================")

    # 1. Sélection des sources
    raw_sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    selected_sources = [s for s in raw_sources if s in {"guichet", "jobboom", "remotive"}]
    if not selected_sources:
        print("Erreur : Aucune source valide sélectionnée ('guichet', 'jobboom', 'remotive').")
        return 1

    print(f"Sources sélectionnées : {', '.join(selected_sources)}")

    data_dir = CUR_DIR / "data"
    cache_dir = CUR_DIR / "cache"

    start_time = time.time()

    # 2. Collecte ou chargement des offres
    if args.scrape:
        print(f"Mode : Collecte par connecteurs (cache: {not args.no_cache})")
        raw_offers = collect_from_scrapers(
            selected_sources=selected_sources,
            cache_root=cache_dir,
            use_cache=not args.no_cache,
            limit=args.limit,
        )
    else:
        print("Mode : Chargement des jeux d'essai consolidés (dossier data/)")
        raw_offers = collect_from_datasets(
            selected_sources=selected_sources,
            data_dir=data_dir,
        )

    if not raw_offers:
        print("Aucune offre collectée. Fin de l'exécution.")
        return 1

    # 3. Exécution du pipeline d'unification et de déduplication
    print("\nExécution de l'unification et de la déduplication multi-sources...")
    unified_offers, stats = unify_offers(raw_offers)

    # 4. Exports finaux (JSON et CSV)
    json_path = Path(args.output_json)
    csv_path = Path(args.output_csv)

    print(f"\nGénération des exports finaux :")
    export_to_json(unified_offers, json_path)
    export_to_csv(unified_offers, csv_path)

    json_size_kb = json_path.stat().st_size / 1024
    csv_size_kb = csv_path.stat().st_size / 1024

    print(f" [Export JSON] {json_path} ({json_size_kb:.1f} Ko, {len(unified_offers)} offres)")
    print(f" [Export CSV]  {csv_path} ({csv_size_kb:.1f} Ko, encodage utf-8-sig, délimiteur ';')")

    # 5. Affichage du rapport statistique
    elapsed = time.time() - start_time
    print(f"\nTemps d'exécution : {elapsed:.2f} secondes\n")
    print(stats.format_summary())

    return 0


if __name__ == "__main__":
    sys.exit(main())
