# Jobs Insights — Espace Hugo

Projet collaboratif visant à développer un **agrégateur intelligent d'offres d'emploi et de stages en informatique** (Québec et Canada), complété par un module d'assistance à la **personnalisation et bonification de CV** selon les compétences demandées.

> 🧭 **Tableau de bord de travail** : Consultez [**`PlanReadMe.MD`**](PlanReadMe.MD) pour voir la localisation actuelle, l'état des modules et la feuille de route.
> 📌 **Cadre académique** : Cours `420-SV2-OQ` — DEC en Techniques de l'informatique au Collège O'Sullivan de Québec.

---

## 📁 Organisation du dossier `equipe/hugo/`

La structure du dossier est organisée de manière chronologique et modulaire, allant des premiers inventaires jusqu'à l'orchestrateur final multi-sources :

```text
equipe/hugo/
├── 01-inventaire-des-sites/     # [Livrable 1] Recensement et analyse des plateformes d'emploi
├── 02-preuve-de-concept-scraping/ # [Livrable 2] Premier POC de scraping sur Guichet-Emplois
├── 03-Scrapping Guichet-Emploi/ # Moteur complet en cascade (Atom XML + HTML paginé + RDFa/DOM)
├── 04-Scrapping Jobillico/      # Module autonome Jobillico Québec (HTML + JSON-LD)
├── 05-Scrapping Jobboom/        # Module autonome Jobboom Québec (HTML + JSON-LD Schema.org)
├── 06-Scrapping Remotive/       # Module autonome Remotive (API REST Télétravail & TI Canada)
├── 07-Scrapping Talent/         # Module autonome Talent.com Canada (JSON-LD @graph)
└── ProjetFinal_V.0.0.0/         # [Livrable 3 - Aboutissement] Pipeline unifié TOP 3 multi-sources
```

---

## 🏛️ Les Modules de Scraping Développés

| Dossier | Source ciblée | Approche technique | Données générées | Tests unitaires |
| :--- | :--- | :--- | :--- | :---: |
| **[`03-Scrapping Guichet-Emploi`](03-Scrapping%20Guichet-Emploi/)** | Guichet-Emplois Canada | Cascade 3 niveaux (Atom XML + HTML paginé + RDFa/DOM), filtrage 22 métiers DEC TI | `data/offres_emploi_canada.json` | 11 tests hors ligne |
| **[`04-Scrapping Jobillico`](04-Scrapping%20Jobillico/)** | Jobillico Québec | Recherche par ville + extraction JSON-LD `JobPosting` | `data/offres_jobillico.json` | 3 tests hors ligne |
| **[`05-Scrapping Jobboom`](05-Scrapping%20Jobboom/)** | Jobboom Québec | Catégorie informatique + extraction sémantique `<script type="application/ld+json">` | `data/offres_jobboom.json` | 3 tests hors ligne |
| **[`06-Scrapping Remotive`](06-Scrapping%20Remotive/)** | Remotive | API REST officielle sans risque de blocage anti-bot + filtre éligibilité Canada | `data/offres_remotive.json` | 2 tests hors ligne |
| **[`07-Scrapping Talent`](07-Scrapping%20Talent/)** | Talent.com Canada | Extraction JSON-LD `@graph` (`ItemList` / `JobPosting`) en une seule requête | `data/offres_talent.json` | 2 tests hors ligne |

---

## 🏆 Projet Final : `ProjetFinal_V.0.0.0`

Le dossier [`ProjetFinal_V.0.0.0`](ProjetFinal_V.0.0.0/) regroupe le **TOP 3 officiel** des sources dans un orchestrateur unifié :
1. **Guichet-Emplois Canada** (données officielles du gouvernement fédéral).
2. **Jobboom Québec** (offres régionales au Québec).
3. **Remotive** (offres TI et développement logiciel en télétravail).

### Fonctionnalités phares :
* **Déduplication sémantique :** Élimine les doublons inter-plateformes grâce à une signature normalisée (`titre_entreprise`).
* **Double export instantané :**
  * `data/offres_top3.json` : Format structuré complet avec compétences techniques et métadonnées.
  * `data/offres_top3.csv` : Format tabulaire compatible Microsoft Excel (séparateur `;`, encodage `utf-8-sig`).
  * `data/rapport_collecte.json` : Statistiques de répartition des sources, modalités et top compétences.

### Lancement rapide du projet final :
```powershell
# Mode ligne de commande
python ProjetFinal_V.0.0.0\collecte_top3.py --keyword "programmeur" --per-source 20

# Ou double-clic sous Windows sur ProjetFinal_V.0.0.0\collecte_top3.py (menu interactif)
```

---

## 🧪 Validation globale par tests unitaires hors ligne

Chaque module dispose de sa propre suite de tests basée sur des fixtures et des mocks (aucun appel réseau pendant les tests) :
```powershell
python -m unittest discover -s "03-Scrapping Guichet-Emploi" -p "test_*.py" -v
python -m unittest discover -s "04-Scrapping Jobillico" -p "test_*.py" -v
python -m unittest discover -s "05-Scrapping Jobboom" -p "test_*.py" -v
python -m unittest discover -s "06-Scrapping Remotive" -p "test_*.py" -v
python -m unittest discover -s "07-Scrapping Talent" -p "test_*.py" -v
python -m unittest discover -s "ProjetFinal_V.0.0.0" -p "test_*.py" -v
```
*(Total : 24 tests unitaires hors ligne validés avec succès).*
