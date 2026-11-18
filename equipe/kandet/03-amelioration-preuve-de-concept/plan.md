# Plan de travail — Livrable 3 (suite du livrable 2)

**Kandet** — 17 novembre 2026

## Point de départ

Mon prototype du livrable 2 ([`poc_multi_source.py`](../02-preuve-de-concept-scraping/poc_multi_source.py)) trouve toutes les offres TI du Québec sur le Guichet-Emplois : 191 offres sur 191 annoncées. Il ne lit que la page de résultats. Il lui manque donc :

- la description et les exigences (champ `description` vide) ;
- le vrai titre écrit par l'employeur (la liste affiche le titre CNP), donc les stages ne sont pas détectés ;
- la date d'expiration, le type d'emploi, les études et l'expérience demandées ;
- un salaire utilisable en chiffres : aujourd'hui c'est du texte (« 52 000,00 $ à 60 000,00 $ par année ») ;
- la ville et la province séparées.

Ces limites sont aussi celles relevées dans le [plan de Gregory](../../gregory/livrable3/plan.md) et dans la [synthèse du livrable 3](../../../livrables/03-amelioration-preuve-de-concept/synthese.md).

## Ce que j'ai vérifié sur les fiches (17 novembre 2026)

J'ai téléchargé 3 fiches : une publiée sur le Guichet-Emplois, une de Jobillico et une de Québec emploi. Chaque fiche contient des balises RDFa (`property="..."`), les mêmes qu'avait utilisées Mamadou :

| Propriété RDFa | Exemple | Champ prévu |
|---|---|---|
| `description` | « Tâches: Coordonner les projets… » | `description` |
| `validThrough` | `2026-12-07` | `expires_at` |
| `employmentType` | « Permanent Temps plein » | `job_type` |
| `minValue` / `maxValue` / `unitText` | `123 000` / `140 000` / `YEAR` | `salary_min`, `salary_max`, `salary_unit` |
| `addressLocality` / `addressRegion` / `postalCode` | Vaudreuil-Dorion / QC / J7V 0M7 | `city`, `province`, `postal_code` |
| `educationRequirements` | « Baccalauréat… Informatique » | `education` |
| `experienceRequirements` | « 5 ans ou plus » | `experience` |
| `specialCommitments` | « Jour, Horaire flexible » | `conditions` |

À savoir :

- **Les offres des partenaires sont moins complètes.** Pas d'études, pas d'expérience. Leur description est en HTML encodé deux fois, avec des `?` à la place des apostrophes ; le problème vient de la source.
- **Elles donnent par contre le lien vers l'annonce d'origine** (ex. `jobillico.com/fr/offre-d-emploi/nord-quantique/architecte-d-ordinateur-quantique-niveau-1/…`). Ce lien contient le vrai titre du poste.
- **Il n'y a pas de latitude/longitude sur les fiches.** Le mot « latitude » n'apparaît que dans un script qui localise le visiteur. On a seulement le code postal. Je ne vais pas inventer de coordonnées ni passer par un service externe de géocodage pour l'instant.

## Ce que je reprends des autres

| Élément | Origine | Utilisation |
|---|---|---|
| Lecture RDFa des fiches | Mamadou, Hugo (`parsers.py`) | Étape 2 |
| Liste de compétences sans faux positifs (`TECH_PATTERNS`, pas de « C » seul ni de « Vue ») | Hugo (`parsers.py`) | Étape 4 |
| Cache des fiches sur disque | Gregory (`scrapers/guichet_emplois.py`) | Étape 2 |
| Pagination par codes CNP, partenaires, déduplication | Mon livrable 2 | Gardé tel quel |

Je réécris ces idées avec la bibliothèque standard (`html.parser`), sans BeautifulSoup ni Pydantic, pour garder un prototype sans dépendance. Chaque emprunt sera cité dans la note du L3.

## Étapes

Chaque étape se termine par des tests hors ligne qui passent, un essai réel et un commit.

### Étape 1 — Découper le script en modules ✅ (17 novembre)

Le fichier faisait plus de 700 lignes. Je l'ai séparé dans ce dossier sans rien changer au fonctionnement. Le prototype du L2 reste tel quel dans `02-preuve-de-concept-scraping/`.

