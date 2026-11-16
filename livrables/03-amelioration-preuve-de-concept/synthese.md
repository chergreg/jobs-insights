# Synthèse — Livrable 3 : Reprendre et améliorer une preuve de concept

Bilan établi après analyse des évolutions de code, des nouveaux modules et des notes techniques déposés par l’équipe (voir l’énoncé dans [`enonce.md`](enonce.md), la synthèse du Livrable 2 dans [`../02-preuve-de-concept-scraping/synthese.md`](../02-preuve-de-concept-scraping/synthese.md) et le référentiel des sources dans [`../01-inventaire-des-sites/inventaire.md`](../01-inventaire-des-sites/inventaire.md)).

---

## 1. Tableau synthèse des remises

Sur les **11 étudiants** inscrits dans [`equipe/equipe.md`](../../equipe/equipe.md) (2 améliorations majeures de code, 1 rattrapage documentaire, 8 sans remise L3) :

| Étudiant | Statut L3 | Site / Source ciblée | Nature de l’amélioration | Tests & Validation | Compte rendu / Note | Emplacement |
| --- | --- | --- | --- | --- | --- | --- |
| **Hugo** | ✅ Fait | Guichet-Emplois Canada | Stratégie en cascade (Atom + HTML + RDFa/DOM), modularisation complète, extraction 100 % descriptions, filtre strict compétences | 23 assertions (6 tests unitaires hors ligne) | [`COMPTE_RENDU_LIVRABLE_2.md`](../../equipe/hugo/02-preuve-de-concept-scraping/COMPTE_RENDU_LIVRABLE_2.md) + [`README.md`](../../equipe/hugo/README.md) | [`02-preuve-de-concept-scraping`](../../equipe/hugo/02-preuve-de-concept-scraping) |
| **Kandet** | ✅ Fait | Guichet-Emplois Canada (+ Remotive) | Remplacement du flux Atom par la pagination HTML exhaustive (14 codes CNP TI, 191 offres QC), détection des partenaires d'origine, fusion doublons inter-plateformes | 33 tests unitaires hors ligne (`stdlib` pure), échantillon JSON 10 offres | [`compte-rendu-livrable-2.md`](../../equipe/kandet/02-preuve-de-concept-scraping/compte-rendu-livrable-2.md) | [`02-preuve-de-concept-scraping`](../../equipe/kandet/02-preuve-de-concept-scraping) |
| **Ferdinand** | ⚠️ Partiel | Welcome to the Jungle | Rattrapage documentaire du Livrable 2 (commandes, limites Europe/Windows), mais aucun changement apporté au code Python | Aucun test, CSV d'origine inchangé | Dans [`sites.md`](../../equipe/ferdinand/01-inventaire-des-sites/sites.md) | [`01-inventaire-des-sites`](../../equipe/ferdinand/01-inventaire-des-sites) |
| **Mamadou** | ❌ Non fait | (Talent.com, Jobboom, Jobillico, Guichet-Emplois) | Aucun nouveau commit depuis le Livrable 2 (POC initial intact) | Tests manuels L2 | Sommaire L2 | [`02-preuve-de-concept-scraping`](../../equipe/mamadou/02-preuve-de-concept-scraping) |
| **Elvira** | ❌ Non fait | (Jobboom) | Aucun nouveau commit depuis le Livrable 2 (POC initial intact) | Échantillon 5 offres L2 | Dans `sites.md` | [`02-preuve-de-concept-scraping`](../../equipe/elvira/02-preuve-de-concept-scraping) |
| **Dan** | ❌ Non fait | (Guichet-Emplois Moncton) | Aucun nouveau commit ; conflit Git non résolu dans `README.md`, sélecteurs non vérifiés | Aucun test ni sortie | Absent | [`02-preuve-de-concept-scraping`](../../equipe/dan/02-preuve-de-concept-scraping) |
| **Rayan** | ❌ Non fait | — | Aucun script de collecte déposé à ce jour | — | Absent | — |
| **Aymerou** | ❌ Non fait | — | Aucun script de collecte déposé à ce jour | — | Absent | — |
| **Nonga** | ❌ Non fait | — | Aucun script de collecte déposé à ce jour | — | Absent | — |
| **Hendrix** | ❌ Non fait | — | Aucun script de collecte déposé à ce jour (cahier des charges théorique uniquement) | — | Absent | — |
| **Mike** | ❌ Non fait | — | Aucun dossier ni contribution dans le dépôt | — | Absent | — |

