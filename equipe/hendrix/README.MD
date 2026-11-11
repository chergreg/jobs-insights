# Job Data Platform

**Plateforme de collecte massive et de recherche d'offres d'emploi**

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green)
![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue)
![Status](https://img.shields.io/badge/Status-In%20Development-orange)

## Présentation

Job Data Platform est un projet de développement visant à concevoir une application web capable de collecter, centraliser et traiter un grand volume d'offres d'emploi et de stages provenant de différentes sources.

L'application permettra de regrouper les offres dans une base de données centralisée afin de faciliter leur recherche et leur consultation.

Le projet met particulièrement l'accent sur l'automatisation de la collecte, le traitement des données, leur normalisation et la détection des doublons.

## Objectifs

- Automatiser la récupération d'offres d'emploi et de stages.
- Collecter des données provenant de plusieurs sources autorisées.
- Traiter des volumes importants de données.
- Normaliser les informations récupérées.
- Détecter et éviter les offres en double.
- Centraliser les données dans PostgreSQL.
- Proposer une interface de recherche avec filtres.
- Visualiser les statistiques de collecte.

## Fonctionnalités

### 1. Collecte de données
- Connexion à plusieurs sources de données.
- Récupération automatisée des offres.
- Traitement des données par lots.
- Historique des collectes.
- Gestion des erreurs.

### 2. Traitement des données
- Nettoyage des informations.
- Normalisation des champs.
- Validation des données.
- Détection des doublons.
- Mise à jour des offres existantes.

### 3. Gestion des offres
- Stockage centralisé.
- Consultation des offres.
- Recherche par mots-clés.
- Filtres par localisation, entreprise et type d'emploi.
- Accès à la publication originale.

### 4. Tableau de bord
- Nombre d'offres collectées.
- Nombre de nouvelles offres.
- Nombre de doublons.
- État des sources.
- Historique des opérations.
- Suivi des erreurs.

### 5. Comparaison CV et offre (fonctionnalité secondaire)
- Importation d'un CV.
- Extraction des compétences.
- Comparaison avec une offre.
- Score indicatif de correspondance.

## Technologies

| Technologie | Utilisation |
|---|---|
| Python | Collecte et traitement des données |
| Polars | Traitement de données volumineuses |
| FastAPI | API backend |
| PostgreSQL | Base de données |
| Next.js | Interface utilisateur |
| TypeScript | Développement frontend |
| Pytest | Tests automatisés |
| Git / GitHub | Gestion du code |

## Architecture du projet

```text
job-data-platform/
│
├── README.md
├── CAHIER_DES_CHARGES_CLASSE.md
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── frontend/
│   └── web/
│
├── backend/
│   └── api/
│
├── collectors/
│   ├── sources/
│   ├── scrapers/
│   └── pipelines/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── docs/
│   └── architecture/
│
└── tests/
```

## Fonctionnement général

Le système suivra un pipeline de traitement :

```text
Sources de données
        |
        v
Collecte des offres
        |
        v
Données brutes
        |
        v
Nettoyage et normalisation
        |
        v
Validation des données
        |
        v
Détection des doublons
        |
        v
Stockage PostgreSQL
        |
        v
API Backend
        |
        v
Interface Web
```

## Installation

### Prérequis

- Python 3.12 ou version compatible.
- Node.js LTS.
- PostgreSQL.
- Git.
- Un gestionnaire de paquets Python et npm.

### 1. Cloner le repository

```bash
git clone <URL_DU_REPOSITORY>
cd job-data-platform
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Compléter les variables nécessaires dans `.env`.

Exemple :

```env
DATABASE_URL=postgresql://user:password@localhost:5432/job_platform
API_HOST=127.0.0.1
API_PORT=8000
```

Ne jamais publier le fichier `.env` dans Git.

### 3. Installer le backend

```bash
cd backend/api
python -m venv .venv
```

Activation sous Windows :

```powershell
.venv\Scripts\activate
```

Activation sous Linux/macOS :

```bash
source .venv/bin/activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Lancer le backend :

```bash
uvicorn main:app --reload
```

L'API sera accessible à :

```text
http://127.0.0.1:8000
```

Documentation interactive :

```text
http://127.0.0.1:8000/docs
```

### 4. Installer le frontend

```bash
cd frontend/web
npm install
```

Lancer le serveur :

```bash
npm run dev
```

L'application sera accessible à :

```text
http://localhost:3000
```

*Ces commandes constituent le parcours d'installation prévu. Elles devront être ajustées selon les fichiers réellement présents dans le repository.*

## API prévue

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/health` | Vérifier l'API |
| GET | `/jobs` | Consulter les offres |
| GET | `/jobs/{id}` | Consulter une offre |
| GET | `/sources` | Consulter les sources |
| GET | `/collections` | Historique des collectes |
| POST | `/collections/{source_id}/run` | Lancer une collecte |
| GET | `/statistics` | Statistiques générales |

## Collecte des données et utilisation des sources

Les données seront récupérées à partir de sources accessibles et autorisant leur utilisation.

Les méthodes possibles comprennent :
- API publiques ou partenaires.
- Flux RSS.
- Pages carrières autorisant l'accès automatisé.
- Autres sources compatibles avec les conditions d'utilisation.

Le système devra respecter les limites de fréquence, les conditions d'accès et les protections techniques des plateformes. Aucun mécanisme de contournement des CAPTCHA, connexions ou restrictions d'accès ne sera utilisé.

## Tests

Les tests permettront de vérifier :
- Le fonctionnement des connecteurs.
- La qualité des données récupérées.
- La normalisation.
- La déduplication.
- L'enregistrement dans PostgreSQL.
- Les endpoints de l'API.
- Les fonctionnalités principales de l'interface.

Lancer les tests backend :

```bash
pytest
```

## État du développement

Le projet est en cours de développement.

| Module | Statut |
|---|---|
| Architecture initiale | À réaliser |
| Base de données | À réaliser |
| Premier collecteur | À réaliser |
| Collecte multi-sources | À réaliser |
| Normalisation | À réaliser |
| Déduplication | À réaliser |
| API | À réaliser |
| Interface web | À réaliser |
| Tableau de bord | À réaliser |
| Comparaison CV/offre | Optionnel |

## Documentation

Le cahier des charges complet est disponible dans :

```text
CAHIER_DES_CHARGES_CLASSE.md
```

Il décrit les fonctionnalités attendues, l'architecture, les technologies, le modèle de données et les critères de validation.

## Contribution

Pour contribuer au projet :

1. Récupérer la dernière version du repository.
2. Créer une branche pour sa fonctionnalité.
3. Développer et tester les modifications.
4. Vérifier que les changements ne cassent pas les fonctionnalités existantes.
5. Soumettre une Pull Request pour révision.

## Licence

Projet développé dans un cadre scolaire. Les conditions de réutilisation et de distribution seront définies par l'équipe.

---

**Job Data Platform — Collecter, organiser et rendre les données d'emploi accessibles.**