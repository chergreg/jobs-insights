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
- Dans 10 fiches, le HTML contient des séquences d'échappement Unicode écrites telles quelles : une barre oblique inverse suivie de `u00E9` au lieu de « é ». Ces séquences sont remplacées par le vrai caractère (« Général »).
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

### Étape 3 — Nettoyer et séparer les champs ✅ (17 novembre)

**Ce qui a été fait :**

- Nouveau module `normalisation.py` :
  - `split_location()` sépare la ville et la province ;
  - `parse_amount()` et `parse_salary_text()` lisent les montants ;
  - `normalize_record()` applique tout à chaque annonce, juste avant la fusion des doublons.
- Nouveaux champs :
  - `salary_min` et `salary_max` (nombres) ;
  - `salary_unit` : heure, jour, semaine, mois ou année ;
  - `salary_currency` : `CAD` pour le Guichet-Emplois, vide pour Remotive, où la devise n'est pas écrite ;
  - `salary_negotiable` : vrai si le salaire est « à négocier ».
- Pour le Guichet-Emplois, le salaire vient des balises RDFa de la fiche. Sans fiche, il est lu dans le texte de la liste.
- Lors d'une fusion, les champs du salaire sont copiés ensemble depuis la même annonce, pour ne pas mélanger le montant d'une annonce et l'unité d'une autre.
- Tests : 18 nouveaux tests dans `test_normalisation.py`. Au total, 70 tests OK.
- Un de ces tests a d'abord échoué à cause d'une erreur dans le test lui-même : deux annonces avaient le même lien. Corrigé.

**Vérification sur les vraies données (17 novembre) :**

- Pour les 188 offres, j'ai comparé le salaire lu dans le texte de la liste avec celui des balises RDFa de la fiche : **0 différence**.
- Salaire en chiffres pour les 186 offres du Guichet-Emplois. Côté Remotive, 3 offres sur 8 : les 5 autres n'indiquent pas de salaire.
- Unités : année (110), heure (68), jour (5), mois (4). L'unité reste vide pour 2 offres Remotive (`$170k - $200k`, `70K-80K`) : elle n'est pas devinée.
- Ville et province pour 179 offres du Guichet-Emplois. Les 7 autres sont « Différentes régions » ou « Lieu de travail indéterminé » et restent vides.
- 32 salaires « à négocier ».

**Limites :**

- On ne convertit pas un taux horaire, journalier ou mensuel en salaire annuel. Les statistiques de l'étape 5 seront donc faites unité par unité.
- Les montants Remotive peuvent être en dollars américains. La devise reste vide parce qu'elle n'est pas écrite.

**Plan de départ de l'étape :**

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

### Étape 4 — Compétences, technologies, expérience, stages ✅ (17 novembre)

**Ce qui a été fait :**

- Nouveau module `competences.py`, appliqué à chaque offre après la fusion des doublons :
  - `technologies` : 51 technologies. La liste reprend l'idée de `TECH_PATTERNS` de Hugo et l'élargit à ce qu'on voit dans nos offres (.NET, Active Directory, SharePoint, Power BI, SAP…).
  - `skills` : 14 compétences générales (soutien aux utilisateurs, réseaux, cybersécurité, bases de données, Agile / Scrum…).
  - `experience_years_min` : lu dans le champ du Guichet-Emplois (« 5 ans ou plus », « 7 mois à moins d'un an »), sinon dans la description (« minimum de 3 ans d'expérience », « 5+ years of experience »).
  - `level` : débutant (moins de 2 ans), intermédiaire (2 à moins de 5 ans), avancé (5 ans et plus). Un mot du titre (junior, stagiaire, senior, lead, architecte) l'emporte sur les années. Sans information, le niveau reste vide.
  - `summary` : les 2 premières tâches, ou les 2 premières phrases de la description, 300 caractères au maximum. Le texte est coupé, jamais réécrit. Le titre répété au début de la description est retiré.
  - Stages : le champ « Stage: Ce poste est un stage… » écrit par le Guichet-Emplois donne un stage confirmé. Sinon, `classify_stage` est appliqué au vrai titre de l'employeur et à la description.
- Correction dans `fiches.py` : les entités encodées deux fois (`&amp;`) sont décodées.
- Tests : 22 nouveaux tests dans `test_competences.py` et 1 dans `test_fiches.py`. Au total, 92 tests OK.

**Essai réel du 17 novembre (194 offres) :**

