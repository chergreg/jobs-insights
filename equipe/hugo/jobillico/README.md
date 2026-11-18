# Collecteur Jobillico Québec (Espace Hugo)

Module autonome de collecte pour la plateforme québécoise **Jobillico**, inspiré des travaux de veille d'El Hadji Konaté.

## 🎯 Caractéristiques
* **Extraction sémantique standardisée :** Lecture du bloc JSON-LD `<script type="application/ld+json">` (`JobPosting`).
* **Focalisation régionale :** Couverture des PME et grandes entreprises de la Capitale-Nationale et du Québec.
* **Format compatible :** Produit des instances conformes au modèle `JobOffer` du projet principal (`data/offres_jobillico.json`).

## 🚀 Utilisation

### Mode interactif (Windows)
```powershell
python main.py
```

### Mode ligne de commande (CLI)
```powershell
python main.py --keyword "programmeur" --location "Quebec" --limit 15 --output data/offres_jobillico.json
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_scraper.py -v
```