> [!NOTE]
> **Précision méthodologique sur les dossiers :**
> Aucun contributeur n'a créé de nouveau sous-dossier `03-amelioration-preuve-de-concept/`. Les améliorations techniques et documentaires ont été intégrées directement dans les dossiers `02-preuve-de-concept-scraping/` et `01-inventaire-des-sites/`. Bien que leurs comptes rendus portent le titre « Livrable 2 », les travaux récents de **Hugo** et de **Kandet** correspondent point par point aux objectifs attendus pour le Livrable 3 (analyse comparative, reprise de code existant, résolution de limites bloquantes et validation par tests).

---

## 2. Fiches par remise

### Hugo (`✅ Fait — Amélioration majeure`)
- **Code :** Architecture modulaire découplée sous [`equipe/hugo/02-preuve-de-concept-scraping/`](../../equipe/hugo/02-preuve-de-concept-scraping/) :
  - [`models.py`](../../equipe/hugo/02-preuve-de-concept-scraping/models.py) : schéma de données typé Pydantic `JobOffer`.
  - [`parsers.py`](../../equipe/hugo/02-preuve-de-concept-scraping/parsers.py) : logique pure d’extraction découplée du réseau.
  - [`collecte.py`](../../equipe/hugo/02-preuve-de-concept-scraping/collecte.py) : moteur réseau HTTP avec temporisation conforme.
  - [`main.py`](../../equipe/hugo/02-preuve-de-concept-scraping/main.py) : interface CLI scriptable et menu interactif Windows.
  - [`test_scraper.py`](../../equipe/hugo/02-preuve-de-concept-scraping/test_scraper.py) : suite de tests unitaires hors ligne.
- **Site choisi et démarche :** **Guichet-Emplois Canada**. Hugo a mis en œuvre une **stratégie de collecte en cascade à 3 niveaux** qui intègre les forces des différentes approches explorées lors de l'Atelier 1 et du Livrable 2 :
  1. *Niveau 1 (Flux Atom XML officiel) :* collecte rapide et structurée sans casse de balisage (approche initialement explorée par Kandet).
  2. *Niveau 2 (Recherche HTML par mots-clés) :* interrogation sur un bouquet de 16 métiers TI au Québec si le flux Atom ne suffit pas.
  3. *Niveau 3 (Enrichissement des fiches détaillées) :* extraction sémantique prioritaire via RDFa / Schema.org (`property="description"`, inspiré des constats de Mamadou) avec repli vers les conteneurs DOM (`div#job-posting-detail`).
- **Problèmes résolus par rapport au Livrable 2 :**
  - **Description complète récupérée :** 100 % des offres enrichies contiennent désormais leur description textuelle intégrale (qui était à `null` au L2).
  - **Élimination des faux positifs sur les compétences :** refonte de `extract_tech_skills()` avec des expressions régulières contextuelles (`TECH_PATTERNS`). Les faux positifs fréquents en français (`"C"` sur les mots isolés ou abréviations, `"Vue"` sur « vue d'ensemble ») sont totalement éliminés.
  - **Autonomie et automatisation :** suppression de l'auto-installation silencieuse `pip` à l'import ; ajout d'arguments CLI (`--limit`, `--province`, `--fast`, `--keyword`) évitant le blocage interactif `input()`.
  - **Conformité réseau :** respect du `crawl-delay` de 5 s par défaut conforme au `robots.txt`, avec identification honnête dans le `User-Agent`.
- **Validation :** 6 tests unitaires hors ligne (23 assertions) validant le flux Atom, la recherche HTML, l'extraction RDFa, le repli DOM et le filtrage des compétences (`python -m unittest discover -s equipe/hugo/02-preuve-de-concept-scraping -p "test_*.py" -v` : succès en 0.01 s).
- **Limites subsistantes :**
  - La recherche HTML s'appuie sur une liste fixe de mots-clés plutôt que sur une pagination exhaustive de tous les codes CNP (contrairement à l'approche de Kandet).
  - Le document de synthèse est nommé `COMPTE_RENDU_LIVRABLE_2.md` au lieu d'un document dédié L3 explicitant les emprunts aux camarades.

