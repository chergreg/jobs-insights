"""
main.py - Point d'entrée pour le collecteur Jobillico (Espace Hugo).
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
FICHIER_SORTIE_DEFAUT = os.path.join(DOSSIER_COURANT, "data", "offres_jobillico.json")

from collecte import CollecteurJobillico


def mode_interactif():
    """Menu interactif convivial pour la console Windows."""
    print("=" * 65)
    print(" JOBS INSIGHTS - COLLECTEUR JOBILLICO QUÉBEC (Espace Hugo)")
    print("=" * 65)
    print("Ce module extrait les offres TI de Jobillico via balises JSON-LD Schema.org.\n")

    mot_cle = input("Entrez un mot-clé de recherche [Défaut: 'informatique'] : ").strip()
    if not mot_cle:
        mot_cle = "informatique"

    lieu = input("Entrez une localisation [Défaut: 'Quebec'] : ").strip()
    if not lieu:
        lieu = "Quebec"

    limite_str = input("Nombre d'offres cibles à récupérer [Défaut: 10] : ").strip()
    try:
        limite = int(limite_str) if limite_str else 10
    except ValueError:
        limite = 10

    collecteur = CollecteurJobillico()
    offres = collecteur.collecter(mot_cle=mot_cle, lieu=lieu, limite=limite, delai=1.0)

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

    parser = argparse.ArgumentParser(description="Collecteur d'offres Jobillico (Jobs Insights)")
    parser.add_argument("--keyword", type=str, default="informatique", help="Mot-clé de recherche")
    parser.add_argument("--location", type=str, default="Quebec", help="Ville ou région")
    parser.add_argument("--limit", type=int, default=10, help="Nombre maximal d'offres à extraire")
    parser.add_argument("--delay", type=float, default=1.0, help="Délai entre requêtes en secondes")
    parser.add_argument("--output", type=str, default=FICHIER_SORTIE_DEFAUT, help="Chemin du fichier JSON de sortie")

    args = parser.parse_args()

    collecteur = CollecteurJobillico()
    offres = collecteur.collecter(mot_cle=args.keyword, lieu=args.location, limite=args.limit, delai=args.delay)
    if offres:
        collecteur.exporter(offres, args.output)


if __name__ == "__main__":
    main()
