"""
poc_emploi_canada.py - Module de compatibilité et moteur de collecte pour Guichet-Emplois.
Espace Hugo - Projet Jobs Insights.

Ce fichier redirige vers l'architecture modulaire moderne (collecte.py, parsers.py, models.py, main.py).
"""

from __future__ import annotations

import sys
import os

# Re-export des composants pour rétrocompatibilité
from models import JobOffer
from parsers import (
    parse_atom_feed,
    parse_search_page_html,
    enrich_offer_detail,
    extract_tech_skills,
    detect_stage
)
from collecte import (
    GuichetEmploisCollecteur,
    MOTS_CLES_TI_DEFAUT,
    logger,
    FICHIER_LOG
)
from main import main, executer_mode_cli, executer_mode_interactif

# Alias rétrocompatible
EmploiCanadaScraper = GuichetEmploisCollecteur

if __name__ == "__main__":
    main()
