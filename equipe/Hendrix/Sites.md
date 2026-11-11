# CAHIER DES CHARGES
## Plateforme de collecte massive et de recherche d'offres d'emploi

**Version :** 1.0  
**Type :** Projet scolaire  
**Marché cible :** Canada  
**Statut :** Cahier des charges initial

---

## 1. Présentation du projet

Le projet consiste à développer une application web permettant de collecter, centraliser, traiter et consulter un grand volume d'offres d'emploi et de stages provenant de différentes sources.

L'objectif principal est de construire un système de collecte de données performant et évolutif. Les offres seront récupérées automatiquement, nettoyées, normalisées, dédupliquées et enregistrées dans une base de données centralisée.

Les utilisateurs pourront ensuite consulter les offres et effectuer des recherches selon plusieurs critères.

Une fonctionnalité complémentaire permettra éventuellement de comparer un CV avec une offre d'emploi.

Le projet scolaire sera volontairement plus simple que la plateforme personnelle complète. Cependant, la collecte massive de données restera au centre du développement.

## 2. Objectifs du projet

### 2.1 Objectif principal

Développer un système automatisé capable de collecter et de traiter un grand volume d'offres d'emploi provenant de plusieurs sources.

### 2.2 Objectifs secondaires

- Centraliser les offres dans une base de données.
- Automatiser les collectes périodiques.
- Éviter les doublons.
- Uniformiser les informations provenant de différentes sources.
- Permettre la recherche et le filtrage des offres.
- Afficher des statistiques sur les données collectées.
- Prévoir une fonctionnalité simple de comparaison entre un CV et une offre.

## 3. Fonctionnalités principales

### 3.1 Module de collecte massive

Ce module représente le cœur du projet.

Le système devra récupérer automatiquement des offres provenant de plusieurs sources.

Sources envisageables :
- API publiques ou partenaires.
- Flux RSS et flux de données.
- Pages carrières d'entreprises.
- Sites d'emploi autorisant explicitement l'accès automatisé.

Chaque source devra disposer de son propre connecteur afin de faciliter son ajout, sa modification ou sa désactivation.

Les informations récupérées devront inclure, lorsque disponibles :

- Titre du poste.
- Nom de l'entreprise.
- Description de l'offre.
- Localisation.
- Province.
- Type d'emploi.
- Type de contrat.
- Mode de travail.
- Salaire.
- Date de publication.
- Date limite de candidature.
- URL originale.
- Source de provenance.

Le système devra pouvoir traiter les données progressivement, par lots, afin de supporter une augmentation du volume.

**Important :** la collecte devra respecter les conditions d'utilisation et les règles d'accès automatisé de chaque source. Aucun contournement de CAPTCHA, de connexion, de paywall ou de protection technique ne sera effectué.

### 3.2 Module de normalisation

Les offres provenant de différentes plateformes peuvent présenter des formats différents.

Le système devra transformer les informations récupérées en un format commun.

Exemples :
- Uniformiser les intitulés de postes.
- Normaliser les noms de provinces.
- Uniformiser les types de contrats.
- Convertir les salaires dans un format cohérent.
- Nettoyer les descriptions.
- Corriger les formats de dates.

Les informations inconnues devront rester vides plutôt que d'être inventées.

### 3.3 Module de déduplication

Une même offre peut apparaître sur plusieurs plateformes.

Le système devra :
- Identifier les offres déjà enregistrées.
- Comparer les URL et les identifiants des sources.
- Utiliser des empreintes de contenu pour détecter certains doublons.
- Éviter les insertions répétées.
- Actualiser les informations d'une offre déjà connue.
- Conserver les différentes sources lorsqu'une même offre est retrouvée ailleurs.

### 3.4 Module de stockage

Toutes les offres normalisées seront enregistrées dans PostgreSQL.

Le système devra conserver :
- Les offres.
- Les sources.
- Les historiques de collecte.
- Les erreurs rencontrées.
- Les dates de première et de dernière observation.

Les offres expirées pourront être marquées comme inactives sans être immédiatement supprimées.

### 3.5 Module de recherche

L'utilisateur pourra rechercher des offres selon :

- Mots-clés.
- Titre du poste.
- Entreprise.
- Ville.
- Province.
- Type d'emploi.
- Stage ou emploi.
- Mode de travail.
- Salaire.
- Source.

Chaque offre devra afficher un lien vers la publication originale.

### 3.6 Tableau de bord administratif

Un espace d'administration permettra de surveiller les opérations de collecte.

