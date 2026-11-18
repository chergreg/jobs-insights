# Collecteur Remotive API (Espace Hugo)

Module autonome de collecte pour l'API REST de **Remotive**, inspiré des travaux de Kandet.

## 🎯 Caractéristiques
* **API REST officielle :** Aucune fragilité liée aux modifications de code HTML, extraction ultra-rapide et fiable.
* **Zéro blocage :** Accès gratuit et ouvert sans besoin de contournement ni de clé privée.
* **Filtrage Canada :** Sélection automatique des offres ouvertes aux candidats basés au Canada / Québec.
* **Format compatible :** Produit des instances conformes au modèle `JobOffer` du projet principal (`data/offres_remotive.json`).

## 🚀 Utilisation

### Mode interactif (Windows)
```powershell
python main.py
```

### Mode ligne de commande (CLI)
```powershell
python main.py --category software-dev --limit 25 --output data/offres_remotive.json
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_scraper.py -v
```
