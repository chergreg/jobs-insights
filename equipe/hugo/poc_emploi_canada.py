"""
poc_emploi_canada.py - Collecteur interactif et autonome pour Guichet-Emplois (Canada).
Espace Hugo - Projet Jobs Insights.

Fonctionnalités avancées :
1. Recherche multi-mots-clés ciblée 100 % informatique (Programmeurs, Analystes, Jeux vidéo, Web, etc.).
2. Déduplication automatique des offres entre les différents mots-clés.
3. Barre de progression dynamique en temps réel dans la console.
4. Système de journalisation complet (logs/collecte.log) pour enregistrer les requêtes, erreurs et plantages.
5. Auto-installation des dépendances (requests, bs4, pydantic).
6. Test préalable de connectivité (Health check).
7. Requêtes humaines respectueuses (délais aléatoires anti-blocage).
8. Export standardisé en JSON.
"""

import sys
import os

# Configuration de l'encodage console pour Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import subprocess
import time
import random
import re
import json
import logging
import traceback
from typing import List, Optional, Set
from urllib.parse import urljoin

# =====================================================================
# 1. AUTO-VÉRIFICATION & INSTALLATION DES DÉPENDANCES
# =====================================================================
def verifier_et_installer_dependances():
    """Vérifie et installe automatiquement les dépendances requises."""
    packages_requis = {
        "requests": "requests>=2.31.0",
        "bs4": "beautifulsoup4>=4.12.0",
        "pydantic": "pydantic>=2.0.0"
    }
    
    print("\n" + "=" * 65)
    print(" [*] VERIFICATION DE L'ENVIRONNEMENT ET DES DEPENDANCES")
    print("=" * 65)
    
    a_installe = False
    for module_name, pkg_spec in packages_requis.items():
        try:
            __import__(module_name)
            print(f" [OK] Dependance presente : {pkg_spec.split('>=')[0]}")
        except ImportError:
            print(f" [!] Dependance manquante detectee : {pkg_spec}")
            print(f"     Installation en cours via pip... Veuillez patienter.")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg_spec],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                print(f"     -> [OK] {pkg_spec} a ete installe avec succes.")
                a_installe = True
            except Exception as e:
                print(f"     -> [ERREUR CRITIQUE] Impossible d'installer {pkg_spec} : {e}")
                sys.exit(1)
                
    if not a_installe:
        print(" [OK] Toutes les dependances sont pretes.\n")
    else:
        print(" [OK] Environnement complete avec succes.\n")

verifier_et_installer_dependances()

import requests
from bs4 import BeautifulSoup
from models import JobOffer

# =====================================================================
# 2. CONFIGURATION DES LOGS (FICHIER ET ERREURS DE PLANTAGE)
# =====================================================================
DOSSIER_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(DOSSIER_LOGS, exist_ok=True)
FICHIER_LOG = os.path.join(DOSSIER_LOGS, "collecte.log")

logger = logging.getLogger("EmploiCanadaScraper")
logger.setLevel(logging.DEBUG)

