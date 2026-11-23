"""Collecteur résilient pour l'API Adzuna Canada et lecteur hors ligne des données du Livrable 2.

Inspiré de :
- `equipe/rayan/02-preuve-de-concept-scraping/adzuna_test_2.py` (prototype L2 initial) ;
- `equipe/dan/livrable3/outils.py` (architecture `Client` avec injection de dépendances
  `session` et `attendre` permettant de tester les délais et retries 100 % hors ligne en 0,00 s) ;
- `equipe/kandet/03-amelioration-preuve-de-concept/collecte.py` (retry automatique sur HTTP 429/503).

Sécurité (AGENTS.md) :
- Les identifiants `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` sont lus uniquement depuis l'environnement.
- La fonction `masquer_secrets()` remplace systématiquement les valeurs de `app_id` et `app_key`
  (ainsi que tout paramètre `app_id=...` ou `app_key=...` dans une URL) par `***` avant tout
  affichage, journalisation ou levée d'exception.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable

try:
    import requests
except ImportError:  # pragma: no cover - permet aux tests hors ligne de tourner même sans requests
    requests = None  # type: ignore[assignment]


BASE_URL = "https://api.adzuna.com/v1/api/jobs/ca"
USER_AGENT = "jobs-insights-rayan/1.0 (Projet etudiant DEC Informatique College O'Sullivan de Quebec)"
TIMEOUT = 20
CODES_RETRY_TEMPORAIRES = {429, 500, 502, 503, 504}

DOSSIER_COURANT = Path(__file__).resolve().parent
DOSSIER_SORTIE_L2 = DOSSIER_COURANT.parent / "02-preuve-de-concept-scraping" / "adzuna_test_output"

PATRON_PARAM_SECRET = re.compile(r"((?:app_id|app_key)=)[^&\s\"']+", re.I)


def masquer_secrets(texte: str, credentials: dict[str, str] | None = None) -> str:
    """Masque systématiquement `app_id` et `app_key` dans une URL ou un message d'erreur."""
    if not texte:
        return ""
    nettoye = PATRON_PARAM_SECRET.sub(r"\1***", str(texte))
    if credentials:
        for cle in ("app_id", "app_key"):
            secret = credentials.get(cle)
            if secret and len(secret) >= 3:
                nettoye = nettoye.replace(secret, "***")
    return nettoye


def slugify(valeur: str) -> str:
    """Produit un nom de fichier simple à partir d'un texte (repris de `adzuna_test_2.py`)."""
    texte = valeur.lower()
    texte = re.sub(r"[^a-z0-9]+", "_", texte)
    return texte.strip("_")


def obtenir_identifiants_env() -> dict[str, str]:
    """Lit `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` depuis les variables d'environnement."""
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise RuntimeError(
            "Identifiants Adzuna manquants : définissez ADZUNA_APP_ID et ADZUNA_APP_KEY "
            "dans vos variables d'environnement (ou utilisez le mode hors ligne --from-l2)."
        )
    return {"app_id": app_id, "app_key": app_key}


class ErreurCollecteAdzuna(RuntimeError):
    """Erreur levée lors d'un appel à l'API Adzuna (message garanti sans clé API exposée)."""


