# Plan Directeur — Livrable 3 (`jobs-insights` — Mamadou)

> **Rôle de ce fichier (`plan.md`) :** Mémoire de travail et repère entre les conversations IA pour travailler **Lot par Lot** (1 conversation = 1 lot = 1 commit) sans saturer la fenêtre de contexte ni brûler les tokens.  
> **Dossier de travail :** `equipe/mamadou/03-amelioration-preuve-de-concept/`

---

## 1. Analyse de l'existant & Sélection des 5 Sources

Plutôt que de nous limiter à 3 sites, nous exploitons **les 5 sources concluantes** de nos recherches initiales en fusionnant nos acquis (`JobTailor_V3`) avec les meilleures briques de la classe (Grégory, Kandet, Hugo, Elvira) :

| # | Source | Mode d'accès | Offres TI retenues (`data/`) |
| :-: | --- | --- | :-: |
| **1** | **Guichet-Emplois Canada** | 14 codes CNP TI (`fn21`) + Fiches RDFa/DOM | **212** |
| **2** | **Jobboom Québec** | Catégorie TI `_i10lfr` + JSON-LD + filtre CNP TI | **109** |
| **3** | **Jobillico Québec** | Recherche TI QC + JSON-LD + filtre CNP TI | **26** |
| **4** | **Talent.com Canada** | Double JSON-LD `@graph` + GPS + filtre CNP TI | **15** |
| **5** | **Remotive** | API REST JSON + filtre Canada & CNP TI | **11** |

- **Total consolidé et dédupliqué (`data/offres_unifiees.json` & `.csv`) :** **368 offres TI uniques** (sur 462 entrées TI après fusion de 89 doublons intra-source et 5 doublons inter-sources, et rejet de 85 offres hors TI).

---

## 2. Schéma de données unifié enrichi (`JobBankOffer` — 36 champs)

Chaque offre collectée sur l'une des 5 sources est normalisée dans la `@dataclass JobBankOffer` (`None` si absent, zéro donnée inventée) :
- **Identifiants & Traçabilité (`JobTailor_V3`) :** `id` (`ge-...`, `tc-...`, `jb-...`, `ji-...`, `rem-...`), `source_id`, `url` (nettoyée sans `;jsessionid` ni `utm_*`), `source`, `source_partenaire`, `url_partenaire` (`a#externalJobLink`), `http_status` (`200`), `content_hash` (`SHA-256` 16 hex), `date_extraction`
- **Classification CNP 2021 TI & Domaine (`JobTailor_V3`) :** `code_cnp` (14 codes CNP 2021 TI), `cnp_title`, `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`), `titre`, `titre_employeur`
- **Entreprise & Géographie (17 régions QC + GPS) :** `entreprise`, `lieu`, `ville`, `region_administrative` (17 régions administratives du Québec), `code_postal`, `province`, `pays`, `latitude`, `longitude`
- **Conditions, Études & Séniorité :** `date_publication` (ISO `AAAA-MM-JJ`), `date_fin`, `type_poste`, `modalite` (`Sur place`, `Hybride`, `Télétravail`), `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`)
- **Rémunération structurée :** `salaire` (texte brut), `salaire_min`, `salaire_max`, `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`)
- **Qualification TI, Missions & Score DEC :** `est_stage` (`bool`), `statut_stage` (`confirmed_stage`, `possible_stage`, `not_indicated`), `competences_cles` (`list[str]`), `missions_cles` (`list[str]`), `score_pertinence_dec` (`0-100`), `description`

---

## 3. Feuille de route par Lots (1 Lot = 1 Conversation = 1 Commit)

### Lot 1 — Cadrage, analyse de la classe et plan directeur *(✅ Terminé)*
- [x] Analyser les travaux du dépôt (Kandet, Hugo, Elvira, Ferdinand, Rayan, Grégory).
- [x] Définir la stack (`requests` + `beautifulsoup4` dans `requirements.txt`).
- [x] Rédiger le compte rendu manquant du Livrable 2 (`02-preuve-de-concept-scraping/compte-rendu.md`).
- [x] Créer `plan.md` pour piloter les itérations.

### Lot 2 — Collecteur 5 sources enrichi, Codes CNP TI, Tests hors ligne & Documentation *(✅ Terminé)*
- [x] Implémenter la recherche Guichet-Emplois par **14 codes CNP TI (`fn21`)**.
- [x] Implémenter la cascade d'enrichissement des fiches Guichet-Emplois (RDFa `property="description"` avec décodage du HTML doublement échappé Jobillico + repli DOM `#job-posting-detail` + bandeau `ul.job-posting-brief` + vrai titre `.source-title-inner`).
- [x] Intégrer les 4 autres sources (**Talent.com GPS**, **Jobboom TI**, **Jobillico**, **Remotive API**) dans le même schéma riche `JobBankOffer` avec dates ISO et extraction des compétences TI.
- [x] Créer **7 tests unitaires hors ligne** (`test_poc_guichet_cnp_v2.py` + `fixtures/`).
- [x] Générer le jeu d'essai vérifié [`echantillon_v2.json`](03-amelioration-preuve-de-concept/echantillon_v2.json) (**22 offres riches, 0 description `null`**).
- [x] Documenter l'usage des scripts dans [`README.md`](03-amelioration-preuve-de-concept/README.md) et [`note.md`](03-amelioration-preuve-de-concept/note.md).

