# Collecteur Talent.com Canada (Espace Hugo)

Module autonome de collecte pour l'agrégateur **Talent.com Canada**, inspiré des travaux de veille d'El Hadji Konaté.

## 🎯 Caractéristiques
* **Extraction JSON-LD @graph :** Récupération directe des listes `JobPosting` injectées dans la page de recherche.
* **Haute efficacité :** Permet de collecter plusieurs offres structurées en un nombre minimal de requêtes.
* **Format compatible :** Produit des instances conformes au modèle `JobOffer` du projet principal (`data/offres_talent.json`).

## 🚀 Utilisation

### Mode interactif (Windows)
```powershell
python main.py
```

### Mode ligne de commande (CLI)
```powershell
python main.py --keyword "informatique" --location "Quebec" --limit 15 --output data/offres_talent.json
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_scraper.py -v
```
