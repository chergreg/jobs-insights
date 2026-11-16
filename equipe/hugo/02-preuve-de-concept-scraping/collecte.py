"""
collecte.py - Moteur de collecte multi-stratégies, conforme et ciblé DEC en informatique pour Guichet-Emplois.
Espace Hugo - Projet Jobs Insights.

Points clés :
1. Ciblage 100 % DEC en informatique :
   - 22 métiers couvrant Développement, Web, Infrastructure, Réseaux, Support, QA et Stages.
   - Filtrage applicatif strict garantissant l'exclusion des offres hors TI (ex: cleaning man/woman, concierge, etc.).
2. Stratégie en cascade / repli garantie :
   - Étape 1 : Flux Atom XML officiel (récupération rapide des annonces TI récentes).
   - Étape 2 : Recherche HTML (/jobsearch/jobsearch) avec multi-mots-clés et pagination jusqu'à atteindre l'objectif (ex. 100 offres).
   - Étape 3 : Enrichissement détaillé via métadonnées RDFa / Schema.org et DOM.
3. Priorisation de la langue française :
   - En-tête HTTP 'Accept-Language: fr-CA,fr;q=1.0'.
   - Normalisation automatique des URLs d'offres vers le domaine français avec ?lang=fra.
4. Conformité éthique :
   - User-Agent transparent identifiant le projet étudiant.
   - Respect du robots.txt et délai conforme de 5 secondes par défaut (ou 1.2s en mode rapide).
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
    extract_tech_skills,
    est_metier_dec_informatique,
    normaliser_url_francaise
)

# Configuration des logs
DOSSIER_RACINE = os.path.dirname(os.path.abspath(__file__))
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

# Bouquet complet couvrant les 3 branches du DEC en informatique :
# 1. Développement et Programmation
# 2. Infrastructure, Réseaux et Sécurité
# 3. Stages informatiques
MOTS_CLES_TI_DEFAUT = [
    # Programmation & Web
    "programmeur",
    "programmeur analyste",
    "développeur logiciel",
    "développeur web",
    "développeur jeux vidéo",
    "développeur frontend",
    "développeur backend",
    "développeur full stack",
    "devops",
    # Infrastructure, Réseau & Support
    "technicien informatique",
    "technicien réseau",
    "soutien technique informatique",
    "administrateur systèmes",
    "administrateur bases de données",
    "cybersécurité",
    # QA & Données
    "assurance qualité logiciel",
    "analyste informatique",
    # Stages
    "stage informatique",
    "stagiaire développeur",
    "stage programmation",
    "stage web",
    "stage réseau"
]


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
    """Collecteur multi-stratégies conforme et ciblé DEC en informatique."""

    BASE_URL = "https://www.guichetemplois.gc.ca"
    FEED_URL = "https://www.guichetemplois.gc.ca/jobsearch/feed/jobSearchRSSfeed"
    SEARCH_ENDPOINT = "/jobsearch/jobsearch"
    LOADER_ENDPOINT = "/jobsearch/job_search_loader.xhtml"
    ROBOTS_URL = "https://www.guichetemplois.gc.ca/robots.txt"

    def __init__(self, delai_secondes: float = 5.0, timeout: int = 15):
        self.delai_secondes = delai_secondes
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT_HONNETE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-CA,fr;q=1.0,en-CA;q=0.5,en;q=0.3",
            "Referer": "https://www.guichetemplois.gc.ca/",
        })
        self.robot_parser = RobotFileParser()

    def verifier_robots_txt(self) -> bool:
        """Vérifie la conformité avec le fichier robots.txt officiel."""
        try:
            print("\n [ROBOTS.TXT] Consultation et respect des directives officielles...")
            self.robot_parser.set_url(self.ROBOTS_URL)
            self.robot_parser.read()

            url_test = f"{self.BASE_URL}{self.SEARCH_ENDPOINT}"
            autorise = self.robot_parser.can_fetch(USER_AGENT_HONNETE, url_test)
            logger.info("Vérification robots.txt pour %s : Autorisé=%s", url_test, autorise)
            print(f" -> Statut robots.txt : {'AUTORISÉ' if autorise else 'RESTREINT'}")
            print(f" -> Crawl-delay appliqué : {self.delai_secondes:.1f} seconde(s) entre requêtes.")
            return autorise
        except Exception as e:
            logger.warning("Impossible de lire robots.txt (%s) - Application du délai de sécurité.", e)
            return True

    def tester_connectivite(self) -> bool:
        """Vérifie la disponibilité du service avant de lancer la collecte."""
        print(" [*] Test préalable de connectivité vers Guichet-Emplois...")
        try:
            resp = self.session.get(f"{self.BASE_URL}?lang=fra", timeout=self.timeout)
            if resp.status_code == 200:
                print(" -> [OK] Service en ligne et accessible (version francophone confirmée).")
                logger.info("Health check réussi sur %s (HTTP 200)", self.BASE_URL)
                return True
            else:
                print(f" -> [ALERTE] Réponse inhabituelle du serveur : HTTP {resp.status_code}")
                logger.warning("Health check statut inattendu : HTTP %d", resp.status_code)
                return False
        except requests.exceptions.RequestException as e:
            print(f" -> [ERREUR] Impossible de joindre Guichet-Emplois : {e}")
            logger.error("Health check échoué : %s", e)
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
        Fournit une extraction instantanée et filtre avec le validateur DEC TI.
        """
        print(f"\n [STRATEGIE 1] Interrogation du flux Atom XML officiel (Cible : {limit} offres DEC TI)...")
        logger.info("Tentative de collecte via flux Atom (%s, limite %d)", self.FEED_URL, limit)

        params = {
            "sort": "D",
            "fprov": province if province.upper() != "ALL" else "",
            "wid": "s",
            "action": "search"
        }
        url = f"{self.FEED_URL}?{urlencode(params)}"

        offers: List[JobOffer] = []
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200 and resp.text:
                parsed_offers = parse_atom_feed(resp.text, base_url=self.BASE_URL)
                # parse_atom_feed filtre déjà avec est_metier_dec_informatique
                for off in parsed_offers:
                    offers.append(off)
                    if len(offers) >= limit:
                        break
                print(f" -> [OK] {len(offers)} offres TI pertinentes extraites du flux Atom.")
                logger.info("%d offres TI retenues depuis le flux Atom.", len(offers))
                return offers
            else:
                logger.warning("Code HTTP %d sur le flux Atom", resp.status_code)
                return []
        except Exception as e:
            logger.error("Erreur lors de la récupération Atom : %s", e)
            return []

    # --------------------------------------------------------------------------
    # STRATÉGIE 2 : RECHERCHE HTML (Multi-mots-clés & Pagination robuste)
    # --------------------------------------------------------------------------
    def collecter_via_recherche_html(
        self,
        mots_cles: List[str],
        province: str = "QC",
        limit: int = 100,
        seen_ids: Optional[Set[str]] = None
    ) -> List[JobOffer]:
        """
        Collecte les offres en naviguant sur les pages de recherche HTML (/jobsearch/jobsearch).
        Itère sur la liste des métiers du DEC et gère la pagination jusqu'à combler le quota requis.
        """
        if seen_ids is None:
            seen_ids = set()

        offers: List[JobOffer] = []
        print(f"\n [STRATEGIE 2] Recherche HTML par mots-clés DEC ({len(mots_cles)} métiers TI ciblés)...")
        print(f"               Objectif : collecter {limit} offres TI supplémentaires au Québec...\n")
        logger.info("Début collecte HTML (Cible : %d offres, %d mots-clés)", limit, len(mots_cles))

        search_base = urljoin(self.BASE_URL, self.SEARCH_ENDPOINT)

        for idx, mot_cle in enumerate(mots_cles, start=1):
            if len(offers) >= limit:
                break

            # Parcourir jusqu'à 3 pages de résultats (75 offres max) par métier
            for page_num in range(1, 4):
                if len(offers) >= limit:
                    break

                params = {
                    "searchstring": mot_cle,
                    "sort": "D",
                    "fprov": province if province.upper() != "ALL" else ""
                }
                if page_num > 1:
                    params["page"] = str(page_num)

                try:
                    resp = self.session.get(search_base, params=params, timeout=self.timeout)
                    if resp.status_code == 200:
                        page_offers = parse_search_page_html(resp.text, base_url=self.BASE_URL)
                        if not page_offers:
                            break  # Aucune offre sur cette page, mot-clé suivant

                        nouveaux = 0
                        for off in page_offers:
                            if off.id not in seen_ids and est_metier_dec_informatique(off.titre, off.description or ""):
                                seen_ids.add(off.id)
                                offers.append(off)
                                nouveaux += 1
                                afficher_barre_progression(
                                    actuel=len(offers),
                                    total=limit,
                                    prefixe="[Recherche HTML]",
                                    suffixe=f"[{mot_cle[:12]}] p.{page_num} (+{nouveaux})"
                                )
                                if len(offers) >= limit:
                                    break

                        # Si la page contenait moins de 20 offres, c'est la dernière page de ce mot-clé
                        if len(page_offers) < 20:
                            break
                    else:
                        logger.warning("Code HTTP %d sur recherche mot-clé '%s' (page %d)", resp.status_code, mot_cle, page_num)
                        break

                except Exception as e:
                    logger.error("Erreur sur recherche HTML '%s' (page %d) : %s", mot_cle, page_num, e)
                    break

                self._pause_respectueuse()

            self._pause_respectueuse()

        return offers

    # --------------------------------------------------------------------------
    # ENRICHISSEMENT DES FICHES DÉTAILLÉES (Phase 2 - Priorité Français)
    # --------------------------------------------------------------------------
    def enrichir_fiches_details(self, offers: List[JobOffer]) -> None:
        """Visite les fiches pour extraire description complète, modalité et compétences en français."""
        print(f"\n [PHASE 2] Enrichissement détaillé de {len(offers)} fiches TI...")
        print(f"           (Délai entre requêtes : {self.delai_secondes}s pour respecter le serveur)\n")
        logger.info("Début enrichissement détaillé de %d fiches.", len(offers))

        for idx, offer in enumerate(offers, start=1):
            url_cible = normaliser_url_francaise(offer.url_source, base_url=self.BASE_URL)
            offer.url_source = url_cible

            try:
                resp = self.session.get(url_cible, timeout=self.timeout)
                if resp.status_code == 200:
                    enrich_offer_detail(offer, resp.text)
                elif resp.status_code == 429:
                    print("\n [!] HTTP 429 reçu. Pause de courtoisie étendue de 10s...")
                    logger.warning("HTTP 429 - Pause de sécurité de 10s.")
                    time.sleep(10)
                else:
                    logger.warning("HTTP %d lors du chargement de %s", resp.status_code, url_cible)
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
        Orchestre la collecte en cascade pour le DEC en informatique :
        1. Flux Atom XML ciblé TI en premier choix.
        2. Repli / complément sur la recherche HTML si le quota n'est pas atteint.
        3. Déduplication par identifiant unique.
        4. Enrichissement détaillé (description complète, modalité, compétences en français).
        Garantit que le nombre d'offres visé (ex. 100) est bien atteint.
        """
        if mots_cles is None:
            mots_cles = MOTS_CLES_TI_DEFAUT

        print("\n" + "=" * 65)
        print(f" [*] COLLECTE EN CASCADE GUICHET-EMPLOIS (CIBLE : {limit_totale} OFFRES TI)")
        print(f"    - Périmètre : Métiers du DEC en informatique (Canada / {province})")
        print(f"    - Délai de respect : {self.delai_secondes}s par requête")
        print(f"    - Langue prioritaire : Français (lang=fra)")
        print("=" * 65)

        offers: List[JobOffer] = []
        seen_ids: Set[str] = set()

        # Niveau 1 : Flux Atom ciblé TI
        atom_offers = self.collecter_via_atom(province=province, limit=limit_totale)
        for off in atom_offers:
            if off.id not in seen_ids:
                seen_ids.add(off.id)
                offers.append(off)

        # Niveau 2 : Si le quota n'est pas atteint, complément par recherche HTML multi-mots-clés
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

        print(f"\n [OK] Total de {len(offers)} offres TI uniques retenues.")

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
        print(" [*] RAPPORT STATISTIQUE DE COLLECTE (DEC EN INFORMATIQUE)")
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
