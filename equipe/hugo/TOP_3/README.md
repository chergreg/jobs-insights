# Pipeline de Collecte Conjointe — TOP 3 des Sites TI (Livrable 3)

Ce dossier contient l'orchestrateur central de collecte pour le **Livrable 3** du projet `jobs-insights` (Espace Hugo).

## 🏆 Le TOP 3 des sources retenues
1. **Guichet-Emplois Canada :** Source fédérale officielle, ciblée sur les métiers du DEC en informatique (22 métiers TI).
2. **Jobboom Québec :** Portail provincial québécois, extrait par balisage sémantique Schema.org (`<script type="application/ld+json">`).
3. **Remotive :** Plateforme de télétravail TI internationale filtrée pour le Canada, interrogée via son API REST officielle.

## 📁 Organisation du dossier `TOP_3/`
```text
TOP_3/
├── models.py            # Modèle unifié JobOffer et signature de déduplication
├── scrapers/            # Collecteurs spécialisés
│   ├── guichet.py       # Scraper Guichet-Emplois (Atom + HTML)
│   ├── jobboom.py       # Scraper Jobboom (JSON-LD)
│   └── remotive.py      # Scraper Remotive (API REST)
├── collecte_top3.py     # Script maître de collecte, déduplication et export
├── test_top3.py         # Tests unitaires hors ligne
└── data/                # Dossier de destination des données collectées
    ├── offres_top3.json # Base de données unifiée au format JSON
    ├── offres_top3.csv  # Fichier tabulaire Excel (séparateur point-virgule)
    └── rapport_collecte.json # Statistiques de répartition et compétences
```

## 🚀 Utilisation

### Mode interactif Windows
Double-cliquez sur `collecte_top3.py` ou exécutez dans le terminal :
```powershell
python collecte_top3.py
```
Le menu vous demandera le mot-clé TI (ex: `informatique`) et le nombre d'offres souhaité par site.

### Mode ligne de commande (CLI)
```powershell
python collecte_top3.py --keyword "developpeur" --per-source 20
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_top3.py -v
```
