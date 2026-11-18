# Guide d'exécution et documentation des scripts — Livrable 3 Final (Mamadou)

Ce dossier contient la réalisation complète du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**, en consolidant, filtrant (14 codes CNP 2021 TI) et enrichissant **5 sources complémentaires** d'offres d'emploi et de stages en TI au Québec et au Canada (**368 offres TI réelles uniques** sous [`data/`](data/)).

---

## 1. Vue d'ensemble des 5 sources TI et des jeux de données générés (`data/`)

| # | Source | Fichier JSON par source | Offres TI retenues | Hors-TI rejetées |
| :-: | --- | --- | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **212** | 0 (filtre `fn21`) |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **109** | 26 |
| **3** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **26** | 31 |
| **4** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **15** | 0 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **11** | 28 |

### Fichiers consolidés et statistiques sous `data/`
- **[`data/offres_unifiees.json`](data/offres_unifiees.json)** : **368 offres TI uniques** après déduplication intra-source (89 fusions) et inter-sources (5 fusions sans perte entre plateformes).
- **[`data/offres_unifiees.csv`](data/offres_unifiees.csv)** : Export tabulaire encodé en `utf-8-sig` (avec BOM UTF-8 et séparateur `;`) s'ouvrant directement dans Microsoft Excel sous Windows sans problème d'accents.
- **[`data/rapport_collecte.json`](data/rapport_collecte.json)** : Rapport statistique complet (compteurs par source, doublons fusionnés, répartition sur les **14 codes CNP 2021 TI**, les **6 sous-domaines TI**, les **17 régions administratives du Québec**, les **4 niveaux de séniorité** et le **top 30 des technologies**).
- **[`echantillon_v2.json`](echantillon_v2.json)** : Échantillon léger vérifié de **22 offres multi-sources** au schéma complet de 36 champs.

---

## 2. Schéma de données enrichi (`JobBankOffer` — 36 champs)

Chaque offre intègre l'ADN de `JobTailor_V3` et les meilleures briques de la classe (Grégory, Kandet, Hugo, Elvira) :
- **Classification CNP 2021 TI & Domaine :** `code_cnp` (14 codes TI), `cnp_title`, `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`).
- **Intitulés & Missions :** `titre`, `titre_employeur` (`.source-title-inner`), `missions_cles` (`list[str]`), `competences_cles` (`list[str]`), `description`.
- **Études, Expérience & Séniorité :** `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`), `est_stage`, `statut_stage`, `score_pertinence_dec` (`0-100`).
- **Salaire structuré :** `salaire` (texte brut), `salaire_min` (`float`), `salaire_max` (`float`), `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`).
- **Géographie (17 régions QC & GPS) :** `lieu`, `ville`, `region_administrative` (17 régions du Québec), `code_postal`, `province`, `pays`, `latitude`, `longitude`.
- **Traçabilité & Intégrité HTTP :** `id`, `source_id`, `source`, `source_partenaire`, `url` (nettoyée sans `;jsessionid` ni `utm_*`), `url_partenaire` (`a#externalJobLink`), `http_status` (`200`), `content_hash` (`SHA-256` 16 hex), `date_publication`, `date_fin`, `date_extraction`.

---

## 3. Utilisation des scripts Python (Entrées / Sorties / Commandes)

### A. Collecteur et consolidateur multi-sources (`poc_guichet_cnp_v2.py`)

- **Fichier :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py)
- **Options CLI principales :**
  - `--consolider-data` : Unifie, filtre (14 codes CNP 2021 TI), déduplique hors ligne les 5 fichiers `data/offres_*.json` et régénère `data/offres_unifiees.json`, `data/offres_unifiees.csv` et `data/rapport_collecte.json` en moins d'une seconde.
  - `--limite-guichet N` : Nombre de fiches Guichet-Emplois CNP à enrichir en direct (défaut : `8`).
  - `--limite-autres M` : Nombre d'offres TI à extraire sur chacune des 4 autres sources (défaut : `4`).
  - `--pages P` : Nombre de pages de résultats à parcourir sur Guichet-Emplois CNP et Jobboom TI (défaut : `1`).
  - `--stages` : Cible en priorité les stages TI (sans activer `fsrc=16` par erreur afin de conserver les stages partenaires Jobillico/Talent.com).
  - `--mot-cle TEXTE` : Mot-clé additionnel optionnel (ex. `python`, `reseau`, `cybersecurite`).
  - `--delai SECONDES` : Délai entre les nouvelles requêtes HTTP (défaut : `2.0` s ; `5.0` s sur Guichet-Emplois).
  - `--sans-cache` : Désactive le cache disque local de 24 h (`cache/`).
  - `--sortie FICHIER` : Nom du fichier JSON généré (défaut : `echantillon_v2.json`).

```powershell
# Installation des dépendances
pip install -r requirements.txt

# 1. Consolider hors ligne les 5 fichiers data/offres_*.json vers offres_unifiees.json/.csv et rapport_collecte.json
python poc_guichet_cnp_v2.py --consolider-data

# 2. Collecte directe sur les 5 sources avec cache 24 h
python poc_guichet_cnp_v2.py --limite-guichet 6 --limite-autres 4 --delai 2

# 3. Collecte multi-pages (2 pages sur Guichet-Emplois CNP et Jobboom TI)
python poc_guichet_cnp_v2.py --pages 2 --limite-guichet 12 --limite-autres 6 --delai 5
```

---

### B. Suite de 16 tests unitaires 100 % hors ligne (`test_poc_guichet_cnp_v2.py`)

Vérifie l'ensemble du pipeline sans aucun appel réseau : URLs CNP (et correction de `fsrc=16`), classification des 14 codes CNP 2021 TI sur les 5 sources, rejet strict des offres hors TI (`YouTube Creator`, `Office Assistant`, `Chef des ventes`, `Programmeur CNC`, `Opérateur à l'enneigement`), détection `domaine_ti`, extraction de `missions_cles`, `niveau_seniorite`, salaire chiffré, résolution des 17 régions administratives du Québec, `content_hash` SHA-256, `score_pertinence_dec`, cache disque 24 h, pagination, fusion inter-sources sans perte et export CSV `utf-8-sig`.

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```
