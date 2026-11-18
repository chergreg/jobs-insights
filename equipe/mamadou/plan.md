# Plan Directeur — Livrable 3 (`jobs-insights` — Mamadou)

> **Rôle de ce fichier (`plan.md`) :** Mémoire de travail et repère entre les conversations IA pour travailler **Lot par Lot** (1 conversation = 1 lot = 1 commit) sans saturer la fenêtre de contexte ni brûler les tokens.  
> **Dossier de travail :** `equipe/mamadou/03-amelioration-preuve-de-concept/`

---

## 1. Analyse de l'existant & Sélection des 5 Sources (Collecte 100 % Autonome)

Notre collecteur (`poc_guichet_cnp_v2.py --collecte-complete`) interroge directement et de façon **100 % autonome** les **5 plateformes** (avec lecture systématique de chaque fiche individuelle et cache disque 24 h) :

| # | Source | Mode d'accès autonome | Offres TI retenues (`data/`) | Hors-TI filtrées |
| :-: | --- | --- | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | 8 pages × 14 codes CNP TI (`fn21`) + **196/196 fiches RDFa/DOM** | **196** | 0 |
| **2** | **Jobboom Québec** | 10 pages catégorie TI `_i10lfr` + **131 fiches JSON-LD** + filtre CNP | **107** | 24 |
| **3** | **Talent.com Canada** | Multi-requêtes TI QC + **101 fiches JSON-LD `@graph` + GPS** | **55** | 46 |
| **4** | **Jobillico Québec** | Multi-requêtes TI QC + **56 fiches JSON-LD `JobPosting`** | **40** | 16 |
| **5** | **Remotive** | API REST JSON multi-catégories TI + filtre Canada & CNP | **7** | 36 |

- **Total consolidé et dédupliqué (`data/offres_unifiees.json` & `.csv`) :** **393 offres TI uniques** (**393 / 393 = 100 % avec description complète** et **393 / 393 = 100 % avec `competences_cles`**, après rejet de 122 offres hors TI et fusion sans perte de 21 doublons intra-source et 12 doublons inter-sources).

---

## 2. Matrice de suivi

| Lot | Description | Statut | Fichiers principaux | Tests hors ligne |
| :-: | --- | :-: | --- | :-: |
| **Lot 1** | Cadrage, analyse & `compte-rendu.md` L2 | ✅ Fait | `plan.md`, `02-.../compte-rendu.md` | S/O |
| **Lot 2** | Collecteur 5 sources CNP + Fiches + Doc | ✅ Fait | `poc_guichet_cnp_v2.py`, `README.md`, `note.md`, `echantillon_v2.json` | **7 tests OK (0,01 s)** |
| **Lot 3** | Cache disque local 24 h & Pagination | ✅ Fait | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py`, `.gitignore` | **10 tests OK (0,04 s)** |
| **Lot 4** | Collecte autonome 5 sources + Enrichissement `JobTailor` + CNP + `data/*.json` (393 offres TI, 100 % descriptions) | ✅ Fait | `poc_guichet_cnp_v2.py`, `data/*.json`, `data/offres_unifiees.csv`, `data/rapport_collecte.json` | **16 tests OK (0,10 s)** |
