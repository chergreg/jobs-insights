"""
collecte.py - Moteur de collecte réseau pour Talent.com Canada.
Gère les requêtes HTTP (User-Agent conforme), l'extraction en deux phases (recherche + détails)
et l'exportation des données standardisées JobOffer.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import List, Optional

# Assurer l'importation locale
DOSSIER = os.path.dirname(os.path.abspath(__file__))
if DOSSIER not in sys.path:
    sys.path.insert(0, DOSSIER)

import requests
from models import JobOffer
from parsers import (
    extract_job_urls_from_search_html,
    extract_json_ld_job_posting_from_detail_html,
    parse_talent_job_posting,
    is_it_offer,
    matches_keyword
)

BASE_URL = "https://ca.talent.com"

# En-têtes conformes évitant le blocage WAF / 403 de Talent.com
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TalentScraper")


class CollecteurTalent:
    """
    Collecteur d'offres d'emploi pour la plateforme Talent.com Canada avec garantie 100% TI.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def collecter(
        self,
        mot_cle: str = "informatique",
        lieu: str = "Quebec",
        limite: int = 15,
        delai: float = 0.8
    ) -> List[JobOffer]:
        """
        Recherche des offres sur Talent.com et extrait les objets JSON-LD structurés de chaque offre.
        """
        logger.info(f"Début collecte Talent.com (Mot-clé: '{mot_cle}', Lieu: '{lieu}', Cible: {limite})")
        offres: List[JobOffer] = []
        urls_vues = set()
        rejets_hors_sujet = 0

        # Estimation du nombre de pages à parcourir
        max_pages = max(1, (limite // 10) + 2)

        for page in range(1, max_pages + 1):
            search_url = f"{BASE_URL}/fr/jobs"
            params = {
                "k": mot_cle,
                "l": lieu,
            }
            if page > 1:
                params["p"] = str(page)

            try:
                resp = self.session.get(search_url, params=params, timeout=12)
                if resp.status_code != 200:
                    logger.warning(f"HTTP {resp.status_code} sur {resp.url}")
                    break

                job_urls = extract_job_urls_from_search_html(resp.text, base_url=BASE_URL)
                if not job_urls:
                    logger.info(f"Fin des offres disponibles ou aucun résultat à la page {page}.")
                    break

                logger.info(f"Page {page} : {len(job_urls)} URLs d'offres détectées.")

                for url in job_urls:
                    if url in urls_vues:
                        continue
                    urls_vues.add(url)

                    # Pause respectueuse entre requêtes
                    time.sleep(delai)

                    try:
                        resp_detail = self.session.get(url, timeout=10)
                        if resp_detail.status_code != 200:
                            continue

                        posting_data = extract_json_ld_job_posting_from_detail_html(resp_detail.text)
                        if not posting_data:
                            continue

                        offre = parse_talent_job_posting(posting_data, url_source=url)

                        # FILTRE STRICT 100% TI
                        if not is_it_offer(offre.titre, offre.description, offre.competences_cles):
                            rejets_hors_sujet += 1
                            logger.debug(f"  -> [REJETÉ NON-TI] {offre.titre}")
                            continue

                        # Filtre mot-clé
                        if mot_cle and not matches_keyword(offre.titre, offre.description, mot_cle):
                            continue

                        offres.append(offre)
                        logger.info(f"  -> [TI VALIDÉ] {offre.titre} ({offre.entreprise} - {offre.lieu})")

                        if len(offres) >= limite:
                            break

                    except requests.exceptions.RequestException as e:
                        logger.debug(f"Erreur accès offre {url} : {e}")
                        continue

                if len(offres) >= limite:
                    break

            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur de connexion réseau lors de la recherche : {e}")
                print(f"\n[ERREUR RÉSEAU] Impossible de joindre Talent.com : {e}")
                break
            except Exception as e:
                logger.error(f"Erreur inattendue à la page {page} : {e}")
                print(f"\n[ERREUR] Une anomalie est survenue : {e}")
                break

        logger.info(
            f"Collecte Talent.com terminée : {len(offres)} offres 100% TI retenues "
            f"({rejets_hors_sujet} non-TI écartées)."
        )
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
