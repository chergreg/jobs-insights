"""
run_demo_remotive.py - Démonstration et test en direct du connecteur Remotive bonifié.

Permet de tester :
1. L'appel à l'API REST publique Remotive (/api/remote-jobs).
2. L'application stricte de la politique de cache local 24 h (respectant la limite de 4 requêtes/jour).
3. Le filtrage géographique précis : ciblage des offres ouvertes au Canada / Québec et télétravail étudiant.
4. La détection native et contextuelle des stages (job_type == 'internship' et filtres sémantiques).
5. La conformité totale au modèle pivot Pydantic v2 JobOffer.

Usage :
    python run_demo_remotive.py [--limit 10] [--geo-filter canada_eligible] [--stage-only] [--save-dataset] [--no-cache]
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from scrapers.remotive import (
    REMOTIVE_CACHE_HOURS,
    REMOTIVE_MAX_REQUESTS_PER_DAY,
    RemotiveScraper,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test et démonstration du collecteur Remotive bonifié (API REST + télétravail / stages)."
    )
    parser.add_argument("--limit", type=int, default=15, help="Nombre maximal d'offres à afficher (défaut : 15)")
    parser.add_argument(
        "--geo-filter",
        type=str,
        default="canada_eligible",
        choices=["canada_eligible", "canada_only", "quebec_only", "all"],
        help="Niveau de filtrage géographique (défaut : canada_eligible)",
    )
    parser.add_argument("--category", type=str, default="", help="Catégorie Remotive ciblée (ex: software-development, data)")
    parser.add_argument("--search", type=str, default="", help="Mot-clé de recherche optionnel")
    parser.add_argument("--stage-only", action="store_true", help="Conserver uniquement les offres qualifiées de stages")
    parser.add_argument("--no-cache", action="store_true", help="Forcer un appel réseau vers l'API Remotive")
    parser.add_argument("--save-dataset", action="store_true", help="Enregistrer les offres dans data/offres_remotive.json")
    args = parser.parse_args()

    use_cache = not args.no_cache
    print("\n" + "=" * 75)
    print("  DÉMONSTRATION EN DIRECT — CONNECTEUR REMOTIVE BONIFIÉ (API REST)")
    print("=" * 75)
    print(f" • Mode cache          : {'Activé (cache local 24h)' if use_cache else 'Désactivé (appel API réel forcé)'}")
    print(f" • Règle d'usage API   : Max {REMOTIVE_MAX_REQUESTS_PER_DAY} requêtes/jour recommandées par Remotive")
    print(f" • Filtre géographique : '{args.geo_filter}'")
    if args.category:
        print(f" • Catégorie ciblée    : '{args.category}'")
    if args.search:
        print(f" • Recherche           : '{args.search}'")
    print(f" • Filtre stage        : {'Activé (stages uniquement)' if args.stage_only else 'Tous types de contrats'}")
    print(f" • Limite maximale     : {args.limit} offre(s)")
    print("-" * 75)

    scraper = RemotiveScraper(cache_hours=REMOTIVE_CACHE_HOURS)
    cache_file = scraper.get_cache_file(args.category if args.category else None)
    is_fresh = scraper.is_cache_fresh(cache_file)

    print(f"\n[Étape 1/2] Récupération du payload JSON Remotive...")
    if use_cache and is_fresh:
        print(f"  -> Cache local valide détecté (< {REMOTIVE_CACHE_HOURS}h) : {cache_file.name}")
        print("  -> Aucun appel réseau émis (préservation du quota de requêtes).")
    else:
        print("  -> Requête HTTP GET vers https://remotive.com/api/remote-jobs...")

    t0 = time.time()
    offers = scraper.scrape_offers(
        category=args.category if args.category else None,
        search=args.search if args.search else None,
        geo_filter=args.geo_filter,
        category_filter=True,
        stage_only=args.stage_only,
        limit=args.limit,
        refresh=args.no_cache,
        use_cache=use_cache,
    )
    elapsed = time.time() - t0
    source_status = "CACHE DISQUE" if (use_cache and is_fresh and not args.no_cache) else f"API RÉSEAU ({elapsed:.2f}s)"

    print(f"[OK] {len(offers)} offre(s) sélectionnée(s) et normalisée(s) via {source_status} en {elapsed:.3f} s.")

    if not offers:
        print("\nAucune offre ne correspond aux critères sélectionnés.")
        return

    # Synthèse statistique
    type_counts = Counter(o.type_poste for o in offers)
    stage_counts = Counter(o.statut_stage for o in offers)
    lieu_counts = Counter(o.lieu for o in offers)
    all_skills = [s for o in offers for s in o.competences_cles]
    top_skills = Counter(all_skills).most_common(8)

    print("\n" + "=" * 75)
    print("  SYNTHÈSE STATISTIQUE DE LA COLLECTE")
    print("=" * 75)
    print(f" • Répartition contrats : {dict(type_counts)}")
    print(f" • Statut des stages    : {dict(stage_counts)} (Total stages : {sum(1 for o in offers if o.est_stage)})")
    print(f" • Répartition des lieux : {dict(lieu_counts)}")
    if top_skills:
        print(f" • Top technologies     : {', '.join(f'{k} ({v})' for k, v in top_skills)}")
    print("-" * 75)

    # Affichage des fiches
    print("\n[Étape 2/2] Aperçu détaillé des offres normalisées :")
    for idx, o in enumerate(offers, start=1):
        stage_tag = " [STAGE CONFIRMÉ]" if o.statut_stage == "confirmed_stage" else (" [STAGE POSSIBLE]" if o.est_stage else "")
        print(f"\n--- [Offre #{idx}] {o.id}{stage_tag} ---")
        print(f" • Titre              : {o.titre}")
        print(f" • Employeur          : {o.entreprise}")
        print(f" • Localisation       : {o.lieu} (Pays: {o.pays})")
        print(f" • Modalité / Contrat : {o.modalite} | {o.type_poste}")
        print(f" • Date publication   : {o.date_publication or 'Non spécifiée'}")
        print(f" • Rémunération       : {o.salaire or 'Non spécifiée (conforme AGENTS.md)'}")
        print(f" • Compétences ({len(o.competences_cles)})   : {', '.join(o.competences_cles) if o.competences_cles else 'Aucune détectée'}")
        print(f" • URL source         : {o.url}")
        if o.description:
            apercu_desc = o.description[:130].strip() + "..."
            print(f" • Description aperçu : {apercu_desc}")

    # Enregistrement optionnel du dataset
    if args.save_dataset:
        out_file = CUR_DIR / "data" / "offres_remotive.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        dump_data = [o.model_dump() for o in offers]
        out_file.write_text(
            json.dumps(dump_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        print(f"\n[SAUVEGARDE] {len(offers)} offres enregistrées dans : {out_file}")


if __name__ == "__main__":
    main()
