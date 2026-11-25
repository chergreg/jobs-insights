# job-insights

**Projet pédagogique collaboratif et non noté** du DEC en Techniques de l’informatique au Collège O’Sullivan de Québec. Encadrement par Grégory, dans le cadre du cours [420-SV2-OQ, Développement de services d’échanges de données (90 h)](https://osullivan-quebec.qc.ca/dec-informatique/cours-dec-techniques-de-linformatique-420-b0/#c0021db93174fa337).

## Objectif

Explorer comment la collecte de données et l’intelligence artificielle peuvent aider les étudiants à repérer des emplois et des stages, à sélectionner des offres pertinentes et à adapter leurs candidatures.

## Pistes de travail

1. **Recenser les sources.** Constituer un inventaire des sites qui publient des offres d’emploi et de stage pertinentes pour les étudiants.
2. **Collecter et structurer les offres.** Expérimenter des méthodes de collecte, dont le scraping, et rapprocher les données issues de différentes sources dans un format commun. Documenter les méthodes essayées et les difficultés rencontrées.
3. **Présenter les offres.** Concevoir une interface qui facilite la recherche, le filtrage et la sélection.
4. **Explorer l’aide à la candidature.** À partir d’un CV ou d’une lettre de motivation fournis, expérimenter la présélection d’offres et la suggestion d’améliorations adaptées à une offre.

## Collaboration

Toute la classe travaille sur un même projet dans un [dépôt GitHub privé](https://github.com/chergreg/jobs-insights). Le développement se fait en **Python**. Chaque étudiant choisit librement son assistant de code, par exemple Codex, Claude Code ou Gemini.

L’expérimentation permet de mettre en pratique les échanges de données, la logique applicative et le contrôle de la qualité dans un projet commun.

## État du projet

Le projet est en phase de cadrage. Le périmètre des offres, les premières sources à explorer, le contenu de la première version, l’architecture et l’organisation des contributions seront précisés au fil du travail.

## Livrables

- **Livrable en cours :** [Livrable 3 — Reprendre et améliorer une preuve de concept](livrables/03-amelioration-preuve-de-concept/enonce.md)
- [Livrable 2 — Preuve de concept de scraping](livrables/02-preuve-de-concept-scraping/enonce.md) ([synthèse](livrables/02-preuve-de-concept-scraping/synthese.md))
- [Livrable 1 — Inventaire des sites d’offres d’emploi et de stage](livrables/01-inventaire-des-sites/enonce.md) ([synthèse](livrables/01-inventaire-des-sites/synthese.md), [inventaire commun](livrables/01-inventaire-des-sites/inventaire.md))

---

## Scripts Python et utilisation

Cette section recense les scripts exécutables du projet, leur rôle, leur configuration et leur mode d'utilisation.

### 1. Prérequis et environnement d'exécution

- **Version Python** : Python 3.12+ (recommandé : Python 3.13 sous Windows).
- **Dépendances tierces** : Le socle unifié utilise Pydantic, BeautifulSoup4 et Requests.
  ```powershell
  pip install -r equipe/gregory/livrable3/requirements.txt
  ```

---

### 2. Démonstration de référence — Livrable 3 (`equipe/gregory/livrable3/`)

Le dossier [`equipe/gregory/livrable3/`](equipe/gregory/livrable3/README.md) propose l'implémentation de référence complète et unifiée fusionnant les meilleures briques techniques de l'équipe :
- **Top 3 de sources complémentaires :** Guichet-Emplois Canada (socle fédéral par codes CNP), Jobboom Québec (portail privé local en JSON-LD Schema.org) et Remotive (API REST pour le télétravail tech et les stages).
- **Pipeline d'unification & déduplication :** Modèle Pydantic `JobOffer`, fusion intra et inter-sources par empreinte `(titre, employeur, lieu)`, 140 offres consolidées avec descriptions intégrales à 100 % et zéro faux positif de compétences (`SQL`, `Python`, `JavaScript`, etc.).
- **Exports finaux :** `data/offres_unifiees.json` (270 Ko) et `data/offres_unifiees.csv` (213 Ko, encodé en `utf-8-sig` avec séparateur `;` pour Microsoft Excel sous Windows).
- **Documentation officielle :**
  - [Note de synthèse et compte rendu de démonstration](equipe/gregory/livrable3/COMPTE_RENDU.md) (`COMPTE_RENDU.md`)
  - [Guide d'exécution détaillé de l'ensemble des scripts](equipe/gregory/livrable3/README.md) (`README.md`)
  - [Plan directeur des 6 lots d'implémentation](equipe/gregory/livrable3/plan.md) (`plan.md`)

#### Exécution rapide du pipeline et des tests

```powershell
# 1. Installer les dépendances requises
pip install -r equipe/gregory/livrable3/requirements.txt

# 2. Exécuter l'ensemble des 110 tests unitaires 100 % hors ligne (~0,78 s)
python -m unittest discover -s equipe/gregory/livrable3 -p "test_*.py" -v

# 3. Lancer le pipeline d'unification et de déduplication multi-sources
python equipe/gregory/livrable3/main.py
```

#### A. Test et démonstration en direct (`run_demo_guichet.py`)

Interroge Guichet-Emplois Canada en conditions réelles, applique les filtres métiers CNP TI, enrichit les fiches individuelles et exploite un cache local pour respecter le serveur.

- **Fichier** : `equipe/gregory/livrable3/run_demo_guichet.py`
- **Configuration** :
  - **Temporisation** : 5,0 secondes entre chaque requête HTTP réelle (`GUICHET_DELAY_SECONDS`, conforme au `robots.txt`).
  - **User-Agent** : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique College O'Sullivan de Quebec; contact: gregory@jobs-insights.local)`.
  - **Cache local** : Répertoire `equipe/gregory/livrable3/cache/guichet_emplois/` (validité 24 heures par défaut).
- **Entrées (Arguments en ligne de commande)** :
  - `--limit N` : Nombre maximal d'offres à collecter (défaut : `5`).
  - `--pages P` : Nombre maximal de pages de recherche à parcourir (défaut : `1`).
  - `--term MOTCLE` : Recherche ciblée par mot-clé (ex: `python`, `stage`).
  - `--no-cache` : Désactive la lecture du cache et force des requêtes réseau réelles.
  - `--enrich` : Active l'enrichissement détaillé des fiches via RDFa/DOM (activé par défaut).
- **Sorties** :
  - **Sortie console** : Affichage fluide de l'avancement, synthèse des données extraites (titre, employeur, lieu, salaire, modalité, stage, compétences clés détectées sans faux positifs, extrait de description).
  - **Sortie disque** : Fichiers HTML mis en cache sous `cache/guichet_emplois/search/` et `cache/guichet_emplois/details/`.
- **Exemples de commandes** :
  ```powershell
  # Test rapide par mot-clé (2 offres au Québec avec enrichissement)
  python equipe/gregory/livrable3/run_demo_guichet.py --term python --limit 2

  # Démonstration par défaut sur les codes CNP TI (3 offres)
  python equipe/gregory/livrable3/run_demo_guichet.py --limit 3

  # Forcer de nouvelles requêtes sans utiliser le cache
  python equipe/gregory/livrable3/run_demo_guichet.py --limit 2 --no-cache
  ```

#### B. Générateur du jeu d'essai standardisé (`generate_dataset.py`)

Normalise, déduplique et valide les offres collectées selon le modèle commun Pydantic `JobOffer`.

- **Fichier** : `equipe/gregory/livrable3/generate_dataset.py`
- **Configuration** : Normalisation canonique des technologies et élimination des faux positifs français (`C` isolé, `VUE`).
- **Entrées** :
  - Données sources Hugo : `equipe/hugo/02-preuve-de-concept-scraping/data/offres_emploi_canada.json`
  - Données sources Kandet : `equipe/kandet/02-preuve-de-concept-scraping/echantillon.json`
- **Sortie** :
  - Fichier JSON unifié et validé : `equipe/gregory/livrable3/data/offres_guichet_emplois.json` (97 offres TI québécoises).
- **Exemple de commande** :
  ```powershell
  python equipe/gregory/livrable3/generate_dataset.py
  ```

#### C. Suite de tests unitaires 100 % hors ligne (`test_guichet_emplois.py`)

Vérifie l'ensemble de la logique de parsing, la validation du schéma Pydantic, l'extraction de compétences et la gestion du cache sans aucun appel réseau.

- **Fichier** : `equipe/gregory/livrable3/test_guichet_emplois.py`
- **Configuration** : `offline_mode=True` garantissant zéro appel réseau lors des tests.
- **Entrées** : Fixtures HTML/XML statiques intégrées.
- **Sortie** : Rapport unitaire standardisé (24 tests validés en ~0,03 s).
- **Exemple de commande** :
  ```powershell
  python -m unittest discover -s equipe/gregory/livrable3 -p "test_*.py" -v
  ```

---

### 3. Preuves de concept individuelles (Livrable 2)

Les membres de l'équipe ont développé plusieurs prototypes autonomes disponibles sous `equipe/<membre>/02-preuve-de-concept-scraping/` :

- **Kandet (`poc_multi_source.py`)** : Collecteur multi-sources (Guichet-Emplois + API Remotive) en bibliothèque standard avec tests unitaires.
  - Tests hors ligne :
    ```powershell
    python -m unittest discover -s equipe/kandet/02-preuve-de-concept-scraping -p "test_*.py" -v
    ```
- **Hugo (`collecte.py` / `parsers.py`)** : Collecteur cascade Guichet-Emplois (Atom + HTML + RDFa) avec Pydantic.
  - Tests hors ligne :
    ```powershell
    python -m unittest discover -s equipe/hugo/02-preuve-de-concept-scraping -p "test_*.py" -v
    ```

