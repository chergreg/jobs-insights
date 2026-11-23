# ProjetFinal_V.0.0.0 — Pipeline Central Multi-Sources (Espace Hugo)

Ce dossier représente l'aboutissement du **Livrable 3** du projet `jobs-insights` : l'orchestrateur central combinant les 3 meilleures sources TI retenues avec déduplication sémantique et double export.

## 🏆 Le TOP 3 des sources intégrées
1. **Guichet-Emplois Canada (`03-Scrapping Guichet-Emploi`) :** Flux Atom XML + cascade HTML paginée ciblant les 22 métiers du DEC en informatique.
2. **Jobboom Québec (`05-Scrapping Jobboom`) :** Extraction sémantique Schema.org (`<script type="application/ld+json">`).
3. **Remotive (`06-Scrapping Remotive`) :** API REST officielle spécialisée en télétravail TI filtrée pour le Canada.

## 📁 Organisation interne
```text
ProjetFinal_V.0.0.0/
├── models.py            # Modèle Pydantic unifié JobOffer et clé de déduplication sémantique
├── scrapers/            # Les 3 connecteurs spécialisés
│   ├── guichet.py       # Scraper Guichet-Emplois
│   ├── jobboom.py       # Scraper Jobboom
│   └── remotive.py      # Scraper Remotive
├── collecte_top3.py     # Script maître d'orchestration, fusion et export
├── test_top3.py         # Tests unitaires hors ligne
└── data/                # Données consolidées
    ├── offres_top3.json # Base de données unifiée complète en JSON
    ├── offres_top3.csv  # Tableur Excel (séparateur point-virgule, UTF-8-sig)
    └── rapport_collecte.json # Statistiques de répartition et compétences
```

## 🚀 Utilisation

### Mode interactif Windows
Double-cliquez directement sur `collecte_top3.py` ou lancez :
```powershell
python collecte_top3.py
```

### Mode ligne de commande (CLI)
```powershell
python collecte_top3.py --keyword "programmeur" --per-source 20
```

## 🧪 Tests unitaires hors ligne
```powershell
python -m unittest test_top3.py -v
```
