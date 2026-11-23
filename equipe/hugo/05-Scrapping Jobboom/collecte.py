"""
collecte.py - Moteur de collecte réseau pour Jobboom Québec avec filtrage strict TI.
Gère les requêtes HTTP, la catégorie officielle TI, la pagination et l'exportation des données.
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
    parse_jobboom_json_ld,
    is_it_offer
)

BASE_URL = "https://www.jobboom.com"
CATEGORY_TI_URL = f"{BASE_URL}/fr/technologies-medias-numeriques/_i10lfr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (ProjetEtudiant-JobsInsights-Sullivan)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.jobboom.com/",
    "Connection": "keep-alive"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("JobboomScraper")


class CollecteurJobboom:
    """
    Collecteur d'offres d'emploi pour la plateforme Jobboom avec garantie 100% TI.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def obtenir_liens_page(self, mot_cle: str = "informatique", page: int = 1) -> List[str]:
        """
        Récupère les liens d'offres pour une page donnée.
        Privilégie la catégorie officielle 'Technologies et Médias Numériques' pour les recherches TI.
        """
        terme = mot_cle.strip().lower()
        if terme in ["informatique", "ti", "it", "tech", "technologie", "technologies", ""]:
            url = f"{CATEGORY_TI_URL}?sortBy=date"
            if page > 1:
                url += f"&page={page}"
        else:
            slug = quote(terme.replace(" ", "-"))
            url = f"{BASE_URL}/fr/emploi/{slug}/_lfrk"
            if page > 1:
                url += f"?page={page}"

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} sur {url}")
                return []
            return extract_job_links_from_html(resp.text, base_url=BASE_URL)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la page {page} ({url}) : {e}")
            return []

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

    def collecter(self, mot_cle: str = "informatique", limite: int = 50, delai: float = 1.0) -> List[JobOffer]:
        """
        Exécute la collecte avec pagination dynamique et filtrage strict anti-hors-sujet.
        Continue de paginer tant que le quota d'offres TI n'est pas atteint.
        """
        logger.info(f"Début collecte Jobboom ciblée TI (Mot-clé: '{mot_cle}', Quota visé: {limite} offres TI)")

        offres_validees: List[JobOffer] = []
        urls_vues: set[str] = set()
        page = 1
        rejets_hors_sujet = 0

        while len(offres_validees) < limite:
            logger.info(f"[Page {page}] Recherche des annonces...")
            liens_page = self.obtenir_liens_page(mot_cle=mot_cle, page=page)

            if not liens_page:
                logger.info(f"Fin des résultats disponibles à la page {page}.")
                break

            nouveaux_liens = [u for u in liens_page if u not in urls_vues]
            if not nouveaux_liens:
                logger.info(f"Aucun nouveau lien unique sur la page {page}, arrêt de la pagination.")
                break

            for url in nouveaux_liens:
                urls_vues.add(url)
                logger.info(f"[{len(offres_validees) + 1}/{limite}] Examen de la fiche : {url}")
                offre = self.collecter_fiche(url)
                
                if not offre:
                    continue

                # APPLICATION DU FILTRE STRICT TI
                if is_it_offer(offre.titre, offre.description, offre.competences_cles):
                    offres_validees.append(offre)
                    logger.info(f"  -> [TI VALIDÉ] {offre.titre} ({offre.entreprise})")
                else:
                    rejets_hors_sujet += 1
                    logger.info(f"  -> [REJETÉ NON-TI] {offre.titre} (Hors domaine informatique)")

                if len(offres_validees) >= limite:
                    break

                time.sleep(delai)

            page += 1
            time.sleep(1.0)

        logger.info(
            f"Collecte Jobboom terminée : {len(offres_validees)} offres 100% TI retenues "
            f"({rejets_hors_sujet} annonces hors-sujet écartées)."
        )
        return offres_validees

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