Il affichera :
- Nombre de sources configurées.
- Nombre total d'offres collectées.
- Nombre de nouvelles offres.
- Nombre de doublons détectés.
- Nombre d'erreurs.
- Date de dernière collecte.
- Durée des collectes.
- État des connecteurs.

### 3.7 Comparaison CV et offres — fonctionnalité secondaire

Une fonctionnalité facultative permettra à un utilisateur d'importer son CV et de sélectionner une offre.

Le système pourra :
- Extraire les compétences présentes dans le CV.
- Identifier les compétences demandées dans l'offre.
- Calculer un score indicatif de correspondance.
- Afficher les compétences communes.
- Identifier les compétences manquantes.

Cette fonctionnalité sera développée uniquement si les fonctionnalités principales sont terminées.

## 4. Architecture de collecte massive

Le système devra utiliser un pipeline organisé en plusieurs étapes.

### 4.1 Fonctionnement du pipeline

1. Sélection des sources actives.
2. Récupération des données.
3. Conservation temporaire des données brutes nécessaires au traitement.
4. Nettoyage des données.
5. Normalisation des champs.
6. Validation des informations.
7. Détection des doublons.
8. Enregistrement dans PostgreSQL.
9. Mise à jour des statistiques de collecte.

### 4.2 Traitement par lots

Pour supporter des volumes importants, le système devra :

- Traiter les données par lots.
- Éviter de charger inutilement toutes les données en mémoire.
- Gérer les erreurs individuellement.
- Prévoir la reprise des collectes interrompues.
- Respecter les limites des sources.
- Journaliser les opérations.

### 4.3 Évolutivité

L'architecture devra permettre d'ajouter de nouvelles sources sans devoir modifier entièrement le système.

Les performances seront évaluées à partir de tests portant notamment sur :
- Le nombre d'offres traitées.
- Le temps de traitement.
- La consommation mémoire.
- Le nombre de doublons.
- Le taux d'erreur.

Aucune capacité maximale ne sera annoncée sans mesure réelle.

## 5. Technologies proposées

| Technologie | Utilisation |
|---|---|
| Python | Collecte et traitement |
| Polars | Traitement de données volumineuses |
| FastAPI | Backend et API |
| PostgreSQL | Base de données |
| Next.js | Interface web |
| TypeScript | Développement frontend |
| Pytest | Tests backend |
| Git et GitHub | Gestion du code source |

Cette architecture pourra être adaptée aux technologies imposées par le cours.

Pour la première version, un backend unique avec des connecteurs modulaires sera privilégié. Une infrastructure plus complexe ne sera ajoutée que si les tests démontrent qu'elle est nécessaire.

## 6. Structure de la base de données

### Table `sources`

| Champ | Description |
|---|---|
| id | Identifiant |
| name | Nom de la source |
| source_type | Type de source |
| base_url | Adresse de la source |
| is_active | État de la source |
| last_run_at | Dernière collecte |
| created_at | Date de création |

### Table `jobs`

| Champ | Description |
|---|---|
| id | Identifiant |
| source_id | Source principale |
| source_job_id | Identifiant externe |
| title | Titre du poste |
| company | Entreprise |
| description | Description |
| location | Localisation |
| province | Province |
| employment_type | Type d'emploi |
| work_mode | Mode de travail |
| salary_min | Salaire minimum |
| salary_max | Salaire maximum |
| currency | Devise |
| published_at | Publication |
| expires_at | Expiration |
| original_url | URL originale |
| first_seen_at | Première observation |
| last_seen_at | Dernière observation |
| status | Statut |
| content_hash | Empreinte du contenu |

### Table `collection_runs`

| Champ | Description |
|---|---|
| id | Identifiant |
| source_id | Source concernée |
| started_at | Début de collecte |
| finished_at | Fin de collecte |
| status | État de l'exécution |
| items_found | Offres trouvées |
| items_inserted | Nouvelles offres |
| duplicates_found | Doublons |
| errors_count | Erreurs |
| error_summary | Résumé des erreurs |

Une table complémentaire `job_source_occurrences` pourra être ajoutée pour conserver les différentes publications d'une même offre sur plusieurs plateformes.