| Module | Contenu |
|---|---|
| `modele.py` | `SourceRecord`, `AggregatedOffer` |
| `collecte.py` | `fetch_url`, nouvel essai sur HTTP 429/503 |
| `texte.py` | nettoyage, comparaison sans accents, dates |
| `guichet.py` | codes CNP, page de résultats, pagination |
| `remotive.py` | API et cache 24 h |
| `fusion.py` | déduplication |
| `analyse.py` | stages, statistiques |
| `main.py` | options en ligne de commande |

J'ai ajouté `texte.py` et `fusion.py` par rapport à l'idée de départ : sans eux, `analyse.py` aurait tout mélangé.

Tests :
- les 33 tests du L2, répartis en un fichier par module (`test_guichet.py`, `test_remotive.py`, `test_collecte_texte.py`, `test_analyse_fusion.py`), avec les fausses pages dans `fixtures.py` ;
- 2 nouveaux tests dans `test_main.py` : une collecte complète avec réponses simulées, et `--sans-sauvegarde` qui n'écrit aucun fichier.

```powershell
python -m unittest discover -s equipe/kandet/03-amelioration-preuve-de-concept -p "test_*.py" -v
```

Résultat : 35 tests OK. Essai réel le 17 novembre : 189 offres récupérées sur 189 annoncées, 195 offres uniques avec Remotive. C'est le même comportement qu'au L2 ; ZipRecruiter apparaît maintenant parmi les sites d'origine.

### Étape 2 — Lire les fiches des offres (RDFa) avec un cache ✅ (17 novembre)

**Ce qui a été fait :**

- Nouveau module `fiches.py` : `parse_job_posting()` lit les balises RDFa, et `enrich_with_postings()` gère le cache et le délai de 5 s.
- En plus de ce qui était prévu, j'ai trouvé sur les fiches des partenaires le **titre écrit par l'employeur** (« Appellation affichée sur Jobillico - … »). Il est gardé dans `original_title`. J'ai aussi récupéré la date de début quand elle est indiquée (`start_date`).
- Le texte caché pour les lecteurs d'écran (« Ce lien ouvrira dans une nouvelle fenêtre ») est retiré du nom de l'employeur.
- Les montants du salaire sont gardés tels quels dans `source_data.posting`, pour l'étape 3.
- Dans 10 fiches, le HTML contient `Général` écrit tel quel. Ces séquences sont remplacées par le vrai caractère (« Général »).
- Quand le site répond 429 ou 503, le script l'affiche avant d'attendre 30 s : on voit qu'il attend, il n'est pas bloqué.
- Tests : 16 nouveaux tests dans `test_fiches.py`, 1 de plus dans `test_main.py` et 1 dans `test_analyse_fusion.py`. Au total, 52 tests OK.

**Essai réel du 17 novembre :**

- 188 fiches lues sur 188, aucune erreur, en environ 17 minutes.
- Relance avec le cache : 65 secondes (les 8 pages de résultats + 0 fiche à télécharger).
- Le site annonçait 189 offres, mais une a été retirée pendant la collecte (page 9 vide).

| Champ (offres du Guichet-Emplois) | L2 | Étape 2 |
|---|---|---|
| Description | 0 | 132 / 186 |
| Titre de l'employeur | 0 | 114 |
| Date d'expiration | 0 | 184 |
| Type d'emploi | 0 | 187 |
| Ville (RDFa) | 0 | 177 |
| Études, expérience, langues | 0 | 71 |
| Tâches | 0 | 55 |
| Lien vers l'annonce d'origine | 0 | 116 |

Les études, l'expérience et les langues ne sont remplies que pour les 71 offres publiées directement sur le Guichet-Emplois : les partenaires ne les donnent pas.

Description remplie selon le site d'origine :

| Site d'origine | Description remplie |
|---|---|
| Guichet-Emplois | 71 / 71 |
| Jobillico | 41 / 41 |
| JobsMedia.ca | 13 / 13 |
| Talent.com | 5 / 18 |
| Québec emploi | 2 / 40 |
| indeed.com, ZipRecruiter | 0 / 3 |

**Limites observées :**

