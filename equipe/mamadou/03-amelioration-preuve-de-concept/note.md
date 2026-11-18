# Livrable 3 — Amélioration, Classification CNP 2021 TI et Unification Multi-Sources (5 Plateformes Québec / Canada)

**Auteur :** Mamadou  
**Date :** 18 novembre 2026  
**Code, données et tests :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) · [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py) · [`README.md`](README.md) · [`plan.md`](plan.md) · [`data/`](data/)

---

## 1. Sources retenues (5 sites) et jeux de données consolidés (`data/`)

Nous avons unifié, filtré selon les **14 codes CNP 2021 TI** et enrichi **5 sources complémentaires** au Québec et au Canada, en générant un fichier JSON par source ainsi que le jeu consolidé dédupliqué sous [`data/`](data/) :

| # | Source | Fichier JSON dédié | Offres TI retenues | Hors-TI filtrées |
| :-: | --- | --- | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **212** | 0 |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **109** | 26 |
| **3** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **26** | 31 |
| **4** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **15** | 0 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **11** | 28 |

- **Jeu global unifié :** [`data/offres_unifiees.json`](data/offres_unifiees.json) et [`data/offres_unifiees.csv`](data/offres_unifiees.csv) (`utf-8-sig`, séparateur `;`) rassemblent **368 offres TI réelles uniques** (après fusion sans perte de 89 doublons intra-source et 5 doublons inter-sources).
- **Rapport statistique :** [`data/rapport_collecte.json`](data/rapport_collecte.json) détaille la répartition par code CNP, sous-domaine TI, région administrative du Québec, niveau de séniorité et top 30 des technologies.

---

## 2. Contributions de la classe et ADN `JobTailor_V3` intégrés

| Source d'inspiration | Brique reprise | Bonification apportée dans notre Lot 4 |
| --- | --- | --- |
| **`JobTailor_V3` (Mamadou)** | `domaine_ti`, `normalize_job_url`, `content_hash` SHA-256, `missions_cles` | Étendu aux 6 sous-domaines TI et couplé au `score_pertinence_dec` (`0-100`) |
| **Grégory** (`livrable3/`) | Jeux consolidés sous `data/`, déduplication intra/inter-sources et export CSV Excel | Étendu de 3 à **5 sources**, filtrage strict hors TI (26 offres non-TI retirées de Jobboom) et schéma 36 champs |
| **Kandet** (`03-.../`) | 14 codes CNP 2021 TI, preuve sur `fsrc=16`, salaire chiffré et 17 régions du Québec | Classification CNP étendue aux **5 sources** (`classify_cnp_2021`) + correction de `fsrc=16` |
| **Hugo** (`02-.../`) | Cascade RDFa/DOM sur les fiches Guichet-Emplois et regex de compétences sans faux positifs | Fusion sans perte de ses descriptions Guichet-Emplois et décodage double HTML partenaire |
| **Elvira** (`03-.../`) | Extraction JSON-LD sur Jobboom TI (`_i10lfr`) | Exclusion des commandites (`job_item_sponsorship`) et filtrage CNP anti-bruit |

---

## 3. Améliorations techniques majeures (Lot 1 à Lot 4)

### A. Classification CNP 2021 TI sur les 5 sources & Filtrage anti-bruit (0 faux positif)
- **Correction de `fsrc=16` sur Guichet-Emplois :** comme démontré par Kandet, `fsrc=16` filtre la source native Guichet-Emplois (excluant les partenaires Jobillico/Talent.com) et non les stages. `build_cnp_search_url` n'active plus `fsrc=16` lors d'une recherche de stages (`student_only=True`).
- **Classifieur déterministe `classify_cnp_2021` :** attribue à chaque offre des 5 sources l'un des **14 codes CNP 2021 TI** (`code_cnp` + `cnp_title`) et rejette systématiquement les postes hors TI présents dans les catégories larges (ex. *Opérateur à l'enneigement*, *Programmeur CNC*, *Audio Specialist*, *Chef des ventes*, *YouTube Creator*, *Office Assistant*, *Journalier au désassemblage*).

### B. Enrichissement à 36 champs (`JobBankOffer`)
- **6 sous-domaines TI (`domaine_ti`) :** `tech_backend` (192 offres), `tech_support` (85), `data_ia` (44), `devops_cloud` (20), `cybersecurite` (17), `tech_frontend` (10).
- **Séniorité, études et missions :** extraction de `missions_cles`, `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Intermédiaire` : 205, `Senior` : 107, `Junior / DEC` : 47, `Étudiant / Stage` : 9) et calcul du `score_pertinence_dec` (`0-100`).
- **Salaire chiffré et 17 régions administratives du Québec :** extraction de `salaire_min`, `salaire_max`, `unite_salaire` (231 offres chiffrées sans conversion artificielle heure/année), `ville`, `code_postal`, `latitude`/`longitude` (34 offres géolocalisées) et résolution vers les **17 régions administratives du Québec**.

---

## 4. Commandes de vérification

```powershell
pip install -r .\equipe\mamadou\03-amelioration-preuve-de-concept\requirements.txt

# 1. Exécuter les 16 tests unitaires 100 % hors ligne (0,10 s)
python -m unittest discover -s .\equipe\mamadou\03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Consolider hors ligne les 5 fichiers data/offres_*.json vers offres_unifiees.json/.csv et rapport_collecte.json
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --consolider-data

# 3. Lancer une collecte directe multi-sources avec cache disque 24 h
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --limite-guichet 6 --limite-autres 4 --delai 2
```

---

## 5. Synthèse quantitative Avant / Après (Livrable 2 vs Livrable 3 Lot 4)

| Indicateur | Livrable 2 (v1) | Livrable 3 (Lot 2-3) | Livrable 3 Final (Lot 4) |
| --- | :-: | :-: | :-: |
| **Sources actives unifiées** | 4 (schémas séparés) | 5 | **5 sources (1 file JSON/source + unifié)** |
| **Offres TI uniques consolidées** | 10 | 22 | **368 offres TI uniques (`data/offres_unifiees.json`)** |
| **Offres hors TI filtrées** | 0 | 0 | **85 offres hors TI rejetées (0 faux positif)** |
| **Classification 14 codes CNP 2021** | 0 | 1 source | **5 / 5 sources (100 % des 368 offres)** |
| **Champs par offre (`JobBankOffer`)** | 10 | 21 | **36 champs (`JobTailor_V3` + Classe)** |
| **Offres avec salaire chiffré** | 0 | 0 (texte brut) | **231 offres (`salaire_min`, `salaire_max`, `unite_salaire`)** |
| **Offres avec coordonnées GPS** | 3 | 4 | **34 offres (`latitude`, `longitude`)** |
| **Export CSV Excel (`utf-8-sig`, `;`)** | Non | Non | **Oui (`data/offres_unifiees.csv`)** |
| **Tests unitaires hors ligne** | 0 | 10 (`0,04 s`) | **16 tests (`OK` en `0,10 s`)** |
