# AGENTS.md — Consignes pour les agents de code (`jobs-insights`)

Ce fichier fournit le contexte du dépôt et les règles de travail à suivre pour tout assistant de code (Codex, Claude Code, Gemini/Antigravity, etc.) intervenant sur ce projet.

---

## 1. Contexte du projet

- **Nom** : `job-insights` (voir [`README.md`](README.md)).
- **Cadre** : projet pédagogique collaboratif et non noté du DEC en Techniques de l’informatique au Collège O’Sullivan de Québec (cours `420-SV2-OQ`, encadré par Grégory).
- **Objectif** : explorer comment la collecte de données et l’IA peuvent aider les étudiants à repérer des offres d’emploi et de stages (Québec / Canada, domaine TI), à les filtrer et à adapter leurs candidatures (CV / lettre de motivation).
- **Quatre pistes de travail** :
  1. Recenser les sources d’offres pertinentes.
  2. Collecter, nettoyer et structurer les offres dans un format commun.
  3. Présenter les offres (recherche, filtrage, sélection).
  4. Explorer l’aide à la candidature (matching et suggestions à partir d’un CV ou d’une lettre).
- **Langage principal** : **Python** (testé avec Python 3.13 ; viser la compatibilité 3.12+).
- **Langue du projet** : français pour la documentation, les explications et les textes destinés aux utilisateurs.

---

## 2. État actuel et organisation du dépôt

Le projet est **en phase de cadrage et d’exploration (Atelier 1 / POCs)**. Aucune architecture applicative unifiée (backend web, frontend ou base de données) n’est encore en place à la racine.

- `README.md` : présentation officielle du projet, des pistes et du fonctionnement collaboratif.
- `.gitignore` : exclusions Python standard.
- `equipe/` : espaces de travail et de veille individuels des membres de l’équipe (recensements `sites.md` / `Sites.md`, scripts POC, exemples de sorties JSON/CSV). Les dossiers sous `equipe/` suivent le nom du membre en minuscules sans accent, aligné sur [`equipe/equipe.md`](equipe/equipe.md) (`aymerou`, `elvira`, `ferdinand`, `gregory`, `hendrix`, `hugo`, `kandet`, `mamadou`, `nonga`, `rayan`, etc.).
  - Exemples de POCs déjà présents :
    - `equipe/hugo/` : collecteur interactif Guichet-Emplois avec modèle Pydantic `JobOffer` (`models.py`, `requirements.txt`).
    - `equipe/kandet/` : POC multi-source (flux Atom Guichet-Emplois + API Remotive) en bibliothèque standard avec déduplication, détection de stages et tests unitaires (`test_poc_multi_source.py`).
    - `equipe/mamadou/` : POCs stdlib sur Talent.com, Jobboom, Guichet-Emplois (RDFa) et Jobillico (JSON-LD).
    - `equipe/elvira/` : scraper Jobboom (`requests` + `BeautifulSoup` + JSON-LD).
    - `equipe/ferdinand/` : collecte via l’API publique Welcome to the Jungle et export CSV.
    - `equipe/rayan/site.md` : analyse de conformité des sources Québec/Canada (données ouvertes, APIs, ATS, sources exclues).
    - `equipe/hendrix/README.MD` : proposition d’architecture cible (non implémentée à ce jour).

### Règles de périmètre
1. **Ne modifiez pas, ne déplacez pas et ne supprimez pas** les fichiers dans le dossier d’un autre membre sous `equipe/<membre>/`, sauf demande explicite de l’utilisateur.
2. **Distinguez l’existant réel des propositions** : certains documents décrivent des architectures futures (FastAPI, Next.js, PostgreSQL, Polars, etc.) qui n’existent pas encore dans le code. Ne supposez jamais qu’elles sont installées ou configurées sans vérifier les fichiers présents.
3. Quand une architecture partagée sera décidée par la classe, ce fichier devra être mis à jour pour documenter les nouveaux dossiers à la racine.

