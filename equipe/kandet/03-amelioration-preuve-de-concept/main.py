"""Collecte d'offres d'emploi et de stage en informatique (livrable 3).

Point d'entrée en ligne de commande. Le travail est réparti dans les modules :
collecte (HTTP), guichet, remotive, fusion (doublons) et analyse.

Lancer depuis la racine du dépôt :
    python .\\equipe\\kandet\\03-amelioration-preuve-de-concept\\main.py
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from analyse import build_summary
from fiches import enrich_with_postings
from fusion import aggregate_records
from guichet import CNP_CODES_TI, GUICHET_DELAY_SECONDS, GUICHET_SEARCH_URL, fetch_guichet
from modele import AggregatedOffer, SourceRecord
from normalisation import normalize_record
from remotive import (
    REMOTIVE_API_URL,
    REMOTIVE_MAX_REQUESTS_PER_DAY,
    load_remotive_payload,
    parse_remotive_payload,
)


DOSSIER = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collecte d'offres TI : Guichet-Emplois (recherche HTML) et Remotive (API)."
    )
    parser.add_argument(
        "--terme",
        action="append",
        default=[],
        help="Mot-clé Guichet-Emplois (répétable). Par défaut : aucun, seuls les codes CNP TI filtrent.",
    )
    parser.add_argument("--province", default="QC", help="Province Guichet-Emplois (défaut : QC).")
    parser.add_argument(
        "--toutes-provinces",
        action="store_true",
        help="Ne pas filtrer le Guichet-Emplois par province.",
    )
    parser.add_argument(
        "--tous-domaines",
        action="store_true",
        help="Ne pas filtrer par codes CNP (à combiner avec --terme).",
    )
    parser.add_argument(
        "--remotive-canada",
        action="store_true",
        help="Garder seulement les offres Remotive ouvertes au Canada, à l'Amérique du Nord ou au monde entier.",
    )
    parser.add_argument(
        "--rafraichir-remotive",
        action="store_true",
        help="Ignorer le cache Remotive (l'API demande au plus 4 appels par jour).",
    )
    parser.add_argument("--sans-remotive", action="store_true", help="Ne pas interroger Remotive.")
    parser.add_argument(
        "--sans-fiches",
        action="store_true",
        help="Ne pas lire les fiches des offres (collecte rapide, comme au livrable 2).",
    )
    parser.add_argument(
        "--max-fiches",
        type=int,
        help="Lire seulement les N premières fiches (pour un essai court). Par défaut : toutes.",
    )
    parser.add_argument(
        "--cache-fiches",
        type=Path,
        default=DOSSIER / "cache" / "fiches",
        help="Dossier où les fiches téléchargées sont gardées (défaut : cache/fiches).",
    )
    parser.add_argument(
        "--sortie",
        type=Path,
        default=DOSSIER / "offres.json",
        help="Fichier JSON de sortie (défaut : offres.json à côté du script).",
    )
    parser.add_argument(
        "--echantillon",
        type=Path,
        help="Écrit aussi un petit fichier avec les 10 premières offres du Guichet-Emplois.",
    )
    parser.add_argument("--sans-sauvegarde", action="store_true", help="Afficher sans écrire de fichier.")
    return parser


def print_offer(offer: AggregatedOffer) -> None:
    sites = ", ".join(record.origin_site or record.source for record in offer.source_records)
    print(
        f"- {offer.published_at or '????-??-??'} | {offer.title} | "
        f"{offer.employer or 'Employeur non précisé'} | {offer.location or 'Lieu non précisé'} | {sites}"
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    province = None if args.toutes_provinces else args.province
    cnp_codes = None if args.tous_domaines else tuple(CNP_CODES_TI)
    terms = args.terme or [""]
    source_records: list[SourceRecord] = []
    searches: list[dict[str, object]] = []
    errors: list[str] = []

    for index, term in enumerate(terms):
        if index > 0:
            time.sleep(GUICHET_DELAY_SECONDS)
        label = f"« {term} »" if term else "codes CNP TI"
        try:
            records, summary = fetch_guichet(
                term,
                province,
                cnp_codes,
                progress=lambda page, count, total: print(
                    f"Guichet-Emplois ({label}) page {page} : {count} offres"
                    + (f" / {total} annoncées" if total is not None else ""),
                    file=sys.stderr,
                ),
            )
            source_records.extend(records)
            searches.append(summary)
        except (OSError, ValueError) as error:
            errors.append(f"Guichet-Emplois ({label}) : {error}")

    postings: dict[str, object] | None = None
    if not args.sans_fiches and source_records:
        postings = enrich_with_postings(
            source_records,
            args.cache_fiches,
            max_postings=args.max_fiches,
            progress=lambda index, total, cached: print(
                f"Fiche {index}/{total}" + (" (cache)" if cached else ""),
                file=sys.stderr,
            ),
        )

    remotive_total: object = None
    if not args.sans_remotive:
        try:
            payload = load_remotive_payload(
                DOSSIER / "remotive-cache.json",
                refresh=args.rafraichir_remotive,
            )
            remotive_total = payload.get("total-job-count", len(payload.get("jobs") or []))
            source_records.extend(
                parse_remotive_payload(payload, location_filter=args.remotive_canada)
            )
        except (OSError, ValueError) as error:
            errors.append(f"Remotive : {error}")

    for error in errors:
        print(f"AVERTISSEMENT : {error}", file=sys.stderr)
    if not source_records:
        if errors:
            raise SystemExit("Aucune offre récupérée; voir les avertissements ci-dessus.")
        print("Aucune offre ne correspond aux critères.")
        return

    for record in source_records:
        normalize_record(record)
    offers = aggregate_records(source_records)
    summary = build_summary(offers)
    print(f"\n{len(offers)} offres uniques ({len(source_records)} annonces lues).")
    for search in searches:
        print(
            f"Guichet-Emplois {search['term'] or '(codes CNP TI)'} : {search['collected']} récupérées"
            f" / {search['announced_total']} annoncées, {search['pages_read']} page(s)"
        )
    if remotive_total is not None:
        kept = summary["offers_by_source"].get("Remotive", 0)
        print(f"Remotive : {kept} gardées sur {remotive_total} dans l'API")
    print(f"Sites d'origine (Guichet-Emplois) : {summary['guichet_by_origin_site']}")
    if postings is not None:
        print(
            f"Fiches lues : {postings['read']} ({postings['from_cache']} du cache, "
            f"{postings['downloaded']} téléchargées), erreurs : {len(postings['errors'])}"
        )
    print(f"Champs remplis : {summary['filled_fields']}")
    print(f"Offres publiées sur plusieurs sites (fusionnées) : {summary['merged_offers']}")
    print(f"Stages : {summary['stage_classification']}\n")
    for offer in offers:
        print_offer(offer)

    if args.sans_sauvegarde:
        return
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "province": province,
            "cnp_codes": list(cnp_codes or []),
            "terms": [term for term in terms if term],
            "remotive_canada_only": args.remotive_canada,
        },
        "sources": {"Guichet-Emplois": GUICHET_SEARCH_URL, "Remotive": REMOTIVE_API_URL},
        "remotive_notice": (
            "Offres Remotive : garder l'attribution et le lien d'origine, ne pas les republier "
            f"sur un site tiers, au plus {REMOTIVE_MAX_REQUESTS_PER_DAY} appels par jour."
        ),
        "errors": errors,
        "guichet_searches": searches,
        "postings": postings,
        "remotive_total_in_api": remotive_total,
        "offer_count": len(offers),
        "summary": summary,
        "offers": [asdict(offer) for offer in offers],
    }
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nRésultats enregistrés dans : {args.sortie}")

    if args.echantillon:
        sample = [
            asdict(offer)
            for offer in offers
            if offer.source_records[0].source == "Guichet-Emplois"
        ][:10]
        args.echantillon.write_text(
            json.dumps(
                {"generated_at": document["generated_at"], "offers": sample},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Échantillon enregistré dans : {args.echantillon}")


if __name__ == "__main__":
    main()
