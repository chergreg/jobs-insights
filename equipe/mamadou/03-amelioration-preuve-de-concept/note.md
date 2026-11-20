# Livrable 3 — Amélioration, Classification CNP 2021 TI et Unification Multi-Sources (5 Plateformes Québec / Canada)

**Auteur :** Mamadou  
**Date :** 18 novembre 2026  
**Code, données et tests :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) · [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py) · [`README.md`](README.md) · [`plan.md`](plan.md) · [`data/`](data/)

---

## 1. Collecte autonome sur les 5 sources et jeux de données générés (`data/`)

Notre collecteur ([`poc_guichet_cnp_v2.py --collecte-complete`](poc_guichet_cnp_v2.py)) parcourt **lui-même toutes les pages et télécharge chaque fiche individuelle** sur les **5 sources complémentaires** au Québec et au Canada :

| # | Source | Fichier JSON dédié | Offres TI retenues | Descriptions complètes | `competences_cles` | Hors-TI filtrées |
| :-: | --- | --- | :-: | :-: | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **196** | **196 / 196 (100 %)** | **196 / 196 (100 %)** | 0 |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **107** | **107 / 107 (100 %)** | **107 / 107 (100 %)** | 24 |
| **3** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **55** | **55 / 55 (100 %)** | **55 / 55 (100 %)** | 46 |
| **4** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **40** | **40 / 40 (100 %)** | **40 / 40 (100 %)** | 16 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **7** | **7 / 7 (100 %)** | **7 / 7 (100 %)** | 36 |

- **Jeu global unifié :** [`data/offres_unifiees.json`](data/offres_unifiees.json) et [`data/offres_unifiees.csv`](data/offres_unifiees.csv) (`utf-8-sig`, séparateur `;`) rassemblent **393 offres TI réelles uniques** (**100 % collectées par notre système**, **393 / 393 avec description complète et compétences clés**, après fusion sans perte de 21 doublons intra-source et 12 doublons inter-sources).
- **Rapport statistique :** [`data/rapport_collecte.json`](data/rapport_collecte.json) détaille la répartition par code CNP, sous-domaine TI, région administrative du Québec, niveau de séniorité et top 30 des technologies.

---

## 2. Contributions de la classe et ADN `JobTailor_V3` intégrés

| Source d'inspiration | Brique méthodologique | Bonification dans notre système autonome (Lot 4) |
| --- | --- | --- |
| **`JobTailor_V3` (Mamadou)** | `domaine_ti`, `normalize_job_url`, `content_hash` SHA-256, `missions_cles`, repli `domain_hint` | Étendu aux 6 sous-domaines TI, 48 technologies/outils TI et `score_pertinence_dec` (`0-100`) |
| **Kandet** (`03-.../`) | 14 codes CNP 2021 TI, preuve sur `fsrc=16`, salaire chiffré et 17 régions du Québec | Classification CNP étendue aux **5 sources** (`classify_cnp_2021`) + lecture des 196 fiches |
| **Hugo** (`02-.../`) | Cascade RDFa/DOM sur les fiches Guichet-Emplois et regex sans faux positifs | Cascade à 3 niveaux garantissant **196 / 196 descriptions non vides** sur Guichet-Emplois |
| **Elvira** (`03-.../`) | Extraction JSON-LD sur Jobboom TI (`_i10lfr`) | Pagination sur 10 pages hors commandites et rejet des 24 annonces hors TI |
| **Grégory** (`livrable3/`) | Architecture `data/offres_*.json`, déduplication intra/inter-sources et CSV Excel | Collecte 100 % autonome sur **5 sources** (`--collecte-complete`) avec schéma à 36 champs |

---

## 3. Commandes de vérification

```powershell
pip install -r .\equipe\mamadou\03-amelioration-preuve-de-concept\requirements.txt

# 1. Exécuter les 16 tests unitaires 100 % hors ligne (0,10 s)
python -m unittest discover -s .\equipe\mamadou\03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Exécuter la collecte autonome complète par notre système sur les 5 plateformes (avec cache disque 24 h)
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --collecte-complete

# 3. Consolider hors ligne les 5 fichiers data/offres_*.json vers offres_unifiees.json/.csv et rapport_collecte.json
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --consolider-data
```

---

## 4. Synthèse quantitative Avant / Après (Livrable 2 vs Livrable 3 Lot 4)

| Indicateur | Livrable 2 (v1) | Livrable 3 (Lot 2-3) | Livrable 3 Final (Lot 4 Autonome) |
| --- | :-: | :-: | :-: |
| **Sources actives collectées par le script** | 4 (schémas séparés) | 5 | **5 sources (1 JSON dédié/source + unifié)** |
| **Offres TI uniques collectées** | 10 | 22 | **393 offres TI uniques (`data/offres_unifiees.json`)** |
| **Offres avec description complète** | Partielle | 22 / 22 | **393 / 393 (100 %)** |
| **Offres avec `competences_cles`** | 0 | 18 / 22 | **393 / 393 (100 % — 48 technos + repli CNP)** |
| **Offres hors TI filtrées** | 0 | 0 | **122 offres hors TI rejetées (0 faux positif)** |
| **Classification 14 codes CNP 2021** | 0 | 1 source | **5 / 5 sources (100 % des 393 offres)** |
| **Champs par offre (`JobBankOffer`)** | 10 | 21 | **36 champs (`JobTailor_V3` + Classe)** |
| **Offres avec salaire chiffré** | 0 | 0 (texte brut) | **213 offres (`salaire_min`, `salaire_max`, `unite_salaire`)** |
| **Offres avec coordonnées GPS** | 3 | 4 | **55 offres (`latitude`, `longitude`)** |
| **Tests unitaires hors ligne** | 0 | 10 (`0,04 s`) | **16 tests (`OK` en `0,10 s`)** |
