# Jobs Insights - Espace Hugo

Projet académique visant à développer un **agrégateur intelligent d'offres d'emploi et de stages en informatique** (Québec et Canada), complété par un module d'assistance à la **personnalisation et bonification de CV** selon les compétences requises.

> 📌 **Note** : Ce document est un fichier évolutif ("living document"). Il est mis à jour au fil de l'avancement de la preuve de concept (POC) et des développements techniques.

---

## 🎯 1. Objectifs du projet

1. **Agrégation et filtrage ciblé** :
   * **Domaine** : Informatique / Technologies de l'information (TI).
   * **Niveau** : Stages (internships) et emplois juniors / début de carrière.
   * **Périmètre géographique** : Québec (prioritaire) et ensemble du Canada.
   * **Filtres multicritères** : Présentiel / Télétravail / Hybride, technologies requises, localisation, langue.

2. **Aide à la bonification de CV** :
   * Extraction des mots-clés et compétences techniques demandées par les offres retenues (langages, frameworks, outils, méthodologies).
   * Recommandations d'ajustements du CV pour maximiser la correspondance (matching) avec l'offre ciblée.

3. **Preuve de concept initiale (POC)** :
   * Source prioritaire : **Emploi Canada / Guichet-Emplois** (données officielles fiables et structurées).
   * Objectif technique : Collecter, normaliser et exporter les offres vers un format **JSON / JSONL** propre et réutilisable par le reste de l'équipe.

---

## 🏛️ 2. Architecture logicielle & Modularité

Afin de garantir un code robuste, maintenable et facilement intégrable avec les autres modules de l'équipe, la solution repose sur une séparation claire des responsabilités :

```
[ Guichet-Emplois (RSS / Web) ]
               │
               ▼
       1. EXTRACTEUR (Fetcher)        --> Gère les requêtes HTTP, flux RSS, pagination et résilience réseau
               │
               ▼
       2. PARSEUR (Parser)            --> Extrait les champs bruts et nettoie le texte
               │
               ▼
       3. MODÈLE (Data Model)         --> Valide les types et structure les données (Pydantic / Dataclass)
               │
               ▼
       4. EXPORTATEUR (Storage)       --> Sauvegarde en JSON / JSONL standardisé
```

### Avantages de cette structure :
* **Modulaire** : Si la structure HTML ou le flux RSS d'Emploi Canada change, seul le parseur est ajusté sans casser le reste du système.
* **Intégrable** : N'importe quel membre de l'équipe pourra réutiliser la même classe de base ou le même modèle de données pour scraper d'autres plateformes (Adzuna, Jobillico, etc.).

---

## 📋 3. Schéma de données cible (Contrat JSON)

Chaque offre extraite respecte la structure standard suivante :

```json
{
  "id": "gc-12345678",
  "titre": "Stagiaire en développement logiciel",
  "entreprise": "Entreprise Exemple Inc.",
  "ville": "Montréal",
  "province": "QC",
  "pays": "Canada",
  "type_poste": "Stage",
  "modalite": "Hybride",
  "salaire": {
    "montant": 25.50,
    "unite": "heure",
    "devise": "CAD"
  },
  "description_texte": "Description complète du poste...",
  "competences_cles": ["Python", "Git", "Docker", "SQL"],
  "date_publication": "2026-11-10",
  "url_source": "https://www.guichetemplois.gc.ca/...",
  "source": "Emploi Canada"
}
```

---

## 📂 4. Organisation du répertoire de travail

```text
equipe/Hugo/
├── main.py                 # Point d'entrée principal (lançable par double-clic ou commande)
├── poc_emploi_canada.py    # Moteur de collecte multi-mots-clés, parsing et enrichissement
├── models.py               # Définition des structures de données typées (Pydantic)
├── README.md               # Documentation principale et suivi d'avancement
├── sites.md                # Répertoire et comparatif des plateformes d'emploi
├── requirements.txt        # Dépendances Python (requests, beautifulsoup4, pydantic)
├── data/                   # Données collectées (offres_emploi_canada.json)
└── logs/                   # Journalisation détaillée des requêtes et erreurs (collecte.log)
```

---

## 🚀 5. Feuille de route (Roadmap)

- [x] **Étape 1 : Veille & exploration des sources**
  - [x] Recherche et recensement des plateformes d'emploi (Canada & International).
  - [x] Évaluation des méthodes d'accès (API, RSS, Scraping) consignée dans `sites.md`.
- [x] **Étape 2 : Cadrage & Socle technique du POC**
  - [x] Création du `README.md` et définition du contrat de données.
  - [x] Configuration de l'environnement Python (`requirements.txt`).
  - [x] Création du modèle de données typé Pydantic (`models.py`).
- [x] **Étape 3 : Implémentation du collecteur Emploi Canada**
  - [x] Développer la recherche ciblée TI et la pagination par session (`poc_emploi_canada.py`).
  - [x] Bouquet étendu de 16 métiers informatiques (Programmeurs, Analystes, Jeux vidéo, Web, etc.).
  - [x] Barre de progression dynamique en temps réel dans le terminal.
  - [x] Système de journalisation et traçage des erreurs de plantage (`logs/collecte.log`).
  - [x] Implémenter l'enrichissement détaillé (modalité télétravail/hybride, compétences TI).
  - [x] Exporter les résultats au format JSON propre dans `data/`.
- [ ] **Étape 4 : Bonification de CV & Matching**
  - [ ] Définir la logique d'extraction de compétences à partir des descriptions de postes.
  - [ ] Implémenter un premier mécanisme de comparaison offre vs compétences du CV.
- [ ] **Étape 5 : Intégration globale**
  - [ ] Harmonisation avec les composants développés par les autres coéquipiers.

---

## 🛠️ 6. Guide d'utilisation du POC

### Méthode 1 : Lancement par double-clic sur le fichier Python
Faites simplement un double-clic sur :
👉 **`main.py`** (ou sur **`poc_emploi_canada.py`**)

Le script s'exécute automatiquement :
1. **Auto-installation** des dépendances requises (`requests`, `beautifulsoup4`, `pydantic`) avec affichage du statut en direct.
2. **Test de connectivité** préalable avec Guichet-Emplois pour vérifier que le site est bien **EN LIGNE (Live)**.
3. **Menu interactif** :
   * Saisissez le nombre d'offres souhaité (défaut : `100`).
   * Choisissez le mode : **Bouquet de 16 métiers informatiques** (recommandé pour un max d'offres ciblées) ou mot-clé unique.
4. **Barre de progression en direct** :
   * `[Recherche] [==============-------] 70.0% (70/100) [développeur jeux vidéo] +5`
   * `[Details  ] [=====================] 100.0% (100/100) Analyste-programmeur (Hybride)`
5. **Rapport de synthèse et sauvegarde** dans `data/offres_emploi_canada.json`.
6. **Journalisation complète** : Toutes les requêtes, erreurs et éventuels plantages sont enregistrés dans `logs/collecte.log`.
7. **Maintien de la fenêtre ouverte** : La console reste ouverte avec le message `"Appuyez sur Entrée pour quitter..."`.

---

### Méthode 2 : Lancement depuis le terminal
```bash
cd C:\Users\hugoc\ProjetGit\jobs-insights\equipe\Hugo
python main.py
```


