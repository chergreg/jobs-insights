"""Livrable 3 (Dan) : lance les 3 scrapers, regroupe les offres sans doublons et exporte.

Usage (depuis equipe/dan/livrable3) :
    python main.py                                   # 3 sites, 1 page, 5 fiches par site
    python main.py --sites guichet jobboom --pages 2 --fiches 10 --csv
    python main.py --sans-cache
    python main.py --respecter-robots                # réactive la vérification de robots.txt

robots.txt n'est pas lu par défaut ; les délais par site sont fixés dans outils.DELAIS_PAR_SITE.
Une source refusée (401, 403, 429, ou robots.txt avec --respecter-robots) ou en erreur n'arrête pas les autres :
son statut apparaît dans le résumé final.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from modele import Offre, exporter_csv, exporter_json
from competences import detecter_competences
from outils import Client
from regroupement import regrouper
from scrapers import guichet_emplois, jobboom, talent

DOSSIER_DATA = Path(__file__).resolve().parent / "data"
# Ordre = priorité d'apparition dans le fichier unifié (le Guichet-Emplois d'abord).
SOURCES = {
    "guichet": ("Guichet-Emplois", guichet_emplois),
    "jobboom": ("Jobboom", jobboom),
    "talent": ("Talent.com", talent),
}


@dataclass
class Resultat:
    nom: str
    offres: list[Offre]
    erreur: str | None = None

    @property
    def statut(self) -> str:
        if self.erreur:
            return f"erreur : {self.erreur}"
        if not self.offres:
            return "0 offre (refus ou page vide : voir les messages plus haut)"
        return "ok"


def lancer_source(cle: str, client: Client, pages: int, fiches: int) -> Resultat:
    """Lance un scraper. Toute exception est capturée : les autres sources continuent."""
    nom, module = SOURCES[cle]
    print(f"\n=== {nom} ===")
    try:
        offres = module.collecter(client, pages=pages, fiches=fiches)
    except Exception as erreur:                         # ex. page au format inattendu, réseau coupé
        print(f"Erreur inattendue : {erreur}")
        return Resultat(nom, [], erreur=f"{type(erreur).__name__}: {erreur}")
    for offre in offres:                                # compétences lues dans le titre et la description
        offre.competences = detecter_competences(offre.titre, offre.description) or offre.competences
    return Resultat(nom, offres)


def afficher_resume(resultats: list[Resultat], uniques: list[Offre], bilan) -> None:
    print("\n=== Résumé ===")
    print(f"{'Source':<17}{'Offres':>7}{'Descriptions':>14}  Statut")
    for r in resultats:
        avec_desc = sum(o.description is not None for o in r.offres)
        print(f"{r.nom:<17}{len(r.offres):>7}{avec_desc:>14}  {r.statut}")
    print(f"\nRegroupement : {bilan.offres_recues} offres reçues, {bilan.doublons} doublons fusionnés "
          f"({bilan.doublons_meme_id} même id, {bilan.doublons_empreinte} même titre + entreprise + ville) "
          f"→ {len(uniques)} offres uniques")
    for exemple in bilan.exemples:
        print(f"  doublon : {exemple}")
    print(f"Compétences repérées dans {sum(bool(o.competences) for o in uniques)} offres sur {len(uniques)}")


def main(arguments: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Regroupe les offres TI des 3 sources du livrable 3.")
    analyseur.add_argument("--sites", nargs="+", choices=list(SOURCES), default=list(SOURCES),
                           help="sources à lancer (défaut : les 3)")
    analyseur.add_argument("--pages", type=int, default=1, help="pages de résultats par source (défaut : 1)")
    analyseur.add_argument("--fiches", type=int, default=5, help="fiches ouvertes par source (défaut : 5)")
    analyseur.add_argument("--sans-cache", action="store_true", help="ignorer le cache disque")
    analyseur.add_argument("--respecter-robots", action="store_true",
                           help="lire et appliquer robots.txt (désactivé par défaut)")
    analyseur.add_argument("--csv", action="store_true", help="écrire aussi un CSV par source")
    analyseur.add_argument("--dossier", type=Path, default=DOSSIER_DATA, help="dossier des fichiers produits")
    args = analyseur.parse_args(arguments)

    client = Client(respecter_robots=args.respecter_robots, **({"cache_dossier": None} if args.sans_cache else {}))   # un seul client : délais par site
    resultats = []
    for cle in [c for c in SOURCES if c in args.sites]:
        resultat = lancer_source(cle, client, args.pages, args.fiches)
        resultats.append(resultat)
        if resultat.offres:
            chemin = exporter_json(resultat.offres, args.dossier / f"offres_{SOURCES[cle][1].SOURCE.replace('-', '_')}.json")
            if args.csv:
                exporter_csv(resultat.offres, chemin.with_suffix(".csv"))

    toutes = [o for r in resultats for o in r.offres]
    uniques, bilan = regrouper(toutes)
    json_unifie = exporter_json(uniques, args.dossier / "offres_unifiees.json")
    csv_unifie = exporter_csv(uniques, args.dossier / "offres_unifiees.csv")

    afficher_resume(resultats, uniques, bilan)
    print(f"\nJSON : {json_unifie}\nCSV  : {csv_unifie}")
    return 0 if toutes else 1                           # 1 = aucune source n'a rien donné


if __name__ == "__main__":
    sys.exit(main())