### Kandet (`✅ Fait — Amélioration majeure`)
- **Code :** [`poc_multi_source.py`](../../equipe/kandet/02-preuve-de-concept-scraping/poc_multi_source.py) et [`test_poc_multi_source.py`](../../equipe/kandet/02-preuve-de-concept-scraping/test_poc_multi_source.py) mis à jour en bibliothèque standard pure Python (aucun paquet externe requis).
- **Site choisi et démarche :** **Guichet-Emplois Canada** (avec Remotive en source d'appoint). Kandet a analysé pourquoi son prototype Atom initial ne remontait qu'une seule offre au Québec : le flux officiel restreint drastiquement le volume et ignore les offres relayées par les partenaires. Il a donc fait évoluer son collecteur vers la **page de recherche HTML avec pagination dynamique sans plafond**.
- **Problèmes résolus et avancées majeures :**
  - **Saut d'échelle du volume :** passage de 1 offre à **191 offres TI réelles au Québec** (100 % des offres annoncées par le site sur 8 pages de résultats) + 8 offres Remotive = **198 offres uniques**.
  - **Identification et traçabilité des partenaires :** détection du site d'origine dans le balisage (Guichet-Emplois : 68, Jobillico : 44, Québec emploi : 38, Talent.com : 19, JobsMedia.ca : 13, CareerBeacon : 5, indeed.com : 3, Jobboom : 1).
  - **Fusion des doublons inter-plateformes :** identification d'une même offre publiée simultanément sur Québec emploi et Jobillico (ex. *Fop experts conseils* à Brossard), regroupée en une seule fiche conservant les deux sources et URLs.
  - **Robustesse réseau et respect strict :** temporisation rigoureuse de 5 s par page (`robots.txt`), reprise après incident (HTTP 429 avec attente 30 s), cache local 24 h sur Remotive (`remotive-cache.json`).
- **Validation :** **33 tests unitaires hors ligne** couvrant la pagination sans plafond, l'arrêt sur page vide/répétée, le parsing HTML, la déduplication et le calcul de délai (`Ran 33 tests in 0.20s - OK`). Échantillon déposé de 10 offres dans [`echantillon.json`](../../equipe/kandet/02-preuve-de-concept-scraping/echantillon.json).
- **Limites observées et documentées :**
  - Les titres extraits sont les libellés officiels de la CNP et non les titres bruts de l'employeur (ce qui neutralise la détection de stages dans l'intitulé : 0 stage détecté sur 198).
  - Pas de visite des fiches individuelles pour limiter le temps d'exécution (191 fiches à 5 s prendraient ~16 minutes) ; par conséquent, la description complète et les exigences ne sont pas encore récupérées (laissées vides de manière intègre).
  - Kandet note explicitement dans son compte rendu l'intérêt de croiser son travail avec les essais de Hugo et Mamadou pour l'analyse des fiches et balises RDFa.

### Ferdinand (`⚠️ Partiel — Documentation L2 sans amélioration code L3`)
- **Fichiers concernés :** [`equipe/ferdinand/01-inventaire-des-sites/sites.md`](../../equipe/ferdinand/01-inventaire-des-sites/sites.md) (commit `4901880`).
- **Travail réalisé :** Ferdinand a complété la documentation manquante de son Livrable 2 en ajoutant une section structurée « Compte rendu - Livrable 2 » :
  - Détail de l'API publique Welcome to the Jungle (`https://api.welcometothejungle.com/api/v3/public/jobs`).
  - Procédure d'installation et d'exécution (`pip install requests`, `python poc_wttj.py`).
  - Échantillon des 30 offres récupérées (mot-clé « stage data »).
  - Reconnaissance explicite des limites du prototype : offres presque toutes localisées en Europe, localisation absente du CSV, format d'API non documenté, et appel `os.startfile()` spécifique à Windows.
