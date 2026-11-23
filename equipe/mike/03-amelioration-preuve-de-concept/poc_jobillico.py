"""Livrable 3 (Mike) : amélioration du POC Jobillico de Mamadou.

Point de départ : la fonction poc_scrape_jobillico() de Mamadou
(equipe/mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py).

Ce que je garde de son code :
- l'adresse de recherche  /recherche-emploi?skwd=...&scty=...
- la recherche des liens  /fr/offre-d-emploi/...
- la lecture du bloc JSON-LD « JobPosting » de chaque offre
- fetch_html() et clean_html()

Repris de Hugo (equipe/hugo/04-Scrapping Jobillico/collecte.py) :
- la pagination par le paramètre ipg (ipg=2 = page 2, que j'ai aussi vérifié
  dans mon navigateur le 18 nov. 2026) ;
- l'arrêt quand une page n'apporte aucune offre nouvelle.

DÉCOUVERTE (23 nov. 2026) : le robots.txt de Jobillico contient
« Disallow: /*&ipg= » et « Allow: /*&ipg=1$ ». Seule la page 1 est permise.
urllib.robotparser ne comprend pas les jokers * et $ et répond « autorisé » :
d'où la classe RobotsAvecJokers. Le script s'arrête donc à la page 1, comme
le demande le site, même avec --pages 3.

Ce que j'ajoute (ni Mamadou ni Hugo ne le font) :
1. Respect du site : le robots.txt de Jobillico est lu avant CHAQUE adresse,
   jokers * et $ compris, et une page interdite n'est jamais téléchargée.
2. Pause d'au moins 5 s entre les requêtes, ou plus si le robots.txt
   demande un Crawl-delay plus long. User-Agent honnête (pas de faux navigateur).
3. Aucune valeur inventée : si l'entreprise ou la ville manque, on met None
   (Mamadou et Hugo mettent « Québec » par défaut).
4. Toutes les offres de chaque page (Mamadou en gardait 2), sans doublon.
5. Des tests hors ligne sur la pagination, le robots.txt et le Crawl-delay.

Lancement :  python poc_jobillico.py --pages 3   (s’arrêtera à la page 1 : robots.txt)
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.jobillico.com"
# Changement : Mamadou se faisait passer pour Firefox. On dit qui on est.
HEADERS = {
    "User-Agent": "jobs-insights-atelier/1.0 (projet etudiant 420-SV2-OQ)",
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
}
PAUSE = 5  # secondes entre deux requêtes


# --------------------------------------------------------------------------
# Fonctions reprises de Mamadou (inchangées)
# --------------------------------------------------------------------------

def clean_html(raw: str) -> str:
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw))
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def fetch_html(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


# --------------------------------------------------------------------------
# Lecture des pages (sans réseau, donc testable)
# --------------------------------------------------------------------------

def url_recherche(keyword: str, city: str, page: int) -> str:
    """Même adresse que Mamadou, plus le numéro de page (ipg)."""
    q_enc = urllib.parse.quote(keyword)
    c_enc = urllib.parse.quote(city)
    return f"{BASE}/recherche-emploi?skwd={q_enc}&scty={c_enc}&ipg={page}"


def extraire_liens(page_html: str) -> List[str]:
    """Liens des offres d'une page de résultats (regex de Mamadou), sans doublon."""
    paths = re.findall(r'href=["\'](/fr/offre-d-emploi/[^"\'?#]+)', page_html)
    return list(dict.fromkeys(paths))


def trouver_job_posting(donnees: Any) -> Optional[Dict[str, Any]]:
    """Ajout : trouve le JobPosting même dans une liste ou un « @graph »
    (Mamadou ne lisait qu'un objet seul)."""
    if isinstance(donnees, list):
        for element in donnees:
            trouve = trouver_job_posting(element)
            if trouve is not None:
                return trouve
        return None
    if not isinstance(donnees, dict):
        return None
    if "@graph" in donnees:
        return trouver_job_posting(donnees["@graph"])
    type_ = donnees.get("@type")
    types = type_ if isinstance(type_, list) else [type_]
    return donnees if "JobPosting" in types else None


