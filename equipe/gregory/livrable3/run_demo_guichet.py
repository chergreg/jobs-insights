"""
run_demo_guichet.py - Script de démonstration et de test en direct du connecteur Guichet-Emplois.

Permet de tester :
1. La connectivité en direct et le respect des règles robots.txt.
2. La recherche en ligne par codes CNP TI au Québec.
3. L'enrichissement sémantique RDFa et repli DOM des fiches détaillées.
4. L'efficacité du cache local (zéro appel réseau lors de ré-exécutions).

Usage :
    python run_demo_guichet.py [--limit 5] [--no-cache] [--enrich]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from scrapers.guichet_emplois import GuichetEmploisScraper, GUICHET_DELAY_SECONDS


def main() -> None:
    parser = argparse.ArgumentParser(description="Test en direct du collecteur Guichet-Emplois Canada.")
    parser.add_argument("--limit", type=int, default=5, help="Nombre maximal d'offres à collecter (défaut : 5)")
    parser.add_argument("--pages", type=int, default=1, help="Nombre de pages de recherche à parcourir (défaut : 1)")
    parser.add_argument("--enrich", action="store_true", default=True, help="Enrichir les fiches détaillées via RDFa / DOM")
    parser.add_argument("--no-cache", action="store_true", help="Désactiver la lecture du cache local")
    parser.add_argument("--term", type=str, default="", help="Mot-clé optionnel de recherche (ex: python, stage)")
    args = parser.parse_args()

    use_cache = not args.no_cache
    print("\n" + "=" * 70)
    print("  DÉMONSTRATION EN DIRECT — CONNECTEUR GUICHET-EMPLOIS CANADA")
    print("=" * 70)
    print(f" • Mode cache      : {'Activé (cache local 24h)' if use_cache else 'Désactivé (100% requêtes réelles)'}")
    print(f" • Filtre CNP      : 14 codes du secteur informatique (TI)")
    print(f" • Province cible  : Québec (QC)")
    if args.term:
        print(f" • Mot-clé ciblé   : '{args.term}'")
    print(f" • Limite d'offres : {args.limit} offre(s) max sur {args.pages} page(s)")
    print(f" • Temporisation   : {GUICHET_DELAY_SECONDS}s par appel réseau direct (conforme robots.txt)")
    print("-" * 70)

    scraper = GuichetEmploisScraper(delai_secondes=GUICHET_DELAY_SECONDS)

    # 1. Étape Recherche
    start_time = time.time()
    print("\n[Étape 1/2] Recherche des offres en cours...")

    def progress_cb(page: int, count: int, total: int | None):
        total_str = f"sur {total} au total" if total else ""
        print(f"  -> Page {page} analysée : {count} offre(s) collectée(s) {total_str}")

    offers = scraper.search(
        term=args.term,
        province="QC",
        max_pages=args.pages,
        limit=args.limit,
        use_cache=use_cache,
        progress=progress_cb
    )

    elapsed_search = time.time() - start_time
    print(f"[OK] {len(offers)} offre(s) récupérée(s) en {elapsed_search:.2f} s.")

    if not offers:
        print("Aucune offre trouvée.")
        return

    # 2. Étape Enrichissement détaillé
    if args.enrich:
        print(f"\n[Étape 2/2] Enrichissement détaillé RDFa / DOM ({len(offers)} fiches)...")
        enriched_offers = []
        for idx, off in enumerate(offers, start=1):
            t0 = time.time()
            enr = scraper.enrich_offer(off, use_cache=use_cache)
            dt = time.time() - t0
            from_cache = dt < 0.1
            status_source = "CACHE" if from_cache else f"RÉSEAU ({dt:.1f}s)"
            print(f"  [{idx}/{len(offers)}] {enr.id} ({status_source}) -> {enr.titre[:45]}...")
            enriched_offers.append(enr)
        offers = enriched_offers

    # 3. Affichage des fiches standardisées
    print("\n" + "=" * 70)
    print(f"  RÉSULTATS DE L'EXTRACTION ({len(offers)} offres normalisées)")
    print("=" * 70)

    for idx, o in enumerate(offers, start=1):
        print(f"\n--- [Offre #{idx}] {o.id} ---")
        print(f" • Titre              : {o.titre}")
        print(f" • Employeur          : {o.entreprise}")
        print(f" • Lieu               : {o.lieu} (Province: {o.province})")
        print(f" • Salaire            : {o.salaire or 'Non spécifié'}")
        print(f" • Date publication   : {o.date_publication or 'Non spécifiée'}")
        print(f" • Modalité travail   : {o.modalite or 'Non spécifiée'}")
        print(f" • Type contrat       : {o.type_poste or 'Non spécifié'}")
        print(f" • Statut stage       : {'OUI (Confirmé)' if o.est_stage else 'Non'}")
        print(f" • Source partenaire  : {o.source_partenaire or 'Guichet-Emplois direct'}")
        print(f" • Compétences clés   : {', '.join(o.competences_cles) if o.competences_cles else 'Aucune détectée'}")
        print(f" • URL                : {o.url}")
        if o.description:
            apercu = o.description.replace("\n", " ")
            if len(apercu) > 160:
                apercu = apercu[:157] + "..."
            print(f" • Description (RDFa) : {apercu}")

    total_time = time.time() - start_time
    print("\n" + "-" * 70)
    print(f"Fin du test : {len(offers)} offres traitées avec succès en {total_time:.2f} s.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