class ClientAdzuna:
    """Client HTTP résilient pour l'API Adzuna Canada avec retry progressif et masquage des clés.

    Comme dans `outils.py` de Dan, `session` et `attendre` sont injectables pour les tests unitaires
    hors ligne.
    """

    def __init__(
        self,
        credentials: dict[str, str],
        base_url: str = BASE_URL,
        user_agent: str = USER_AGENT,
        timeout: int = TIMEOUT,
        max_tentatives: int = 3,
        delai_initial_retry: float = 1.5,
        delai_entre_pages: float = 0.4,
        session: Any | None = None,
        attendre: Callable[[float], None] = time.sleep,
    ) -> None:
        self.credentials = dict(credentials)
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_tentatives = max(1, max_tentatives)
        self.delai_initial_retry = delai_initial_retry
        self.delai_entre_pages = delai_entre_pages
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:
            self.session = None
        self.attendre = attendre

    def appeler_api(self, endpoint: str, **params: Any) -> dict[str, Any]:
        """Effectue un appel GET avec retry progressif sur HTTP 429/5xx et protection des clés API."""
        if self.session is None:
            raise ErreurCollecteAdzuna("Aucune session HTTP disponible (module requests absent).")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        query = {
            **self.credentials,
            "content-type": "application/json",
            **params,
        }
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        derniere_erreur = ""
        for tentative in range(1, self.max_tentatives + 1):
            try:
                reponse = self.session.get(
                    url,
                    params=query,
                    headers=headers,
                    timeout=self.timeout,
                )
            except Exception as exc:
                msg_propre = masquer_secrets(str(exc), self.credentials)
                derniere_erreur = f"Erreur réseau ({msg_propre})"
                if tentative < self.max_tentatives:
                    self.attendre(self.delai_initial_retry * (2 ** (tentative - 1)))
                    continue
                raise ErreurCollecteAdzuna(
                    f"Échec après {self.max_tentatives} tentatives sur {endpoint} : {derniere_erreur}"
                ) from None

            code = getattr(reponse, "status_code", 0)
            if code == 200:
                try:
                    return reponse.json()
                except ValueError:
                    raise ErreurCollecteAdzuna(
                        f"Réponse JSON invalide reçue sur {endpoint}."
                    ) from None

            if code in (401, 403):
                raise ErreurCollecteAdzuna(
                    f"Accès refusé par Adzuna (HTTP {code}) sur {endpoint} : vérifiez vos identifiants."
                )

            if code in CODES_RETRY_TEMPORAIRES:
                derniere_erreur = f"HTTP {code} sur {endpoint}"
                if tentative < self.max_tentatives:
                    attente = self.delai_initial_retry * (2 ** (tentative - 1))
                    self.attendre(attente)
                    continue
                raise ErreurCollecteAdzuna(
                    f"Indisponibilité persistante après {self.max_tentatives} tentatives ({derniere_erreur})."
                )

            # Autre code HTTP (ex. 400, 404)
            url_reponse = masquer_secrets(getattr(reponse, "url", endpoint), self.credentials)
            raise ErreurCollecteAdzuna(f"Erreur HTTP {code} sur {url_reponse}.")

        raise ErreurCollecteAdzuna(f"Échec inattendu sur {endpoint} : {derniere_erreur}")

    def chercher_combinaison(
        self,
        keyword: str,
        location: str,
        category: str = "it-jobs",
        results_per_page: int = 20,
        max_pages: int = 2,
        dossier_cache: Path | None = None,
    ) -> dict[str, Any]:
        """Collecte jusqu'à `max_pages` pour un couple `(keyword, location)` et sauvegarde immédiatement."""
        all_jobs: list[dict[str, Any]] = []
        page_summaries: list[dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            data = self.appeler_api(
                f"search/{page}",
                what=keyword,
                where=location,
                category=category,
                results_per_page=results_per_page,
                sort_by="date",
            )
            jobs = data.get("results") or []
            total_count = data.get("count", 0)
            all_jobs.extend(jobs)
            page_summaries.append(
                {
                    "page": page,
                    "returned": len(jobs),
                    "total_count": total_count,
                }
            )
            if not jobs:
                break
            if page < max_pages and self.delai_entre_pages > 0:
                self.attendre(self.delai_entre_pages)

        document = {
            "search": {
                "keyword": keyword,
                "location": location,
                "category": category,
                "results_per_page": results_per_page,
                "max_pages": max_pages,
            },
            "pages": page_summaries,
            "results": all_jobs,
        }

        if dossier_cache is not None:
            dossier_cache.mkdir(parents=True, exist_ok=True)
            nom_fichier = f"{slugify(location)}__{slugify(keyword)}.json"
            (dossier_cache / nom_fichier).write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        return document

    def collecter_campagne(
        self,
        locations: list[str],
        keywords: list[str],
        category: str = "it-jobs",
        results_per_page: int = 20,
        max_pages: int = 2,
        dossier_cache: Path | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Exécute une campagne de recherches en isolant les erreurs pour ne jamais perdre les résultats acquis."""
        documents: list[dict[str, Any]] = []
        erreurs: list[str] = []

        for location in locations:
            for keyword in keywords:
                try:
                    doc = self.chercher_combinaison(
                        keyword=keyword,
                        location=location,
                        category=category,
                        results_per_page=results_per_page,
                        max_pages=max_pages,
                        dossier_cache=dossier_cache,
                    )
                    documents.append(doc)
                except ErreurCollecteAdzuna as err:
                    erreurs.append(f"[{location} | {keyword}] {masquer_secrets(str(err), self.credentials)}")
                if self.delai_entre_pages > 0:
                    self.attendre(self.delai_entre_pages)

        return documents, erreurs


def charger_reponses_locales(dossier: Path = DOSSIER_SORTIE_L2) -> list[dict[str, Any]]:
    """Charge hors ligne les fichiers JSON bruts de recherche Adzuna (ex. les 10 fichiers du Livrable 2)."""
    if not dossier.is_dir():
        raise FileNotFoundError(f"Dossier de réponses JSON introuvable : {dossier}")

    documents: list[dict[str, Any]] = []
    for chemin in sorted(dossier.glob("*.json")):
        if chemin.name == "summary.json":
            continue
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        if isinstance(contenu, dict) and isinstance(contenu.get("results"), list):
            documents.append(contenu)
    return documents