| Champ | Offres |
|---|---|
| Technologies détectées | 83 |
| Compétences générales | 112 |
| Années d'expérience | 81 |
| Niveau | 124 (avancé 63, intermédiaire 34, débutant 27) |
| Description courte | 140 |
| Stage confirmé | 1 |

- Technologies les plus demandées : SQL (32), JavaScript (21), Windows (19), HTML/CSS (19), Azure (18), Python (18), Git (16), Jira (16), .NET (15), React (13).
- Vérification à la main des détections les plus risquées (Windows, Oracle, SAP, Swift, Rust, Cisco, Git, Java) : le texte autour de chaque détection confirme qu'il s'agit bien de la technologie.

**Limites :**

- Un seul stage sur 194 offres. Le Guichet-Emplois publie très peu de stages en TI au Québec, et les descriptions de Québec emploi ne sont pas disponibles.
- Les technologies sont trouvées seulement si elles sont écrites. Les 54 offres du Guichet-Emplois sans description en ont rarement.
- Le niveau est une règle simple. « Architecte » dans un titre CNP donne « avancé », même si l'offre ne le précise pas.

**Plan de départ de l'étape :**

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

### Étape 5 — Statistiques sur les offres ✅ (17 novembre)

**Ce qui a été fait :**

- `analyse.py` calcule maintenant, dans le résumé de `offres.json` et à l'affichage :
  - le top 10 des technologies, des compétences et des villes ;
  - les niveaux et les types d'emploi ;
  - les salaires par devise et par unité ;
  - les offres qui expirent dans les 7 jours ;
  - le nombre d'offres où chaque champ est rempli.
- Salaires : pour chaque groupe (ex. « CAD / année »), le nombre d'offres, le plus bas, le plus haut et la médiane de la valeur basse.
  - On ne mélange jamais les unités ni les devises.
  - Un salaire sans unité (ex. `$170k - $200k`) n'entre pas dans le tableau des salaires, parce qu'on ne sait pas si c'est par année ou par heure. L'offre, elle, reste comptée partout ailleurs, et son montant est gardé dans `offres.json`.
- La date du jour est un paramètre de `build_summary()`, pour que les tests donnent toujours le même résultat.
- Tests : 10 nouveaux tests dans `test_statistiques.py` (médiane paire et impaire, unités séparées, aucune offre avec salaire, expirations, liste vide). Au total, 102 tests OK.

**Résultats du 17 novembre (194 offres) :**

| Salaire | Offres | Médiane (valeur basse) | Plus bas | Plus haut |
|---|---|---|---|---|
| CAD / année | 111 | 70 000 $ | 42 000 $ | 230 000 $ |
| CAD / heure | 68 | 36 $ | 19 $ | 105 $ |
| CAD / jour | 4 | 118 $ | 101 $ | 135 $ |
| CAD / mois | 3 | 10 000 $ | 4 337 $ | 10 000 $ |

- Top villes : Montréal (50), Brossard (39), Québec (20), Sherbrooke (13), Saint-Laurent (6).
- Top compétences : réseaux (25), soutien aux utilisateurs (23), bases de données (23), DevOps (19), développement Web (17).
- 71 offres expirent d'ici le 24 novembre. J'ai vérifié que ce sont bien les dates des fiches : par exemple, les 18 offres Talent.com et 15 offres de Fop experts conseils expirent toutes cette semaine.

**Limites :**

- Brossard arrive 2e seulement à cause d'une firme de recrutement (Fop experts conseils) qui publie beaucoup d'offres. Les statistiques comptent des offres, pas des employeurs.
- La médiane porte sur la valeur basse de chaque fourchette. C'est un choix simple : il n'y a pas de « vrai » salaire moyen pour une fourchette.

**Plan de départ de l'étape :**

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

### Étape 6 — Vérification et note du livrable 3 ✅ (17 novembre)

La note est dans [`note-livrable-3.md`](note-livrable-3.md). Elle contient :
- le tableau avant/après ;
- le contrôle de 5 fiches en ligne, toutes correctes ;
- les liens vers les contributions consultées et vers les commits ;
- les limites qui restent.

J'y ai aussi vérifié le paramètre `fsrc=16` du plan de Mamadou : c'est un filtre de source (offres publiées sur le Guichet-Emplois), pas un filtre de stages.

**Plan de départ de l'étape :**

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

