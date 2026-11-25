# Livrable 3 — Amélioration, Classification CNP 2021 TI, Portail Web Interactif et Assistant JobTailor (5 Plateformes Québec / Canada)

**Auteur :** Mamadou  
**Date :** 18 novembre 2026  
**Code, données et tests :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) · [`assistant_et_interface.py`](assistant_et_interface.py) · [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py) · [`README.md`](README.md) · [`plan.md`](plan.md) · [`data/`](data/)

---

## 1. Collecte autonome sur les 5 sources et jeux de données générés (`data/`)

Notre collecteur ([`poc_guichet_cnp_v2.py --collecte-complete`](poc_guichet_cnp_v2.py)) parcourt **lui-même toutes les pages et télécharge chaque fiche individuelle** sur les **5 sources complémentaires** au Québec et au Canada, en appliquant le filtre des 14 codes CNP 2021 TI (`classify_cnp_2021`) et le filtre de fraîcheur 2026 (`is_recent_and_valid_offer`) :

| # | Source | Fichier JSON dédié | Offres TI 2026 retenues | Descriptions complètes | `competences_cles` | Hors-TI / pré-2026 filtrées |
| :-: | --- | --- | :-: | :-: | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **188** | **188 / 188 (100 %)** | **188 / 188 (100 %)** | 0 |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **86** | **86 / 86 (100 %)** | **86 / 86 (100 %)** | 41 (25 hors-TI + 16 pré-2026) |
| **3** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **51** | **51 / 51 (100 %)** | **51 / 51 (100 %)** | 56 |
| **4** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **43** | **43 / 43 (100 %)** | **43 / 43 (100 %)** | 15 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **6** | **6 / 6 (100 %)** | **6 / 6 (100 %)** | 36 |

- **Jeu global unifié :** [`data/offres_unifiees.json`](data/offres_unifiees.json) et [`data/offres_unifiees.csv`](data/offres_unifiees.csv) (`utf-8-sig`, séparateur `;`) rassemblent **365 offres TI 2026 réelles uniques** (**100 % collectées par notre système**, **365 / 365 avec description complète et compétences clés**, après fusion sans perte de 18 doublons intra-source et 9 doublons inter-sources avec champ `doublons` et suivi `nouvelle` + `data/historique-collectes.csv`).
- **Format commun de la classe (`JobOffer` — 18 champs) :** [`data/offres_format_commun.json`](data/offres_format_commun.json) exporte les 365 offres dans le schéma pivot de 18 champs adopté par Grégory (`equipe/gregory/livrable3/models.py`), validé automatiquement par `--verifier`.
- **Portail Web interactif autonome (`--html`) :** [`data/portail_ti_jobtailor.html`](data/portail_ti_jobtailor.html) embarque les 365 offres avec filtres par source, code CNP 2021, sous-domaine TI, région du Québec, technologie, séniorité, comparateur de CV par Score ATS en direct et vérificateur de lettre de motivation.
- **Rapport statistique :** [`data/rapport_collecte.json`](data/rapport_collecte.json) détaille la répartition par code CNP, sous-domaine TI, région administrative du Québec, niveau de séniorité et top 30 des technologies.

---

## 2. Contributions de la classe et ADN `JobTailor_V3` intégrés

| Source d'inspiration | Brique méthodologique | Bonification dans notre système autonome |
| --- | --- | --- |
| **`JobTailor_V3` (Mamadou)** | `domaine_ti`, `normalize_job_url`, `content_hash` SHA-256, `missions_cles`, matching ATS CV & méthode *Vous / Moi / Nous* | Étendu aux 6 sous-domaines TI, 48 technologies/outils TI, `score_pertinence_dec` (`0-100`), `--cv` et `--lettre` |
| **Kandet** (`03-.../`) | 14 codes CNP 2021 TI, preuve sur `fsrc=16`, 17 régions QC, `--cv`/`.docx`, `--lettre` et `format-commun/` | Classification CNP sur **5 sources** (`classify_cnp_2021`) + assistant CV/lettre multi-format + portail Web unifié |
| **Hugo** (`02-.../` & `03..07-*`) | Cascade RDFa/DOM sur les fiches Guichet-Emplois et regex sans faux positifs | Cascade à 3 niveaux garantissant **194 / 194 descriptions non vides** sur Guichet-Emplois |
| **Elvira** (`03-.../`) | Extraction JSON-LD sur Jobboom TI (`_i10lfr`), `is_recent_and_valid_offer` et `visualiseur.html` | Purge des 16 offres Jobboom pré-2026 (`2023`/`2025`) et portail Web interactif XSS-safe (`textContent`) |
| **Grégory** (`livrable3/` & `bilan/`) | Architecture `data/offres_*.json`, modèle pivot `JobOffer` (17 champs), déduplication et CSV Excel | Collecte 100 % autonome sur **5 sources** (`--collecte-complete`) + export `--format-commun` |

---

## 3. Commandes de vérification

```powershell
pip install -r .\equipe\mamadou\03-amelioration-preuve-de-concept\requirements.txt

# 1. Exécuter les 25 tests unitaires 100 % hors ligne (0,29 s)
python -m unittest discover -s .\equipe\mamadou\03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Exécuter la collecte autonome complète par notre système sur les 5 plateformes (avec cache disque 24 h)
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --collecte-complete

# 3. Consolider hors ligne + générer le Portail Web HTML + exporter au Format Commun de la classe
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --consolider-data --html --format-commun

# 4. Tester le filtrage hors ligne, l'appariement CV (--cv) et l'audit de lettre (--lettre)
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --filtrer --region Capitale-Nationale --techno Python
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --cv cv_etudiant_dec_exemple.txt --lettre lettre_motivation_exemple.txt --top 5
```

---

## 4. Synthèse quantitative Avant / Après (Livrable 2 vs Livrable 3 Final)

| Indicateur | Livrable 2 (v1) | Livrable 3 (Lot 2-3) | Livrable 3 Final (Lot 4 + Pistes 3 & 4) |
| --- | :-: | :-: | :-: |
| **Sources actives collectées par le script** | 4 (schémas séparés) | 5 | **5 sources (1 JSON dédié/source + unifié + format commun)** |
| **Offres TI 2026 uniques collectées** | 10 | 22 | **365 offres TI 2026 uniques (`data/offres_unifiees.json`)** |
| **Offres avec description complète** | Partielle | 22 / 22 | **365 / 365 (100 %)** |
| **Offres avec `competences_cles`** | 0 | 18 / 22 | **365 / 365 (100 % — 48 technos + repli CNP)** |
| **Offres hors TI ou pré-2026 filtrées** | 0 | 0 | **148 offres rejetées (132 hors-TI + 16 pré-2026, 0 faux positif)** |
| **Classification 14 codes CNP 2021** | 0 | 1 source | **5 / 5 sources (100 % des 365 offres)** |
| **Champs par offre (`JobBankOffer`)** | 10 | 21 | **38 champs (`doublons`, `nouvelle`) + export `JobOffer` (18 champs communs validés)** |
| **Interfaces & Assistant Candidature** | Aucun | CLI collecte | **`--filtrer`, `--nouveautes`, `--nettoyer-cache`, `--html`, `--cv`, `--lettre`, `--verifier`** |
| **Tests unitaires hors ligne** | 0 | 10 (`0,04 s`) | **25 tests (`OK` en `0,29 s`)** |
