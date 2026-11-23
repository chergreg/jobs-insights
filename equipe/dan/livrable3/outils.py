"""Outils réseau communs aux trois scrapers : délai par site, cache disque, arrêt propre.

robots.txt est **optionnel** et désactivé par défaut (remarque du prof, 2026-11-23) :
- par défaut, aucune lecture de robots.txt ; le délai vient de ``DELAIS_PAR_SITE``
  (5 s pour le Guichet-Emplois, la valeur de son Crawl-delay) ;
- ce qui reste toujours actif : User-Agent honnête, délai entre deux requêtes, cache 24 h
  et **arrêt sur 401, 403 et 429** (le serveur qui refuse vraiment, comme CareerBeacon) ;
- ``Client(respecter_robots=True)`` (option ``--respecter-robots``) réactive la vérification
  complète : adresse interdite → arrêt, et Crawl-delay appliqué s'il est plus grand.

Pourquoi un vérificateur maison plutôt que ``urllib.robotparser`` ?
- ``RobotFileParser`` ne comprend pas les jokers ``*`` et ``$`` : avec le robots.txt de
  CareerBeacon, il autorise ``/fr/rechercher?filter-salary_min=40000`` alors que la règle
  ``Disallow: /*filter-salary_min=`` l'interdit ;
- sa méthode ``read()`` se présente comme « Python-urllib » : si le serveur refuse ce nom,
  il conclut à tort que tout est interdit (constaté avec CareerBeacon au livrable 2).

Ce module suit la norme RFC 9309 : la règle la plus longue gagne, ``Allow`` gagne à égalité.

Usage dans un scraper :
    client = Client()                         # ou Client(respecter_robots=True)
    html = client.telecharger("https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fprov=QC")
    # → AccesRefuse si le serveur répond 401, 403 ou 429
    #   (et, avec respecter_robots=True, si robots.txt interdit l'URL).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import requests

USER_AGENT = "jobs-insights-dan/0.3 (projet etudiant, College O'Sullivan de Quebec)"
DELAI_MIN = 2.0                                 # secondes entre deux requêtes au même site
# Délais fixes par site (secondes), utilisés sans robots.txt. Le Guichet-Emplois demande 5 s
# dans son robots.txt (Crawl-delay: 5) : on garde cette valeur écrite en dur.
DELAIS_PAR_SITE = {
    "www.guichetemplois.gc.ca": 5.0,
    "www.jobboom.com": 2.0,
    "ca.talent.com": 2.0,
}
CACHE_DOSSIER = Path(__file__).with_name("cache")
CACHE_DUREE = 24 * 3600                         # secondes (24 h)
TIMEOUT = 20


# --- Erreur d'accès --------------------------------------------------------------

class AccesRefuse(Exception):
    """Le site ne veut pas de notre robot : on s'arrête, sans contourner."""

    def __init__(self, url: str, raison: str) -> None:
        self.url = url
        self.raison = raison
        super().__init__(f"Accès refusé : {url}\n  {raison}\n  On s'arrête, sans contournement.")


# --- robots.txt --------------------------------------------------------------------

@dataclass
class _Groupe:
    agents: list[str] = field(default_factory=list)
    regles: list[tuple[bool, str]] = field(default_factory=list)   # (permis, motif)
    crawl_delay: float | None = None


def _motif_vers_regex(motif: str) -> re.Pattern[str]:
    """``*`` = n'importe quelle suite de caractères ; ``$`` final = fin de l'URL."""
    fin = motif.endswith("$")
    if fin:
        motif = motif[:-1]
    corps = ".*".join(re.escape(morceau) for morceau in motif.split("*"))
    return re.compile("^" + corps + ("$" if fin else ""))


