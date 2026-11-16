# Jobs Insights — Espace Hugo

Projet collaboratif visant à développer un **agrégateur intelligent d'offres d'emploi et de stages en informatique** (Québec et Canada), complété par un module d'assistance à la **personnalisation et bonification de CV** selon les compétences demandées.

> 📌 **Cadre académique** : Cours `420-SV2-OQ` — DEC en Techniques de l'informatique au Collège O'Sullivan de Québec.

---

## 🎯 1. Objectifs du projet

1. **Agrégation et filtrage ciblé** :
   * **Domaine** : Technologies de l'information (TI) / Génie logiciel.
   * **Niveau** : Stages (*internships*) et postes juniors / début de carrière.
   * **Périmètre géographique** : Québec (prioritaire) et ensemble du Canada.
   * **Filtres multicritères** : Télétravail / Hybride / Sur place, compétences techniques requises, salaire et employeur.

2. **Aide à la bonification de CV (Étape 4)** :
   * Extraction précise des mots-clés et technologies demandées (langages, frameworks, outils, cloud, bases de données).
   * Analyse de l'écart (*gap analysis*) entre le CV de l'étudiant et les exigences réelles du poste pour maximiser le matching.

3. **Preuve de concept robuste & pérenne (POC)** :
   * Source principale : **Guichet-Emplois Canada** (données officielles du gouvernement fédéral).
   * Architecture à haute résilience basée sur une **stratégie de collecte en cascade**.

---

## 🏛️ 2. Architecture logicielle & Stratégie en Cascade

Pour garantir un code professionnel, testable hors ligne et résilient aux changements de mise en page, la solution est découpée en modules spécialisés :

```
┌─────────────────────────────────────────────────────────────┐
│                 GUICHET-EMPLOIS CANADA                      │
└─────────────────────────────────────────────────────────────┘
                               │
       ┌───────────────────────┴───────────────────────┐
       ▼                                               ▼
[ Stratégie 1 : Flux Atom XML ]            [ Stratégie 2 : Recherche HTML ]
  - Officiel, ultra-rapide (1 req)           - Mots-clés ciblés TI (16 métiers)
  - Codes CNP TI (21230, etc.)               - Complément de quota & pagination
       │                                               │
       └───────────────────────┬───────────────────────┘
                               ▼
               [ Normalisation & Déduplication ]
                 - Identifiant unique `gc-...`
                               ▼
             [ Stratégie 3 : Enrichissement Fiches ]
                 - 1. Balises Schema.org / RDFa
                 - 2. Repli conteneurs DOM HTML
                 - Extraction description & compétences strictes
                               ▼
                  [ Modèle Typé : JobOffer ]
                               ▼
               [ Export JSON Standardisé & Logs ]
```

### Organisation des modules
* **[`models.py`](02-preuve-de-concept-scraping/models.py)** : Modèle de données Pydantic `JobOffer` (typage strict, validation, horodatage ISO).
* **[`parsers.py`](02-preuve-de-concept-scraping/parsers.py)** : Logique pure d'extraction (Flux Atom, HTML, RDFa, DOM, compétences strictes) **découplée de tout appel réseau**.
* **[`collecte.py`](02-preuve-de-concept-scraping/collecte.py)** : Moteur HTTP avec `User-Agent` transparent, respect du `crawl-delay` (5s conforme robots.txt), et cascade de repli.
* **[`main.py`](02-preuve-de-concept-scraping/main.py)** : Point d'entrée à double mode (CLI pour automatisation / Menu interactif pour double-clic sous Windows).
* **[`test_scraper.py`](02-preuve-de-concept-scraping/test_scraper.py)** : Suite de **tests unitaires hors ligne** validant les parseurs sur fixtures locales.
* **[`COMPTE_RENDU_LIVRABLE_2.md`](02-preuve-de-concept-scraping/COMPTE_RENDU_LIVRABLE_2.md)** : Rapport formel d'analyse critique requis pour le Livrable 2.

---

## 🚀 3. Guide d'exécution

### 1. Prérequis & Installation des dépendances
Le script ne modifie pas votre environnement silencieusement (pas d'auto-installation pip cachée). Installez simplement les paquets déclarés :

```powershell
cd 02-preuve-de-concept-scraping
pip install -r requirements.txt
```

### 2. Exécution des tests unitaires hors ligne
Valide instantanément la logique d'extraction et l'élimination des faux positifs sans connexion Internet :

```powershell
python -m unittest test_scraper.py -v
```

### 3. Mode Ligne de commande (Automatisable & Scriptable)
Idéal pour les scripts automatisés ou l'intégration par l'équipe sans blocage :

```powershell
# Collecte standard conforme (100 offres par défaut, délai 5s)
python main.py --limit 100 --province QC

# Collecte rapide de développement (délai accéléré à 1.2s)
python main.py --limit 20 --fast

# Recherche sur un mot-clé précis
python main.py --keyword "stage informatique" --limit 50
```

### 4. Mode Interactif (Lancement par double-clic sous Windows)
Faites simplement un double-clic sur **`main.py`** dans l'Explorateur Windows :
1. Choisissez la vitesse : Mode Conforme (5s) ou Rapide (1.2s).
2. Choisissez le volume souhaité (valeur par défaut : **100**).
3. Choisissez le mode : Bouquet de 16 métiers TI ou mot-clé spécifique.
4. Visualisez la **barre de progression en temps réel**.
5. Consultez le rapport final et appuyez sur Entrée pour fermer la fenêtre.

---

## 🛡️ 4. Conformité, Éthique & Bonnes Pratiques

* **User-Agent transparent** : Identifie clairement la provenance académique du projet (`jobs-insights-atelier/1.0`).
* **Respect du `crawl-delay`** : Respecte les 5 secondes imposées par le `robots.txt` officiel de Guichet-Emplois.
* **Résolution des faux positifs** : Les termes comme `"Vue.js"` ou `"Langage C"` sont vérifiés avec des expressions régulières contextuelles pour ne pas confondre le français courant (*"en vue de"*, *"c'est"*) avec des technologies.
* **Champ description garanti** : La description complète de l'offre est systématiquement extraite via balises sémantiques ou repli DOM.

---

## 📋 5. Feuille de route (Roadmap)

- [x] **Étape 1 : Veille & exploration des sources** (`01-inventaire-des-sites/sites.md`).
- [x] **Étape 2 : Cadrage & Contrat de données** (`models.py`, `JobOffer`).
- [x] **Étape 3 : Collecteur Guichet-Emplois multi-stratégies** (`collecte.py`, `parsers.py`).
- [x] **Étape 3b : Tests unitaires hors ligne et conformité éthique** (`test_scraper.py`, robots.txt, délais).
- [ ] **Étape 4 : Bonification de CV & Matching** (Analyse des compétences requises vs CV).
- [ ] **Étape 5 : Intégration globale** (Convergence avec les sources des coéquipiers : Adzuna, Jobboom, Remotive).