### Lot 3 — Cache disque local & Pagination multi-pages *(✅ Terminé)*
- [x] Ajouter un gestionnaire de cache local sur disque (`cache/` avec TTL 24 h, ignoré par Git via `.gitignore`) pour ne pas re-télécharger les fiches déjà lues et respecter le `Crawl-delay: 5s` sans attente inutile.
- [x] Ajouter la pagination multi-pages (`--pages N`) sur Guichet-Emplois CNP et Jobboom TI avec déduplication inter-pages.
- [x] Ajouter les tests unitaires hors ligne du cache et de la pagination (**10 tests OK en 0,04 s**).
- [x] Mettre à jour `README.md` et `plan.md`.

### Lot 4 — Enrichissement maximal (`JobTailor` + Classe), Classification CNP sur les 5 sources, Datasets par source (`data/*.json` > 350 offres), Déduplication & Export CSV *(✅ Terminé)*
- [x] **Étendre le filtre et la classification des 14 codes CNP TI aux 5 sources** :
  - Sur **Guichet-Emplois** : conserver le filtre URL natif `fn21` (14 codes CNP TI) et corriger l'usage de `fsrc=16` (qui filtre la source Guichet-Emplois directe et non les stages, comme démontré par Kandet).
  - Sur **Jobboom, Talent.com, Jobillico et Remotive** : implémenter le classifieur CNP automatique (`classify_cnp_2021`) qui attribue à chaque offre son `code_cnp` et son `cnp_title`, et **rejette automatiquement toute offre hors TI** (85 offres hors TI filtrées, 0 faux positif).
- [x] **Enrichir chaque offre dans les JSONs avec l'ADN de `JobTailor_V3` + les meilleures briques de la classe (Grégory, Kandet, Elvira, Hugo)** :
  - `code_cnp` & `cnp_title` (sur les 5 sources)
  - `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite` — repris de `JobTailor_V3`)
  - `missions_cles` (`list[str]` — responsabilités/tâches extraites)
  - `niveau_etudes`, `experience_requise` et `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`)
  - `salaire`, `salaire_min`, `salaire_max`, `unite_salaire` (`heure`, `année`, `mois`)
  - `ville`, `region_administrative` (17 régions du Québec), `code_postal`, `latitude`, `longitude`
  - `url` (nettoyée sans `;jsessionid` ni traceurs `utm_*`), `url_partenaire` (`a#externalJobLink`), `http_status` (`200`) et `content_hash` (`SHA-256` repris de `JobTailor_V3`)
  - `score_pertinence_dec` (`0-100` : score d'adéquation pour un étudiant du DEC en informatique)
- [x] **Générer un fichier JSON dédié par source + le fichier global consolidé (368 offres TI réelles uniques) + CSV Excel + Rapport** sous `data/` :
  - `data/offres_guichet_emplois.json` (**212 offres TI QC** enrichies)
  - `data/offres_jobboom.json` (**109 offres TI QC** enrichies, 26 hors-TI rejetées)
  - `data/offres_talent.json` (**15 offres TI QC** avec coordonnées GPS)
  - `data/offres_jobillico.json` (**26 offres TI QC** enrichies, 31 hors-TI rejetées)
  - `data/offres_remotive.json` (**11 offres TI télétravail Canada** 100 % filtrées TI)
  - `data/offres_unifiees.json` (**368 offres TI uniques** après déduplication intra/inter-sources et fusion sans perte)
  - `data/offres_unifiees.csv` (compatible Excel Windows `utf-8-sig`, séparateur `;`)
  - `data/rapport_collecte.json` (statistiques par source, doublons fusionnés, top technologies, répartition par code CNP et par région)
- [x] **Ajouter les tests unitaires hors ligne** (**16 tests OK en 0,10 s**) et mettre à jour `README.md`, `note.md` et `plan.md`.

---

## 4. Matrice de suivi

| Lot | Description | Statut | Fichiers principaux | Tests hors ligne |
| :-: | --- | :-: | --- | :-: |
| **Lot 1** | Cadrage, analyse & `compte-rendu.md` L2 | ✅ Fait | `plan.md`, `02-.../compte-rendu.md` | S/O |
| **Lot 2** | Collecteur 5 sources CNP + Fiches + Doc | ✅ Fait | `poc_guichet_cnp_v2.py`, `README.md`, `note.md`, `echantillon_v2.json` | **7 tests OK (0,01 s)** |
| **Lot 3** | Cache disque local 24 h & Pagination | ✅ Fait | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py`, `.gitignore` | **10 tests OK (0,04 s)** |
| **Lot 4** | Enrichissement `JobTailor` + CNP 5 sources + Datasets `data/*.json` (368 offres TI) + Dédup + CSV | ✅ Fait | `poc_guichet_cnp_v2.py`, `data/*.json`, `data/offres_unifiees.csv`, `data/rapport_collecte.json` | **16 tests OK (0,10 s)** |
