# Plan Directeur — Livrable 3 (`jobs-insights` — Mamadou)

> **Rôle de ce fichier (`plan.md`) :** Mémoire de travail et repère entre les conversations IA pour travailler **Lot par Lot** (1 conversation = 1 lot = 1 commit) sans saturer la fenêtre de contexte ni brûler les tokens.  
> **Dossier de travail :** `equipe/mamadou/03-amelioration-preuve-de-concept/`

---

## 1. Analyse de l'existant & Sélection des 5 Sources (Collecte 100 % Autonome + Fraîcheur 2026)

Notre collecteur (`poc_guichet_cnp_v2.py --collecte-complete`) interroge directement et de façon **100 % autonome** les **5 plateformes** (avec lecture systématique de chaque fiche individuelle, filtre des 14 codes CNP 2021 TI `classify_cnp_2021`, filtre de fraîcheur 2026 `is_recent_and_valid_offer` et cache disque 24 h) :

| # | Source | Mode d'accès autonome | Offres TI 2026 retenues (`data/`) | Hors-TI / pré-2026 filtrées |
| :-: | --- | --- | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | 8 pages × 14 codes CNP TI (`fn21`) + **189/189 fiches RDFa/DOM** | **188** | 0 |
| **2** | **Jobboom Québec** | 10 pages catégorie TI `_i10lfr` + **127 fiches JSON-LD** + filtre CNP & 2026 | **86** | 41 (25 hors-TI + 16 pré-2026) |
| **3** | **Talent.com Canada** | Multi-requêtes TI QC + **107 fiches JSON-LD `@graph` + GPS** | **51** | 56 |
| **4** | **Jobillico Québec** | Multi-requêtes TI QC + **58 fiches JSON-LD `JobPosting`** | **43** | 15 |
| **5** | **Remotive** | API REST JSON multi-catégories TI + filtre Canada & CNP | **6** | 36 |

- **Total consolidé et dédupliqué (`data/offres_unifiees.json` & `.csv`) :** **365 offres TI 2026 uniques** (**365 / 365 = 100 % avec description complète** et **365 / 365 = 100 % avec `competences_cles`**, après rejet de 148 offres (132 hors TI + 16 pré-2026) et fusion sans perte de 18 doublons intra-source et 9 doublons inter-sources).

---

## 2. Schéma de données unifié enrichi (`JobBankOffer` — 36 champs + Format Commun 17 champs)

Chaque offre collectée sur l'une des 5 sources est normalisée dans la `@dataclass JobBankOffer` (`None` si absent, zéro donnée inventée) :
- **Identifiants & Traçabilité (`JobTailor_V3`) :** `id` (`ge-...`, `tc-...`, `jb-...`, `ji-...`, `rem-...`), `source_id`, `url` (nettoyée sans `;jsessionid` ni `utm_*`), `source`, `source_partenaire`, `url_partenaire` (`a#externalJobLink`), `http_status` (`200`), `content_hash` (`SHA-256` 16 hex), `date_extraction`
- **Classification CNP 2021 TI & Domaine (`JobTailor_V3`) :** `code_cnp` (14 codes CNP 2021 TI), `cnp_title`, `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`), `titre`, `titre_employeur`
- **Entreprise & Géographie (17 régions QC + GPS) :** `entreprise`, `lieu`, `ville`, `region_administrative` (17 régions administratives du Québec), `code_postal`, `province`, `pays`, `latitude`, `longitude`
- **Conditions, Études & Séniorité :** `date_publication` (ISO `AAAA-MM-JJ` >= 2026), `date_fin`, `type_poste`, `modalite` (`Sur place`, `Hybride`, `Télétravail`), `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`)
- **Rémunération structurée :** `salaire` (texte brut), `salaire_min`, `salaire_max`, `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`)
- **Qualification TI, Missions & Score DEC :** `est_stage` (`bool`), `statut_stage` (`confirmed_stage`, `possible_stage`, `not_indicated`), `competences_cles` (`list[str]` — 48 technologies/outils + repli domaine `JobTailor_V3`), `missions_cles` (`list[str]`), `score_pertinence_dec` (`0-100`), `description`

---

## 3. Feuille de route par Lots (1 Lot = 1 Conversation = 1 Commit)

### Lot 1 — Cadrage, analyse de la classe et plan directeur *(✅ Terminé)*
- [x] Analyser les travaux du dépôt (Kandet, Hugo, Elvira, Ferdinand, Rayan, Grégory).
- [x] Définir la stack (`requests` + `beautifulsoup4` dans `requirements.txt`).
- [x] Rédiger le compte rendu manquant du Livrable 2 (`02-preuve-de-concept-scraping/compte-rendu.md`).
- [x] Créer `plan.md` pour piloter les itérations.

### Lot 2 — Collecteur 5 sources enrichi, Codes CNP TI, Tests hors ligne & Documentation *(✅ Terminé)*
- [x] Implémenter la recherche Guichet-Emplois par **14 codes CNP TI (`fn21`)**.
- [x] Implémenter la cascade d'enrichissement des fiches Guichet-Emplois (RDFa + DOM + bandeau + vrai titre).
- [x] Intégrer les 4 autres sources (**Talent.com GPS**, **Jobboom TI**, **Jobillico**, **Remotive API**).
- [x] Créer **7 tests unitaires hors ligne** (`test_poc_guichet_cnp_v2.py` + `fixtures/`).
- [x] Générer le jeu d'essai vérifié [`echantillon_v2.json`](echantillon_v2.json) (**22 offres riches, 0 description `null`**).

