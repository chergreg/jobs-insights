"""
main.py - Point d'entrée principal pour Jobs Insights (Espace Hugo).
Supporte un double mode d'exécution :
1. Lancement en ligne de commande (CLI automatisable sans blocage).
2. Lancement par double-clic sous Windows (menu interactif avec maintien de console).
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

# Configuration de l'encodage console sous Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ==============================================================================
# VÉRIFICATION PASSIVE DES DÉPENDANCES (Aucune auto-installation pip)
# ==============================================================================
def verifier_dependances_passives() -> bool:
    """Vérifie la présence des dépendances requises et avertit l'utilisateur sans installer."""
    modules_requis = {
        "requests": "requests>=2.31.0",
        "bs4": "beautifulsoup4>=4.12.0",
        "pydantic": "pydantic>=2.0.0"
    }

    manquants = []
    for mod_name, pkg_name in modules_requis.items():
        try:
            __import__(mod_name)
        except ImportError:
            manquants.append(pkg_name)

    if manquants:
        print("\n" + "=" * 65)
        print(" [!] DÉPENDANCES MANQUANTES DÉTECTÉES")
        print("=" * 65)
        print(" Les paquets suivants doivent être installés manuellement :")
        for pkg in manquants:
            print(f"   - {pkg}")
        print("\n Commande recommandée pour les installer :")
        print("   pip install -r requirements.txt")
        print("=" * 65 + "\n")
        return False

    return True


if not verifier_dependances_passives():
    print("Veuillez installer les dépendances et relancer le programme.")
    if len(sys.argv) == 1:
        input("\nAppuyez sur Entrée pour quitter...")
    sys.exit(1)

from collecte import (
    GuichetEmploisCollecteur,
    MOTS_CLES_TI_DEFAUT,
    logger,
    FICHIER_LOG
)


def executer_mode_cli(args: argparse.Namespace):
    """Exécute la collecte en mode ligne de commande non bloquant."""
    delai = 1.2 if args.fast else 5.0
    collecteur = GuichetEmploisCollecteur(delai_secondes=delai)

    if not args.skip_health_check:
        if not collecteur.tester_connectivite():
            logger.error("Échec du test de connectivité en mode CLI.")
            sys.exit(1)

    collecteur.verifier_robots_txt()

    mots_cles = [args.keyword] if args.keyword else MOTS_CLES_TI_DEFAUT

    offres = collecteur.collecter_en_cascade(
        limit_totale=args.limit,
        province=args.province,
        mots_cles=mots_cles,
        enrichir=not args.no_enrich
    )

    if offres:
        collecteur.exporter(offres, args.output)
    else:
        print("\n[INFO] Aucune offre n'a été collectée.")


def executer_mode_interactif():
    """Exécute la collecte en mode interactif pour lancement par double-clic."""
    print("\n" + "=" * 65)
    print(" [*] JOBS INSIGHTS - COLLECTEUR GUICHET-EMPLOIS (ESPACE HUGO)")
    print("=" * 65)

    # 1. Choix du délai / vitesse
    print("\n Options d'exécution :")
    print(" 1. Mode Conforme (Délai 5s respectant robots.txt - Recommandé)")
    print(" 2. Mode Rapide / Développement (Délai 1.2s pour tests)")
    choix_vitesse = input(" Votre choix [Défaut: 1] : ").strip()
    delai = 1.2 if choix_vitesse == "2" else 5.0

    collecteur = GuichetEmploisCollecteur(delai_secondes=delai)

    # 2. Test préalable de connectivité
    if not collecteur.tester_connectivite():
        print("\n [ATTENTION] Le site ne semble pas joignable pour l'instant.")
        choix = input(" Voulez-vous tout de même continuer ? (o/N) : ").strip().lower()
        if choix != "o":
            print(" Opération annulée.")
            return

    collecteur.verifier_robots_txt()

    # 3. Choix du nombre d'offres (Défaut : 100)
    print("\n" + "-" * 65)
    saisie_quantite = input(" Combien d'offres souhaitez-vous extraire ? [Défaut: 100] : ").strip()
    if saisie_quantite.isdigit() and int(saisie_quantite) > 0:
        nb_offres = int(saisie_quantite)
    else:
        nb_offres = 100
        print(f" -> Valeur par défaut appliquée : {nb_offres} offres.")

    # 4. Mode de recherche
    print("\n Modes de recherche disponibles :")
    print(" 1. Bouquet étendu de 16 métiers TI (Programmeurs, Web, Jeux vidéo...) [Défaut]")
    print(" 2. Saisir un mot-clé personnalisé")
    choix_mode = input(" Votre choix [Défaut: 1] : ").strip()

    if choix_mode == "2":
        kw = input(" Entrez le mot-clé : ").strip()
        mots_cles = [kw] if kw else MOTS_CLES_TI_DEFAUT
    else:
        mots_cles = MOTS_CLES_TI_DEFAUT
        print(f" -> Utilisation du bouquet de {len(mots_cles)} métiers TI.")
    print("-" * 65)

    # 5. Lancement de la collecte en cascade
    offres = collecteur.collecter_en_cascade(
        limit_totale=nb_offres,
        province="QC",
        mots_cles=mots_cles,
        enrichir=True
    )

    # 6. Sauvegarde
    chemin_sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "offres_emploi_canada.json")
    if offres:
        collecteur.exporter(offres, chemin_sortie)
    else:
        print("\n [INFO] Aucune offre n'a été collectée.")


def main():
    parser = argparse.ArgumentParser(
        description="Collecteur Jobs Insights (Guichet-Emplois) - Double mode CLI / Interactif."
    )
    parser.add_argument("--limit", type=int, default=100, help="Nombre maximal d'offres à collecter (défaut: 100)")
    parser.add_argument("--province", type=str, default="QC", help="Code de province (ex: QC, ON, ALL) (défaut: QC)")
    parser.add_argument("--keyword", type=str, default=None, help="Mot-clé spécifique de recherche")
    parser.add_argument("--fast", action="store_true", help="Active le mode rapide (délai 1.2s au lieu de 5.0s)")
    parser.add_argument("--no-enrich", action="store_true", help="Désactive l'enrichissement détaillé des fiches")
    parser.add_argument("--output", type=str, default="data/offres_emploi_canada.json", help="Chemin du fichier JSON de sortie")
    parser.add_argument("--skip-health-check", action="store_true", help="Ignore le test de connectivité initial")
    parser.add_argument("--non-interactif", action="store_true", help="Force le mode non-interactif sans demande utilisateur")

    # Si des arguments sont fournis en ligne de commande, utiliser le mode CLI
    if len(sys.argv) > 1 and not (len(sys.argv) == 2 and sys.argv[1].startswith("-h")):
        args = parser.parse_args()
        executer_mode_cli(args)
    elif len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        parser.parse_args()
    else:
        # Aucun argument fourni : mode interactif par défaut (double-clic)
        try:
            executer_mode_interactif()
        except KeyboardInterrupt:
            print("\n\n [!] Opération interrompue par l'utilisateur (Ctrl+C).")
        except Exception as e:
            err = traceback.format_exc()
            print(f"\n\n [ERREUR CRITIQUE] : {e}")
            print(f" Consigné dans : {FICHIER_LOG}")
            logger.critical("Erreur inattendue :\n%s", err)
        finally:
            print("\n" + "-" * 65)
            input(" Appuyez sur Entrée pour quitter...")


if __name__ == "__main__":
    main()