## 7. API proposée

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/health` | Vérifier le fonctionnement |
| GET | `/jobs` | Consulter les offres |
| GET | `/jobs/{id}` | Consulter une offre précise |
| GET | `/sources` | Consulter les sources |
| GET | `/collections` | Historique des collectes |
| POST | `/collections/{source_id}/run` | Lancer une collecte |
| GET | `/statistics` | Statistiques globales |

Les routes administratives devront être protégées si l'application est accessible publiquement.

## 8. Interface utilisateur

L'application comportera les pages suivantes :

### Accueil
- Présentation du projet.
- Accès à la recherche.
- Quelques statistiques générales.

### Recherche d'offres
- Liste des offres disponibles.
- Barre de recherche.
- Filtres.
- Tri des résultats.

### Détail d'une offre
- Description complète.
- Entreprise.
- Localisation.
- Type d'emploi.
- Salaire si disponible.
- Source originale.
- Lien vers la candidature.

### Administration
- Sources configurées.
- État des collectes.
- Historique.
- Statistiques.
- Erreurs.

### Comparaison CV-offre
- Importation du CV.
- Sélection d'une offre.
- Résultat de correspondance.

## 9. Sécurité et confidentialité

- Les clés API et mots de passe ne devront jamais être publiés dans Git.
- Les variables sensibles seront conservées dans des fichiers d'environnement non versionnés.
- Les sources devront être utilisées conformément à leurs conditions.
- Les données personnelles non nécessaires ne devront pas être collectées.
- Les CV importés devront être stockés de manière privée.
- La suppression des CV devra être possible si cette fonctionnalité est mise en place.
- Les exigences applicables en matière de confidentialité devront être prises en compte, notamment la Loi 25 au Québec et les règles fédérales pertinentes.

## 10. Plan de développement

### Phase 1 — Initialisation
- Création du repository.
- Organisation des dossiers.
- Configuration frontend et backend.
- Configuration de PostgreSQL.
- Mise en place de l'environnement de développement.

### Phase 2 — Base de données
- Création des tables.
- Relations entre les tables.
- Index de recherche.
- Tests de connexion.

### Phase 3 — Premier collecteur
- Sélection d'une source autorisée.
- Développement du connecteur.
- Récupération des offres.
- Normalisation.
- Enregistrement en base.

### Phase 4 — Collecte multi-sources
- Ajout de nouveaux connecteurs.
- Traitement par lots.
- Déduplication.
- Gestion des erreurs.
- Historique des collectes.

### Phase 5 — Interface de recherche
- Affichage des offres.
- Barre de recherche.
- Filtres.
- Détails des offres.

### Phase 6 — Tableau de bord
- Statistiques de collecte.
- Historique.
- État des sources.
- Suivi des erreurs.

### Phase 7 — Comparaison CV
- Importation du CV.
- Extraction des compétences.
- Comparaison avec une offre.
- Affichage du résultat.

### Phase 8 — Tests et livraison
- Tests des collecteurs.
- Tests de normalisation.
- Tests de déduplication.
- Tests API.
- Tests frontend.
- Documentation finale.

## 11. Critères d'acceptation

Le projet sera considéré comme fonctionnel lorsque :

- Une ou plusieurs sources autorisées peuvent être collectées.
- Les données sont normalisées.
- Les offres sont enregistrées dans PostgreSQL.
- Les doublons sont détectés.
- Les collectes sont journalisées.
- Les erreurs sont enregistrées.
- Les utilisateurs peuvent rechercher des offres.
- Les filtres fonctionnent.
- Les statistiques sont accessibles.
- Les tests principaux passent.
- L'application peut être installée à partir de la documentation.

Le volume cible et le nombre de sources seront définis avec l'équipe et validés par des tests.

## 12. Fonctionnalités hors périmètre

Afin de maintenir un projet scolaire réaliste, les fonctionnalités suivantes ne sont pas obligatoires :

- Agents IA autonomes.
- Génération automatique de candidatures.
- Envoi automatique de CV.
- Abonnements et facturation.
- Système SaaS avancé.
- Entraînement d'un modèle IA propriétaire.
- Infrastructure distribuée complexe.
- Automatisation de sites interdisant le scraping.

Ces fonctionnalités pourront être envisagées dans une version personnelle ultérieure.

## 13. Résultat final attendu

À la fin du projet, l'équipe devra présenter une application capable de collecter des offres d'emploi depuis plusieurs sources autorisées, de traiter un volume important de données, de supprimer les doublons, de stocker les résultats dans une base centralisée et de permettre leur consultation depuis une interface web.

**La priorité du projet est la qualité et la capacité d'évolution du pipeline de collecte massive, et non le nombre de fonctionnalités d'intelligence artificielle.**

---

**Principe directeur : une interface simple, un système de collecte robuste et une architecture capable d'évoluer.**