- Pour Québec emploi, Indeed et ZipRecruiter, le Guichet-Emplois n'affiche presque jamais la description. Il renvoie seulement vers le site d'origine, dont on garde le lien. Je ne vais pas lire Québec emploi tant que ses conditions d'accès ne sont pas vérifiées.
- Les textes des partenaires contiennent des `?` à la place des apostrophes (« d?ordinateur »). L'erreur vient de la source. Je ne les remplace pas, car un `?` peut aussi être un vrai point d'interrogation.
- Unités de salaire trouvées : `YEAR` (110), `HOUR` (68), `DAY` (5), `MONTH` (3). L'étape 3 devra gérer les quatre.
- Le cache ne se périme pas. Pour relire une fiche, il faut supprimer son fichier dans `cache/fiches/`.

**Commandes :**

```powershell
# Collecte complète avec les fiches (environ 17 min la première fois, rapide ensuite grâce au cache)
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py

# Essai court sur 5 fiches
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --max-fiches 5

# Sans les fiches (comme au livrable 2)
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --sans-fiches
```

**Plan de départ de l'étape :**

- Nouvelle fonction `parse_job_posting(html)` qui lit les propriétés RDFa du tableau ci-dessus.
- Pour les partenaires : décoder le HTML encodé deux fois, garder le texte et récupérer le lien vers l'annonce d'origine (`original_url`).
- Toujours 5 s entre deux fiches. Au premier lancement, compter 191 × 5 s ≈ **16 minutes**.
- Cache dans `cache/fiches/<id>.html`, ignoré par Git. Une fiche déjà lue n'est pas redemandée, donc les lancements suivants ne téléchargent que les nouvelles offres.
- Options :
  - `--sans-fiches` pour une collecte rapide (comportement du L2) ;
  - `--max-fiches N` pour un essai court. Par défaut, **toutes** les fiches sont lues.

Tests (fixtures = vraies fiches réduites, une par type) :
- fiche du Guichet-Emplois : description, `validThrough`, salaire min/max/unité, études, expérience, code postal ;
- fiche Jobillico : HTML encodé deux fois nettoyé, lien d'origine trouvé, études et expérience vides (non devinées) ;
- fiche sans salaire ou sans date d'expiration : champs vides ;
- le cache évite l'appel réseau, et une fiche absente du cache est téléchargée puis enregistrée ;
- le délai de 5 s est respecté entre deux fiches non cachées, mais aucun délai n'est ajouté pour une fiche en cache ;
- `--max-fiches 3` ne lit que 3 fiches.

### Étape 3 — Nettoyer et séparer les champs

- **Ville et province :** depuis `addressLocality` / `addressRegion`, sinon depuis la liste (« Montréal (QC) », « Longueuil, QC »). « Différentes régions » donne une ville vide, pas inventée.
- **Salaire en chiffres :** `salary_min`, `salary_max` (nombres), `salary_unit` (`heure`, `année`, `semaine`…).
  - On ne convertit pas un taux horaire en salaire annuel : il faudrait supposer un nombre d'heures.
  - Pour Remotive (texte libre comme « $80k - $100k »), on lit les montants seulement s'ils sont clairs ; sinon on laisse vide.
- **Dates :** `published_at` et `expires_at` au format `AAAA-MM-JJ`.

Tests :
- « Montréal (QC) », « Longueuil, QC », « Différentes régions », lieu vide ;
- « 34,62 $ de l'heure », « 52 000,00 $ à 60 000,00 $ par année », « 123 000 » (espace insécable), salaire absent ;
- textes Remotive : « $80k - $100k », « Competitive », vide ;
- `validThrough` absent.

### Étape 4 — Compétences, technologies, expérience, stages

