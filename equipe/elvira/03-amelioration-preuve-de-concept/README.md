# Documentation du Projet Global Multi-Sources — Elvira (`jobs-insights`)

Ce dossier contient l’implémentation complète et modulaire du projet d’agrégation d’offres d’emploi et de stages TI au Québec et au Canada (**exclusivement des offres récentes de 2026 toujours valides**).

> Pour lire l’historique de progression et d’amélioration du projet **de L1 à L2, puis de L2 à L3**, consultez **[`note.md`](note.md)**.

---

## 📂 1. Fichiers et architecture du projet

| Fichier | Type | Description |
| :--- | :--- | :--- |
| **[`models.py`](models.py)** | Module Python | Classe `@dataclass JobOffer` (modèle commun aux 4 sites), filtre de validité 2026 `is_recent_and_valid_offer()`, filtre métier TI `is_it_job()`, détection de stages/modalités/compétences et empreinte `dedup_key()` |
| **[`collecteurs.py`](collecteurs.py)** | Module Python | Classe `RobotGuard` (`robots.txt`) et les 4 collecteurs : `JobboomCollector`, `GuichetEmploisCollector`, `JobillicoCollector`, `RemotiveCollector` |
| **[`pipeline.py`](pipeline.py)** | Module Python | Classe `MultiSourcePipeline` : consolidation, déduplication inter-sites sans perte (`merge_two_offers`), filtrage multicritère et exports JSON / CSV Excel |
| **[`main.py`](main.py)** | Script CLI | Point d’entrée principal (options `--source`, `--ville`, `--modalite`, `--competence`, `--stage`, `--recherche`, `--live`) et générateur de `visualiseur.html` |
| **[`scraper_jobboom_v2.py`](scraper_jobboom_v2.py)** | Script CLI | Collecteur autonome ciblé sur Jobboom (Catégorie TI `_i10lfr` + Mots-clés) |
| **[`test_scraper_jobboom_v2.py`](test_scraper_jobboom_v2.py)** | Tests `unittest` | **11 tests unitaires 100 % hors ligne** appuyés sur [`fixtures/jobboom_fixture.json`](fixtures/jobboom_fixture.json) |
| **[`offres_multi_sources.json`](offres_multi_sources.json)** | Données JSON | **118 offres TI de 2026 valides et dédupliquées** (Guichet-Emplois : 79, Jobboom : 26, Remotive : 11, Jobillico : 2) |
| **[`offres_multi_sources.csv`](offres_multi_sources.csv)** | Données CSV | Export encodé en `utf-8-sig` (séparateur `;`) directement ouvrable dans Microsoft Excel |
| **[`visualiseur.html`](visualiseur.html)** | Interface Web | Tableau de bord interactif ouvrable d’un double-clic dans le navigateur (filtres par source, ville, modalité, compétence, stage et inspecteur JSON) |
| **[`note.md`](note.md)** | Note L1 → L2 → L3 | Bilan détaillé de l’évolution du projet du Livrable 1 au Livrable 2, puis du Livrable 2 au Livrable 3 |

---

## ⚙️ 2. Explication détaillée des classes et fonctions

### A. `models.py` — Contrat de données et règles métier
- **`JobOffer`** : classe `@dataclass` qui unifie les champs de toutes les plateformes (`id`, `source`, `partenaire_origine`, `origines_decouverte`, `urls_sources`, `titre`, `entreprise`, `ville`, `province`, `pays`, `code_postal`, `coordonnees_gps`, `salaire`, `type_contrat`, `modalite`, `est_stage`, `competences_cles`, `date_publication`, `date_expiration`, `url`, `description_texte`).
- **`is_recent_and_valid_offer(date_publication, date_expiration)`** : garantit qu’aucune offre publiée avant **2026** ni aucune offre expirée n’entre dans le jeu de données.
- **`is_it_job(title, url)`** : filtre positivement les métiers TI et rejette les postes hors informatique (comptabilité, ventes, CVC/bâtiment, journalier).
- **`clean_html_text(raw_html)`** : nettoie le HTML (même doublement échappé) pour ne conserver qu’une seule description en texte propre (`description_texte`).
- **`extract_skills(title, description_text)`** : détecte 43 technologies TI via des expressions régulières strictes sans faux positifs français.
- **`dedup_key(offer)`** : calcule l’empreinte normalisée `(titre, entreprise, ville)` permettant de repérer une même annonce présente sur deux sites différents.

### B. `collecteurs.py` — Collecte éthique sur les 4 plateformes
- **`RobotGuard`** : vérifie automatiquement `robots.txt` via `urllib.robotparser` avant toute requête HTTP et applique un `User-Agent` académique transparent (`jobs-insights-osullivan/1.0`).
- **`JobboomCollector`** : combine la catégorie *Technologies et médias numériques* (`_i10lfr`) et la recherche par mots-clés, puis extrait le bloc JSON-LD `JobPosting` et les coordonnées GPS.
- **`GuichetEmploisCollector`** : interroge les 14 codes CNP TI au Québec (`fprov=QC`), identifie le site partenaire (`Jobillico`, `Québec emploi`, etc.), respecte le `Crawl-delay: 5s` et enrichit les fiches via RDFa (`property="description"`) ou repli DOM.
- **`JobillicoCollector`** : extrait les fiches d’offres TI au Québec à partir de leur balise JSON-LD `JobPosting`.
- **`RemotiveCollector`** : interroge l’API REST JSON `/api/remote-jobs`, filtre les offres TI accessibles depuis le Canada et détecte nativement les stages (`job_type == "internship"`).

### C. `pipeline.py` — Fusion inter-sources et exports
- **`MultiSourcePipeline.deduplicate_and_merge(offers)`** : regroupe les doublons par `id` et par empreinte `(titre, entreprise, ville)`. Lorsqu’une offre existe à la fois sur Guichet-Emplois et sur Jobboom/Jobillico, `merge_two_offers()` conserve le salaire de l’une, le GPS/code postal de l’autre, la description la plus longue et cumule les compétences et les URLs (`urls_sources`).
- **`MultiSourcePipeline.export_json()` & `export_csv()`** : produisent les fichiers finaux prêts pour l’analyse ou Microsoft Excel.

---

## 🚀 3. Commandes d’exécution

```powershell
# 1. Installer les dépendances
pip install -r equipe/elvira/03-amelioration-preuve-de-concept/requirements.txt

# 2. Exécuter les 11 tests unitaires hors ligne
python -m unittest discover -s equipe/elvira/03-amelioration-preuve-de-concept -p "test_*.py" -v

# 3. Exécuter le pipeline complet (JSON + CSV + visualiseur.html)
python equipe/elvira/03-amelioration-preuve-de-concept/main.py

# 4. Ouvrir le visualiseur Web dans le navigateur
Start-Process .\equipe\elvira\03-amelioration-preuve-de-concept\visualiseur.html
```
