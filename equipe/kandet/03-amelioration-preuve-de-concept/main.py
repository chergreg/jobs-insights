"""Collecte d'offres d'emploi et de stage en informatique (livrable 3).

Point d'entrée en ligne de commande. Le travail est réparti dans les modules :
collecte (HTTP), guichet, fiches, remotive, normalisation, fusion (doublons),
competences, analyse (statistiques), regions, filtres, export (CSV) et interface (page HTML).

Lancer depuis la racine du dépôt :
    python .\\equipe\\kandet\\03-amelioration-preuve-de-concept\\main.py
Aide sur toutes les options :
    python .\\equipe\\kandet\\03-amelioration-preuve-de-concept\\main.py --help
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
from competences import enrich_offer
from export import load_offers, write_csv
from fiches import enrich_with_postings
from filtres import Filters, filter_offers
from fusion import aggregate_records
from interface import write_html
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
        description="Collecte d'offres TI : Guichet-Emplois (recherche HTML et fiches) et Remotive (API)."
    )
    collecte = parser.add_argument_group("collecte")
    collecte.add_argument(
        "--terme",
        action="append",
        default=[],
        help="Mot-clé Guichet-Emplois (répétable). Par défaut : aucun, seuls les codes CNP TI filtrent.",
    )
    collecte.add_argument("--province", default="QC", help="Province Guichet-Emplois (défaut : QC).")
    collecte.add_argument(
        "--toutes-provinces",
        action="store_true",
        help="Ne pas filtrer le Guichet-Emplois par province.",
    )
    collecte.add_argument(
        "--tous-domaines",
        action="store_true",
        help="Ne pas filtrer par codes CNP (à combiner avec --terme).",
    )
    collecte.add_argument(
        "--remotive-canada",
        action="store_true",
        help="Garder seulement les offres Remotive ouvertes au Canada, à l'Amérique du Nord ou au monde entier.",
    )
    collecte.add_argument(
        "--rafraichir-remotive",
        action="store_true",
        help="Ignorer le cache Remotive (l'API demande au plus 4 appels par jour).",
    )
    collecte.add_argument("--sans-remotive", action="store_true", help="Ne pas interroger Remotive.")
    collecte.add_argument(
        "--sans-fiches",
        action="store_true",
        help="Ne pas lire les fiches des offres (collecte rapide, comme au livrable 2).",
    )
    collecte.add_argument(
        "--max-fiches",
        type=int,
        help="Lire seulement les N premières fiches (pour un essai court). Par défaut : toutes.",
    )
    collecte.add_argument(
        "--cache-fiches",
        type=Path,
        default=DOSSIER / "cache" / "fiches",
        help="Dossier où les fiches téléchargées sont gardées (défaut : cache/fiches).",
    )
    collecte.add_argument(
        "--depuis",
        type=Path,
        help="Ne rien télécharger : relire un offres.json déjà produit (pour filtrer ou exporter vite).",
    )

    filtres = parser.add_argument_group("filtres (affichage et CSV ; offres.json garde toutes les offres)")
    filtres.add_argument("--ville", default="", help="Ex. --ville Montréal (accents facultatifs).")
    filtres.add_argument(
        "--region",
        default="",
        help="Région administrative ou début de son nom : --region Montérégie, --region capitale.",
    )
    filtres.add_argument("--techno", default="", help="Ex. --techno Python, --techno SQL, --techno \"C#\".")
    filtres.add_argument("--niveau", default="", help="débutant, intermédiaire ou avancé.")
    filtres.add_argument("--stages", action="store_true", help="Seulement les stages (confirmés ou possibles).")
    filtres.add_argument(
        "--salaire-min",
        type=float,
        help="Bas de la fourchette au moins égal à ce montant (ex. 60000), dans l'unité --unite-salaire.",
    )
    filtres.add_argument(
        "--unite-salaire",
        default="année",
        help="Unité pour --salaire-min : heure, jour, semaine, mois ou année (défaut : année).",
    )
    filtres.add_argument("--employeur", default="", help="Partie du nom de l'employeur.")

    sorties = parser.add_argument_group("sorties")
    sorties.add_argument(
        "--sortie",
        type=Path,
        default=DOSSIER / "offres.json",
        help="Fichier JSON de sortie (défaut : offres.json à côté du script).",
    )
    sorties.add_argument(
        "--csv",
        type=Path,
        nargs="?",
        const=DOSSIER / "offres.csv",
        help="Exporter les offres affichées en CSV pour Excel (défaut : offres.csv à côté du script).",
    )
    sorties.add_argument(
        "--html",
        type=Path,
        nargs="?",
        const=DOSSIER / "offres.html",
        help="Créer une page à ouvrir dans le navigateur pour chercher les offres (défaut : offres.html).",
    )
    sorties.add_argument(
        "--echantillon",
        type=Path,
        help="Écrit aussi un petit fichier avec les 10 premières offres du Guichet-Emplois.",
    )
    sorties.add_argument("--sans-sauvegarde", action="store_true", help="Ne pas écrire offres.json.")
    sorties.add_argument(
        "--resume-seulement",
        action="store_true",
        help="Afficher les statistiques sans la liste des offres.",
    )
    return parser


def print_offer(offer: AggregatedOffer) -> None:
    sites = ", ".join(record.origin_site or record.source for record in offer.source_records)
    salary = ""
    if offer.salary_min is not None:
        top = f" à {offer.salary_max:g}" if offer.salary_max is not None else ""
        salary = f" | {offer.salary_min:g}{top} $ / {offer.salary_unit or '?'}"
    print(
        f"- {offer.published_at or '????-??-??'} | {offer.original_title or offer.title} | "
        f"{offer.employer or 'Employeur non précisé'} | {offer.city or offer.location or 'Lieu non précisé'}"
        f"{salary} | {sites}"
    )


def print_summary(summary: dict[str, object]) -> None:
    print(f"Sites d'origine (Guichet-Emplois) : {summary['guichet_by_origin_site']}")
    print(f"Champs remplis : {summary['filled_fields']}")
    print(f"Offres publiées sur plusieurs sites (fusionnées) : {summary['merged_offers']}")
    print(f"Stages : {summary['stage_classification']}")
    print(f"Niveaux : {summary['levels']}")
    print(f"Top technologies : {summary['top_technologies']}")
    print(f"Top compétences : {summary['top_skills']}")
    print(f"Top villes : {summary['top_cities']}")
    print(f"Régions : {summary['regions']}")
    print("Salaires (valeur basse médiane, plus bas, plus haut) :")
    for key, stats in summary["salaries"].items():  # type: ignore[union-attr]
        print(
            f"  {key} : {stats['offers']} offres, médiane {stats['median_low']}, "
            f"de {stats['lowest']} à {stats['highest']}"
        )
    print(f"Offres qui expirent dans 7 jours : {len(summary['expiring_within_7_days'])}")  # type: ignore[arg-type]


def collect(args: argparse.Namespace) -> tuple[list[AggregatedOffer], dict[str, object]]:
    """Collecte en ligne : pages de résultats, fiches, Remotive, puis enrichissement."""
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
            records, search = fetch_guichet(
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
            searches.append(search)
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
            payload = load_remotive_payload(DOSSIER / "remotive-cache.json", refresh=args.rafraichir_remotive)
            remotive_total = payload.get("total-job-count", len(payload.get("jobs") or []))
            source_records.extend(parse_remotive_payload(payload, location_filter=args.remotive_canada))
        except (OSError, ValueError) as error:
            errors.append(f"Remotive : {error}")

    for error in errors:
        print(f"AVERTISSEMENT : {error}", file=sys.stderr)
    if not source_records and errors:
        raise SystemExit("Aucune offre récupérée; voir les avertissements ci-dessus.")

    for record in source_records:
        normalize_record(record)
    offers = aggregate_records(source_records)
    for offer in offers:
        enrich_offer(offer)

    print(f"\n{len(offers)} offres uniques ({len(source_records)} annonces lues).")
    for search in searches:
        print(
            f"Guichet-Emplois {search['term'] or '(codes CNP TI)'} : {search['collected']} récupérées"
            f" / {search['announced_total']} annoncées, {search['pages_read']} page(s)"
        )
    if remotive_total is not None:
        kept = sum(offer.source_records[0].source == "Remotive" for offer in offers)
        print(f"Remotive : {kept} gardées sur {remotive_total} dans l'API")
    if postings is not None:
        print(
            f"Fiches lues : {postings['read']} ({postings['from_cache']} du cache, "
            f"{postings['downloaded']} téléchargées), erreurs : {len(postings['errors'])}"  # type: ignore[arg-type]
        )

    report = {
        "parameters": {
            "province": province,
            "cnp_codes": list(cnp_codes or []),
            "terms": [term for term in terms if term],
            "remotive_canada_only": args.remotive_canada,
        },
        "errors": errors,
        "guichet_searches": searches,
        "postings": postings,
        "remotive_total_in_api": remotive_total,
    }
    return offers, report


def save_json(args: argparse.Namespace, offers: list[AggregatedOffer], report: dict[str, object], summary: dict[str, object]) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    document = {
        "generated_at": generated_at,
        "parameters": report["parameters"],
        "sources": {"Guichet-Emplois": GUICHET_SEARCH_URL, "Remotive": REMOTIVE_API_URL},
        "remotive_notice": (
            "Offres Remotive : garder l'attribution et le lien d'origine, ne pas les republier "
            f"sur un site tiers, au plus {REMOTIVE_MAX_REQUESTS_PER_DAY} appels par jour."
        ),
        "errors": report["errors"],
        "guichet_searches": report["guichet_searches"],
        "postings": report["postings"],
        "remotive_total_in_api": report["remotive_total_in_api"],
        "offer_count": len(offers),
        "summary": summary,
        "offers": [asdict(offer) for offer in offers],
    }
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Résultats enregistrés dans : {args.sortie}")

    if args.echantillon:
        sample = [asdict(offer) for offer in offers if offer.source_records[0].source == "Guichet-Emplois"][:10]
        args.echantillon.write_text(
            json.dumps({"generated_at": generated_at, "offers": sample}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Échantillon enregistré dans : {args.echantillon}")


def collected_on(path: Path) -> str | None:
    """Date de la collecte écrite dans un offres.json (AAAA-MM-JJ), si elle y est."""
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("generated_at", "")
        return datetime.fromisoformat(value).astimezone().date().isoformat()
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    filters = Filters(
        city=args.ville,
        region=args.region,
        technology=args.techno,
        level=args.niveau,
        stages_only=args.stages,
        salary_min=args.salaire_min,
        salary_unit=args.unite_salaire,
        employer=args.employeur,
    )

    if args.depuis:
        # Aucune requête réseau : on relit une collecte déjà faite.
        try:
            offers = load_offers(args.depuis)
        except (OSError, ValueError) as error:
            raise SystemExit(f"Impossible de lire {args.depuis} : {error}")
        report = None
        collection_date = collected_on(args.depuis)
        print(f"{len(offers)} offres relues depuis {args.depuis} (aucun téléchargement).")
    else:
        offers, report = collect(args)
        collection_date = datetime.now().date().isoformat()

    if not offers:
        print("Aucune offre ne correspond aux critères.")
        return

    summary = build_summary(offers)
    print_summary(summary)

    selected = filter_offers(offers, filters)
    print(f"\nOffres affichées ({filters.describe()}) : {len(selected)} sur {len(offers)}")
    if not args.resume_seulement:
        for offer in selected:
            print_offer(offer)

    print()
    if report is not None and not args.sans_sauvegarde:
        save_json(args, offers, report, summary)
    if args.csv:
        write_csv(selected, args.csv)
        print(f"CSV pour Excel enregistré dans : {args.csv} ({len(selected)} offres)")
    if args.html:
        write_html(selected, args.html, generated_on=collection_date)
        print(f"Page à ouvrir dans le navigateur : {args.html} ({len(selected)} offres)")


if __name__ == "__main__":
    main()