- **Technologies** (`technologies`) : liste inspirée de `TECH_PATTERNS` de Hugo (Python, Java, C#, React, SQL, Docker, AWS…), cherchée dans le titre, la description et les tags Remotive.
- **Compétences générales** (`skills`) : quelques mots repérables (soutien aux utilisateurs, réseaux, cybersécurité, bases de données, Agile…), à partir des tâches et exigences de la fiche.
- **Langues** : français, anglais, depuis la propriété `qualification`.
- **Expérience :** `experience_years_min` à partir de « 5 ans ou plus », « 1 à moins de 2 ans », « Aucune expérience ». Puis `level`, selon des règles écrites et testées :
  - débutant : 0 à 2 ans, ou « junior » ou « stagiaire » dans le titre ;
  - intermédiaire : 2 à 5 ans ;
  - avancé : plus de 5 ans, ou « senior », « lead » ou « architecte ».

  Si rien n'est indiqué, le niveau reste vide.
- **Stages :** relancer `classify_stage` sur la description complète et sur le titre de l'annonce d'origine.
- **Description courte** (`summary`) : les 2 premières phrases des tâches, 300 caractères au maximum. On coupe le texte existant, sans le réécrire ni l'inventer.

Tests :
- « C » seul, « vue d'ensemble » et « Java » dans « JavaScript » ne sont pas détectés ; « C# », « C++ », « Vue.js » le sont ;
- « 5 ans ou plus » → 5 → avancé ; « Aucune expérience » → 0 → débutant ; absent → vide ;
- « Senior » dans le titre l'emporte sur une expérience absente ;
- une description « stage rémunéré en développement » → `possible_stage` ;
- la description courte coupe à la fin d'une phrase et ne dépasse pas 300 caractères.

### Étape 5 — Statistiques sur les offres

Ajoutées au résumé de `offres.json` et à l'affichage :

- top 10 des technologies et des compétences ;
- salaires par unité : nombre d'offres, minimum, maximum et médiane, à l'heure et à l'année séparément ;
- top des villes, répartition par niveau et par type d'emploi ;
- part des champs remplis (description, salaire, expiration, études…), pour mesurer le gain par rapport au L2 ;
- offres qui expirent dans les 7 prochains jours.

Tests :
- statistiques calculées sur une petite liste d'offres préparée à la main (résultats connus d'avance) ;
- médiane avec un nombre pair et impair d'offres ;
- aucune offre avec salaire : pas d'erreur, valeurs vides.

### Étape 6 — Vérification et note du livrable 3

- Collecte complète avec fiches, puis comparaison avant/après :

  | Mesure | L2 | L3 |
  |---|---|---|
  | Description remplie | 0 % | à mesurer |
  | Stages détectés | 0 | à mesurer |
  | Salaire en chiffres | 0 % | à mesurer |
  | Date d'expiration | 0 % | à mesurer |
  | Technologies détectées | 0 | à mesurer |
- Contrôle manuel de 5 fiches : description, salaire, expiration et technologies comparés à la page du site.
- Nouvel `echantillon.json` (10 offres enrichies).
- Note `03-amelioration-preuve-de-concept/note-livrable-3.md` :
  - le site choisi ;
  - les contributions consultées avec leurs liens (Hugo, Mamadou, Gregory) ;
  - ce que j'ai repris ou modifié ;
  - les commandes ;
  - le résultat de la vérification ;
  - les limites restantes.

## Pour plus tard (après le L3)

Ce sont des pistes 3 et 4 du projet (présenter les offres, aider à la candidature). Je ne les fais pas dans le L3 pour rester centré sur la collecte :

- **Filtres en ligne de commande** : `--ville`, `--techno`, `--salaire-min`, `--niveau`, `--stages`, puis export CSV pour Excel (`utf-8-sig`).
- **Score de pertinence pour un étudiant du DEC** : règles simples et affichées (stage, niveau débutant, technologies vues au cours). Le score doit être expliqué, pas une note magique.
- **Géolocalisation** : à partir du code postal, seulement avec une source de données autorisée.
- **Remotive** : l'API publique ne donne que 14 offres, presque toutes hors Québec (télétravail Canada ou international). Elle reste une source d'appoint. Pour avoir plus d'offres québécoises hors Guichet-Emplois, Jobboom est la meilleure piste : JSON-LD sur chaque fiche, déjà testé par Elvira, Mamadou et Gregory.

## Règles que je garde

- Je travaille seulement dans `equipe/kandet/`. Les autres dossiers sont lus, jamais modifiés.
- Bibliothèque standard seulement, tests sans réseau, 5 s entre les requêtes au Guichet-Emplois, 4 appels par jour au plus à Remotive.
- Un champ absent reste vide, il n'est jamais deviné.
- Les fichiers de cache et `offres.json` ne vont pas dans Git.
