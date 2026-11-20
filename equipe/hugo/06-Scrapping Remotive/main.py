"""
main.py - Point d'entrée pour le collecteur Remotive API (Espace Hugo).
Supporte l'exécution en ligne de commande (CLI) et en mode interactif Windows.
"""

from __future__ import annotations

import argparse
import os
import sys

# Configuration encodage console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DOSSIER_COURANT = os.path.dirname(os.path.abspath(__file__))
FICHIER_SORTIE_DEFAUT = os.path.join(DOSSIER_COURANT, "data", "offres_remotive.json")

from collecte import CollecteurRemotive


def mode_interactif():
    """Menu interactif convivial pour la console Windows."""
    print("=" * 65)
    print(" JOBS INSIGHTS - COLLECTEUR REMOTIVE API (Espace Hugo)")
    print("=" * 65)
    print("Ce module extrait les offres TI en télétravail via l'API REST Remotive.\n")

    print("Catégories disponibles :")
    print(" 1. Développement logiciel (software-dev) [Défaut]")
    print(" 2. DevOps / Infrastructure (devops)")
    print(" 3. Données / Data (data)")
    print(" 4. Assurance qualité / QA (qa)")

    choix = input("Votre choix [Défaut: 1] : ").strip()
    cat_map = {"1": "software-dev", "2": "devops", "3": "data", "4": "qa"}
    categorie = cat_map.get(choix, "software-dev")

    mot_cle = input("Filtre mot-clé spécifique (laisser vide pour tout prendre) : ").strip() or None

    limite_str = input("Nombre d'offres cibles à récupérer [Défaut: 20] : ").strip()
    try:
        limite = int(limite_str) if limite_str else 20
    except ValueError:
        limite = 20

    collecteur = CollecteurRemotive()
    offres = collecteur.collecter(categorie=categorie, mot_cle=mot_cle, limite=limite)

    if offres:
        collecteur.exporter(offres, FICHIER_SORTIE_DEFAUT)
        print(f"\n[SUCCÈS] {len(offres)} offres enregistrées dans :\n  -> {FICHIER_SORTIE_DEFAUT}")
    else:
        print("\n[INFO] Aucune offre trouvée.")

    print("\nAppuyez sur Entrée pour quitter...")
    try:
        input()
    except EOFError:
        pass


def main():
    if len(sys.argv) == 1:
        mode_interactif()
        return

    parser = argparse.ArgumentParser(description="Collecteur d'offres Remotive API (Jobs Insights)")
    parser.add_argument("--category", type=str, default="software-dev", help="Catégorie d'emploi")
    parser.add_argument("--search", type=str, default=None, help="Mot-clé de filtrage")
    parser.add_argument("--limit", type=int, default=20, help="Nombre maximal d'offres à extraire")
    parser.add_argument("--all-locations", action="store_true", help="Désactive le filtre d'éligibilité Canada")
    parser.add_argument("--output", type=str, default=FICHIER_SORTIE_DEFAUT, help="Chemin du fichier JSON de sortie")

    args = parser.parse_args()

    collecteur = CollecteurRemotive()
    offres = collecteur.collecter(
        categorie=args.category,
        mot_cle=args.search,
        limite=args.limit,
        filtrer_canada=not args.all_locations
    )
    if offres:
        collecteur.exporter(offres, args.output)


if __name__ == "__main__":
    main()