---

## 3. Environnement Python, dépendances et tests

- **Dépendances** : il n’y a pas encore de `requirements.txt` ou `pyproject.toml` commun à la racine.
  - Privilégiez la bibliothèque standard Python (`urllib`, `json`, `xml.etree.ElementTree`, `html.parser`, `dataclasses`, `pathlib`, `unittest`) pour les scripts autonomes et les tests.
  - Si des bibliothèques tierces sont nécessaires (`requests`, `beautifulsoup4`, `pydantic`, etc.), documentez-les explicitement (ex. `requirements.txt` local au module). N’ajoutez pas d’auto-installation `pip` à l’import d’un module réutilisable.
- **Tests existants** :
  - Exécuter les tests unitaires hors ligne existants :
    ```powershell
    python -m unittest discover -s equipe/kandet -p "test_*.py" -v
    ```
- **Règle de test** : toute nouvelle logique de parsing, normalisation, classification ou déduplication doit être accompagnée de tests unitaires **hors ligne** (fixtures HTML/XML/JSON locales ou mocks), sans effectuer d’appels réseau réels pendant les tests.
- **Précaution avant d’exécuter un script POC** : inspectez d’abord son code ; certains scripts effectuent des requêtes HTTP en direct, demandent une saisie interactive (`input()`), créent des fichiers de sortie dans le répertoire courant ou appellent `os.startfile(...)` sous Windows.

---

## 4. Règles de collecte de données, conformité et sécurité

La collecte de données est au cœur du projet et doit rester responsable :

1. **Privilégier les accès officiels et structurés** : APIs publiques ou gratuites avec clé, portails de données ouvertes (ex. Guichet-Emplois / Job Bank), flux RSS/Atom, puis pages HTML contenant des métadonnées structurées (`application/ld+json` `JobPosting`, RDFa).
2. **Respecter les règles des sites** : consulter `robots.txt` et les conditions d’utilisation avant d’automatiser une nouvelle source ; envoyer un `User-Agent` honnête ; respecter les délais (`crawl-delay`, ex. 5 secondes sur Guichet-Emplois) et quotas d’API (cache local recommandé).
3. **Aucun contournement** : ne jamais implémenter de contournement de CAPTCHA, de protection anti-bot/Cloudflare, d’authentification ou de restriction d’accès. Les sites l’interdisant (ex. LinkedIn, Indeed, Glassdoor, Québec emploi selon leurs conditions) restent en consultation manuelle ou exclus sauf autorisation explicite.
4. **Intégrité des données** : ne jamais inventer ou deviner une information absente d’une offre (salaire, entreprise, lieu, modalité, date). Utiliser `None`, une chaîne vide ou une valeur explicite comme `"Non spécifié"`.
5. **Secrets et vie privée** : ne jamais commiter de clés API, jetons, fichiers `.env` ni données personnelles (CV réels d’étudiants, etc.).

---

## 5. Conventions de développement et collaboration

- **Modularité** : séparer clairement la collecte réseau (HTTP/API), le parsing/nettoyage, la structure de données (modèle typé) et l’export/stockage.
- **Compatibilité Windows & encodage** : l’équipe travaille notamment sous Windows (`powershell`). Toujours ouvrir les fichiers texte/JSON/CSV avec `encoding="utf-8"` (ou `utf-8-sig` si export CSV destiné à Excel) et gérer proprement l’encodage de la sortie console si nécessaire.
- **Simplicité pédagogique** : éviter la sur-ingénierie prématurée. Produire un code clair, lisible, typé et bien commenté sur le *pourquoi* des choix non évidents.
- **Hygiène Git** :
  - Vérifier `git status` et `git diff` avant de conclure.
  - Éviter de commiter des caches temporaires, des journaux d’exécution (`logs/`) ou de volumineux fichiers de données générés par des tests ad hoc, sauf s’il s’agit d’un échantillon volontairement documenté.
