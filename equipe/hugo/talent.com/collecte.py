"""
collecte.py - Moteur de collecte réseau pour Talent.com Canada.
Gère les requêtes HTTP, le respect des délais et l'exportation des données.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import List, Optional

import requests

from models import JobOffer
from parsers import (
    extract_json_ld_job_postings_from_html,
    parse_talent_job_posting
)

BASE_URL = "https://ca.talent.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (ProjetEtudiant-JobsInsights-Sullivan)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TalentScraper")


class CollecteurTalent:
    """
    Collecteur d'offres d'emploi pour la plateforme Talent.com Canada.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def collecter(
        self,
        mot_cle: str = "informatique",
        lieu: str = "Quebec",
        limite: int = 15,
        delai: float = 1.0
    ) -> List[JobOffer]:
        """
        Recherche des offres sur Talent.com et extrait les objets JSON-LD structurés.
        """
        logger.info(f"Début collecte Talent.com (Mot-clé: '{mot_cle}', Lieu: '{lieu}', Cible: {limite})")
        offres: List[JobOffer] = []
        ids_vus = set()

        max_pages = max(1, (limite // 10) + 1)

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/fr/jobs"
            params = {
                "k": mot_cle,
                "l": lieu,
            }
            if page > 1:
                params["p"] = str(page)

            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"HTTP {resp.status_code} sur {url}")
                    break

                raw_postings = extract_json_ld_job_postings_from_html(resp.text)
                if not raw_postings:
                    logger.info(f"Fin des données structurées Talent.com à la page {page}.")
                    break

                logger.info(f"Page {page} : {len(raw_postings)} offres JSON-LD détectées.")

                for raw_post in raw_postings:
                    offre = parse_talent_job_posting(raw_post, default_url=url)
                    if offre.id not in ids_vus:
                        ids_vus.add(offre.id)
                        offres.append(offre)

                    if len(offres) >= limite:
                        break

                if len(offres) >= limite:
                    break

                time.sleep(delai)
            except Exception as e:
                logger.error(f"Erreur collecte Talent.com page {page} : {e}")
                break

        logger.info(f"Collecte Talent.com terminée : {len(offres)} offres récupérées.")
        return offres

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
