# Plan Directeur — Livrable 3 (`jobs-insights` — Mamadou)

> **Rôle de ce fichier (`plan.md`) :** Mémoire de travail et repère entre les conversations IA pour travailler **Lot par Lot** (1 conversation = 1 lot = 1 commit) sans saturer la fenêtre de contexte ni brûler les tokens.  
> **Dossier de travail :** [`03-amelioration-preuve-de-concept/`](03-amelioration-preuve-de-concept/)

---

## 1. Analyse de l'existant & Sélection des 5 Sources (Collecte 100 % Autonome + Fraîcheur 2026)

Notre collecteur ([`poc_guichet_cnp_v2.py --collecte-complete`](03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py)) interroge directement et de façon **100 % autonome** les **5 plateformes** (avec lecture systématique de chaque fiche individuelle, filtre des 14 codes CNP 2021 TI `classify_cnp_2021`, filtre de fraîcheur 2026 `is_recent_and_valid_offer` et cache disque 24 h) :

| # | Source | Mode d'accès autonome | Offres TI 2026 retenues (`data/`) | Hors-TI / pré-2026 filtrées |
| :-: | --- | --- | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | 8 pages × 14 codes CNP TI (`fn21`) + **196/196 fiches RDFa/DOM** | **196** | 0 |
| **2** | **Jobboom Québec** | 10 pages catégorie TI `_i10lfr` + **131 fiches JSON-LD** + filtre CNP & 2026 | **91** | 40 (24 hors-TI + 16 pré-2026) |
| **3** | **Talent.com Canada** | Multi-requêtes TI QC + **101 fiches JSON-LD `@graph` + GPS** | **55** | 46 |
| **4** | **Jobillico Québec** | Multi-requêtes TI QC + **56 fiches JSON-LD `JobPosting`** | **40** | 16 |
| **5** | **Remotive** | API REST JSON multi-catégories TI + filtre Canada & CNP | **7** | 36 |

- **Total consolidé et dédupliqué (`data/offres_unifiees.json` & `.csv`) :** **377 offres TI 2026 uniques** (**377 / 377 = 100 % avec description complète** et **377 / 377 = 100 % avec `competences_cles`**, après rejet de 138 offres hors TI / pré-2026 et fusion sans perte de 21 doublons intra-source et 12 doublons inter-sources).

---

## 2. Matrice de suivi des Lots

| Lot | Description | Statut | Fichiers principaux | Tests hors ligne |
| :-: | --- | :-: | --- | :-: |
| **Lot 1** | Cadrage, analyse & `compte-rendu.md` L2 | ✅ Fait | `plan.md`, `02-.../compte-rendu.md` | S/O |
| **Lot 2** | Collecteur 5 sources CNP + Fiches + Doc | ✅ Fait | `poc_guichet_cnp_v2.py`, `README.md`, `note.md`, `echantillon_v2.json` | **7 tests OK (0,01 s)** |
| **Lot 3** | Cache disque local 24 h & Pagination | ✅ Fait | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py`, `.gitignore` | **10 tests OK (0,04 s)** |
| **Lot 4** | Collecte autonome 5 sources + Enrichissement `JobTailor` + CNP + `data/*.json` | ✅ Fait | `poc_guichet_cnp_v2.py`, `data/*.json`, `data/offres_unifiees.csv`, `data/rapport_collecte.json` | **16 tests OK (0,10 s)** |
| **Lot 5** | Fraîcheur 2026 (377 offres) + `--filtrer` + `--format-commun` + `--html` + `--cv` + `--lettre` | ✅ Fait | `assistant_et_interface.py`, `data/portail_ti_jobtailor.html`, `data/offres_format_commun.json` | **21 tests OK (0,20 s)** |