def lire_offre(job_html: str, full_url: str) -> Optional[Dict[str, Any]]:
    """Lit le JSON-LD JobPosting d'une offre. Renvoie None s'il n'y en a pas."""
    ld_blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        job_html, re.S)
    for block in ld_blocks:
        if "JobPosting" not in block:
            continue
        try:
            donnees = json.loads(block.strip())
        except json.JSONDecodeError:
            continue  # ajout : un bloc mal formé ne fait plus planter le script
        data = trouver_job_posting(donnees)
        if data is None:
            continue
        org = data.get("hiringOrganization") or {}
        loc = data.get("jobLocation") or {}
        if isinstance(loc, list) and loc:
            loc = loc[0]
        addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
        description = clean_html(data.get("description", ""))
        return {
            "source": "Jobillico Québec",
            "title": clean_html(data.get("title", "")) or None,
            # Changement : plus de « Employeur Jobillico » ni de « Québec » inventés.
            "company": (clean_html(org.get("name", "")) or None) if isinstance(org, dict) else None,
            "city": addr.get("addressLocality") or None,
            # Ajouts : date de publication et type d'emploi, déjà présents dans le JSON-LD.
            "date_posted": (data.get("datePosted") or "")[:10] or None,
            "employment_type": data.get("employmentType") or None,
            "url": full_url,
            # Changement : description complète au lieu des 220 premiers caractères.
            "description": description or None,
        }
    return None


# --------------------------------------------------------------------------
# Collecte avec pagination
# --------------------------------------------------------------------------

class RobotsAvecJokers:
    """Lecteur de robots.txt qui comprend les jokers « * » et « $ ».

    Pourquoi : urllib.robotparser (bibliothèque standard) ignore ces jokers.
    Or le robots.txt de Jobillico contient « Disallow: /*&ipg= » : la page 2
    et les suivantes sont interdites, mais urllib.robotparser répond « autorisé ».
    Règles appliquées (norme RFC 9309, comme Google) :
    - le groupe « User-agent » qui correspond à notre robot, sinon « * » ;
    - la règle la plus longue qui correspond gagne ;
    - à égalité entre Allow et Disallow, Allow gagne.
    """

    def __init__(self, contenu: Optional[str], tout_interdire: bool = False):
        self.tout_interdire = tout_interdire
        self.groupes: List[Dict[str, Any]] = []
        if contenu:
            self._lire(contenu)

    def _lire(self, contenu: str) -> None:
        groupe = None
        derniere_etait_agent = False
        for ligne in contenu.splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if ":" not in ligne:
                continue
            cle, valeur = (x.strip() for x in ligne.split(":", 1))
            cle = cle.lower()
            if cle == "user-agent":
                if groupe is None or not derniere_etait_agent:
                    groupe = {"agents": [], "regles": [], "crawl_delay": None}
                    self.groupes.append(groupe)
                groupe["agents"].append(valeur.lower())
                derniere_etait_agent = True
                continue
            derniere_etait_agent = False
            if groupe is None:
                continue
            if cle in ("allow", "disallow") and valeur:
                groupe["regles"].append((cle == "allow", valeur))
            elif cle == "crawl-delay":
                try:
                    groupe["crawl_delay"] = float(valeur)
                except ValueError:
                    pass

    def _groupe(self, agent: str) -> Optional[Dict[str, Any]]:
        nom = agent.split("/")[0].lower()
        for groupe in self.groupes:
            if any(a != "*" and a in nom for a in groupe["agents"]):
                return groupe
        for groupe in self.groupes:
            if "*" in groupe["agents"]:
                return groupe
        return None

    @staticmethod
    def _correspond(motif: str, chemin: str) -> bool:
        fin = motif.endswith("$")
        if fin:
            motif = motif[:-1]
        regex = ".*".join(re.escape(morceau) for morceau in motif.split("*"))
        return re.match(regex + ("$" if fin else ""), chemin) is not None

    def can_fetch(self, agent: str, url: str) -> bool:
        if self.tout_interdire:
            return False
        groupe = self._groupe(agent)
        if groupe is None:
            return True
        morceaux = urllib.parse.urlsplit(url)
        chemin = (morceaux.path or "/") + (f"?{morceaux.query}" if morceaux.query else "")
        meilleure = None  # (longueur de la règle, autorisé ?)
        for autorise, motif in groupe["regles"]:
            if self._correspond(motif, chemin):
                candidat = (len(motif), autorise)
                if meilleure is None or candidat > meilleure:
                    meilleure = candidat
        return True if meilleure is None else meilleure[1]

    def crawl_delay(self, agent: str) -> Optional[float]:
        groupe = self._groupe(agent)
        return groupe["crawl_delay"] if groupe else None


