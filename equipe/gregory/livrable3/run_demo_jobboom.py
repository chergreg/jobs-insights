"""
run_demo_jobboom.py - Démonstration et test en direct du connecteur Jobboom Québec.

Permet de tester :
1. La découverte des offres avec pagination ordonnée (dépassement du seuil de 5 offres).
2. L'extraction robuste des blocs JSON-LD Schema.org/JobPosting via json.loads natif.
3. L'application stricte du délai de temporisation de 2.0 s conforme aux règles éthiques.
4. L'accélération majeure grâce au gestionnaire de cache local 24h.
5. La conformité au modèle pivot Pydantic v2 JobOffer.

Usage :
    python run_demo_jobboom.py [--limit 5] [--pages 1] [--keyword python] [--no-cache] [--save-dataset]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from scrapers.jobboom import JobboomScraper, JOBBOOM_DELAY_SECONDS


def main() -> None:
    parser = argparse.ArgumentParser(description="Test en direct du collecteur Jobboom Québec fiabilisé.")
    parser.add_argument("--limit", type=int, default=5, help="Nombre maximal d'offres à collecter (défaut : 5)")
    parser.add_argument("--pages", type=int, default=1, help="Nombre de pages de résultats à parcourir (défaut : 1)")
    parser.add_argument("--keyword", type=str, default="", help="Mot-clé optionnel de recherche (ex: python, stage, devops)")
    parser.add_argument("--no-cache", action="store_true", help="Désactiver la lecture du cache local")
    parser.add_argument("--save-dataset", action="store_true", help="Enregistrer les résultats dans data/offres_jobboom.json")
    args = parser.parse_args()

    use_cache = not args.no_cache
    print("\n" + "=" * 70)
    print("  DÉMONSTRATION EN DIRECT — CONNECTEUR JOBBOOM QUÉBEC")
    print("=" * 70)
    print(f" • Mode cache      : {'Activé (cache local 24h)' if use_cache else 'Désactivé (100% requêtes réelles)'}")
    print(f" • Catégorie       : Technologies et médias numériques (_i10lfr)")
    if args.keyword:
        print(f" • Mot-clé ciblé   : '{args.keyword}'")
    print(f" • Limite d'offres : {args.limit} offre(s) max sur {args.pages} page(s)")
    print(f" • Temporisation   : {JOBBOOM_DELAY_SECONDS}s par appel réseau direct (éthique conforme)")
    print("-" * 70)

    scraper = JobboomScraper(delai_secondes=JOBBOOM_DELAY_SECONDS)

    # 1. Étape Découverte des URLs
    start_time = time.time()
    print("\n[Étape 1/2] Découverte ordonnée des offres...")

    def progress_search_cb(page: int, count: int, total: int | None):
        total_str = f"sur ~{total} au total" if total else ""
        print(f"  -> Page {page} analysée : {count} URL(s) d'offres repérée(s) {total_str}")

    job_urls, total_annonces = scraper.scrape_job_urls(
        keyword=args.keyword,
        max_pages=args.pages,
        limit=args.limit,
        use_cache=use_cache,
        progress=progress_search_cb
    )

    elapsed_search = time.time() - start_time
    print(f"[OK] {len(job_urls)} URL(s) d'offres sélectionnée(s) en {elapsed_search:.2f} s.")

    if not job_urls:
        print("Aucune offre trouvée.")
        return

    # 2. Étape Extraction JSON-LD et typage
    print(f"\n[Étape 2/2] Extraction JSON-LD Schema.org ({len(job_urls)} fiches)...")
    offers = []
    for idx, u in enumerate(job_urls, start=1):
        t0 = time.time()
        offer = scraper.fetch_offer_detail(u, use_cache=use_cache)
        dt = time.time() - t0
        from_cache = dt < 0.1
        status_source = "CACHE" if from_cache else f"RÉSEAU ({dt:.1f}s)"

        if offer:
            print(f"  [{idx}/{len(job_urls)}] {offer.id} ({status_source}) -> {offer.titre[:45]}...")
            offers.append(offer)
        else:
            print(f"  [{idx}/{len(job_urls)}] Échec d'extraction pour : {u}")

    # 3. Synthèse des résultats
    print("\n" + "=" * 70)
    print(f"  RÉSULTATS DE L'EXTRACTION ({len(offers)} offres normalisées)")
    print("=" * 70)

    for idx, o in enumerate(offers, start=1):
        print(f"\n--- [Offre #{idx}] {o.id} ---")
        print(f" • Titre              : {o.titre}")
        print(f" • Employeur          : {o.entreprise}")
        print(f" • Lieu               : {o.lieu} (Province: {o.province})")
        print(f" • Contrat / Type     : {o.type_poste}")
        print(f" • Modalité           : {o.modalite or 'Non spécifiée'}")
        print(f" • Est un stage       : {'Oui (' + o.statut_stage + ')' if o.est_stage else 'Non'}")
        print(f" • Salaire            : {o.salaire or 'Non spécifié'}")
        print(f" • Date publication   : {o.date_publication or 'Non spécifiée'}")
        print(f" • Compétences clés   : {', '.join(o.competences_cles) if o.competences_cles else 'Aucune détectée'}")
        print(f" • URL directe        : {o.url}")
        if o.description:
            apercu = o.description[:140].replace("\n", " ")
            print(f" • Extrait description: {apercu}...")

    # 4. Enregistrement optionnel du jeu d'essai
    if args.save_dataset:
        data_dir = CUR_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        out_file = data_dir / "offres_jobboom.json"
        data = [o.model_dump() for o in offers]
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[OK] {len(offers)} offres sauvegardées dans {out_file}")


if __name__ == "__main__":
    main()
