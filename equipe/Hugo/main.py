"""
main.py - Point d'entrée principal pour l'application Jobs Insights (Espace Hugo).
Lançable directement par double-clic dans Windows ou depuis le terminal.
"""

import sys
import os
import traceback

from poc_emploi_canada import main, logger, FICHIER_LOG

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n [!] Collecte interrompue par l'utilisateur.")
        logger.warning("Interruption manuelle par l'utilisateur (Ctrl+C).")
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"\n\n [ERREUR CRITIQUE DE PLANTAGE] : {e}")
        print(f" [!] Le détail du plantage a été consigné dans : {FICHIER_LOG}")
        logger.critical("PLANTAGE CRITIQUE :\n%s", err_msg)
    finally:
        print("\n" + "-" * 65)
        input(" Appuyez sur Entrée pour quitter...")