- **Filtres en ligne de commande et export CSV ✅ (17 novembre)** :
  - modules `filtres.py` (`--ville`, `--techno`, `--niveau`, `--stages`, `--salaire-min` avec `--unite-salaire`, `--employeur`) et `export.py` (`--csv` en `utf-8-sig` avec `;` pour Excel) ;
  - `--depuis offres.json` filtre une collecte déjà faite sans Internet ;
  - 16 nouveaux tests dans `test_filtres_export.py` ; au total, 118 tests OK ;
  - le guide « Tester le projet » est au début de `note-livrable-3.md`.
- **Région administrative ✅ (17 novembre)** :
  - essai d'abord : 178 des 179 villes de nos offres sont retrouvées dans le Répertoire des municipalités du Québec (MAMH, CC-BY 4.0), aucune n'est ambiguë ;
  - ajout ensuite : module `regions.py`, fichier `regions_quebec.csv` (3 colonnes, sans données personnelles), script `preparer_regions.py`, filtre `--region`, colonne `region` dans le CSV ;
  - 11 nouveaux tests dans `test_regions.py` ; au total, 129 tests OK.
- **Page de recherche HTML ✅ (17 novembre)** :
  - essai d'abord : prototype dans un dossier temporaire, ouvert dans Edge sans fenêtre. Mêmes résultats que les filtres de `main.py`, clics testés (afficher plus, région puis ville, export CSV, effacer), captures sur ordinateur, téléphone et mode sombre ;
  - ajout ensuite : `interface.py`, `interface_modele.html`, option `--html` ;
  - 11 nouveaux tests dans `test_interface.py` ; au total, 140 tests OK.
- **Aide à la candidature (piste 4) ✅ (20 novembre)** :
  - essai d'abord, avec deux CV fictifs sur les 195 offres. Trois défauts de la règle de note trouvés et corrigés (nombre de technologies en commun, niveau trop élevé, offres avec trop peu d'information). La lecture d'un vrai `.docx` créé par Word a été vérifiée ;
  - ajout ensuite : `candidature.py`, `cv-exemple.txt` (fictif), options `--cv`, `--nb-offres` et `--rapport-cv` ;
  - 21 nouveaux tests dans `test_candidature.py` ; au total, 161 tests OK.
- **CV dans la page et lettre de motivation ✅ (20 novembre)** :
  - essai d'abord : mêmes notes en JavaScript et en Python (0 différence sur 3 CV × 195 offres), lecture d'un vrai `.docx` dans Edge, lettre fictive testée. Deux défauts de la lettre corrigés (employeur et titre déclarés cités à tort) ;
  - ajout ensuite : `interface_cv.js` et panneau « Comparer avec mon CV » dans `offres.html`, `lettre.py`, `lettre-exemple.txt`, options `--lettre`, `--offre` et `--rapport-lettre` ;
  - nouveaux tests : `test_lettre.py` et `test_interface_cv.py` (comparaison avec Node.js) ; au total, 178 tests OK.
- **Lettre dans la page ✅ (20 novembre)** :
  - essai d'abord : 780 cas sur 780 identiques entre JavaScript et `lettre.py` (4 lettres × 195 offres, avec et sans CV) ;
  - ajout ensuite : bouton « Vérifier ma lettre pour cette offre » et fenêtre de vérification dans `offres.html`. Les listes de mots de `lettre.py` sont copiées dans la page ;
  - test Node.js de la lettre, renforcé après avoir constaté qu'il ne voyait pas un changement de règle ; au total, 179 tests OK.
- **Descriptions de Québec emploi ❌ (vérifié le 17 novembre)** : techniquement possible (JSON-LD `JobPosting`, `robots.txt` permissif), mais interdit par les conditions d'utilisation du site. Non ajouté.
- **Score de pertinence pour un étudiant du DEC** : règles simples et affichées (stage, niveau débutant, technologies vues au cours). Le score doit être expliqué, pas une note magique.
- **Géolocalisation** : à partir du code postal, seulement avec une source de données autorisée.
- **Remotive** : l'API publique ne donne que 14 offres, presque toutes hors Québec (télétravail Canada ou international). Elle reste une source d'appoint. Pour avoir plus d'offres québécoises hors Guichet-Emplois, Jobboom est la meilleure piste : JSON-LD sur chaque fiche, déjà testé par Elvira, Mamadou et Gregory.

## Règles que je garde

- Je travaille seulement dans `equipe/kandet/`. Les autres dossiers sont lus, jamais modifiés.
- Bibliothèque standard seulement, tests sans réseau, 5 s entre les requêtes au Guichet-Emplois, 4 appels par jour au plus à Remotive.
- Un champ absent reste vide, il n'est jamais deviné.
- Les fichiers de cache et `offres.json` ne vont pas dans Git.
