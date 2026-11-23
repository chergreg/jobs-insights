# 05 - Scrapping Jobboom Québec (Espace Hugo)

Module autonome de collecte pour la plateforme québécoise **Jobboom**, inspiré des travaux d'Elvira et d'El Hadji Konaté.

## 🎯 Caractéristiques
* **Extraction sémantique standardisée :** Récupération directe des métadonnées `<script type="application/ld+json">` (`@type: JobPosting`).
* **Conformité & robustesse :** Évite la fragilité du scraping HTML visuel ; extrait le titre, l'entreprise, le lieu, la description et les compétences.
* **Format compatible :** Produit des instances conformes au modèle `JobOffer` du projet principal (`data/offres_jobboom.json`).

## 🚀 Utilisation

### Mode interactif Windows
```powershell
python main.py
```

### Mode ligne de commande (CLI)
```powershell
python main.py --keyword "developpeur" --limit 15 --output data/offres_jobboom.json
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_jobboom.py -v
```
