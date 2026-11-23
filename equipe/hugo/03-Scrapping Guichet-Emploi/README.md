# 03 - Scrapping Guichet-Emplois Canada (Espace Hugo)

Module autonome de collecte pour la plateforme officielle fédérale **Guichet-Emplois Canada** (Job Bank), calibré spécifiquement pour les métiers du **DEC en Techniques de l'informatique**.

## 🎯 Caractéristiques & Stratégie en cascade
1. **Étape 1 — Flux Atom XML officiel :** Récupération rapide et structurée des dernières annonces TI en français.
2. **Étape 2 — Recherche HTML paginée :** Interrogation multi-mots-clés couvrant 22 métiers TI (Développement logiciel, Web, Infrastructure, QA, DevOps, Réseaux, Cybersécurité) avec pagination jusqu'à 100 offres.
3. **Étape 3 — Enrichissement profond :** Extraction sémantique prioritaire via RDFa / Schema.org (`property="description"`) avec repli vers le conteneur DOM.
4. **Filtrage CNP 2021 & Compétences :** Validation stricte des codes CNP informatiques et extraction des langages/frameworks sans faux positifs.

## 🚀 Utilisation

### Mode interactif Windows
Double-cliquez sur `main.py` ou lancez :
```powershell
python main.py
```

### Mode ligne de commande (CLI)
```powershell
python main.py --limit 50 --fast --output data/offres_emploi_canada.json
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_scraper.py -v
```
*(11 tests unitaires validant l'Atom XML, le HTML, le RDFa, les codes CNP et les compétences sans appel réseau).*