def preparer_robots(telecharger=fetch_html) -> RobotsAvecJokers:
    """Lit le robots.txt avec NOTRE User-Agent (robots.read() s'annoncerait
    comme « Python-urllib »)."""
    try:
        return RobotsAvecJokers(telecharger(f"{BASE}/robots.txt"))
    except urllib.error.HTTPError as e:
        print(f"  -> robots.txt : réponse {e.code}.")
        # 404 : pas de robots.txt, donc aucune règle. Autre refus : on ne lit rien.
        return RobotsAvecJokers(None, tout_interdire=(e.code != 404))
    except (urllib.error.URLError, OSError) as e:
        print(f"  ! robots.txt illisible ({e}) : collecte annulée par prudence.")
        return RobotsAvecJokers(None, tout_interdire=True)


def scrape_jobillico(keyword: str = "développeur", city: str = "Québec, QC",
                     max_pages: int = 3, robots=None, telecharger=fetch_html,
                     pause: float = PAUSE) -> List[Dict[str, Any]]:
    if robots is None:
        robots = preparer_robots(telecharger)
    agent = HEADERS["User-Agent"]
    # Ajout : si le robots.txt demande d'attendre plus longtemps, on obéit.
    crawl_delay = robots.crawl_delay(agent) if hasattr(robots, "crawl_delay") else None
    if crawl_delay and float(crawl_delay) > pause:
        print(f"  -> Le robots.txt demande {crawl_delay} s entre les requêtes : pause ajustée.")
        pause = float(crawl_delay)

    # 1. Parcourir les pages de résultats et noter tous les liens.
    tous_les_liens: List[str] = []
    for page in range(1, max_pages + 1):
        url = url_recherche(keyword, city, page)
        if not robots.can_fetch(agent, url):
            print(f"  ! robots.txt interdit cette page : {url}")
            break
        print(f"\n[Page {page}] {url}")
        if page > 1:
            time.sleep(pause)
        try:
            liens = extraire_liens(telecharger(url))
        except Exception as e:  # ajout : une page en erreur ne fait plus perdre les offres trouvées
            print(f"  ! Erreur sur la page {page} ({e}) : on garde les offres déjà trouvées.")
            break
        nouveaux = [l for l in liens if l not in tous_les_liens]
        print(f"  -> {len(liens)} offres sur la page, dont {len(nouveaux)} nouvelles.")
        if not nouveaux:
            print("  -> Aucune nouvelle offre : on arrête la pagination.")
            break
        tous_les_liens.extend(nouveaux)

    # 2. Ouvrir chaque offre et lire son JSON-LD.
    results: List[Dict[str, Any]] = []
    print(f"\nLecture de {len(tous_les_liens)} offres (pause de {pause:g} s entre chacune)...")
    for path in tous_les_liens:
        full_url = f"{BASE}{path}"
        if not robots.can_fetch(agent, full_url):
            print(f"  ! robots.txt interdit : {full_url}")
            continue
        time.sleep(pause)
        try:
            item = lire_offre(telecharger(full_url), full_url)
        except Exception as e:  # même choix que Mamadou : une erreur n'arrête pas tout
            print(f"  ! Erreur sur {full_url}: {e}")
            continue
        if item is None:
            print(f"  ! Pas de JSON-LD JobPosting : {full_url}")
            continue
        results.append(item)
        print(f"  ✓ {item['title']} — {item['company'] or '?'} ({item['city'] or '?'})")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="POC Jobillico amélioré (pagination).")
    parser.add_argument("--mot-cle", default="développeur")
    parser.add_argument("--ville", default="Québec, QC")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--sortie", default="offres_jobillico_v2.json")
    args = parser.parse_args()

    offres = scrape_jobillico(args.mot_cle, args.ville, args.pages)
    Path(args.sortie).write_text(json.dumps(offres, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOTAL : {len(offres)} offres sauvegardées dans {args.sortie}")