### Lot 3 — Cache disque local & Pagination multi-pages *(✅ Terminé)*
- [x] Ajouter un gestionnaire de cache local sur disque (`cache/` avec TTL 24 h, ignoré par Git via `.gitignore`).
- [x] Ajouter la pagination multi-pages (`--pages N`) sur Guichet-Emplois CNP et Jobboom TI avec déduplication inter-pages.
- [x] Ajouter les tests unitaires hors ligne du cache et de la pagination (**10 tests OK en 0,04 s**).

### Lot 4 — Collecte autonome complète (`--collecte-complete`), Enrichissement `JobTailor`, Classification CNP 5 sources, Datasets `data/*.json` & Export CSV *(✅ Terminé)*
- [x] Étendre le filtre et la classification des 14 codes CNP TI aux 5 sources (`classify_cnp_2021`) et corriger `fsrc=16`.
- [x] Collecter de manière 100 % autonome par notre propre système (`--collecte-complete`) toutes les pages et toutes les fiches détaillées des 5 sources vers `data/offres_*.json`, `data/offres_unifiees.json`, `data/offres_unifiees.csv` et `data/rapport_collecte.json`.

### Lot 5 — Filtre de fraîcheur 2026, Filtrage hors ligne (`--filtrer`), Format Commun (`--format-commun`), Portail Web Interactif (`--html`) & Assistant Candidature JobTailor (`--cv`, `--lettre`) *(✅ Terminé)*
- [x] **Filtre de fraîcheur 2026 (`is_recent_and_valid_offer`)** : Écarter les 16 anciennes offres Jobboom de 2023/2025 pour garantir **372 offres TI 100 % 2026 et valides**.
- [x] **Filtrage multicritère hors ligne (`--filtrer`)** : Par ville, région administrative (17 régions QC), sous-domaine TI, code CNP 2021, technologie, séniorité, source, stages et salaire minimum.
- [x] **Export au Format Commun de la classe (`--format-commun`)** : Générer [`data/offres_format_commun.json`](data/offres_format_commun.json) au schéma pivot `JobOffer` (17 champs) de Grégory.
- [x] **Portail Web Interactif autonome (`--html`)** : Générer [`data/portail_ti_jobtailor.html`](data/portail_ti_jobtailor.html) (zéro serveur, protection XSS `textContent`, filtres dynamiques, matching CV en direct, audit de lettre et export CSV Excel).
- [x] **Assistant de candidature Piste 4 (`--cv` et `--lettre`)** : Lecture de CV `.txt`, `.md`, `.docx` (via `zipfile`) ou `.json`, classement des offres par **Score ATS (`/100`)** avec compétences maîtrisées vs manquantes, et audit de lettre de motivation selon la méthode *Vous / Moi / Nous* de `JobTailor_V3`.
- [x] **Tests unitaires hors ligne étendus** : **21 tests unitaires OK en 0,20 s**.

### Lot 6 — Nouveautés/disparues, règle de fusion Dan, format commun 18 champs & nettoyage du cache *(✅ Terminé)*
- [x] **Nouveautés & offres disparues (`--nouveautes`, `data/historique-collectes.csv`)** : Comparaison par clé `(source, source_id)` avant écrasement de `offres_unifiees.json`, marquage `nouvelle: bool`, liste des disparues dans `rapport_collecte.json` et option `--purger --garder-historique`.
- [x] **Règle de fusion (inspirée de `equipe/dan/livrable3/regroupement.py`)** : Conservation de l'offre la plus complète, comblement des champs vides uniquement, champ `doublons`, maintien des offres distinctes du même site et mention `Aussi publié sur : ...` dans les rapports.
- [x] **Validation Format Commun (`JobOffer` 18 champs)** : Contrôle strict dans `--verifier` contre `equipe/gregory/livrable3/models.py` (365/365 offres valides).
- [x] **Nettoyage du cache (`--nettoyer-cache`)** : Suppression des pages disparues et expirées (> 24 h) avec affichage des pages et Mo libérés.
- [x] **Tests unitaires & validation complète** : **25 tests unitaires OK** + `tester_tout.ps1` et `tester_tout.ps1 -Complet` (**19/19 PASS**).

---

## 4. Matrice de suivi

| Lot | Description | Statut | Fichiers principaux | Tests hors ligne |
| :-: | --- | :-: | --- | :-: |
| **Lot 1** | Cadrage, analyse & `compte-rendu.md` L2 | ✅ Fait | `plan.md`, `02-.../compte-rendu.md` | S/O |
| **Lot 2** | Collecteur 5 sources CNP + Fiches + Doc | ✅ Fait | `poc_guichet_cnp_v2.py`, `README.md`, `note.md`, `echantillon_v2.json` | **7 tests OK (0,01 s)** |
| **Lot 3** | Cache disque local 24 h & Pagination | ✅ Fait | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py`, `.gitignore` | **10 tests OK (0,04 s)** |
| **Lot 4** | Collecte autonome 5 sources + Enrichissement `JobTailor` + CNP + `data/*.json` | ✅ Fait | `poc_guichet_cnp_v2.py`, `data/*.json`, `data/offres_unifiees.csv`, `data/rapport_collecte.json` | **16 tests OK (0,10 s)** |
| **Lot 5** | Fraîcheur 2026 + `--filtrer` + `--format-commun` + `--html` + `--cv` + `--lettre` | ✅ Fait | `assistant_et_interface.py`, `data/portail_ti_jobtailor.html`, `data/offres_format_commun.json` | **21 tests OK (0,20 s)** |
| **Lot 6** | `--nouveautes`, `historique-collectes.csv`, fusion `doublons`, validation `JobOffer` (18 champs) & `--nettoyer-cache` | ✅ Fait | `poc_guichet_cnp_v2.py`, `assistant_et_interface.py`, `tester_tout.ps1`, `data/historique-collectes.csv` | **25 tests OK (0,29 s)** |
