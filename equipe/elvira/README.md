# Jobs Insights — Espace Elvira (Projet Global Multi-Sources TI)

**Auteure :** Elvira  
**Cours :** `420-SV2-OQ` — Développement de services d’échanges de données (Collège O’Sullivan de Québec)

Ce dépôt regroupe l’ensemble de mon projet pour **`job-insights`** : une plateforme de collecte, de normalisation, de déduplication multi-sources et de visualisation Web d’offres d’emploi et de stages en informatique au Québec et au Canada (**exclusivement des offres récentes de 2026 toujours valides**).

---

## 📂 1. Organisation générale du dossier `equipe/elvira/`

| Dossier / Fichier | Rôle dans le projet |
| :--- | :--- |
| **[`01-inventaire-des-sites/sites.md`](01-inventaire-des-sites/sites.md)** | **Livrable 1 :** Recensement et étude technique de 8 plateformes d’emploi québécoises et canadiennes |
| **[`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/README.md)** | **Livrable 2 :** Premier collecteur Python sur Jobboom (`Scraper.py`, 12 offres TI de 2026 valides) |
| **[`03-amelioration-preuve-de-concept/`](03-amelioration-preuve-de-concept/README.md)** | **Livrable 3 (Projet global Multi-Sources) :** Architecture modulaire unifiant **4 sources** (**228 offres TI de 2026**), tests unitaires hors ligne, export CSV Excel et visualiseur Web |
| **[`03-amelioration-preuve-de-concept/note.md`](03-amelioration-preuve-de-concept/note.md)** | **Note d’évolution :** Trace la progression complète du projet **de L1 à L2, puis de L2 à L3** |

---

## 🏛️ 2. Architecture du projet global (`03-amelioration-preuve-de-concept/`)

Le projet global interroge et unifie **4 sources complémentaires** :
1. **Guichet-Emplois Canada** (socle public fédéral par codes CNP TI au Québec + fiches RDFa/DOM).
2. **Jobboom Québec** (portail privé québécois par catégorie TI `_i10lfr` + mots-clés + JSON-LD `JobPosting` + GPS).
3. **Jobillico Québec** (offres TI des PME et entreprises du Québec via JSON-LD `JobPosting`).
4. **Remotive** (API REST JSON publique pour les postes et stages TI 100 % télétravail ouverts au Canada).

### Rôle de chaque module et classe Python

| Module | Classes / Fonctions clés | Ce qu’il fait |
| :--- | :--- | :--- |
| **[`models.py`](03-amelioration-preuve-de-concept/models.py)** | `JobOffer` (`@dataclass`), `is_recent_and_valid_offer()`, `is_it_job()`, `extract_skills()`, `dedup_key()` | Définit le modèle de données commun aux 4 sources, filtre strictement les offres TI de **2026 non expirées**, nettoie le HTML en une seule `description_texte` et extrait les compétences sans faux positifs |
| **[`collecteurs.py`](03-amelioration-preuve-de-concept/collecteurs.py)** | `RobotGuard`, `JobboomCollector`, `GuichetEmploisCollector`, `JobillicoCollector`, `RemotiveCollector` | Gère la conformité `robots.txt` et implémente la logique d’extraction propre à chacune des 4 plateformes |
| **[`pipeline.py`](03-amelioration-preuve-de-concept/pipeline.py)** | `MultiSourcePipeline` (`deduplicate_and_merge`, `filter_offers`, `export_json`, `export_csv`) | Fusionne les doublons entre sites sans perte d’information (salaire + GPS + compétences + URLs cumulées), filtre les offres et génère les exports JSON et CSV Excel |
| **[`main.py`](03-amelioration-preuve-de-concept/main.py)** | `main()`, `generate_html_viewer()`, `build_arg_parser()` | Point d’entrée en ligne de commande (CLI) qui orchestre le pipeline et régénère automatiquement l’application Web [`visualiseur.html`](03-amelioration-preuve-de-concept/visualiseur.html) |
| **[`test_scraper_jobboom_v2.py`](03-amelioration-preuve-de-concept/test_scraper_jobboom_v2.py)** | `TestScraperMultiSourcesV2` (`unittest.TestCase`) | Suite de **11 tests unitaires 100 % hors ligne** validant les 4 collecteurs, le rejet des offres `< 2026` et la déduplication inter-sources |

---

## 🚀 3. Guide d’utilisation rapide

### Installation des dépendances
```powershell
pip install -r equipe/elvira/03-amelioration-preuve-de-concept/requirements.txt
```

### Exécution du pipeline Multi-Sources et des filtres CLI
```powershell
# Générer et mettre à jour en mode cumulatif les 228 offres TI 2026 unifiées (JSON + CSV Excel + visualiseur.html)
python equipe/elvira/03-amelioration-preuve-de-concept/main.py

# Filtrer par source, ville, compétence ou stage
python equipe/elvira/03-amelioration-preuve-de-concept/main.py --source Jobboom
python equipe/elvira/03-amelioration-preuve-de-concept/main.py --ville Québec --competence Python
python equipe/elvira/03-amelioration-preuve-de-concept/main.py --stage
```

### Ouverture du Visualiseur Web interactif
```powershell
Start-Process .\equipe\elvira\03-amelioration-preuve-de-concept\visualiseur.html
```

### Exécution des 11 tests unitaires hors ligne
```powershell
python -m unittest discover -s equipe/elvira/03-amelioration-preuve-de-concept -p "test_*.py" -v
```
