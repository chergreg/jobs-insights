"""
main.py - Point d'entrée pour le collecteur Remotive API (Espace Hugo).
Supporte l'exécution en ligne de commande (CLI) et en mode interactif Windows.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

# Configuration encodage console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Sécuriser l'importation locale
DOSSIER_COURANT = os.path.dirname(os.path.abspath(__file__))
if DOSSIER_COURANT not in sys.path:
    sys.path.insert(0, DOSSIER_COURANT)

FICHIER_SORTIE_DEFAUT = os.path.join(DOSSIER_COURANT, "data", "offres_remotive.json")

from collecte import CollecteurRemotive


def mode_interactif():
    """Menu interactif convivial pour la console Windows."""
    print("=" * 65)
    print(" JOBS INSIGHTS - COLLECTEUR REMOTIVE API (Espace Hugo)")
    print("=" * 65)
    print("Ce module extrait les offres TI en télétravail via l'API REST Remotive.\n")

    print("Catégories disponibles :")
    print(" 1. Développement logiciel (software-development) [Défaut]")
    print(" 2. DevOps / Infrastructure (devops)")
    print(" 3. Données / Data (data)")
    print(" 4. Assurance qualité / QA (qa)")
    print(" 5. Toutes les catégories TI")

    choix = input("\nVotre choix [Défaut: 1] : ").strip()
    cat_map = {
        "1": "software-development",
        "2": "devops",
        "3": "data",
        "4": "qa",
        "5": None
    }
    categorie = cat_map.get(choix, "software-development")

    mot_cle = input("Filtre mot-clé spécifique (laisser vide pour tout prendre) : ").strip() or None

    limite_str = input("Nombre d'offres cibles à récupérer [Défaut: 20] : ").strip()
    try:
        limite = int(limite_str) if limite_str else 20
    except ValueError:
        limite = 20

    print("\n[INFO] Lancement de la collecte en cours...")
    try:
        collecteur = CollecteurRemotive()
        offres = collecteur.collecter(categorie=categorie, mot_cle=mot_cle, limite=limite)

        if offres:
            collecteur.exporter(offres, FICHIER_SORTIE_DEFAUT)
            print(f"\n[SUCCÈS] {len(offres)} offres 100% TI enregistrées dans :\n  -> {FICHIER_SORTIE_DEFAUT}")
        else:
            print("\n[INFO] Aucune offre trouvée correspondant aux critères TI.")
    except Exception as e:
        print(f"\n[ERREUR] Une erreur inattendue est survenue : {e}")
        traceback.print_exc()

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
    parser.add_argument("--category", type=str, default="software-development", help="Catégorie d'emploi")
    parser.add_argument("--search", "--keyword", dest="search", type=str, default=None, help="Mot-clé de filtrage")
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
        print(f"[SUCCÈS] {len(offres)} offres exportées vers {args.output}")
    else:
        print("[INFO] Aucune offre trouvée.")


if __name__ == "__main__":
    main()
