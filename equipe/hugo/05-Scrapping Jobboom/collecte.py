"""
collecte.py - Moteur de collecte réseau pour Jobboom Québec.
Gère les requêtes HTTP, le respect des délais et l'exportation des données.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import List, Optional
from urllib.parse import quote

import requests

from models import JobOffer
from parsers import (
    extract_job_links_from_html,
    extract_json_ld_from_detail_html,
    parse_jobboom_json_ld
)

BASE_URL = "https://www.jobboom.com"

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
logger = logging.getLogger("JobboomScraper")


class CollecteurJobboom:
    """
    Collecteur d'offres d'emploi pour la plateforme Jobboom.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def obtenir_liens_recherche(self, mot_cle: str = "informatique", max_pages: int = 2) -> List[str]:
        """
        Interroge la recherche Jobboom et extrait les liens des fiches d'offres.
        """
        liens_totaux: set[str] = set()
        slug_mot_cle = quote(mot_cle.strip().replace(" ", "-"))

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/fr/emploi/{slug_mot_cle}/_lfrk"
            params = {"dk": mot_cle}
            if page > 1:
                params["page"] = str(page)

            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"Réponse HTTP {resp.status_code} sur {url}")
                    break

                liens = extract_job_links_from_html(resp.text, base_url=BASE_URL)
                if not liens:
                    logger.info(f"Fin des résultats Jobboom à la page {page}.")
                    break

                liens_totaux.update(liens)
                logger.info(f"Page {page} : {len(liens)} offres trouvées (Total unique : {len(liens_totaux)})")
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Erreur lors de la recherche Jobboom page {page} : {e}")
                break

        return sorted(list(liens_totaux))

    def collecter_fiche(self, url_offre: str) -> Optional[JobOffer]:
        """
        Télécharge et analyse une fiche d'offre Jobboom via son bloc JSON-LD.
        """
        try:
            resp = self.session.get(url_offre, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} pour l'offre {url_offre}")
                return None

            json_ld = extract_json_ld_from_detail_html(resp.text)
            if not json_ld:
                logger.warning(f"Aucun bloc JSON-LD JobPosting trouvé sur {url_offre}")
                return None

            return parse_jobboom_json_ld(json_ld, url_offre)
        except Exception as e:
            logger.error(f"Erreur d'extraction sur {url_offre} : {e}")
            return None

    def collecter(self, mot_cle: str = "informatique", limite: int = 10, delai: float = 1.0) -> List[JobOffer]:
        """
        Exécute la collecte complète : recherche des liens puis extraction des fiches.
        """
        logger.info(f"Début de collecte Jobboom (Mot-clé: '{mot_cle}', Cible: {limite} offres)")
        liens = self.obtenir_liens_recherche(mot_cle=mot_cle, max_pages=max(1, (limite // 15) + 1))
        
        offres: List[JobOffer] = []
        for idx, url in enumerate(liens[:limite], start=1):
            logger.info(f"[{idx}/{min(len(liens), limite)}] Extraction : {url}")
            offre = self.collecter_fiche(url)
            if offre:
                offres.append(offre)
            time.sleep(delai)

        logger.info(f"Collecte Jobboom terminée : {len(offres)} offres récupérées.")
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