# Handler fichier : enregistre tout (DEBUG, INFO, WARNING, ERROR, CRITICAL + stack traces)
file_handler = logging.FileHandler(FICHIER_LOG, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# =====================================================================
# 3. LISTE ÉTENDUE DE MOTS-CLÉS 100% INFORMATIQUE
# =====================================================================
MOTS_CLES_INFORMATIQUE = [
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

USER_AGENTS_HUMAINS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0"
]

TECH_KEYWORDS = [
    "python", "java", "c#", ".net", "c++", "c", "javascript", "typescript",
    "react", "angular", "vue", "vue.js", "node", "node.js", "sql",
    "postgresql", "mysql", "mongodb", "docker", "kubernetes", "aws",
    "azure", "gcp", "git", "linux", "html", "css", "django", "fastapi",
    "spring", "spring boot", "php", "agile", "scrum", "jira", "ci/cd",
    "rest", "api", "devops", "cloud", "qa", "machine learning", "ia",
    "unity", "unreal", "unreal engine", "godot", "shader", "opengl"
]


# =====================================================================
# 4. BARRE DE PROGRESSION CONSOLE
# =====================================================================
def afficher_barre_progression(actuel: int, total: int, prefixe: str = "", suffixe: str = "", longueur: int = 25):
    """Affiche une barre de progression fluide et universellement compatible."""
    if total <= 0:
        return
    actuel_borne = min(actuel, total)
    pourcentage = f"{100 * (actuel_borne / float(total)):.1f}"
    rempli = int(longueur * actuel_borne // total)
    barre = "=" * rempli + "-" * (longueur - rempli)
    # Affichage dynamique avec remplacement de ligne
    sys.stdout.write(f"\r {prefixe} [{barre}] {pourcentage}% ({actuel_borne}/{total}) {suffixe:<35}")
    sys.stdout.flush()
    if actuel_borne >= total:
        sys.stdout.write("\n")


# =====================================================================
# 5. MOTEUR DE COLLECTE (SCRAPER)
# =====================================================================
class EmploiCanadaScraper:
    """Collecteur Guichet-Emplois avec recherche multi-mots-clés, gestion des logs et barre de progression."""
    BASE_URL = "https://www.guichetemplois.gc.ca"
    SEARCH_ENDPOINT = "/jobsearch/jobsearch"
    LOADER_ENDPOINT = "/jobsearch/job_search_loader.xhtml"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS_HUMAINS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7",
            "Referer": "https://www.guichetemplois.gc.ca/",
            "Connection": "keep-alive"
        })
        logger.info("Session de scraping initialisée avec User-Agent: %s", self.session.headers["User-Agent"])

    def tester_connectivite(self) -> bool:
        """Teste si Guichet-Emplois répond (Health check)."""
        print(" [TEST] Verification de la connectivite avec Emploi Canada...")
        logger.info("Test de connectivite vers %s", self.BASE_URL)
        start_time = time.time()
        try:
            resp = self.session.get(self.BASE_URL, timeout=self.timeout)
            elapsed_ms = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                print(f" [LIVE] Le site Emploi Canada est EN LIGNE (HTTP 200 - {elapsed_ms} ms)")
                logger.info("Connexion reussie (HTTP 200 en %d ms)", elapsed_ms)
                return True
            else:
                print(f" [ATTENTION] Reponse inattendue : HTTP {resp.status_code} ({elapsed_ms} ms)")
                logger.warning("Reponse inattendue lors du test : HTTP %s", resp.status_code)
                return False
        except requests.exceptions.Timeout:
            print(" [ERREUR] Delai d'attente depasse (Timeout) pour Emploi Canada.")
            logger.error("Timeout lors de la requete de connectivite.")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f" [ERREUR] Impossible de joindre Emploi Canada : {e}")
            logger.error("Erreur de connexion : %s", e)
            return False
        except Exception as e:
            print(f" [ERREUR] Erreur inattendue : {e}")
            logger.exception("Exception inattendue lors du test de connectivite : %s", e)
            return False

    def _pause_humaine(self, mini: float = 1.1, maxi: float = 2.2):
        """Pause non invasive simulant le comportement d'un utilisateur humain."""
        delay = round(random.uniform(mini, maxi), 2)
        time.sleep(delay)

    def _extract_tech_skills(self, text: str) -> List[str]:
        """Extrait les mots-clés technologiques trouvés dans un texte."""
        if not text:
            return []
        text_lower = f" {text.lower()} "
        found = set()
        for kw in TECH_KEYWORDS:
            pattern = rf"(?:\b|\W){re.escape(kw)}(?:\b|\W)"
            if re.search(pattern, text_lower):
                found.add(kw.upper() if len(kw) <= 3 else kw.capitalize())
        return sorted(list(found))

    def _parse_article(self, article: BeautifulSoup) -> Optional[JobOffer]:
        """Extrait les métadonnées d'une carte d'offre d'emploi."""
        try:
            link_tag = article.find("a", class_="resultJobItem")
            if not link_tag or "href" not in link_tag.attrs:
                return None

            raw_href = link_tag["href"]
            clean_href = raw_href.split(";")[0]
            full_url = urljoin(self.BASE_URL, clean_href)
            
            raw_id = article.get("id", "")
            job_id = raw_id.replace("article-", "") if raw_id else clean_href.split("/")[-1]
            job_id = f"gc-{job_id}"

            title_tag = article.find("span", class_="noctitle")
            titre = title_tag.get_text(strip=True) if title_tag else "Titre non spécifié"

            business_tag = article.find("li", class_="business")
            entreprise = business_tag.get_text(strip=True) if business_tag else "Non spécifié"

            location_tag = article.find("li", class_="location")
            lieu_brut = location_tag.get_text(" ", strip=True) if location_tag else "Québec (QC)"
            lieu_propre = re.sub(r"^(emplacement|location)\s*", "", lieu_brut, flags=re.IGNORECASE).strip()

            province = "QC"
            for prov in ["QC", "ON", "BC", "AB", "MB", "NB", "NS"]:
                if f"({prov})" in lieu_propre:
                    province = prov
                    break

            salary_tag = article.find("li", class_="salary")
            salaire = None
            if salary_tag:
                sal_txt = salary_tag.get_text(" ", strip=True)
                salaire = re.sub(r"^(salaire\s*:?|salary\s*:?)\s*", "", sal_txt, flags=re.IGNORECASE).strip()

            date_tag = article.find("li", class_="date")
            date_pub = date_tag.get_text(strip=True) if date_tag else None

            source_tag = article.find("span", class_="job-source")
            partenaire = "Guichet-Emplois (Direct)"
            if source_tag:
                part_text = source_tag.get_text(strip=True)
                if part_text:
                    partenaire = part_text

            type_poste = "Temps plein"
            titre_lower = titre.lower()
            if any(k in titre_lower for k in ["stage", "intern", "stagiaire"]):
                type_poste = "Stage"
            elif any(k in titre_lower for k in ["étudiant", "student"]):
                type_poste = "Étudiant"

            return JobOffer(
                id=job_id,
                titre=titre,
                entreprise=entreprise,
                lieu=lieu_propre,
                province=province,
                pays="Canada",
                salaire=salaire,
                date_publication=date_pub,
                type_poste=type_poste,
                modalite="Non spécifié",
                competences_cles=self._extract_tech_skills(titre),
                description=None,
                url_source=full_url,
                source="Guichet-Emplois",
                partenaire=partenaire
            )
        except Exception as e:
            logger.warning("Erreur de parsing sur article: %s", e)
            return None

    def enrichir_offre_details(self, offer: JobOffer) -> JobOffer:
        """Visite la page détaillée pour extraire la modalité et les compétences techniques."""
        try:
            logger.debug("Visite detail de l'offre : %s (%s)", offer.id, offer.url_source)
            resp = self.session.get(offer.url_source, timeout=self.timeout)
            
            if resp.status_code == 429:
                msg = f"[ALERTE HTTP 429] Trop de requetes ! Pause de securite de 6s..."
                print(f"\n {msg}")
                logger.warning(msg)
                time.sleep(6)
                return offer
            elif resp.status_code != 200:
                logger.error("Erreur HTTP %d lors du chargement de %s", resp.status_code, offer.url_source)
                return offer

            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Analyse du bandeau résumé
            brief = soup.find("ul", class_="job-posting-brief")
            if brief:
                brief_text = brief.get_text(" ", strip=True).lower()
                if "télétravail" in brief_text or "remote" in brief_text:
                    offer.modalite = "Télétravail"
                elif "hybride" in brief_text or "hybrid" in brief_text:
                    offer.modalite = "Hybride"
                elif "sur place" in brief_text or "on site" in brief_text:
                    offer.modalite = "Sur place"

                if "stage" in brief_text:
                    offer.type_poste = "Stage"
                elif "temps partiel" in brief_text:
                    offer.type_poste = "Temps partiel"

            # 2. Détection des compétences dans toute la page
            page_text = soup.get_text(" ", strip=True)
            competences_enrichies = self._extract_tech_skills(page_text)
            offer.competences_cles = sorted(list(set(offer.competences_cles + competences_enrichies)))

            # Pause humaine entre les consultations de pages
            self._pause_humaine(mini=1.0, maxi=2.0)

        except requests.exceptions.Timeout:
            logger.warning("Timeout lors de l'enrichissement de l'offre %s", offer.id)
        except Exception as e:
            logger.error("Erreur inattendue sur l'enrichissement de %s : %s", offer.id, e)

        return offer

    def collecter_multi_mots_cles(
        self,
        mots_cles: List[str],
        province: str = "QC",
        limit_totale: int = 100
    ) -> List[JobOffer]:
        """
        Recherche des offres à travers une liste étendue de mots-clés informatiques,
        avec déduplication automatique, affichage de barres de progression et journalisation.
        """
        print("\n" + "=" * 65)
        print(f" [*] COLLECTE MULTI-MOTS-CLES (CIBLE : {limit_totale} OFFRES TI)")
        print(f"    - Mots-cles actifs : {len(mots_cles)} metiers cibles")
        print(f"    - Region           : {province} (Canada)")
        print("=" * 65)
        logger.info("Debut de la collecte multi-mots-cles. Cible: %d offres. Mots-cles: %s", limit_totale, mots_cles)

        offers: List[JobOffer] = []
        seen_ids: Set[str] = set()

        print("\n[PHASE 1/2] Reperage et agregation des offres d'emploi...")
        
        for idx_kw, mot_cle in enumerate(mots_cles, start=1):
            if len(offers) >= limit_totale:
                break

            logger.info("Recherche mot-cle [%d/%d] : '%s'", idx_kw, len(mots_cles), mot_cle)
            params = {
                "searchstring": mot_cle,
                "sort": "D",
                "fprov": province if province.upper() != "ALL" else ""
            }
            search_url = urljoin(self.BASE_URL, self.SEARCH_ENDPOINT)

            try:
                resp = self.session.get(search_url, params=params, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning("HTTP %d pour la recherche mot-cle '%s'", resp.status_code, mot_cle)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                articles = soup.find_all("article")
                nouveaux = 0
                for art in articles:
                    offer = self._parse_article(art)
                    if offer and offer.id not in seen_ids:
                        seen_ids.add(offer.id)
                        offers.append(offer)
                        nouveaux += 1
                        afficher_barre_progression(
                            actuel=len(offers),
                            total=limit_totale,
                            prefixe="[Recherche]",
                            suffixe=f"[{mot_cle[:15]}] +{nouveaux}"
                        )
                        if len(offers) >= limit_totale:
                            break

                # Si on a besoin de plus et que des résultats existent, faire 1 appel pagination
                if len(offers) < limit_totale and len(articles) >= 20:
                    self._pause_humaine(mini=1.0, maxi=1.8)
                    loader_url = urljoin(self.BASE_URL, self.LOADER_ENDPOINT)
                    loader_resp = self.session.get(loader_url, timeout=self.timeout)
                    if loader_resp.status_code == 200 and loader_resp.text.strip():
                        loader_soup = BeautifulSoup(loader_resp.text, "html.parser")
                        for art in loader_soup.find_all("article"):
                            offer = self._parse_article(art)
                            if offer and offer.id not in seen_ids:
                                seen_ids.add(offer.id)
                                offers.append(offer)
                                nouveaux += 1
                                afficher_barre_progression(
                                    actuel=len(offers),
                                    total=limit_totale,
                                    prefixe="[Recherche]",
                                    suffixe=f"[{mot_cle[:15]}] +{nouveaux}"
                                )
                                if len(offers) >= limit_totale:
                                    break

            except Exception as e:
                logger.error("Erreur lors de la recherche '%s' : %s", mot_cle, e)

            self._pause_humaine(mini=1.0, maxi=1.8)

        # Forcer la barre à 100% visuel de Phase 1
        afficher_barre_progression(actuel=len(offers), total=len(offers), prefixe="[Recherche]", suffixe="Phase 1 terminee")
        print(f"\n [OK] {len(offers)} offres uniques reperees au total.")
        logger.info("%d offres uniques retenues apres Phase 1.", len(offers))

        # Phase 2 : Enrichissement approfondi avec barre de progression
        print("\n[PHASE 2/2] Analyse approfondie (modalite & competences technologiques)...")
        print("            (Requetes humaines douces pour respecter le serveur)\n")
        logger.info("Debut de la Phase 2 (enrichissement approfondi de %d offres)...", len(offers))

        for idx, offer in enumerate(offers, start=1):
            self.enrichir_offre_details(offer)
            suffixe = f"{offer.titre[:22]} ({offer.modalite})"
            afficher_barre_progression(
                actuel=idx,
                total=len(offers),
                prefixe="[Details  ]",
                suffixe=suffixe
            )

        print("\n [OK] Analyse approfondie completee avec succes !")
        logger.info("Phase 2 terminee avec succes.")
        return offers

    @staticmethod
    def exporter(offers: List[JobOffer], output_path: str = "data/offres_emploi_canada.json") -> None:
        """Sauvegarde les offres et affiche un rapport statistique complet."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        data = [o.model_dump() for o in offers]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Export reussi : %s (%d offres enregistrees)", output_path, len(data))

        print("\n" + "=" * 65)
        print(" [*] RAPPORT DE SAUVEGARDE")
        print("=" * 65)
        print(f" [OK] Fichier genere : {os.path.abspath(output_path)}")
        print(f" [OK] Fichier de log : {FICHIER_LOG}")
        print(f" [OK] Total d'offres : {len(data)}")
        
        stages = sum(1 for o in offers if o.type_poste == "Stage")
        teletravail = sum(1 for o in offers if o.modalite in ["Télétravail", "Hybride"])
        toutes_competences = [skill for o in offers for skill in o.competences_cles]
        
        print(f" [OK] Stages identifies : {stages}")
        print(f" [OK] Postes en teletravail/hybride : {teletravail}")
        if toutes_competences:
            from collections import Counter
            top_tech = Counter(toutes_competences).most_common(8)
            top_str = ", ".join(f"{tech} ({count})" for tech, count in top_tech)
            print(f" [OK] Top competences detectees : {top_str}")
        print("=" * 65 + "\n")


# =====================================================================
# 6. PROGRAMME PRINCIPAL AVEC GESTION CRITIQUE DES ERREURS
# =====================================================================
def main():
    logger.info("Lancement de l'application.")
    print("\n" + "=" * 65)
    print(" [*] JOBS INSIGHTS - COLLECTEUR EMPLOI CANADA (ESPACE HUGO)")
    print("=" * 65)

    scraper = EmploiCanadaScraper()

    # 1. Test de connectivité
    if not scraper.tester_connectivite():
        print("\n [ATTENTION] Le site ne semble pas joignable pour l'instant.")
        logger.warning("Test de connectivite echoue.")
        choix = input(" Voulez-vous tout de meme tenter la collecte ? (o/N) : ").strip().lower()
        if choix != "o":
            print(" Operation annulee.")
            return

    # 2. Demande interactive
    print("\n" + "-" * 65)
    saisie_quantite = input(" Combien d'offres souhaitez-vous extraire ? [Defaut: 100] : ").strip()
    if saisie_quantite.isdigit() and int(saisie_quantite) > 0:
        nb_offres = int(saisie_quantite)
    else:
        nb_offres = 100
        print(f" -> Valeur par defaut appliquee : {nb_offres} offres.")

    print("\n Modes de recherche disponibles :")
    print(" 1. Recherche elargie 100% TI (Programmeurs, Analystes, Jeux video, Web...) [Recommande]")
    print(" 2. Saisir un mot-cle personnalise")
    choix_mode = input(" Votre choix [Defaut: 1] : ").strip()

    if choix_mode == "2":
        kw = input(" Entrez le mot-cle : ").strip()
        mots_cles = [kw] if kw else MOTS_CLES_INFORMATIQUE
    else:
        mots_cles = MOTS_CLES_INFORMATIQUE
        print(f" -> Utilisation du bouquet de {len(mots_cles)} metiers en informatique.")
    print("-" * 65)

    # 3. Lancement de la collecte
    resultats = scraper.collecter_multi_mots_cles(
        mots_cles=mots_cles,
        province="QC",
        limit_totale=nb_offres
    )

    # 4. Sauvegarde
    if resultats:
        scraper.exporter(resultats, output_path="data/offres_emploi_canada.json")
    else:
        print("\n [INFO] Aucune offre trouvee.")
        logger.info("Aucune offre collectee.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n [!] Collecte interrompue par l'utilisateur.")
        logger.warning("Interruption manuelle par l'utilisateur (Ctrl+C).")
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"\n\n [ERREUR CRITIQUE DE PLANTAGE] : {e}")
        print(f" [!] Le detail de l'erreur a ete enregistre dans : {FICHIER_LOG}")
        logger.critical("PLANTAGE NON GERE DE L'APPLICATION :\n%s", err_msg)
    finally:
        print("\n" + "-" * 65)
        input(" Appuyez sur Entrée pour quitter...")
