# Guide d'exécution et documentation des scripts — Livrable 3 Final (Mamadou)

Ce dossier contient la réalisation complète du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**. Notre système ([`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) + [`assistant_et_interface.py`](assistant_et_interface.py)) collecte, filtre (14 codes CNP 2021 TI + filtre de fraîcheur 2026) et enrichit **de manière 100 % autonome** les offres et leurs fiches individuelles sur **5 sources complémentaires** au Québec et au Canada (**372 offres TI 2026 réelles uniques, 100 % avec description complète et compétences clés** sous [`data/`](data/)).

Il intègre également :
- **Piste 3 (Exploration & Format commun)** : Filtrage multicritère instantané hors ligne en CLI (`--filtrer`), **Portail Web interactif autonome** ([`data/portail_ti_jobtailor.html`](data/portail_ti_jobtailor.html) via `--html`) et export au **Format Commun de la classe** ([`data/offres_format_commun.json`](data/offres_format_commun.json) via `--format-commun`, compatible avec les 17 champs du modèle `JobOffer` de Grégory).
- **Piste 4 (Assistant de candidature `JobTailor_V3`)** : Comparaison d'un CV étudiant (`.txt`, `.md`, `.docx`, `.json`) avec les 372 offres TI par **Score ATS (`/100`)** (`--cv`) et audit de **lettre de motivation** selon la méthode *Vous / Moi / Nous* (`--lettre`).

---

## 1. Vue d'ensemble des 5 sources collectées par notre système (`data/`)

| # | Source | Fichier JSON par source | Offres TI 2026 retenues | Fiches avec description | Offres avec `competences_cles` | Hors-TI ou pré-2026 rejetées |
| :-: | --- | --- | :-: | :-: | :-: | :-: |
| **1** | **Guichet-Emplois Canada** | [`data/offres_guichet_emplois.json`](data/offres_guichet_emplois.json) | **194** | **194 / 194 (100 %)** | **194 / 194 (100 %)** | 0 (filtre `fn21`) |
| **2** | **Jobboom Québec** | [`data/offres_jobboom.json`](data/offres_jobboom.json) | **91** | **91 / 91 (100 %)** | **91 / 91 (100 %)** | 41 (25 hors-TI + 16 pré-2026) |
| **3** | **Talent.com Canada** | [`data/offres_talent.json`](data/offres_talent.json) | **49** | **49 / 49 (100 %)** | **49 / 49 (100 %)** | 53 |
| **4** | **Jobillico Québec** | [`data/offres_jobillico.json`](data/offres_jobillico.json) | **42** | **42 / 42 (100 %)** | **42 / 42 (100 %)** | 14 |
| **5** | **Remotive** | [`data/offres_remotive.json`](data/offres_remotive.json) | **6** | **6 / 6 (100 %)** | **6 / 6 (100 %)** | 40 |
| **Total** | **Jeu global unifié** | **[`data/offres_unifiees.json`](data/offres_unifiees.json)** | **372** | **372 / 372 (100 %)** | **372 / 372 (100 %)** | **148** |

### Fichiers consolidés, interfaces et statistiques sous `data/`
- **[`data/offres_unifiees.json`](data/offres_unifiees.json)** : **372 offres TI 2026 uniques** (100 % collectées par notre propre script) après déduplication intra-source (18 fusions) et inter-sources (10 fusions sans perte entre plateformes).
- **[`data/offres_unifiees.csv`](data/offres_unifiees.csv)** : Export tabulaire encodé en `utf-8-sig` (avec BOM UTF-8 et séparateur `;`) s'ouvrant directement dans Microsoft Excel sous Windows.
- **[`data/offres_format_commun.json`](data/offres_format_commun.json)** : Les **372 offres TI** converties au **schéma pivot de 17 champs (`JobOffer`)** défini par Grégory et adopté par la classe.
- **[`data/portail_ti_jobtailor.html`](data/portail_ti_jobtailor.html)** : Portail Web interactif autonome (zéro serveur, protection XSS `textContent`) embarquant les 372 offres avec filtres par source, code CNP 2021, sous-domaine TI, région administrative du Québec, technologie, séniorité, comparateur de CV en direct (chargement .txt/.md/.json/.docx ou texte collé) et vérificateur de lettre de motivation.
- **[`data/rapport_collecte.json`](data/rapport_collecte.json)** : Rapport statistique complet (compteurs par source, doublons fusionnés, répartition sur les **14 codes CNP 2021 TI**, les **6 sous-domaines TI**, les **17 régions administratives du Québec**, les **4 niveaux de séniorité** et le **top 30 des technologies**).
- **[`echantillon_v2.json`](echantillon_v2.json)** : Échantillon léger vérifié de **22 offres multi-sources** au schéma complet de 36 champs.

---

## 2. Schéma de données enrichi (`JobBankOffer` — 36 champs)

Chaque offre intègre l'ADN de `JobTailor_V3` et les meilleures briques de la classe (Grégory, Kandet, Hugo, Elvira) :
- **Classification CNP 2021 TI & Domaine :** `code_cnp` (14 codes TI), `cnp_title`, `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`).
- **Intitulés & Missions :** `titre`, `titre_employeur` (`.source-title-inner`), `missions_cles` (`list[str]`), `competences_cles` (`list[str]` — 48 technologies/outils TI + repli par code CNP `JobTailor_V3`), `description`.
- **Études, Expérience & Séniorité :** `niveau_etudes`, `experience_requise`, `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`), `est_stage`, `statut_stage`, `score_pertinence_dec` (`0-100`).
- **Salaire structuré :** `salaire` (texte brut), `salaire_min` (`float`), `salaire_max` (`float`), `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`).
- **Géographie (17 régions QC & GPS) :** `lieu`, `ville`, `region_administrative` (17 régions du Québec), `code_postal`, `province`, `pays`, `latitude`, `longitude` (49 offres géolocalisées).
- **Traçabilité, Fraîcheur 2026 & Intégrité HTTP :** `id`, `source_id`, `source`, `source_partenaire`, `url` (nettoyée sans `;jsessionid` ni `utm_*`), `url_partenaire` (`a#externalJobLink`), `http_status` (`200`), `content_hash` (`SHA-256` 16 hex), `date_publication` (filtrée >= 2026 via `is_recent_and_valid_offer`), `date_fin`, `date_extraction`.

---

## 3. Commandes d'utilisation et de test (Collecte, Filtrage, Portail Web, CV & Lettre)

```powershell
# Installation des dépendances
pip install -r requirements.txt

# 1. Collecte autonome complète sur les 5 sources (lit toutes les pages et toutes les fiches individuelles)
python poc_guichet_cnp_v2.py --collecte-complete

# 2. Consolider hors ligne + générer le Portail Web HTML + exporter au Format Commun de la classe
python poc_guichet_cnp_v2.py --consolider-data --html --format-commun

# 3. Filtrage multicritère instantané hors ligne (ville, région, domaine, CNP, techno, séniorité, stages, salaire)
python poc_guichet_cnp_v2.py --filtrer --region Capitale-Nationale --techno Python
python poc_guichet_cnp_v2.py --filtrer --stages
python poc_guichet_cnp_v2.py --filtrer --domaine cybersecurite --salaire-min 30 --unite-salaire heure

# 4. Piste 4 (JobTailor) — Comparer un CV (.txt, .md, .docx, .json) aux 372 offres TI par Score ATS (/100)
python poc_guichet_cnp_v2.py --cv cv_etudiant_dec_exemple.txt --top 5

# 5. Piste 4 (JobTailor) — Auditer une lettre de motivation selon la méthode Vous / Moi / Nous
python poc_guichet_cnp_v2.py --cv cv_etudiant_dec_exemple.txt --lettre lettre_motivation_exemple.txt --top 3
python poc_guichet_cnp_v2.py --lettre lettre_motivation_exemple.txt --id-offre ge-50711091

# 6. Exécuter les 21 tests unitaires 100 % hors ligne
python -m unittest discover -s . -p "test_*.py" -v
```
