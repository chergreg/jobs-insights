"""
collecte.py - Moteur de collecte via l'API REST de Remotive avec filtrage strict TI.
Gère les requêtes HTTP, le respect de la vie privée, le filtrage bilingue et l'exportation des données.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import List, Optional

# Assurer l'importation locale
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)

import requests
from models import JobOffer
from parsers import (
    is_canada_eligible,
    is_it_offer,
    matches_keyword,
    parse_remotive_job
)

API_URL = "https://remotive.com/api/remote-jobs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RemotiveScraper")


class CollecteurRemotive:
    """
    Collecteur d'offres d'emploi pour la plateforme Remotive via son API officielle avec garantie 100% TI.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 (ProjetEtudiant-JobsInsights-Sullivan)"
            ),
            "Accept": "application/json"
        })

    def collecter(
        self,
        categorie: Optional[str] = "software-development",
        mot_cle: Optional[str] = None,
        limite: int = 20,
        filtrer_canada: bool = True
    ) -> List[JobOffer]:
        """
        Interroge l'API Remotive et filtre strictement les offres TI accessibles au Canada.
        Effectue un double filtrage (serveur + client) pour garantir l'absence d'offres hors-sujet.
        """
        params = {}
        # Normaliser les catégories pour l'API Remotive
        cat_api = None
        if categorie:
            cat_clean = categorie.strip().lower()
            if cat_clean in ["software-dev", "software-development", "dev", "programmation"]:
                cat_api = "software-development"
            elif cat_clean in ["devops", "cloud"]:
                cat_api = "devops"
            elif cat_clean in ["data", "donnees", "ai"]:
                cat_api = "data"
            elif cat_clean in ["qa", "test"]:
                cat_api = "qa"
            else:
                cat_api = cat_clean
            params["category"] = cat_api

        if mot_cle:
            params["search"] = mot_cle.strip()

        logger.info(f"Interrogation de l'API Remotive (catégorie: '{cat_api or 'Toutes TI'}', filtre: '{mot_cle or 'Tous'}')...")

        try:
            resp = self.session.get(API_URL, params=params, timeout=15)
            if resp.status_code != 200:
                logger.error(f"Erreur HTTP {resp.status_code} sur l'API Remotive")
                return []

            data = resp.json()
            jobs = data.get("jobs", [])
            logger.info(f"L'API Remotive a renvoyé {len(jobs)} offres brutes.")

            offres: List[JobOffer] = []
            rejets_hors_sujet = 0
            rejets_geo = 0

            for raw_job in jobs:
                # 1. Filtre d'éligibilité géographique Canada
                if filtrer_canada and not is_canada_eligible(raw_job):
                    rejets_geo += 1
                    continue

                offre = parse_remotive_job(raw_job)

                # 2. FILTRE STRICT TI (Écarte Content Reviewer, Marketing, Rédaction, etc.)
                if not is_it_offer(offre.titre, offre.description, offre.competences_cles):
                    rejets_hors_sujet += 1
                    logger.debug(f"  -> [REJETÉ NON-TI] {offre.titre}")
                    continue

                # 3. Filtre mot-clé bilingue côté client (car l'API ne filtre pas toujours correctement)
                tags = raw_job.get("tags") or []
                if mot_cle and not matches_keyword(offre.titre, offre.description, tags, mot_cle):
                    continue

                offres.append(offre)
                logger.info(f"  -> [TI VALIDÉ] {offre.titre} ({offre.entreprise})")

                if len(offres) >= limite:
                    break

            logger.info(
                f"Collecte Remotive terminée : {len(offres)} offres 100% TI retenues "
                f"({rejets_hors_sujet} non-TI écartées, {rejets_geo} hors Canada écartées)."
            )
            return offres

        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de connexion réseau avec Remotive API : {e}")
            print(f"\n[ERREUR RÉSEAU] Impossible de joindre l'API Remotive : {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la collecte Remotive : {e}")
            print(f"\n[ERREUR] Une anomalie est survenue : {e}")
            return []

    @staticmethod
    def exporter(offres: List[JobOffer], chemin_fichier: str) -> None:
        """Exporte la liste d'offres au format JSON avec création automatique des dossiers."""
        dossier = os.path.dirname(os.path.abspath(chemin_fichier))
        if dossier and not os.path.exists(dossier):
            os.makedirs(dossier, exist_ok=True)

        data = [offre.model_dump() for offre in offres]
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Fichier exporté avec succès ({len(data)} offres) : {chemin_fichier}")
