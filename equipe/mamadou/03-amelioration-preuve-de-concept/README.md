# Guide d'exécution et documentation des scripts — Livrable 3 Final (Mamadou)

Ce dossier contient la réalisation complète du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**. Notre système ([`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py)) collecte, filtre (14 codes CNP 2021 TI) et enrichit **de manière 100 % autonome** les offres et leurs fiches individuelles sur **5 sources complémentaires** au Québec et au Canada (**393 offres TI réelles uniques, 100 % avec description complète et compétences clés** sous [`data/`](data/)).

---

## 1. Vue d'ensemble des 5 sources collectées par notre système (`data/`)

| # | Source | Fichier JSON par source | Offres TI retenues | Fiches avec description | Offres avec `competences_cles` | Hors-TI rejetées |
| :-: | --- | --- | :-: | :-: | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **196** | **196 / 196 (100 %)** | **196 / 196 (100 %)** | 0 (filtre `fn21`) |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **107** | **107 / 107 (100 %)** | **107 / 107 (100 %)** | 24 |
| **3** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **55** | **55 / 55 (100 %)** | **55 / 55 (100 %)** | 46 |
| **4** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **40** | **40 / 40 (100 %)** | **40 / 40 (100 %)** | 16 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **7** | **7 / 7 (100 %)** | **7 / 7 (100 %)** | 36 |
| **Total** | **Jeu global unifié** | **[`data/offres_unifiees.json`](data/offres_unifiees.json)** | **393** | **393 / 393 (100 %)** | **393 / 393 (100 %)** | **122** |

### Fichiers consolidés et statistiques sous `data/`
- **[`data/offres_unifiees.json`](data/offres_unifiees.json)** : **393 offres TI uniques** (100 % collectées par notre propre script) après déduplication intra-source (21 fusions) et inter-sources (12 fusions sans perte entre plateformes).
- **[`data/offres_unifiees.csv`](data/offres_unifiees.csv)** : Export tabulaire encodé en `utf-8-sig` (avec BOM UTF-8 et séparateur `;`) s'ouvrant directement dans Microsoft Excel sous Windows.
- **[`data/rapport_collecte.json`](data/rapport_collecte.json)** : Rapport statistique complet (compteurs par source, doublons fusionnés, répartition sur les **14 codes CNP 2021 TI**, les **6 sous-domaines TI**, les **17 régions administratives du Québec**, les **4 niveaux de séniorité** et le **top 30 des technologies**).
- **[`echantillon_v2.json`](echantillon_v2.json)** : Échantillon léger vérifié de **22 offres multi-sources** au schéma complet de 36 champs.

---

## 2. Schéma de données enrichi (`JobBankOffer` — 36 champs)

Chaque offre intègre l'ADN de `JobTailor_V3` et les meilleures briques de la classe (Grégory, Kandet, Hugo, Elvira) :
- **Classification CNP 2021 TI & Domaine :** `code_cnp` (14 codes TI), `cnp_title`, `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`).
- **Intitulés & Missions :** `titre`, `titre_employeur` (`.source-title-inner`), `missions_cles` (`list[str]`), `competences_cles` (`list[str]` — 48 technologies/outils TI + repli par code CNP `JobTailor_V3`), `description`.
- **Études, Expérience & Séniorité :** `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`), `est_stage`, `statut_stage`, `score_pertinence_dec` (`0-100`).
- **Salaire structuré :** `salaire` (texte brut), `salaire_min` (`float`), `salaire_max` (`float`), `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`).
- **Géographie (17 régions QC & GPS) :** `lieu`, `ville`, `region_administrative` (17 régions du Québec), `code_postal`, `province`, `pays`, `latitude`, `longitude` (55 offres géolocalisées).
- **Traçabilité & Intégrité HTTP :** `id`, `source_id`, `source`, `source_partenaire`, `url` (nettoyée sans `;jsessionid` ni `utm_*`), `url_partenaire` (`a#externalJobLink`), `http_status` (`200`), `content_hash` (`SHA-256` 16 hex), `date_publication`, `date_fin`, `date_extraction`.

---

## 3. Utilisation des scripts Python (Entrées / Sorties / Commandes)

### A. Collecteur autonome multi-sources (`poc_guichet_cnp_v2.py`)

- **Fichier :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py)
- **Options CLI principales :**
  - `--collecte-complete` : Lance la collecte autonome complète par notre système sur toutes les pages des 5 plateformes, télécharge chaque fiche individuelle dans `cache/` (196 fiches Guichet-Emplois, 131 fiches Jobboom, 101 fiches Talent.com, 56 fiches Jobillico, API Remotive) et génère les 5 fichiers `data/offres_*.json`, `data/offres_unifiees.json`, `data/offres_unifiees.csv` et `data/rapport_collecte.json`.
  - `--consolider-data` : Unifie et déduplique hors ligne les 5 fichiers `data/offres_*.json` vers `data/offres_unifiees.json`, `data/offres_unifiees.csv` et `data/rapport_collecte.json` en moins d'une seconde.
  - `--limite-guichet N` / `--limite-autres M` / `--pages P` : Collecte d'un échantillon rapide vers `echantillon_v2.json`.
  - `--stages` : Cible en priorité les stages TI (sans activer `fsrc=16` par erreur).
  - `--sans-cache` : Désactive le cache disque local de 24 h (`cache/`).

```powershell
# Installation des dépendances
pip install -r requirements.txt

# 1. Collecte autonome complète sur les 5 sources (lit toutes les pages et toutes les fiches individuelles)
python poc_guichet_cnp_v2.py --collecte-complete

# 2. Consolider hors ligne les 5 fichiers data/offres_*.json vers offres_unifiees.json/.csv et rapport_collecte.json
python poc_guichet_cnp_v2.py --consolider-data

# 3. Collecte d'un échantillon rapide sur les 5 sources
python poc_guichet_cnp_v2.py --limite-guichet 6 --limite-autres 4 --delai 2
```

---

### B. Suite de 16 tests unitaires 100 % hors ligne (`test_poc_guichet_cnp_v2.py`)

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```
