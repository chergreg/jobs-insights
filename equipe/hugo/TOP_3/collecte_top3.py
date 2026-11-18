"""
collecte_top3.py - Pipeline central d'agrégation et de déduplication multi-sources (TOP 3).
Espace Hugo - Projet Jobs Insights (Livrable 3).

Sources orchestrées :
1. Guichet-Emplois Canada (Gouvernement fédéral)
2. Jobboom Québec (Portail provincial)
3. Remotive (API REST Télétravail & TI)

Fonctionnalités :
- Collecte séquentielle et conforme avec gestion des délais.
- Déduplication intelligente multi-plateformes basée sur l'empreinte sémantique (titre normalisé + employeur).
- Statistiques complètes de collecte (modalités, compétences clés, répartition des sources).
- Double export immédiat dans le dossier TOP_3 (JSON + CSV compatible Excel).
- Double mode d'exécution : CLI scriptable et menu interactif Windows avec maintien de console.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Set, Tuple

# Configuration console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DOSSIER_TOP3 = os.path.dirname(os.path.abspath(__file__))
if DOSSIER_TOP3 not in sys.path:
    sys.path.insert(0, DOSSIER_TOP3)

DOSSIER_DATA = os.path.join(DOSSIER_TOP3, "data")
os.makedirs(DOSSIER_DATA, exist_ok=True)

FICHIER_SORTIE_JSON = os.path.join(DOSSIER_DATA, "offres_top3.json")
FICHIER_SORTIE_CSV = os.path.join(DOSSIER_DATA, "offres_top3.csv")
FICHIER_RAPPORT_JSON = os.path.join(DOSSIER_DATA, "rapport_collecte.json")

from models import JobOffer
from scrapers.guichet import CollecteurGuichet
from scrapers.jobboom import CollecteurJobboom
from scrapers.remotive import CollecteurRemotive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PipelineTop3")


class PipelineTop3:
    """
    Orchestrateur du TOP 3 des sources avec déduplication et normalisation unifiée.
    """

    def __init__(self):
        self.guichet = CollecteurGuichet()
        self.jobboom = CollecteurJobboom()
        self.remotive = CollecteurRemotive()

    def dedupliquer_offres(self, offres: List[JobOffer]) -> Tuple[List[JobOffer], int]:
        """
        Détecte et élimine les offres redondantes provenant de multiples plateformes.
        """
        offres_uniques: List[JobOffer] = []
        empreintes_vues: Set[str] = set()
        urls_vues: Set[str] = set()
        doublons_detectes = 0

        for offre in offres:
            url_norm = offre.url_source.split("?")[0].rstrip("/")
            if url_norm in urls_vues:
                doublons_detectes += 1
                continue

            cle = offre.cle_deduplication()
            if cle and len(cle) > 6 and cle in empreintes_vues:
                doublons_detectes += 1
                logger.debug(f"Doublon ignoré : '{offre.titre}' chez '{offre.entreprise}' (Source: {offre.source})")
                continue

            if cle and len(cle) > 6:
                empreintes_vues.add(cle)
            urls_vues.add(url_norm)
            offres_uniques.append(offre)

        return offres_uniques, doublons_detectes

    def executer_collecte(
        self,
        mot_cle: str = "informatique",
        cible_par_source: int = 15,
        delai: float = 1.0
    ) -> List[JobOffer]:
        """
        Exécute la collecte conjointe sur les 3 sites du TOP 3.
        """
        print("\n" + "=" * 70)
        print(" [1/3] COLLECTE : GUICHET-EMPLOIS CANADA")
        print("=" * 70)
        offres_guichet = self.guichet.collecter(limite=cible_par_source, delai=delai)
        print(f" -> {len(offres_guichet)} offres récupérées depuis Guichet-Emplois.")

        print("\n" + "=" * 70)
        print(" [2/3] COLLECTE : JOBBOOM QUÉBEC (HTML + JSON-LD)")
        print("=" * 70)
        offres_jobboom = self.jobboom.collecter(mot_cle=mot_cle, limite=cible_par_source, delai=delai)
        print(f" -> {len(offres_jobboom)} offres récupérées depuis Jobboom.")

        print("\n" + "=" * 70)
        print(" [3/3] COLLECTE : REMOTIVE (API REST TÉLÉTRAVAIL TI)")
        print("=" * 70)
        offres_remotive = self.remotive.collecter(categorie="software-dev", mot_cle=mot_cle, limite=cible_par_source)
        print(f" -> {len(offres_remotive)} offres récupérées depuis Remotive.")

        toutes_brutes = offres_guichet + offres_jobboom + offres_remotive
        total_brut = len(toutes_brutes)

        print("\n" + "=" * 70)
        print(" PHASE DE DÉDUPLICATION INTELLIGENTE MULTI-SOURCES")
        print("=" * 70)
        offres_finales, nb_doublons = self.dedupliquer_offres(toutes_brutes)
        print(f" -> Total brut collecté      : {total_brut} offres")
        print(f" -> Doublons éliminés        : {nb_doublons}")
        print(f" -> Offres uniques retenues  : {len(offres_finales)}")

        return offres_finales

    @staticmethod
    def generer_statistiques(offres: List[JobOffer]) -> Dict:
        """Calcule les métriques clés de la base de données collectée."""
        total = len(offres)
        if total == 0:
            return {}

        sources = Counter(o.source for o in offres)
        modalites = Counter(o.modalite for o in offres)
        all_skills = [s for o in offres for s in o.competences_cles]
        skills_top10 = Counter(all_skills).most_common(10)

        return {
            "date_generation": datetime.now().isoformat(),
            "total_offres": total,
            "repartition_sources": dict(sources),
            "repartition_modalites": dict(modalites),
            "top_10_competences": dict(skills_top10),
            "nb_avec_description": sum(1 for o in offres if len(o.description) > 50),
        }

    def exporter(self, offres: List[JobOffer], chemin_json: str, chemin_csv: str) -> None:
        """Exporte les offres en JSON et CSV avec rapport statistique."""
        # 1. Export JSON
        data = [o.model_dump() for o in offres]
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n [OK] Base JSON enregistrée ({len(data)} offres) :\n      -> {chemin_json}")

        # 2. Export CSV (compatible Excel avec utf-8-sig)
        if data:
            colonnes = [
                "id", "source", "titre", "entreprise", "lieu", "province",
                "modalite", "type_poste", "salaire", "competences_cles",
                "date_publication", "url_source"
            ]
            with open(chemin_csv, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore", delimiter=";")
                writer.writeheader()
                for o in data:
                    row = dict(o)
                    row["competences_cles"] = ", ".join(row.get("competences_cles", []))
                    writer.writerow(row)
            print(f" [OK] Tableur CSV enregistré :\n      -> {chemin_csv}")

        # 3. Rapport statistique
        stats = self.generer_statistiques(offres)
        with open(FICHIER_RAPPORT_JSON, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f" [OK] Rapport d'analyse sauvegardé :\n      -> {FICHIER_RAPPORT_JSON}")


def mode_interactif():
    """Menu interactif convivial sous Windows."""
    print("*" * 75)
    print("  JOBS INSIGHTS — COLLECTEUR CONJOINT DU TOP 3 (Espace Hugo)")
    print("  Sources : 1. Guichet-Emplois | 2. Jobboom | 3. Remotive")
    print("*" * 75)
    print("Ce programme interroge vos 3 sources officielles, fusionne les résultats,")
    print("détecte les doublons et génère les exports JSON et CSV dans le dossier TOP_3.\n")

    mot_cle = input("Entrez un mot-clé de recherche TI [Défaut: 'informatique'] : ").strip()
    if not mot_cle:
        mot_cle = "informatique"

    cible_str = input("Nombre d'offres cibles à récupérer par source [Défaut: 15] : ").strip()
    try:
        cible = int(cible_str) if cible_str else 15
    except ValueError:
        cible = 15

    pipeline = PipelineTop3()
    debut = time.time()
    offres = pipeline.executer_collecte(mot_cle=mot_cle, cible_par_source=cible, delai=1.0)
    duree = round(time.time() - debut, 1)

    if offres:
        pipeline.exporter(offres, FICHIER_SORTIE_JSON, FICHIER_SORTIE_CSV)
        stats = pipeline.generer_statistiques(offres)
        print("\n" + "=" * 70)
        print(" SYNTHÈSE STATISTIQUE DU TOP 3")
        print("=" * 70)
        print(f" • Durée d'exécution      : {duree} secondes")
        print(f" • Total d'offres uniques : {len(offres)}")
        print(f" • Répartition sources    : {stats.get('repartition_sources')}")
        print(f" • Modalités de travail   : {stats.get('repartition_modalites')}")
        print(f" • Compétences phares     : {list(stats.get('top_10_competences', {}).keys())[:5]}")
        print("=" * 70)
    else:
        print("\n[INFO] Aucune offre n'a pu être récupérée.")

    print("\nOpération terminée. Appuyez sur Entrée pour quitter...")
    try:
        input()
    except EOFError:
        pass


def main():
    if len(sys.argv) == 1:
        mode_interactif()
        return

    parser = argparse.ArgumentParser(description="Pipeline d'agrégation multi-sources TOP 3 (Jobs Insights)")
    parser.add_argument("--keyword", type=str, default="informatique", help="Mot-clé de filtrage")
    parser.add_argument("--per-source", type=int, default=15, help="Nombre d'offres à collecter par site")
    parser.add_argument("--delay", type=float, default=1.0, help="Délai entre requêtes en secondes")
    parser.add_argument("--output-json", type=str, default=FICHIER_SORTIE_JSON, help="Fichier JSON de sortie")
    parser.add_argument("--output-csv", type=str, default=FICHIER_SORTIE_CSV, help="Fichier CSV de sortie")

    args = parser.parse_args()

    pipeline = PipelineTop3()
    offres = pipeline.executer_collecte(
        mot_cle=args.keyword,
        cible_par_source=args.per_source,
        delai=args.delay
    )
    if offres:
        pipeline.exporter(offres, args.output_json, args.output_csv)


if __name__ == "__main__":
    main()