class Robots:
    """Règles d'un robots.txt qui s'appliquent à notre User-Agent."""

    def __init__(self, texte: str, user_agent: str = USER_AGENT) -> None:
        groupes = self._lire_groupes(texte)
        jeton = user_agent.split("/")[0].strip().lower()       # « jobs-insights-dan »

        # Groupe applicable : celui qui nous nomme, sinon celui de « * » (RFC 9309, §2.2.1).
        choisis = [g for g in groupes if jeton in (a.lower() for a in g.agents)]
        if not choisis:
            choisis = [g for g in groupes if "*" in g.agents]

        self.regles = [(permis, motif, _motif_vers_regex(motif))
                       for g in choisis for permis, motif in g.regles]
        delais = [g.crawl_delay for g in choisis if g.crawl_delay is not None]
        self.crawl_delay: float | None = max(delais) if delais else None

    @staticmethod
    def _lire_groupes(texte: str) -> list[_Groupe]:
        groupes: list[_Groupe] = []
        courant: _Groupe | None = None
        regles_commencees = False
        for ligne in texte.splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if ":" not in ligne:
                continue
            cle, valeur = (x.strip() for x in ligne.split(":", 1))
            cle = cle.lower()
            if cle == "user-agent":
                # Plusieurs « User-agent » de suite partagent le même groupe.
                if courant is None or regles_commencees:
                    courant = _Groupe()
                    groupes.append(courant)
                    regles_commencees = False
                courant.agents.append(valeur)
            elif courant is None:
                continue                                       # ligne hors groupe (ex. Sitemap)
            elif cle in ("allow", "disallow"):
                regles_commencees = True
                if valeur:                                     # « Disallow: » vide = rien d'interdit
                    courant.regles.append((cle == "allow", valeur))
            elif cle == "crawl-delay":
                regles_commencees = True
                try:
                    courant.crawl_delay = float(valeur)
                except ValueError:
                    pass
        return groupes

    def autorise(self, url: str) -> bool:
        morceaux = urlsplit(url)
        chemin = (morceaux.path or "/") + (f"?{morceaux.query}" if morceaux.query else "")
        if chemin == "/robots.txt":
            return True
        meilleure: tuple[int, bool] | None = None              # (longueur du motif, permis)
        for permis, motif, regex in self.regles:
            if regex.match(chemin):
                candidat = (len(motif), permis)                # à longueur égale, True > False
                if meilleure is None or candidat > meilleure:
                    meilleure = candidat
        return meilleure is None or meilleure[1]


# --- Client HTTP --------------------------------------------------------------------

def _site(url: str) -> str:
    morceaux = urlsplit(url)
    return f"{morceaux.scheme}://{morceaux.netloc}"


def _raison_refus(reponse: requests.Response) -> str:
    code = reponse.status_code
    serveur = reponse.headers.get("Server", "")
    if "cf-ray" in {k.lower() for k in reponse.headers} or "cloudflare" in serveur.lower():
        serveur = "Cloudflare (protection anti-robot)"
    if code == 429:
        attente = reponse.headers.get("Retry-After", "non précisé")
        return f"HTTP 429 : trop de requêtes (réessayer après : {attente} s)."
    if code == 401:
        return "HTTP 401 : la page demande une connexion."
    return f"HTTP 403 : le serveur refuse les robots{f' — {serveur}' if serveur else ''}."


