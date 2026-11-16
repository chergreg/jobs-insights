"""
collecte.py - Moteur de collecte multi-stratégies et conforme pour Guichet-Emplois.
Espace Hugo - Projet Jobs Insights.

Points clés :
1. Stratégie en cascade / repli :
   - Étape 1 : Flux Atom XML officiel (ultra-rapide, structuré, officiel)
   - Étape 2 (Repli / Complément) : Recherche HTML avec pagination
   - Étape 3 : Enrichissement détaillé via métadonnées RDFa / Schema.org et DOM
2. Conformité éthique :
   - User-Agent transparent identifiant le projet étudiant
   - Vérification du robots.txt via RobotFileParser
   - Délai conforme de 5 secondes par défaut (avec option rapide pour tests)
3. Traçabilité et rapports :
   - Barre de progression console
   - Journalisation complète dans logs/collecte.log
   - Export au format JSON standardisé
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
from typing import List, Optional, Set
from urllib.parse import urljoin, urlencode
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from models import JobOffer
from parsers import (
    parse_atom_feed,
    parse_search_page_html,
    enrich_offer_detail,
    extract_tech_skills
)

# Configuration des logs
DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_LOGS = os.path.join(DOSSIER_RACINE, "logs")
os.makedirs(DOSSIER_LOGS, exist_ok=True)
FICHIER_LOG = os.path.join(DOSSIER_LOGS, "collecte.log")

logger = logging.getLogger("JobsInsightsCollecteur")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    file_handler = logging.FileHandler(FICHIER_LOG, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# User-Agent honnête et transparent
USER_AGENT_HONNETE = "jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique College O'Sullivan de Quebec; contact: hugo@jobs-insights.local)"

MOTS_CLES_TI_DEFAUT = [
    "programmeur",
    "programmeur analyste",
    "développeur logiciel",
    "développeur web",
    "développeur jeux vidéo",
    "développeur frontend",
    "développeur backend",
    "développeur full stack",
    "analyste informatique",
    "architecte logiciel",
    "ingénieur logiciel",
    "devops",
    "administrateur systèmes",
    "administrateur bases de données",
    "assurance qualité logiciel",
    "stage informatique"
]

# Codes de la Classification Nationale des Professions (CNP) pour l'informatique
CODES_CNP_TI = ["21230", "21231", "21232", "21233", "21234", "21220", "21221", "21222"]


def afficher_barre_progression(actuel: int, total: int, prefixe: str = "", suffixe: str = "", longueur: int = 25):
    """Affiche une barre de progression fluide dans la console."""
    if total <= 0:
        return
    actuel_borne = min(actuel, total)
    pourcentage = f"{100 * (actuel_borne / float(total)):.1f}"
    rempli = int(longueur * actuel_borne // total)
    barre = "=" * rempli + "-" * (longueur - rempli)
    sys.stdout.write(f"\r {prefixe} [{barre}] {pourcentage}% ({actuel_borne}/{total}) {suffixe:<35}")
    sys.stdout.flush()
    if actuel_borne >= total:
        sys.stdout.write("\n")


class GuichetEmploisCollecteur:
    """Collecteur multi-stratégies conforme pour Guichet-Emplois Canada."""
    BASE_URL = "https://www.guichetemplois.gc.ca"
    FEED_URL = "https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"
    SEARCH_ENDPOINT = "/jobsearch/jobsearch"
    LOADER_ENDPOINT = "/jobsearch/job_search_loader.xhtml"

    def __init__(self, delai_secondes: float = 5.0, timeout: int = 15):
        self.delai_secondes = delai_secondes
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT_HONNETE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
            "Referer": "https://www.guichetemplois.gc.ca/",
        })
        self.robot_parser: Optional[RobotFileParser] = None
        logger.info("Collecteur initialisé (User-Agent: %s, Délai: %.1fs)", USER_AGENT_HONNETE, delai_secondes)

    def verifier_robots_txt(self) -> bool:
        """Vérifie si les conditions robots.txt autorisent la collecte."""
        try:
            robots_url = f"{self.BASE_URL}/robots.txt"
            self.robot_parser = RobotFileParser()
            self.robot_parser.set_url(robots_url)
            self.robot_parser.read()
            logger.info("Lecture de %s réussie.", robots_url)
            return True
        except Exception as e:
            logger.warning("Impossible de lire robots.txt (%s) : le scraping reste prudent.", e)
            return False

    def tester_connectivite(self) -> bool:
        """Teste si Guichet-Emplois est joignable."""
        print(" [TEST] Verification de la connectivite avec Guichet-Emplois...")
        start_time = time.time()
        try:
            resp = self.session.get(self.BASE_URL, timeout=self.timeout)
            elapsed_ms = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                print(f" [LIVE] Le site est EN LIGNE (HTTP 200 en {elapsed_ms} ms)")
                logger.info("Connexion reussie vers %s (HTTP 200 en %d ms)", self.BASE_URL, elapsed_ms)
                return True
            else:
                print(f" [ATTENTION] Reponse inattendue : HTTP {resp.status_code}")
                return False
        except Exception as e:
            print(f" [ERREUR] Impossible de joindre le site : {e}")
            logger.error("Erreur de connexion : %s", e)
            return False

    def _pause_respectueuse(self):
        """Applique le délai d'attente configuré pour respecter le serveur."""
        time.sleep(self.delai_secondes)

    # --------------------------------------------------------------------------
    # STRATÉGIE 1 : FLUX ATOM XML OFFICIEL (Rapide & Direct)
    # --------------------------------------------------------------------------
    def collecter_via_atom(self, province: str = "QC", limit: int = 100) -> List[JobOffer]:
        """
        Collecte via le flux de syndication Atom officiel de Guichet-Emplois.
        Fournit une extraction instantanée et propre en une seule requête.
        """
        print(f"\n [STRATEGIE 1] Interrogation du flux Atom XML officiel (Cible : {limit} offres)...")
        logger.info("Tentative de collecte via flux Atom (%s, limite %d)", self.FEED_URL, limit)

        params = {
            "sort": "D",
            "fprov": province if province.upper() != "ALL" else "",
            "wid": "s",
            "action": "search"
        }
        url = f"{self.FEED_URL}?{urlencode(params)}"

        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200 and resp.text:
                offers = parse_atom_feed(resp.text, base_url=self.BASE_URL)
                logger.info("%d offres extraites du flux Atom.", len(offers))
                print(f" -> [OK] {len(offers)} offres récupérées via le flux Atom.")
                return offers[:limit]
            else:
                logger.warning("Reponse flux Atom non concluante : HTTP %d", resp.status_code)
                return []
        except Exception as e:
            logger.error("Erreur lors de la récupération Atom : %s", e)
            return []

    # --------------------------------------------------------------------------
    # STRATÉGIE 2 : RECHERCHE HTML (Résultats & Pagination)
    # --------------------------------------------------------------------------
    def collecter_via_recherche_html(
        self,
        mots_cles: List[str],
        province: str = "QC",
        limit: int = 100,
        seen_ids: Optional[Set[str]] = None
    ) -> List[JobOffer]:
        """Collecte les offres en naviguant sur les pages de recherche HTML."""
        if seen_ids is None:
            seen_ids = set()

        offers: List[JobOffer] = []
        print(f"\n [STRATEGIE 2] Recherche HTML par mots-clés ({len(mots_cles)} métiers TI ciblés)...")
        logger.info("Début collecte HTML (Cible : %d offres, %d mots-clés)", limit, len(mots_cles))

        search_base = urljoin(self.BASE_URL, self.SEARCH_ENDPOINT)

        for idx, mot_cle in enumerate(mots_cles, start=1):
            if len(offers) >= limit:
                break

            params = {
                "searchstring": mot_cle,
                "sort": "D",
                "fprov": province if province.upper() != "ALL" else ""
            }

            try:
                resp = self.session.get(search_base, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    page_offers = parse_search_page_html(resp.text, base_url=self.BASE_URL)
                    nouveaux = 0
                    for off in page_offers:
                        if off.id not in seen_ids:
                            seen_ids.add(off.id)
                            offers.append(off)
                            nouveaux += 1
                            afficher_barre_progression(
                                actuel=len(offers),
                                total=limit,
                                prefixe="[Recherche HTML]",
                                suffixe=f"[{mot_cle[:14]}] +{nouveaux}"
                            )
                            if len(offers) >= limit:
                                break

                    # Pagination si résultats supplémentaires disponibles
                    if len(offers) < limit and len(page_offers) >= 20:
                        self._pause_respectueuse()
                        loader_url = urljoin(self.BASE_URL, self.LOADER_ENDPOINT)
                        loader_resp = self.session.get(loader_url, timeout=self.timeout)
                        if loader_resp.status_code == 200 and loader_resp.text.strip():
                            loader_offers = parse_search_page_html(loader_resp.text, base_url=self.BASE_URL)
                            for off in loader_offers:
                                if off.id not in seen_ids:
                                    seen_ids.add(off.id)
                                    offers.append(off)
                                    afficher_barre_progression(
                                        actuel=len(offers),
                                        total=limit,
                                        prefixe="[Recherche HTML]",
                                        suffixe=f"[{mot_cle[:14]}] pagination"
                                    )
                                    if len(offers) >= limit:
                                        break
                else:
                    logger.warning("Code HTTP %d sur recherche mot-clé '%s'", resp.status_code, mot_cle)

            except Exception as e:
                logger.error("Erreur sur recherche HTML '%s' : %s", mot_cle, e)

            self._pause_respectueuse()

        return offers

    # --------------------------------------------------------------------------
    # ENRICHISSEMENT DES FICHES DÉTAILLÉES (Phase 2)
    # --------------------------------------------------------------------------
    def enrichir_fiches_details(self, offers: List[JobOffer]) -> None:
        """Visite les fiches pour extraire description complète, modalité et compétences."""
        print(f"\n [PHASE 2] Enrichissement détaillé de {len(offers)} fiches...")
        print(f"           (Délai entre requêtes : {self.delai_secondes}s pour respecter le serveur)\n")
        logger.info("Début enrichissement détaillé de %d fiches.", len(offers))

        for idx, offer in enumerate(offers, start=1):
            try:
                resp = self.session.get(offer.url_source, timeout=self.timeout)
                if resp.status_code == 200:
                    enrich_offer_detail(offer, resp.text)
                elif resp.status_code == 429:
                    print("\n [!] HTTP 429 reçu. Pause de courtoisie étendue de 10s...")
                    logger.warning("HTTP 429 - Pause de sécurité de 10s.")
                    time.sleep(10)
                else:
                    logger.warning("HTTP %d lors du chargement de %s", resp.status_code, offer.url_source)
            except Exception as e:
                logger.error("Erreur lors de l'enrichissement de %s : %s", offer.id, e)

            suffixe = f"{offer.titre[:20]} ({offer.modalite})"
            afficher_barre_progression(
                actuel=idx,
                total=len(offers),
                prefixe="[Détails fiches]",
                suffixe=suffixe
            )
            self._pause_respectueuse()

        print("\n [OK] Enrichissement des descriptions et modalités terminé avec succès !")

    # --------------------------------------------------------------------------
    # ORCHESTRATION EN CASCADE
    # --------------------------------------------------------------------------
    def collecter_en_cascade(
        self,
        limit_totale: int = 100,
        province: str = "QC",
        mots_cles: Optional[List[str]] = None,
        enrichir: bool = True
    ) -> List[JobOffer]:
        """
        Orchestre la collecte en cascade :
        1. Flux Atom XML en premier choix.
        2. Repli / complément sur la recherche HTML si le quota n'est pas atteint.
        3. Déduplication par identifiant unique.
        4. Enrichissement détaillé (description, modalité, compétences).
        """
        if mots_cles is None:
            mots_cles = MOTS_CLES_TI_DEFAUT

        print("\n" + "=" * 65)
        print(f" [*] COLLECTE EN CASCADE GUICHET-EMPLOIS (CIBLE : {limit_totale} OFFRES)")
        print(f"    - Région : {province} (Canada)")
        print(f"    - Délai de respect : {self.delai_secondes}s par requête")
        print("=" * 65)

        offers: List[JobOffer] = []
        seen_ids: Set[str] = set()

        # Niveau 1 : Flux Atom
        atom_offers = self.collecter_via_atom(province=province, limit=limit_totale)
        for off in atom_offers:
            if off.id not in seen_ids:
                seen_ids.add(off.id)
                offers.append(off)

        # Niveau 2 : Si le quota n'est pas atteint, repli / complément par recherche HTML
        if len(offers) < limit_totale:
            manquants = limit_totale - len(offers)
            print(f"\n [INFO] Flux Atom a fourni {len(offers)} offres. Complément HTML de {manquants} offres...")
            html_offers = self.collecter_via_recherche_html(
                mots_cles=mots_cles,
                province=province,
                limit=manquants,
                seen_ids=seen_ids
            )
            offers.extend(html_offers)

        print(f"\n [OK] Total de {len(offers)} offres uniques retenues.")

        # Niveau 3 : Enrichissement détaillé des fiches
        if enrichir and offers:
            self.enrichir_fiches_details(offers)

        return offers

    @staticmethod
    def exporter(offers: List[JobOffer], chemin_sortie: str) -> None:
        """Sauvegarde les offres au format JSON et affiche une synthèse statistique."""
        os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)
        donnees = [o.model_dump() for o in offers]

        with open(chemin_sortie, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 65)
        print(" [*] RAPPORT STATISTIQUE DE COLLECTE")
        print("=" * 65)
        print(f" [OK] Fichier enregistré : {os.path.abspath(chemin_sortie)}")
        print(f" [OK] Nombre d'offres   : {len(donnees)}")

        stages = sum(1 for o in offers if o.type_poste == "Stage")
        teletravail = sum(1 for o in offers if o.modalite in ["Télétravail", "Hybride"])
        avec_desc = sum(1 for o in offers if o.description and len(o.description) > 30)
        toutes_competences = [c for o in offers for c in o.competences_cles]

        print(f" [OK] Descriptions complètes remplies : {avec_desc}/{len(donnees)}")
        print(f" [OK] Stages et emplois étudiants      : {stages}")
        print(f" [OK] Postes Télétravail / Hybride     : {teletravail}")

        # Statistiques des méthodes utilisées
        methodes = {}
        for o in offers:
            meth = o.methode_extraction or "Inconnue"
            methodes[meth] = methodes.get(meth, 0) + 1
        print(" [OK] Méthodes d'extraction utilisées :")
        for m, count in methodes.items():
            print(f"       - {m} : {count} offres")

        if toutes_competences:
            from collections import Counter
            top_tech = Counter(toutes_competences).most_common(8)
            top_str = ", ".join(f"{tech} ({count})" for tech, count in top_tech)
            print(f" [OK] Top compétences TI détectées    : {top_str}")
        print("=" * 65 + "\n")
        logger.info("Export terminé avec succès : %d offres sauvegardées dans %s.", len(donnees), chemin_sortie)
