# Guide d'exécution et documentation des scripts — Livrable 3

Ce répertoire constitue l'espace de référence de la démonstration du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**.

> 📄 **Note de synthèse officielle :** Consultez [`COMPTE_RENDU.md`](COMPTE_RENDU.md) pour le compte rendu complet de démonstration (analyse comparative, justifications du Top 3, traçabilité des contributions étudiantes et métriques avant/après).  
> 🗺️ **Plan directeur de référence :** Consultez [`plan.md`](plan.md) pour l'historique complet des 6 lots de réalisation (100 % validés).

---

## 1. Vue d'ensemble de l'architecture

Le livrable fusionne et bonifie les travaux de l'équipe :
- **Connecteur #1 : Guichet-Emplois Canada** (Lot 2) :
  - Pagination exhaustive par codes CNP TI (approche de Kandet, 191 offres ciblées).
  - Enrichissement sémantique RDFa / repli DOM et détection de compétences contextuelles (approche de Hugo).
  - Gestionnaire de cache local et respect du délai de 5 s de `robots.txt`.
- **Connecteur #2 : Jobboom Québec** (Lot 3) :
  - Pagination ordonnée et paramétrable de la catégorie TI (surpassant la limite de 5 offres d'Elvira).
  - Extraction robuste du JSON-LD Schema.org/JobPosting via `json.loads` natif (fiabilisant l'approche de Mamadou).
  - Respect de la temporisation éthique de 2.0 s et gestion du cache local disque (search/details).
- **Connecteur #3 : Remotive** (Lot 4) :
  - Client API REST JSON (`/api/remote-jobs`) bonifié à partir des travaux de Kandet.
  - Politique stricte de cache local 24 h (respectant la limitation de 4 requêtes/jour de Remotive).
  - Moteur de classification géographique multi-niveaux ciblant le Canada, le Québec et le télétravail étudiant.
  - Détection native des stages via `job_type == "internship"` et complétée sémantiquement.
- **Pipeline d'unification et déduplication multi-sources** (Lot 5) :
  - Déduplication intra-source (ID / URL nettoyée) et inter-sources (empreinte titre + employeur + lieu).
  - Fusion intelligente maximisant la richesse (description la plus longue, cumul des compétences, priorisation du signal de stage).
  - Exports consolidés sous formats JSON complet et CSV compatible Microsoft Excel Windows (`utf-8-sig`, délimiteur `;`).
- **Modèle commun Pydantic v2 `JobOffer`** (zéro invention de données, conformité `AGENTS.md`).

---

## 2. Procédure pas à pas : exécution de tous les scripts pour récupérer le maximum d'offres

Cette procédure décrit l'enchaînement méthodique des commandes Python pour collecter le volume maximal d'offres d'emploi et de stages TI au Québec et au Canada, consolider les jeux d'essai intermédiaires, orchestrer la déduplication et valider l'intégrité globale.

### Tableau récapitulatif des commandes et points de contrôle

| Étape | Script exécuté | Rôle principal | Fichier(s) produit(s) | Volume attendu |
| :---: | --- | --- | --- | :---: |
| **0** | `unittest discover` | Validation préalable hors ligne | S/O | 110 tests OK (< 1 s) |
| **1a** | `run_demo_guichet.py` | Scraping direct + enrichissement RDFa | `cache/guichet_emplois/` | 188 fiches répertoriées (8 pages) |
| **1b** | `generate_dataset.py` | Consolidation du jeu Guichet-Emplois | `data/offres_guichet_emplois.json` | 204 offres QC |
| **2a** | `run_demo_jobboom.py` | Collecte paginée Jobboom + JSON-LD | `cache/jobboom/` | 131 fiches complètes (9 pages) |
| **2b** | `generate_jobboom_dataset.py` | Consolidation du jeu Jobboom | `data/offres_jobboom.json` | 133 offres QC |
| **3a** | `run_demo_remotive.py` | Interrogation API REST Remotive | `cache/remotive/` | 9 offres éligibles CA |
| **3b** | `generate_remotive_dataset.py` | Consolidation du jeu Remotive | `data/offres_remotive.json` | 12 offres (3 stages) |
| **4** | `main.py` | Unification, déduplication et exports | `data/offres_unifiees.json`, `.csv` | 343 offres consolidées |
| **5** | `unittest discover` | Validation finale de non-régression | S/O | 110 tests OK (100 %) |

---

### Détail des étapes d'exécution et critères de vérification

#### Étape 0 — Préparation de l'environnement et validation préalable
Avant toute exécution, ouvrir un terminal PowerShell dans le dossier du Livrable 3 et valider que l'environnement est fonctionnel :
```powershell
cd equipe/gregory/livrable3
python -m unittest discover -s . -p "test_*.py" -v
```
- **Quoi vérifier :**
  - La suite de tests affiche `Ran 110 tests in ~0.8s` suivi de `OK`.
  - Aucun appel réseau n'est émis (`offline_mode=True` actif sur les tests, conformité stricte `AGENTS.md`).

#### Étape 1 — Collecte et consolidation Guichet-Emplois Canada
Lancer la démonstration / collecte en direct avec enrichissement sémantique RDFa pour alimenter le cache disque, puis exécuter le générateur consolidé :
```powershell
# 1. Collecte et enrichissement RDFa / DOM
python run_demo_guichet.py --limit 10 --enrich

# 2. Consolidation du jeu d'essai standardisé
python generate_dataset.py
```
- **Quoi vérifier :**
  - **Console `run_demo_guichet.py` :** Vérifier l'extraction des fiches (`[OK] 10 offre(s) récupérée(s)`), le respect du `crawl-delay` (5,0 s en cas d'appel réseau réel) et l'extraction sémantique (descriptions nettoyées sans balises HTML, salaires horaires/annuels).
  - **Console `generate_dataset.py` :** Message `[OK] 204 offres exportees avec succes dans data/offres_guichet_emplois.json`.
  - **Fichier de sortie :** [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) existe et contient **204 offres** (87 offres d'Hugo + 10 offres de Kandet + 107 offres issues du cache des 8 pages de recherche enrichies).
  - **Intégrité des données :** Tous les identifiants débutent par `ge-`, le champ `province` vaut `"QC"`, aucun salaire n'est inventé (`None` si absent).

#### Étape 2 — Collecte et consolidation Jobboom Québec
Parcourir l'ensemble des pages de la catégorie TI (`_i10lfr`) sans limitation artificielle pour extraire les blocs JSON-LD Schema.org/JobPosting, puis générer le jeu d'essai consolidé :
```powershell
# 1. Découverte ordonnée et extraction JSON-LD intégrale
python run_demo_jobboom.py --pages 0 --limit 0

# 2. Consolidation multi-contributeurs (Elvira + Mamadou + JobboomScraper)
python generate_jobboom_dataset.py
```
- **Quoi vérifier :**
  - **Console `run_demo_jobboom.py` :** Vérifier que les 9 pages sont découvertes (`131 annonces au total`), puis que l'ensemble des fiches est analysé via JSON-LD (`status_source` `CACHE` ou `RÉSEAU`).
  - **Console `generate_jobboom_dataset.py` :** Affichage de l'intégration des contributions étudiantes et des 131 fiches réelles du connecteur `JobboomScraper`, menant à `[OK] 133 offres Jobboom consolidées`.
  - **Fichier de sortie :** [`data/offres_jobboom.json`](data/offres_jobboom.json) contient **133 offres uniques** conformes Pydantic v2.
  - **Intégrité des données :** Tous les identifiants débutent par `jb-`, le lieu est normalisé au Québec (ex: `"Montréal, QC"`, `"Québec, QC"`), les compétences techniques sont extraites sans faux positifs (`C` et `Vue` filtrés).

#### Étape 3 — Collecte et consolidation Remotive (API REST, stages & télétravail)
Interroger l'API REST Remotive en appliquant le filtre géographique `canada_eligible` et le cache local obligatoire de 24 h, puis générer le jeu consolidé :
```powershell
# 1. Test du client API REST avec classification géographique
python run_demo_remotive.py --limit 50 --geo-filter canada_eligible

# 2. Consolidation avec les cas historiques de stages TI (conformité Kandet)
python generate_remotive_dataset.py
```
- **Quoi vérifier :**
  - **Console `run_demo_remotive.py` :** Vérifier la détection du cache local valide (`Cache local valide détecté (< 24h)` sans appel réseau inutile), le filtre géographique (`canada_eligible` retenant les offres ouvertes au Canada/Québec) et la liste des offres typées.
  - **Console `generate_remotive_dataset.py` :** Affichage de `[OK] Fichier généré avec succès` avec **12 offres** dont **3 stages confirmés** (`internship`).
  - **Fichier de sortie :** [`data/offres_remotive.json`](data/offres_remotive.json) (42,7 Ko, 12 offres uniques).
  - **Intégrité des données :** Tous les identifiants commencent par `rem-`, les tags et compétences clés sont normalisés.

#### Étape 4 — Unification, déduplication multi-sources et exports finaux (`main.py`)
Exécuter le point d'entrée principal qui orchestre le chargement des 3 jeux d'essai, applique l'algorithme de déduplication intra/inter-sources et produit les exports finaux :
```powershell
# Exécution du pipeline complet
python main.py
```
*(Variante possible : exécuter une collecte directe par connecteurs avec l'option `python main.py --scrape --limit 10`).*
- **Quoi vérifier :**
  - **Console `main.py` :**
    - Annonces en entrée : **349 annonces** (204 Guichet-Emplois + 133 Jobboom + 12 Remotive).
    - Doublons inter-sources fusionnés : **6 doublons fusionnés** (détection d'annonces rediffusées sur plusieurs plateformes, ex. Guichet et Jobboom via Jobillico / Québec emploi).
    - Offres uniques consolidées : **343 offres**.
    - Détections de stages : **6 stages confirmés** (`confirmed_stage`), 337 contrats réguliers.
    - Top technologies : vérifier l'absence des faux positifs `C` et `Vue` et le palmarès (SQL, Python, JavaScript, C#, Agile, Linux, Git, Azure, Java, React).
  - **Fichier JSON unifié :** [`data/offres_unifiees.json`](data/offres_unifiees.json) fait environ **924 Ko**, contient 343 enregistrements valides Pydantic, encodé en UTF-8 indenté.
  - **Fichier CSV unifié :** [`data/offres_unifiees.csv`](data/offres_unifiees.csv) fait environ **789 Ko**, encodé en `utf-8-sig` (avec BOM `\xef\xbb\xbf` pour Microsoft Excel Windows) avec délimiteur `;` et sauts de ligne nettoyés.
  - **Vérification Excel Windows :** Le fichier CSV doit s'ouvrir sous Excel sans texte tronqué ni caractères d'accents corrompus (`é`, `è`, `à`, `ô`).

#### Étape 5 — Validation finale de la non-régression
Pour conclure, relancer la suite complète de tests unitaires :
```powershell
python -m unittest discover -s . -p "test_*.py" -v
```
- **Quoi vérifier :**
  - 110 tests unitaires exécutés (24 Guichet, 23 Jobboom, 34 Remotive, 29 Pipeline).
  - Résultat : `OK` (0 échec, 0 erreur).
  - Durée totale : < 1,5 seconde.

---

## 3. Scripts Python : guide d'utilisation, entrées, sorties et configuration détaillée

### A. Script de démonstration et test en direct (`run_demo_guichet.py`)

Interroge Guichet-Emplois Canada en direct pour effectuer une recherche selon les 14 codes CNP du domaine informatique au Québec, enrichir les fiches détaillées et démontrer l'accélération par le cache.

- **Fichier** : `run_demo_guichet.py`
- **Configuration** :
  - `delai_secondes` : `5.0` s entre chaque requête HTTP directe vers le site officiel.
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/guichet_emplois/` (conservation 24 heures).
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre d'offres maximum à retourner (défaut : `5`).
  - `--pages P` : Nombre de pages de recherche HTML à explorer (défaut : `1`).
  - `--term MOTCLE` : Filtrage optionnel par mot-clé (ex: `python`, `stage`).
  - `--enrich` : Télécharge et analyse la fiche détaillée pour extraire la description et les compétences clés (activé par défaut).
  - `--no-cache` : Force des requêtes HTTP réelles sans lire le cache existant.
- **Sorties** :
  - **Console** : Affichage structuré pour chaque offre (ID normalisé, titre officiel + titre employeur, entreprise, lieu, modalité, salaire, compétences détectées, statut de stage, extrait de description).
  - **Cache disque** : Fichiers HTML enregistrés sous `cache/guichet_emplois/search/` et `cache/guichet_emplois/details/`.
- **Exemples de commandes** :
  ```powershell
  # 1. Test rapide par mot-clé (2 offres au Québec)
  python run_demo_guichet.py --term python --limit 2

  # 2. Recherche par défaut sur les codes CNP TI (3 offres)
  python run_demo_guichet.py --limit 3

  # 3. Forcer le rafraîchissement sans cache
  python run_demo_guichet.py --limit 2 --no-cache
  ```

---

### B. Générateur du jeu d'essai standardisé (`generate_dataset.py`)

Normalise, nettoie et consolide les données réelles issues des POCs précédents et du cache de recherche dans le schéma pivot `JobOffer`.

- **Fichier** : `generate_dataset.py`
- **Configuration** :
  - Dictionnaire de normalisation canonique des technologies (`TECH_CANONICAL`).
  - Filtrage strict éliminant les faux positifs récurrents en français (`C` isolé, `VUE`).
- **Entrées** :
  - Données sources Hugo : `../../hugo/02-preuve-de-concept-scraping/data/offres_emploi_canada.json` (87 offres).
  - Données sources Kandet : `../../kandet/02-preuve-de-concept-scraping/echantillon.json` (10 offres).
  - Cache de recherche et fiches détaillées Guichet-Emplois : `cache/guichet_emplois/` (107 offres supplémentaires enrichies).
- **Sorties** :
  - Fichier JSON structuré : `data/offres_guichet_emplois.json` (204 offres TI québécoises validées par Pydantic).
- **Exemple de commande** :
  ```powershell
  python generate_dataset.py
  ```

---

### C. Suite de tests unitaires 100 % hors ligne (`test_guichet_emplois.py`)

Garantit la non-régression et la robustesse de chaque composant sans dépendre de la connexion réseau.

- **Fichier** : `test_guichet_emplois.py`
- **Configuration** :
  - Mode hors ligne forcé (`offline_mode=True`) : tout appel réseau non simulé lève immédiatement une exception.
- **Entrées** : Fixtures HTML/XML statiques intégrées au fichier de test.
- **Sorties** : Rapport d'exécution unittest (24 tests validés en ~0,03 s).
- **Exemple de commande** :
  ```powershell
  python -m unittest test_guichet_emplois.py -v
  ```

---

### D. Script de démonstration et test en direct Jobboom (`run_demo_jobboom.py`)

Interroge le portail Jobboom Québec en direct ou depuis le cache pour collecter et enrichir les offres du secteur TI via JSON-LD.

- **Fichier** : `run_demo_jobboom.py`
- **Configuration** :
  - `delai_secondes` : `2.0` s entre chaque requête HTTP directe (éthique et conforme).
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/jobboom/` (conservation 24 heures).
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre d'offres maximal à retourner (défaut : `5`).
  - `--pages P` : Nombre de pages de résultats à parcourir (défaut : `1`).
  - `--keyword MOTCLE` : Filtrage optionnel par mot-clé (ex: `python`, `stage`).
  - `--no-cache` : Force des requêtes HTTP réelles sans lire le cache existant.
  - `--save-dataset` : Sauvegarde les offres collectées dans `data/offres_jobboom.json`.
- **Sorties** :
  - **Console** : Affichage structuré pour chaque offre (ID `jb-...`, titre, employeur, lieu, type de contrat, modalité, salaire, compétences détectées, statut de stage, extrait de description).
  - **Cache disque** : Fichiers HTML enregistrés sous `cache/jobboom/search/` et `cache/jobboom/details/`.
- **Exemples de commandes** :
  ```powershell
  # 1. Test rapide sur 3 offres TI (mode cache automatique)
  python run_demo_jobboom.py --limit 3

  # 2. Recherche par mot-clé sur 2 pages
  python run_demo_jobboom.py --keyword devops --pages 2 --limit 5

  # 3. Forcer le rafraîchissement sans cache
  python run_demo_jobboom.py --limit 2 --no-cache
  ```

---

### E. Générateur du jeu d'essai Jobboom (`generate_jobboom_dataset.py`)

Consolide les contributions d'Elvira (5 offres) et Mamadou (8 offres v1/v2) avec une collecte paginée exhaustive sur l'ensemble de la catégorie TI du connecteur Jobboom fiabilisé.

- **Fichier** : `generate_jobboom_dataset.py`
- **Entrées** :
  - Données sources Elvira : `../../elvira/02-preuve-de-concept-scraping/offres_jobboom.json`
  - Données sources Mamadou : `../../mamadou/02-preuve-de-concept-scraping/sample_scraped_jobs.json` et `../../mamadou/03-amelioration-preuve-de-concept/echantillon_v2.json`
  - Collecte en direct/cache sur la catégorie `_i10lfr` via `JobboomScraper` (131 fiches complètes analysées)
- **Sorties** :
  - Fichier JSON structuré : `data/offres_jobboom.json` (133 offres TI québécoises validées par Pydantic).
- **Exemple de commande** :
  ```powershell
  python generate_jobboom_dataset.py
  ```

---

### F. Suite de tests unitaires 100 % hors ligne Jobboom (`test_jobboom.py`)

Garantit la robustesse du parsing de listing et du bloc JSON-LD Schema.org/JobPosting sans connexion réseau.

- **Fichier** : `test_jobboom.py`
- **Configuration** : Mode hors ligne forcé (`offline_mode=True`).
- **Entrées** : Fixtures HTML/JSON-LD locales (JobPosting, @graph, MonetaryAmount, etc.).
- **Sorties** : Rapport d'exécution unittest (23 tests validés en ~0,03 s).
- **Exemple de commande** :
  ```powershell
  python -m unittest test_jobboom.py -v
  ```

---

### G. Script de démonstration et test en direct Remotive (`run_demo_remotive.py`)

Interroge l'API REST publique Remotive avec politique de cache local 24 h (respectant la limite stricte de 4 requêtes/jour), classification géographique fine et détection native des stages.

- **Fichier** : `run_demo_remotive.py`
- **Configuration** :
  - `cache_hours` : `24` h (utilisation prioritaire du cache disque).
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/remotive/remotive_cache.json`.
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre maximal d'offres à afficher (défaut : `15`).
  - `--geo-filter FILTRE` : `canada_eligible` (défaut), `canada_only`, `quebec_only`, `all`.
  - `--category CAT` : Catégorie d'emplois Remotive (ex: `software-development`, `data`).
  - `--search RECHERCHE` : Mot-clé de recherche optionnel.
  - `--stage-only` : Conserver uniquement les stages.
  - `--no-cache` : Forcer un appel réseau direct vers l'API Remotive.
  - `--save-dataset` : Exporter les offres normalisées dans `data/offres_remotive.json`.
- **Sorties** :
  - **Console** : Synthèse statistique (répartition des contrats, lieux, technologies, stages) et fiches d'offres détaillées.
  - **Cache disque** : Fichier JSON complet avec enveloppe et horodatage UTC.
- **Exemples de commandes** :
  ```powershell
  # 1. Démonstration rapide sur les offres ouvertes au Canada
  python run_demo_remotive.py --limit 5

  # 2. Filtrer uniquement les stages TI
  python run_demo_remotive.py --stage-only

  # 3. Cibler les offres strictement au Québec ou Canada
  python run_demo_remotive.py --geo-filter canada_only
  ```

---

### H. Générateur du jeu d'essai standardisé Remotive (`generate_remotive_dataset.py`)

Collecte les offres en direct/cache de Remotive et consolide les cas de référence de stages (conformité Kandet).

- **Fichier** : `generate_remotive_dataset.py`
- **Sortie** : `data/offres_remotive.json` (12 offres normalisées `JobOffer`, dont 3 stages confirmés).
- **Exemple de commande** :
  ```powershell
  python generate_remotive_dataset.py
  ```

---

### I. Suite de tests unitaires 100 % hors ligne Remotive (`test_remotive.py`)

Valide l'ensemble des règles de parsing, de classification géographique, de détection de stages et de cache sans aucun appel réseau.

- **Fichier** : `test_remotive.py`
- **Configuration** : Mode hors ligne forcé (`offline_mode=True`).
- **Entrées** : Fixtures JSON locales complètes (stages, Québec, Amérique du Nord, Monde, Hors cible).
- **Sorties** : 34 tests validés en ~0,05 s.
- **Exemple de commande** :
  ```powershell
  python -m unittest test_remotive.py -v
  ```

---

### J. Point d'entrée unifié et exécutable (`main.py`)

Orchestre la collecte ciblée ou complète des trois sources (Guichet-Emplois, Jobboom, Remotive), applique le pipeline de fusion / déduplication et génère les deux exports finaux consolidés.

- **Fichier** : `main.py`
- **Entrées (Paramètres CLI)** :
  - `--sources LISTE` : Sources à inclure séparées par virgule (`guichet,jobboom,remotive`, défaut: les trois).
  - `--scrape` : Active les connecteurs de collecte au lieu de lire les jeux d'essai préexistants.
  - `--no-cache` : Désactive le cache disque pour forcer des requêtes HTTP réelles (si `--scrape` est actif).
  - `--limit N` : Limite d'offres extraites par source.
  - `--output-json CHEMIN` : Destination de l'export JSON (défaut : `data/offres_unifiees.json`).
  - `--output-csv CHEMIN` : Destination de l'export CSV (défaut : `data/offres_unifiees.csv`).
  - `--verbose` : Affiche les journaux d'exécution détaillés.
- **Sorties** :
  - Fichier JSON unifié : `data/offres_unifiees.json` (343 offres consolidées, 923.8 Ko, structurées et indentées).
  - Fichier CSV unifié : `data/offres_unifiees.csv` (343 offres consolidées, 788.5 Ko, encodage `utf-8-sig`, délimiteur `;`).
  - Console : Rapport statistique de synthèse (349 annonces en entrée, 6 doublons inter-sources fusionnés, 343 uniques, 6 stages confirmés, top technologies).
- **Exemples de commandes** :
  ```powershell
  # 1. Exécution par défaut (unification instantanée des jeux d'essai)
  python main.py

  # 2. Collecte ciblée sur Guichet-Emplois et Jobboom uniquement
  python main.py --sources guichet,jobboom

  # 3. Lancer une collecte en direct avec scraping
  python main.py --scrape --limit 5
  ```

---

### K. Moteur de déduplication et pipeline d'unification (`pipeline.py`)

Module central assurant l'unification sans perte d'information :
1. **Déduplication intra-source** : Par identifiant unique normalisé (`id`) et URL canonique sans paramètres de tracking (`clean_url`).
2. **Déduplication inter-sources** : Par empreinte normalisée `(titre, employeur, lieu)` avec tolérance aux variantes graphiques et corporatives (`Inc.`, `Ltée`, etc.). Les annonces d'un même diffuseur ne sont jamais fusionnées sur le titre seul.
3. **Fusion intelligente** :
   - Préservation de la description la plus longue et informative.
   - Cumul des compétences clés uniques normalisées.
   - Conservation du partenaire d'origine si l'offre a été agrégée (ex: `source_partenaire="Jobillico"`).
   - Priorisation stricte du signal de stage (`confirmed_stage` > `possible_stage` > `not_indicated`).
   - Rétention des modalités de travail (Télétravail, Hybride) et salaires explicites.
4. **Exports spécialisés** :
   - `export_to_json` : JSON indenté standardisé UTF-8.
   - `export_to_csv` : CSV encodé en `utf-8-sig` avec séparateur `;` et nettoyage des sauts de ligne pour un affichage parfait dans Excel sur Windows.

---

### L. Suite de tests unitaires hors ligne du pipeline (`test_pipeline.py`)

Valide l'ensemble des règles de normalisation, de déduplication, de fusion et d'export sans aucun appel réseau.

- **Fichier** : `test_pipeline.py`
- **Couverture** :
  - Normalisation textuelle, employeur, titre et localisation québécoise.
  - Déduplication intra-source et inter-sources (rediffusions cross-plateformes).
  - Préservation des descriptions, compétences, salaires et partenaires.
  - Priorisation des stages et enrichissement du type de poste.
  - Conformité des exports JSON et CSV (`utf-8-sig`, BOM Excel, délimiteur `;`).
  - Validation de bout en bout sur batch synthétique et sur les jeux d'essai réels consolidés sous `data/`.
- **Sorties** : 29 tests validés en ~0,68 s.
- **Exemple de commande** :
  ```powershell
  python -m unittest test_pipeline.py -v
  ```

---

### Exécution globale de l'ensemble des tests du Livrable 3

Pour exécuter d'un coup l'ensemble des suites de tests unitaires (Guichet-Emplois + Jobboom + Remotive + Pipeline) :

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```
*(110 tests unitaires validés en ~0,78 s).*

---

## 4. Schéma de données unifié (`models.py`)

Chaque offre est représentée par la classe Pydantic `JobOffer` :

```python
class JobOffer(BaseModel):
    id: str                        # Ex: "ge-50701948"
    titre: str                     # Intitulé du poste
    entreprise: str                # Nom de l'employeur
    lieu: str                      # Ex: "Québec (QC)", "Montréal (QC)"
    province: str                  # Ex: "QC"
    pays: str                      # "Canada"
    url: str                       # Lien direct propre (sans session)
    source: str                    # "guichet-emplois"
    source_partenaire: Optional[str] # Partenaire d'origine (ex: "Jobillico", "Talent")
    date_publication: Optional[str]# Date au format ISO AAAA-MM-JJ
    type_poste: Optional[str]      # "Temps plein", "Stage", etc.
    modalite: Optional[str]        # "Sur place", "Hybride", "Télétravail"
    est_stage: bool                # True si stage identifié
    statut_stage: str              # "confirmed_stage", "possible_stage", "not_indicated"
    description: Optional[str]     # Description nettoyée sans HTML
    competences_cles: List[str]    # Technologies clés extraites sans faux positifs
    salaire: Optional[str]         # Rémunération textuelle brute si mentionnée
    date_extraction: str           # Horodatage ISO
```
