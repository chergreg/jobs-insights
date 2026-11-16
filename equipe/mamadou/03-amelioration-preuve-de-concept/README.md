# Guide d'exécution et documentation des scripts — Livrable 3 (Mamadou)

Ce dossier contient la réalisation du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**, en consolidant et enrichissant **5 sources complémentaires** d'offres d'emploi et de stages en TI au Québec et au Canada.

---

## 1. Vue d'ensemble des 5 sources intégrées

1. **Guichet-Emplois Canada (`guichet-emplois`)** :
   - Recherche par les **14 codes CNP 2021 du secteur informatique** (`fn21`) au Québec (`fprov=QC`) + filtre officiel emplois étudiants / stages (`fsrc=16`).
   - Enrichissement de chaque fiche individuelle via une cascade à 3 niveaux :
     - **Niveau A :** Balises sémantiques RDFa (`property="description"`, avec décodage du HTML doublement échappé `&lt;p&gt;` des offres partenaires Jobillico).
     - **Niveau B :** Conteneurs DOM (`#job-posting-detail`, `.job-posting-detail-requirements`).
     - **Niveau C :** Bandeau résumé (`ul.job-posting-brief` pour la modalité et les conditions) + extraction du **vrai titre de l'employeur** (`.source-title-inner`).
2. **Talent.com Canada (`talent-canada`)** :
   - Double extraction JSON-LD `@graph` (`ItemList` ➔ `JobPosting`) incluant les **coordonnées GPS (`latitude` / `longitude`)**.
3. **Jobboom Québec (`jobboom`)** :
   - Parcours ordonné de la catégorie **Technologies et médias numériques (`_i10lfr`)** (hors annonces commanditées) + extraction JSON-LD `JobPosting`.
4. **Jobillico Québec (`jobillico`)** :
   - Recherche TI au Québec + extraction JSON-LD `JobPosting`.
5. **Remotive (`remotive`)** :
   - API REST JSON officielle (`/api/remote-jobs`) filtrée sur les postes TI ouverts au Canada.

---

## 2. Scripts Python : comment les utiliser (Entrées / Sorties / Configuration)

### A. Collecteur multi-sources enrichi (`poc_guichet_cnp_v2.py`)

Interroge les 5 plateformes, normalise les dates au format ISO (`AAAA-MM-JJ`), extrait jusqu'à **35 compétences techniques TI** sans faux positifs (`competences_cles`), classifie les stages (`est_stage`, `statut_stage`) et exporte un JSON unifié.

- **Fichier :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py)
- **Configuration :**
  - `USER_AGENT` : `jobs-insights-osullivan/1.0 (atelier-livrable-3; mamadou)`
  - `DEFAULT_CRAWL_DELAY` : `5.0` s sur Guichet-Emplois (vérifié automatiquement via `robots.txt` et `RobotFileParser`).
  - `CACHE_DIR` & `DEFAULT_CACHE_TTL_SECONDS` : Dossier local `cache/` (ignoré par `.gitignore`) avec expiration automatique après **24 heures** (`86400` s) pour éviter de re-télécharger les fiches déjà lues et accélérer les relances sans attente inutile.
  - `CNP_CODES_TI` : 14 codes CNP 2021 (`20012`, `21211`, `21220`, `21221`, `21222`, `21223`, `21230`, `21231`, `21232`, `21233`, `21234`, `22220`, `22221`, `22222`).
- **Entrées (Paramètres CLI) :**
  - `--limite-guichet N` : Nombre de fiches Guichet-Emplois CNP à enrichir (défaut : `8`).
  - `--limite-autres M` : Nombre d'offres à extraire sur chacune des 4 autres sources (défaut : `4`).
  - `--pages P` : Nombre de pages de résultats à parcourir sur Guichet-Emplois CNP et Jobboom TI (défaut : `1`).
  - `--stages` : Active le filtre officiel emplois étudiants / stages (`fsrc=16`) et cible les stages sur les autres sites.
  - `--mot-cle TEXTE` : Mot-clé additionnel optionnel (ex. `python`, `reseau`, `cybersecurite`).
  - `--delai SECONDES` : Délai entre les nouvelles requêtes HTTP (défaut : `2.0` s ; mettre `5.0` pour le délai strict de Guichet-Emplois).
  - `--sans-cache` : Désactive le cache disque local de 24 h et force le re-téléchargement HTTP.
  - `--sortie FICHIER` : Nom du fichier JSON généré (défaut : `echantillon_v2.json`).
- **Sorties :**
  - **Console :** Progression détaillée par source avec indicateur `[HTTP]` ou `[CACHE]`, titre employeur, entreprise, coordonnées GPS et nombre de compétences TI détectées.
  - **Cache disque :** Fichiers JSON horodatés dans `cache/<sha256>.json` (TTL 24 h, ignorés par Git).
  - **Fichier JSON :** [`echantillon_v2.json`](echantillon_v2.json) contenant les offres complètes validées selon le schéma `JobBankOffer`.
- **Exemples de commandes :**
  ```powershell
  # Installation des dépendances
  pip install -r requirements.txt

  # 1. Collecte complète enrichie sur les 5 sources avec cache 24 h (délai 2s sur nouvelles fiches)
  python poc_guichet_cnp_v2.py --limite-guichet 6 --limite-autres 4 --delai 2

  # 2. Collecte multi-pages (2 pages sur Guichet-Emplois CNP et Jobboom TI)
  python poc_guichet_cnp_v2.py --pages 2 --limite-guichet 12 --limite-autres 6 --delai 5

  # 3. Recherche ciblée sur les stages TI au Québec (filtre fsrc=16)
  python poc_guichet_cnp_v2.py --stages --limite-guichet 5 --limite-autres 3
  ```

---

### B. Suite de tests unitaires 100 % hors ligne (`test_poc_guichet_cnp_v2.py`)

Vérifie l'ensemble des parseurs (liste CNP Guichet-Emplois, fiches RDFa avec `<div>` imbriqués, HTML doublement échappé des partenaires Jobillico, JSON-LD Talent.com avec GPS, Jobboom hors commandites, détection des stages, compétences TI sans faux positifs, **cache disque 24 h** et **pagination multi-pages avec déduplication**) **sans aucun appel réseau**.

- **Fichier :** [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py)
- **Configuration :** Lecture exclusive des fichiers locaux sous [`fixtures/`](fixtures/) et d'un répertoire temporaire isolé (`tempfile.TemporaryDirectory`) pour le cache.
- **Entrées :**
  - [`fixtures/liste_resultats_exemple.html`](fixtures/liste_resultats_exemple.html)
  - [`fixtures/fiche_offre_imbriquee.html`](fixtures/fiche_offre_imbriquee.html)
- **Sorties :** Rapport `unittest` (**10 tests validés en ~0,04 s**).
- **Commande d'exécution :**
  ```powershell
  python -m unittest discover -s . -p "test_*.py" -v
  ```
