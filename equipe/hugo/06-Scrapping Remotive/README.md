# 06 - Scrapping Remotive API (Espace Hugo)

Module autonome de collecte pour l'API REST officielle de **Remotive**, inspiré des travaux de Kandet et aligné sur les exigences du cours (Livrable 3).

## 🎯 Caractéristiques
* **API REST officielle :** Aucune fragilité liée aux modifications de code HTML, extraction rapide et fiable.
* **Garantie 100% TI :** Filtrage strict éliminant les offres hors-sujet retournées par Remotive (rédaction, marketing, service client, etc.).
* **Recherche bilingue FR/EN :** Correspondance intelligente des termes français (`programmeur`, `données`, `stage`, etc.) vers les équivalents anglais (`developer`, `data`, `intern`, etc.).
* **Filtrage Canada :** Sélection automatique des offres de télétravail ouvertes aux candidats basés au Canada / Québec.
* **Format compatible :** Produit des instances conformes au modèle Pydantic `JobOffer` du projet (`data/offres_remotive.json`).

## 🚀 Utilisation

> **Note Windows PowerShell :** En raison de l'espace dans le nom du dossier, veillez à toujours entourer le chemin de guillemets ou à vous positionner directement dans le répertoire.

### Option A : Depuis le dossier `06-Scrapping Remotive`
```powershell
cd "06-Scrapping Remotive"
python main.py
```

### Option B : Depuis la racine de l'espace Hugo
```powershell
python "06-Scrapping Remotive\main.py"
```

### Mode ligne de commande (CLI)
```powershell
# Recherche de 10 offres en développement logiciel
python "06-Scrapping Remotive\main.py" --category software-development --limit 10

# Recherche par mot-clé bilingue
python "06-Scrapping Remotive\main.py" --keyword python --limit 5

# Toutes les offres sans filtre géographique
python "06-Scrapping Remotive\main.py" --all-locations --limit 15
```

## 🧪 Tests unitaires hors ligne (100% autonomes)
```powershell
python -m unittest discover -s "06-Scrapping Remotive" -p "test_*.py" -v
```