class Client:
    """Téléchargeur poli : délai par site, cache 24 h, arrêt sur 401/403/429.

    ``respecter_robots=True`` ajoute la vérification de robots.txt (désactivée par défaut).

    ``session``, ``attendre``, ``horloge`` et ``maintenant`` sont remplaçables pour les tests
    hors ligne (aucun appel réseau).
    """

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        delai_min: float = DELAI_MIN,
        delais: dict[str, float] | None = None,
        respecter_robots: bool = False,
        cache_dossier: Path | None = CACHE_DOSSIER,
        cache_duree: float = CACHE_DUREE,
        session: requests.Session | None = None,
        attendre: Callable[[float], None] = time.sleep,
        horloge: Callable[[], float] = time.monotonic,
        maintenant: Callable[[], float] = time.time,
    ) -> None:
        self.user_agent = user_agent
        self.delai_min = delai_min
        self.delais = DELAIS_PAR_SITE if delais is None else delais
        self.respecter_robots = respecter_robots
        self.cache_dossier = cache_dossier
        self.cache_duree = cache_duree
        self.session = session or requests.Session()
        self.attendre = attendre
        self.horloge = horloge
        self.maintenant = maintenant
        self._robots: dict[str, Robots] = {}
        self._derniere_requete: dict[str, float] = {}

    # robots.txt ---------------------------------------------------------------
    def robots(self, url: str) -> Robots:
        """Lit (une fois par site) le robots.txt qui s'applique à ``url``."""
        site = _site(url)
        if site not in self._robots:
            adresse = site + "/robots.txt"
            try:
                reponse = self._requete(adresse)
            except requests.RequestException as erreur:
                raise AccesRefuse(adresse, f"robots.txt illisible ({erreur}).") from erreur
            code = reponse.status_code
            if code == 200:
                self._robots[site] = Robots(reponse.text, self.user_agent)
            elif code in (401, 403, 429):
                raise AccesRefuse(adresse, _raison_refus(reponse))
            elif 400 <= code < 500:                            # 404, 410… : aucune règle déclarée
                self._robots[site] = Robots("", self.user_agent)
            else:                                              # 5xx : par prudence, tout interdit
                raise AccesRefuse(adresse, f"robots.txt indisponible (HTTP {code}).")
        return self._robots[site]

    def delai(self, url: str) -> float:
        """Délai à respecter pour ce site : le plus grand entre DELAI_MIN et le délai fixe du site,
        et aussi le Crawl-delay de robots.txt si ``respecter_robots`` est activé."""
        delai = max(self.delai_min, self.delais.get(urlsplit(url).netloc.lower(), 0.0))
        if self.respecter_robots:
            delai = max(delai, self.robots(url).crawl_delay or 0.0)
        return delai

    # téléchargement -------------------------------------------------------------
    def telecharger(self, url: str, utiliser_cache: bool = True) -> str:
        """Renvoie le contenu texte de ``url``. Lève ``AccesRefuse`` si le site nous refuse."""
        if utiliser_cache:
            contenu = self._lire_cache(url)
            if contenu is not None:
                return contenu                                 # aucune requête, aucune attente

        if self.respecter_robots and not self.robots(url).autorise(url):
            raise AccesRefuse(url, "robots.txt interdit cette adresse.")

        reponse = self._requete(url, delai=self.delai(url))
        if reponse.status_code in (401, 403, 429):
            raise AccesRefuse(url, _raison_refus(reponse))
        reponse.raise_for_status()
        if not reponse.encoding:
            reponse.encoding = "utf-8"
        contenu = reponse.text
        if utiliser_cache:
            self._ecrire_cache(url, contenu)
        return contenu

    def _requete(self, url: str, delai: float = 0.0) -> requests.Response:
        """Attend ce qu'il faut depuis la dernière requête au même site, puis envoie le GET."""
        site = _site(url)
        derniere = self._derniere_requete.get(site)
        if derniere is not None:
            reste = delai - (self.horloge() - derniere)
            if reste > 0:
                self.attendre(reste)
        try:
            return self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=TIMEOUT)
        finally:
            self._derniere_requete[site] = self.horloge()

    # cache disque ---------------------------------------------------------------
    def _fichier_cache(self, url: str) -> Path | None:
        if self.cache_dossier is None:
            return None
        cle = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.cache_dossier / f"{cle}.json"

    def _lire_cache(self, url: str) -> str | None:
        fichier = self._fichier_cache(url)
        if fichier is None or not fichier.exists():
            return None
        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None                                        # cache abîmé : on retélécharge
        if donnees.get("url") != url or self.maintenant() - donnees.get("date", 0) > self.cache_duree:
            return None
        return donnees.get("contenu")

    def _ecrire_cache(self, url: str, contenu: str) -> None:
        fichier = self._fichier_cache(url)
        if fichier is None:
            return
        fichier.parent.mkdir(parents=True, exist_ok=True)
        donnees = {"url": url, "date": self.maintenant(), "contenu": contenu}
        fichier.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
