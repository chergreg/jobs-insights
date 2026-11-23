# Guide d'exécution — Livrable 3 : Enrichissement du POC Adzuna Canada

**Auteur :** Rayan Dimitri Motchebe Ngoubo  
**Projet :** `jobs-insights` — Cours `420-SV2-OQ` (Collège O'Sullivan de Québec)

Ce dossier contient l'amélioration de notre preuve de concept sur l'API **Adzuna Canada**. Le pipeline enrichit les annonces à partir de leurs extraits de description (salaires, devises, périodes salariales, types et durées de contrat, horaires et modalités), normalise la géographie québécoise (`location.area` + régions administratives), déduplique les résultats multi-recherches et conserve la provenance exacte de chaque valeur.

> 📄 Consultez [`note.md`](note.md) pour la note complète du Livrable 3 (problème initial, travaux de l'équipe réutilisés, règles d'extraction, résultats avant/après et limites).

---

## 1. Architecture des fichiers

| Fichier | Rôle |
| --- | --- |
| [`models.py`](models.py) | Modèle `@dataclass OffreAdzuna` à 3 niveaux (valeurs API brutes, valeurs extraites du texte, valeurs consolidées avec provenance) et conversion vers le format commun |
| [`extraction_texte.py`](extraction_texte.py) | Extraction déterministe par expressions régulières ancrées (salaires, contrats, durées, horaires, modalités) et règles d'arbitrage |
| [`normalisation.py`](normalisation.py) | Décodage de `location.area` + régions du Québec (`regions_quebec.csv`), filtre de pertinence TI, compétences techniques et stages |
| [`collecteur.py`](collecteur.py) | Client API Adzuna résilient (retry progressif HTTP 429/5xx, masquage de `app_id`/`app_key`) et lecteur hors ligne des JSON du Livrable 2 |
| [`pipeline.py`](pipeline.py) | Déduplication (321 annonces $\rightarrow$ 229 offres uniques), bilan statistique Avant/Après et exports JSON / CSV Excel / Format commun |
| [`main.py`](main.py) | Point d'entrée en ligne de commande (mode hors ligne par défaut ou mode `--live`) |
| [`test_adzuna_v3.py`](test_adzuna_v3.py) | Suite de 15 tests unitaires 100 % hors ligne (`unittest`) |
| [`requirements.txt`](requirements.txt) | Dépendance externe unique (`requests>=2.31.0`, requise uniquement en mode `--live`) |

---

## 2. Exécution rapide (100 % hors ligne)

Depuis la racine du dépôt `jobs-insights` :

```powershell
# 1. Exécuter les 15 tests unitaires hors ligne (aucun appel réseau)
python -m unittest discover -s equipe/rayan/03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Exécuter le pipeline hors ligne sur les 10 fichiers JSON du Livrable 2
python equipe/rayan/03-amelioration-preuve-de-concept/main.py
```

### Fichiers générés dans `data/`
- [`data/offres_adzuna_v3.json`](data/offres_adzuna_v3.json) : les **229 offres uniques** enrichies avec toutes les colonnes de provenance (`api_*`, `texte_*`, `provenance_*`, `anomalies`) et l'objet `statistiques` complet.
- [`data/offres_adzuna_v3.csv`](data/offres_adzuna_v3.csv) : export tabulaire encodé en `utf-8-sig` avec séparateur `;` pour ouverture directe dans Microsoft Excel sous Windows.
- [`data/offres_format_commun.json`](data/offres_format_commun.json) : les 229 offres converties dans les **18 champs du format commun** de la classe (`JobOffer`).

---

## 3. Exécution en direct via l'API Adzuna (optionnel)

Si vous souhaitez relancer une collecte en direct auprès de l'API Adzuna Canada :

```powershell
pip install -r equipe/rayan/03-amelioration-preuve-de-concept/requirements.txt
$env:ADZUNA_APP_ID = "votre_app_id"
$env:ADZUNA_APP_KEY = "votre_app_key"
python equipe/rayan/03-amelioration-preuve-de-concept/main.py --live --max-pages 2
```
