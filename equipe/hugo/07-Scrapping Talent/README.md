# 07 - Scrapping Talent.com Canada (Espace Hugo)

Module autonome de collecte pour la plateforme **Talent.com Canada**, inspiré des travaux de veille de Mamadou et aligné sur les exigences du cours (Livrable 3).

## 🎯 Caractéristiques
* **Extraction JSON-LD @graph en deux phases :**
  1. Détection des URLs d'offres via l'`ItemList` JSON-LD et liens HTML de la page de recherche.
  2. Extraction des métadonnées riches `JobPosting` (titre, entreprise, localisation GPS/adresse, salaire précis, date et description) sur chaque fiche.
* **Garantie 100% TI :** Filtrage strict éliminant les postes hors informatique (magasinier, commis, caissier, service client, etc.).
* **Formatage précis des salaires :** Prise en charge des taux horaires (ex. `30.59 $ - 52.43 $ CAD / heure`), salaires annuels et détection automatique des stages.
* **Format compatible :** Produit des instances conformes au modèle Pydantic standardisé `JobOffer` (`data/offres_talent.json`).

## 🚀 Utilisation

> **Note Windows PowerShell :** En raison de l'espace dans le nom du dossier, veillez à toujours entourer le chemin de guillemets ou à vous positionner directement dans le répertoire.

### Option A : Depuis le dossier `07-Scrapping Talent`
```powershell
cd "07-Scrapping Talent"
python main.py
```

### Option B : Depuis la racine de l'espace Hugo
```powershell
python "07-Scrapping Talent\main.py"
```

### Mode ligne de commande (CLI)
```powershell
# Recherche de 10 offres en informatique à Québec
python "07-Scrapping Talent\main.py" --keyword "informatique" --location "Quebec" --limit 10

# Recherche avec mot-clé spécifique et délai adapté
python "07-Scrapping Talent\main.py" --keyword "programmeur" --location "Montreal" --limit 5 --delay 1.0
```

## 🧪 Tests unitaires hors ligne (100% autonomes)
```powershell
python -m unittest discover -s "07-Scrapping Talent" -p "test_*.py" -v
```