- **Limites et points bloquants pour le Livrable 3 :**
  - **Aucune évolution du code :** le script [`poc_wttj.py`](../../equipe/ferdinand/02-preuve-de-concept-scraping/poc_wttj.py) n'a subi aucune modification.
  - Les correctifs attendus (extraction du champ `office`/`offices` pour le lieu, filtrage sur le Québec ou le Canada, suppression de `os.startfile()`, ajout d'un `requirements.txt` et de tests) restent à faire.

### Mamadou (`❌ Non fait en L3`)
- **Situation :** Aucun nouveau commit depuis le 11 novembre.
- **Rappel de l'existant L2 :** Mamadou avait produit le POC le plus diversifié au L2 ([`poc_scrapers_atelier1.py`](../../equipe/mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py) testant Talent.com, Jobboom, Jobillico et Guichet-Emplois en RDFa).
- **Besoins d'évolution :** Remplacer le parsing HTML par regex par un vrai parseur, ajouter une temporisation conforme et des tests unitaires, ou s'associer à l'effort de standardisation Guichet-Emplois.

### Elvira (`❌ Non fait en L3`)
- **Situation :** Aucun nouveau commit depuis le 11 novembre.
- **Rappel de l'existant L2 :** Prototype fonctionnel sur Jobboom ([`Scraper.py`](../../equipe/elvira/02-preuve-de-concept-scraping/Scraper.py)) extrayant 5 offres via JSON-LD.
- **Besoins d'évolution :** Ajouter la pagination des résultats, remplacer l'ensemble non ordonné d'URLs par une structure stable, nettoyer les balises HTML des descriptions, ajouter un `requirements.txt` et vérifier les conditions d'accès de Jobboom.

### Dan (`❌ Non fait en L3`)
- **Situation :** Aucun nouveau commit depuis le 11 novembre.
- **Points bloquants persistants :** Conflit Git non résolu dans `README.md`, sélecteurs non vérifiés dans [`Poc guichetemploi.py`](../../equipe/dan/02-preuve-de-concept-scraping/Poc%20guichetemploi.py), périmètre centré sur Moncton (N.-B.) au lieu du Québec, absence totale de résultats concrets.

### Rayan, Aymerou, Nonga, Hendrix & Mike (`❌ Non fait en L3`)
- **Rayan :** Dispose d'un travail d'inventaire remarquable au L1 (APIs Adzuna/Jooble et carrières ATS), mais n'a pas encore livré de code Python.
- **Aymerou & Nonga :** N'ont pas encore produit de POC de collecte fonctionnel.
- **Hendrix :** Présente une réflexion d'architecture théorique dans son dossier, sans brique logicielle exécutable.
- **Mike :** Absent du dépôt.

---

## 3. Constats techniques et méthodologiques transversaux

### La convergence Guichet-Emplois : deux approches hautement complémentaires
Le résultat marquant de ce livrable est la double avancée réalisée indépendamment par Hugo et Kandet sur **Guichet-Emplois**. Leurs contributions respectives résolvent les deux faces du même problème :

| Dimension de la collecte | Approche Kandet | Approche Hugo | Synergie idéale (Cible commune) |
| --- | --- | --- | --- |
| **Périmètre & Volume** | Pagination HTML exhaustive sans plafond (14 codes CNP, **191 offres**) | Recherche par bouquet de mots-clés TI + Flux Atom (**87 offres**) | Pagination complète par codes CNP (Kandet) |
| **Profondeur de données** | Niveau liste de résultats (métadonnées d'aperçu, pas de fiche détaillée) | Enrichissement fiche par fiche (Cascade RDFa Schema.org + Repli DOM) | Enrichissement systématique des fiches (Hugo) |
| **Descriptions & Contenu** | Non extrait (laissé vide pour respecter les délais réseau) | **100 % extrait** et nettoyé de tout balisage | Descriptions complètes normalisées (Hugo) |
| **Compétences TI** | Non extrait au niveau des fiches | Extraction stricte sans faux positifs (`TECH_PATTERNS`) | Module de compétences strictes de Hugo |
| **Doublons & Partenaires** | Détection multi-partenaires et fusion des doublons inter-sites | Champ `partenaire` identifié, déduplication par ID | Moteur de déduplication et traçabilité (Kandet) |
| **Dépendances** | **100 % bibliothèque standard** Python (`urllib`, `html.parser`, `dataclasses`) | Bibliothèques tierces standardisées (`requests`, `beautifulsoup4`, `pydantic`) | Modèle Pydantic partagé ou couche stdlib découplée |
| **Tests automatisés** | **33 tests unitaires** (pagination, quotas, délais, déduplication) | **6 tests unitaires** (23 assertions sur RDFa, Atom, compétences, DOM) | **56 assertions cumulées** prêtes pour l'intégration |

### Maturité logicielle en forte hausse
Par rapport aux scripts initiaux de l'Atelier 1, les deux remises fonctionnelles témoignent d'un saut qualitatif remarquable :
1. **Tests unitaires hors ligne systématiques :** 56 tests unitaires s'exécutent en moins d'une demi-seconde sans aucune dépendance au réseau, utilisant des fixtures locales (fichiers ou chaînes HTML/XML/JSON fictives).
2. **Conformité stricte :** respect scrupuleux du `crawl-delay` de 5 secondes imposé par Guichet-Emplois, gestion transparente des `User-Agent` de projet et intégration de pauses intelligentes (backoff sur HTTP 429).
3. **Architecture découplée :** séparation nette entre la récupération réseau (`collecte.py` / `fetch`), l'analyse syntaxique (`parsers.py`), la validation des données (`models.py`) et les points d'entrée (`main.py`).

### Fracture d'avancement au sein de l'équipe
L'équipe se divise désormais en trois groupes très distincts :
- **Groupe moteur (Hugo, Kandet) :** code de qualité quasi-professionnelle, entièrement testé, prêt à servir de socle partagé.
- **Groupe en phase de consolidation (Ferdinand, Elvira, Mamadou) :** prototypes L2 existants et fonctionnels, mais sans saut qualitatif en L3 à ce stade.
- **Groupe en décrochage technique (Dan, Rayan, Aymerou, Nonga, Hendrix, Mike) :** 6 étudiants sur 11 n'ont encore produit aucun script de collecte fonctionnel. Une remobilisation rapide est nécessaire avant la mise en commun globale.

---

## 4. Recommandations et plan d'action pour la suite

### 1. Fusionner les travaux sur Guichet-Emplois dans le socle commun
Plutôt que de laisser coexister deux collecteurs Guichet-Emplois séparés, l'étape suivante consiste à créer le premier module partagé à la racine du dépôt :
- Utiliser le **moteur de recherche et de pagination de Kandet** pour découvrir exhaustivement toutes les URLs d'offres TI du Québec sans doublon inter-partenaire.
- Utiliser le **moteur de parsing RDFa / DOM et d'extraction de compétences de Hugo** pour visiter et enrichir les fiches d'offres sélectionnées.
- Standardiser le modèle d'export autour du schéma `JobOffer` (Pydantic).

### 2. Actions attendues par membre

1. **Hugo & Kandet :** Collaborer à la fusion de leurs deux briques pour constituer le connecteur officiel `scrapers/guichet_emplois.py` du projet.
2. **Ferdinand :** Mettre à jour `poc_wttj.py` : extraire la ville et le pays depuis le bloc `organization`/`offices`, filtrer les offres Canada/Québec, et supprimer `os.startfile()`.
3. **Elvira & Mamadou :** Faire évoluer leurs prototypes Jobboom et Jobillico en ajoutant la pagination, une temporisation respectueuse (2 à 3 s) et des tests unitaires hors ligne inspirés de ceux de Kandet et Hugo.
4. **Dan :** Résoudre immédiatement le conflit Git dans son `README.md`, recentrer son script sur le Québec et valider ses sélecteurs avec un échantillon réel.
5. **Rayan, Aymerou, Nonga, Hendrix :**
   - Rayan peut prototyper un connecteur d'API (Adzuna ou Jooble) en utilisant la clé gratuite qu'il a identifiée.
   - Aymerou, Nonga et Hendrix doivent prendre en main l'un des prototypes existants (Jobboom, Jobillico ou le socle Guichet-Emplois) pour contribuer à l'enrichissement ou à la déduplication.
