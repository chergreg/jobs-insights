"""
collecte.py - Moteur de collecte via l'API REST de Remotive.
Extraction rapide, sans parsing HTML complexe, sans blocage anti-bot.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import List, Optional

import requests

from models import JobOffer
from parsers import is_canada_eligible, parse_remotive_job

API_URL = "https://remotive.com/api/remote-jobs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RemotiveScraper")


class CollecteurRemotive:
    """
    Collecteur d'offres d'emploi pour la plateforme Remotive via son API officielle.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "JobsInsights-Student-Project/1.0 (Canada; Education)",
            "Accept": "application/json"
        })

    def collecter(
        self,
        categorie: str = "software-dev",
        mot_cle: Optional[str] = None,
        limite: int = 20,
        filtrer_canada: bool = True
    ) -> List[JobOffer]:
        """
        Interroge l'API Remotive et convertit les offres au format JobOffer.
        """
        params = {}
        if categorie:
            params["category"] = categorie
        if mot_cle:
            params["search"] = mot_cle

        logger.info(f"Interrogation de l'API Remotive (catégorie: '{categorie}', mot-clé: '{mot_cle}')")

        try:
            resp = self.session.get(API_URL, params=params, timeout=20)
            if resp.status_code != 200:
                logger.error(f"Erreur HTTP {resp.status_code} sur l'API Remotive")
                return []

            data = resp.json()
            jobs = data.get("jobs", [])
            logger.info(f"L'API Remotive a renvoyé {len(jobs)} offres brutes.")

            offres: List[JobOffer] = []
            for raw_job in jobs:
                if filtrer_canada and not is_canada_eligible(raw_job):
                    continue

                offre = parse_remotive_job(raw_job)
                offres.append(offre)

                if len(offres) >= limite:
                    break

            logger.info(f"Retenu {len(offres)} offres éligibles (Cible max: {limite}).")
            return offres
        except Exception as e:
            logger.error(f"Erreur lors de la requête API Remotive : {e}")
            return []

    @staticmethod
    def exporter(offres: List[JobOffer], chemin_fichier: str) -> None:
        """Exporte la liste d'offres au format JSON."""
        dossier = os.path.dirname(os.path.abspath(chemin_fichier))
        if dossier and not os.path.exists(dossier):
            os.makedirs(dossier, exist_ok=True)

        data = [offre.model_dump() for offre in offres]
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Fichier exporté avec succès ({len(data)} offres) : {chemin_fichier}")
