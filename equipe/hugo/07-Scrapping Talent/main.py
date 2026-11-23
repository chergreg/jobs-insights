"""
main.py - Point d'entrée pour le collecteur Talent.com Canada (Espace Hugo).
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

FICHIER_SORTIE_DEFAUT = os.path.join(DOSSIER_COURANT, "data", "offres_talent.json")

from collecte import CollecteurTalent


def mode_interactif():
    """Menu interactif convivial pour la console Windows."""
    print("=" * 65)
    print(" JOBS INSIGHTS - COLLECTEUR TALENT.COM CANADA (Espace Hugo)")
    print("=" * 65)
    print("Ce module extrait les offres TI via les métadonnées JSON-LD de Talent.com.\n")

    mot_cle = input("Entrez un mot-clé de recherche [Défaut: 'informatique'] : ").strip() or "informatique"
    lieu = input("Entrez une localisation [Défaut: 'Quebec'] : ").strip() or "Quebec"

    limite_str = input("Nombre d'offres cibles à récupérer [Défaut: 10] : ").strip()
    try:
        limite = int(limite_str) if limite_str else 10
    except ValueError:
        limite = 10

    print("\n[INFO] Lancement de la collecte en cours...")
    try:
        collecteur = CollecteurTalent()
        offres = collecteur.collecter(mot_cle=mot_cle, lieu=lieu, limite=limite, delai=0.6)

        if offres:
            collecteur.exporter(offres, FICHIER_SORTIE_DEFAUT)
            print(f"\n[SUCCÈS] {len(offres)} offres 100% TI enregistrées dans :\n  -> {FICHIER_SORTIE_DEFAUT}")
        else:
            print("\n[INFO] Aucune offre trouvée correspondant aux critères.")
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

    parser = argparse.ArgumentParser(description="Collecteur d'offres Talent.com Canada (Jobs Insights)")
    parser.add_argument("--keyword", "--search", dest="keyword", type=str, default="informatique", help="Mot-clé de recherche")
    parser.add_argument("--location", type=str, default="Quebec", help="Ville ou région")
    parser.add_argument("--limit", type=int, default=10, help="Nombre maximal d'offres à extraire")
    parser.add_argument("--delay", type=float, default=0.6, help="Délai entre requêtes en secondes")
    parser.add_argument("--output", type=str, default=FICHIER_SORTIE_DEFAUT, help="Chemin du fichier JSON de sortie")

    args = parser.parse_args()

    collecteur = CollecteurTalent()
    offres = collecteur.collecter(mot_cle=args.keyword, lieu=args.location, limite=args.limit, delai=args.delay)
    if offres:
        collecteur.exporter(offres, args.output)
        print(f"[SUCCÈS] {len(offres)} offres exportées vers {args.output}")
    else:
        print("[INFO] Aucune offre trouvée.")


if __name__ == "__main__":
    main()
