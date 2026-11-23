# Plan — Livrable 3 (Dan)

> **Rôle de ce fichier :** repère commun entre les conversations avec l'assistant IA.
> On travaille **par lot** : 1 lot = 1 conversation = 1 commit.
> **Dossier de travail :** `equipe/dan/livrable3/`
> **Début d'une conversation :** lire ce plan, puis travailler seulement sur le lot indiqué « ⏳ Prochain lot ».
> **État (2026-11-23) :** les 7 lots sont terminés et publiés (44 offres réelles dans `data/`). Lot 8 : `robots.txt` rendu optionnel à la demande du prof.

---

## 1. Objectif

1. Analyser ce que l'équipe a déjà fait en scraping : ce qui marche, les limites.
2. Choisir un **top 3 des sites** à scraper.
3. Écrire un scraper Python pour ces 3 sites, en réutilisant ce qui a déjà été testé et en ajoutant des bonifications.

Cible du projet : **stages et postes TI en début de carrière au Québec** (DEC en informatique, Collège O'Sullivan de Québec).

---

## 2. Analyse de l'existant (dépôt au 2026-11-17)

| Auteur | Site | Méthode | Résultat | Tests | Ce qui marche | Limites |
| --- | --- | --- | --- | --- | --- | --- |
| **Dan** (L2) | Guichet-Emplois | HTML, `requests` + BS4 | 25 offres QC (1 page) | Non | Filtres QC + CNP TI, délai 5 s | 1 page, pas de description, pas de site d'origine |
| **Dan** (L2) | CareerBeacon | HTML | 0 (403) | Non | Arrêt propre, aucun contournement | Bloqué par Cloudflare |
| **Kandet** | Guichet-Emplois, Remotive | HTML + pagination, API | 191 + 8 offres | 33 | Pagination complète, 14 codes CNP, site d'origine, doublons | Pas de fiches : titres CNP, pas de description |
| **Hugo** | Guichet-Emplois | Atom + HTML + RDFa | 87 offres | 6 | 100 % des descriptions, compétences sans faux positifs | Mots-clés fixes au lieu de la pagination CNP |
| **Elvira** | Jobboom | HTML + JSON-LD | 20 offres | Non | JSON-LD `JobPosting` complet | Recherche par mots-clés seulement |
| **Mamadou** (L3) | 5 sources dont Talent.com | JSON-LD, RDFa, API | 22 offres | 17 | Talent.com `@graph` + GPS, cache 24 h | `RobotFileParser` (ne comprend pas les `*`) |
| **Gregory** (démo L3) | Guichet, Jobboom, Remotive | RDFa, JSON-LD, API | 140 offres unifiées | 110 | Modèle `JobOffer`, pipeline, doublons, CSV Excel | Délais fixés dans le code, `robots.txt` non relu |

### Constats

- **Guichet-Emplois** est le site le mieux maîtrisé. La meilleure combinaison connue : pagination CNP (Kandet) + fiches RDFa (Hugo).
- **JSON-LD `JobPosting`** est la méthode la plus fiable sur Jobboom et Talent.com : données structurées, pas de sélecteurs CSS fragiles.
- **Conformité :** personne ne lit vraiment toutes les règles de `robots.txt`. `RobotFileParser` ignore les `*`, ce qui a fait mal conclure plusieurs scripts. Leçon de CareerBeacon : `robots.txt` peut permettre une page que le serveur refuse quand même (403).
- **Temps :** à 5 s par requête, lire 190 fiches prend environ 16 minutes → **cache disque** nécessaire.

Analyse détaillée de L2 : [`../03-amelioration-preuve-de-concept/note.md`](../03-amelioration-preuve-de-concept/note.md).

---

## 3. Top 3 des sites

| Rang | Site | Méthode | Pourquoi | Code repris |
| :-: | --- | --- | --- | --- |
| 1 | **Guichet-Emplois** | Pagination CNP + fiches RDFa | Mon site du L2, le plus de volume au Québec, reprend des partenaires (Jobillico, Talent.com, CareerBeacon…) | Mon POC, Kandet, Hugo |
| 2 | **Jobboom** | Catégorie TI `_i10lfr` + JSON-LD | Portail québécois, PME absentes du Guichet | Elvira, Mamadou |
| 3 | **Talent.com** | JSON-LD `@graph` (`ItemList` → `JobPosting`) | Agrégateur canadien avec GPS ; le prof l'a proposé comme 3e site possible | Mamadou |

**Plan B pour le site 3 :** si `robots.txt` de Talent.com interdit les pages visées, ou si le serveur répond 403, on passe à **Remotive** (API officielle, code de Kandet et de Gregory). Aucun contournement.

---

## 4. Décisions techniques

- **Bibliothèques :** `requests` + `beautifulsoup4` (déjà utilisées dans mon POC), listées dans `requirements.txt`. Pas de Pydantic : une `dataclass` suffit.
- **Modèle commun `Offre`** (une seule forme pour les 3 sites, champ absent = `None`, jamais deviné) :
  `id`, `source`, `source_partenaire`, `titre`, `entreprise`, `lieu`, `province`, `latitude`, `longitude`, `date_publication` (ISO), `type_poste`, `modalite`, `est_stage`, `salaire`, `description`, `competences`, `url`.
- **Bonifications de Dan :**
  1. **Vérificateur `robots.txt` complet** (règle la plus longue, `*` et `$`, `Crawl-delay` lu dans le fichier) partagé par les 3 scrapers.
  2. **Arrêt propre sur 401, 403 et 429**, avec un message clair (leçon de CareerBeacon).
  3. **Cache disque 24 h** des pages déjà lues (dans `cache/`, ignoré par Git).
- **Tests :** hors ligne seulement (fixtures HTML/JSON locales, zéro appel réseau).
- **Sorties :** `data/offres_<site>.json` par site, puis `data/offres_unifiees.json` et `.csv` (`utf-8-sig`, séparateur `;`).

Structure visée :

```
equipe/dan/livrable3/
├── plan.md
├── requirements.txt
├── outils.py              # robots.txt, délai, cache, téléchargement
├── modele.py              # dataclass Offre
├── scrapers/
│   ├── commun.py          # fonctions de texte partagées (ajouté au lot 4)
│   ├── jsonld.py          # lecture JSON-LD partagée Jobboom / Talent.com (ajouté au lot 5)
│   ├── guichet_emplois.py
│   ├── jobboom.py
│   └── talent.py          # ou remotive.py (plan B)
├── main.py                # lance les 3 scrapers + doublons + exports
├── regroupement.py        # détection et fusion des doublons (ajouté au lot 6)
├── tests/                 # tests hors ligne + fixtures/
└── data/                  # petits échantillons documentés
```

---

## 5. Lots

### Lot 1 — Analyse, top 3 et plan *(✅ Terminé)*
- [x] Lire les travaux du dépôt (Dan, Kandet, Hugo, Elvira, Mamadou, Gregory) et la synthèse du L3.
- [x] Choisir le top 3 avec un plan B.
- [x] Créer ce `plan.md`.
- [x] Ajouter la section « Scripts Python » dans [`../README.md`](../README.md).

### Lot 2 — Socle commun *(✅ Terminé)*
- [x] `requirements.txt`, `.gitignore` (`cache/`, `__pycache__/`).
- [x] `modele.py` : dataclass `Offre` + `exporter_json`, `exporter_csv`, `lire_json`.
- [x] `outils.py` : classe `Robots` (groupe qui nous nomme sinon `*`, règle la plus longue, `*`, `$`, `Crawl-delay`) et classe `Client` (`User-Agent` honnête, délai par site = max(2 s, `Crawl-delay`), exception `AccesRefuse` sur 401/403/429 et sur robots.txt refusé ou en 5xx, cache disque 24 h).
- [x] 30 tests hors ligne (`tests/test_outils.py`, `tests/test_modele.py`), dont le vrai `robots.txt` de CareerBeacon (`tests/fixtures/`). Un test prouve que `RobotFileParser` autorise à tort `?filter-salary_min=`.
- [x] Section « Scripts Python » du README mise à jour (`modele.py`, `outils.py`, commande des tests).

**Notes pour la suite**
- Un scraper crée un seul `Client()` et le réutilise : le délai et `robots.txt` sont gérés par site.
- Intercepter `AccesRefuse` par source : une source refusée s'arrête, les autres continuent.
- Choix prudent : `robots.txt` en 401/403 = arrêt (la norme RFC 9309 permettrait de tout lire).

### Lot 3 — Guichet-Emplois *(✅ Code et tests terminés — échantillon réel à produire par Dan)*
- [x] `scrapers/guichet_emplois.py` : recherche `fprov=QC` + 14 codes CNP `fn21` + `sort=D`, pagination `page` (arrêt au total annoncé, sur page vide ou après `--pages`), site d'origine (`source_partenaire`), `jsessionid` retiré, `id` = `ge-<numéro>`.
- [x] Fiches (limite `--fiches N`) : description RDFa `property="description"`, HTML encodé deux fois relu (offres partenaires), repli DOM `#job-posting-detail`. Aussi lus : entreprise, lieu, date, type de poste, salaire, modalité, stage.
- [x] Aucune valeur devinée (corrige les défauts « Non spécifié », « Québec (QC) », « Temps plein » de la démo).
- [x] 22 tests hors ligne (`tests/test_guichet_emplois.py`) + 4 fixtures HTML (`tests/fixtures/ge_*.html`, balisage de Kandet). Vérifié aussi sur les fixtures de Kandet, sans adaptation.
- [x] README : section `guichet_emplois.py` (entrée, sortie, configuration).
- [ ] **À faire par Dan** : `data/offres_guichet_emplois.json`. L'assistant n'a pas d'accès réseau ; commande à lancer depuis `equipe/dan/livrable3/` :
  `python -m scrapers.guichet_emplois --pages 1 --fiches 5`
  puis vérifier 2 offres à la main sur le site et noter le résultat ici.

**Notes pour la suite**
- `lire_resultats(html)` et `lire_fiche(html)` ne font aucun appel réseau : ce sont elles qu'on teste.
- `collecter()` ne lève pas `AccesRefuse` : elle affiche le refus et rend ce qui est déjà lu. `main.py` (lot 6) pourra donc enchaîner les sites.
- `est_stage` vaut `True` ou `None`, jamais `False` : un titre sans « stage » ne prouve pas que ce n'en est pas un.

### Lot 4 — Jobboom *(✅ Code et tests terminés — échantillon réel à produire par Dan)*
- [x] Repris de l'équipe : catégorie `_i10lfr`, cartes `div.job_item[data-url]` et exclusion `job_item_sponsorship` (Mamadou) ; JSON-LD précédé d'un bloc `Organization`, GPS, `employmentType` en liste (Elvira) ; total « 1 - 15 de 131 résultats » (Gregory).
- [x] `robots.txt` : vérifié **à l'exécution** par `outils.Client`. Personne dans l'équipe n'a noté son contenu : le relever au premier lancement et le noter ici.
- [x] `scrapers/jobboom.py` : pagination `--pages` (arrêt au total, sur page vide), ordre d'affichage, commandites, doublons et liens sans numéro exclus, `id` = `jb-<numéro>`.
- [x] Fiches `--fiches N` : JSON-LD `JobPosting` lu avec `json.loads` (objet, liste ou `@graph`, bloc invalide ignoré), description en texte propre (HTML encodé deux fois accepté), salaire, GPS, type de poste traduit, modalité seulement si `jobLocationType` = `TELECOMMUTE`, `est_stage` `True` ou `None`.
- [x] `scrapers/commun.py` : fonctions de texte sorties de `guichet_emplois.py` pour être partagées (dates, HTML → texte, stage, montants).
- [x] Correction : les balises en ligne (`<strong>`, `<a>`) ne coupent plus les phrases de la description (trouvé en testant les fixtures d'Elvira).
- [x] 20 tests hors ligne (`tests/test_jobboom.py`) + 4 fixtures (`tests/fixtures/jb_*.html`). Vérifié aussi sur les fixtures d'Elvira et de Gregory, sans adaptation.
- [x] README : sections `jobboom.py` et `commun.py`.
- [ ] **À faire par Dan** : `data/offres_jobboom.json`, depuis `equipe/dan/livrable3/` :
  `python -m scrapers.jobboom --pages 1 --fiches 5`
  puis vérifier 2 offres sur le site, et noter ici ce que dit le `robots.txt` de Jobboom.

**Notes pour la suite**
- Sur Jobboom, la liste ne donne que lien + titre : sans fiche, une offre est presque vide. Garder `--fiches` assez grand.
- `completer()` de Jobboom écrase la carte par la fiche (la fiche est plus complète) ; celui du Guichet ne comble que les trous.
- Modalité : on ne la déduit pas du texte libre (« possibilité de télétravail » ≠ télétravail).

### Lot 5 — Talent.com (ou Remotive) *(✅ Code et tests terminés — essai réel à faire par Dan)*
- [x] Ce que l'équipe sait : Talent.com **n'est pas connu comme bloqué**. Mamadou y a lu 4 vraies offres le 2026-11-16 (`/fr/view?id=<numéro>`, JSON-LD `ItemList` puis `JobPosting`, GPS, région « Quebec », `employmentType` en texte). L'inventaire commun note `robots.txt` « à vérifier » → **plan A (Talent.com)**, Remotive pas encore nécessaire.
- [x] Porte d'entrée : la 1re requête passe par `outils.Client` (robots.txt puis 401/403/429) ; en cas de refus, message clair + conseil « plan B (Remotive) », 0 offre, aucune autre tentative.
- [x] `scrapers/talent.py` : recherche `k=informatique` / `l=Québec, QC` (`--mot-cle`, `--lieu`), pagination `--pages` (paramètre `p` 🔍 non vérifié : arrêt automatique si la page 2 répète la page 1), `id` = `tc-<numéro>` seulement si l'URL contient `id=` (Mamadou fabriquait un id avec `hash()`), aucune valeur devinée (Mamadou mettait « QC » et « Temps plein » par défaut).
- [x] `scrapers/jsonld.py` : lecture JSON-LD sortie de `jobboom.py` pour être partagée ; provinces en français et en anglais (`Quebec` → `QC`).
- [x] 15 tests hors ligne (`tests/test_talent.py`), dont la porte d'entrée avec le vrai `outils.Client` et un faux `robots.txt` + 3 fixtures (`tests/fixtures/tc_*.html`). Vérifié aussi sur la fixture Talent.com de Mamadou.
- [x] README : sections `talent.py` et `jsonld.py`.
- [ ] **À faire par Dan** : essai réel depuis `equipe/dan/livrable3/` :
  `python -m scrapers.talent --pages 2 --fiches 5`
  - si le refus s'affiche (robots.txt ou 403) → le noter ici et demander le **plan B** (`scrapers/remotive.py`) ;
  - sinon : noter si `p=2` donne de nouvelles offres, vérifier 2 offres sur le site.

**Notes pour la suite**
- Limite assumée : `est_stage` ne lit pas la description. Ex. réel de Mamadou : « Technicien(ne) informatique » (OPEQ), dont la description dit « Stage rémunéré » → `None` chez nous. Lire la description donnerait des faux positifs (« aucun stage requis »). À rediscuter au lot 6 si besoin.
- Jobboom et Talent.com partagent `jsonld.champs_jobposting` : un correctif profite aux deux.

### Lot 6 — Regroupement et exports *(✅ Code et tests terminés — exécution réelle à faire par Dan)*
- [x] `main.py` : lance `guichet`, `jobboom`, `talent` avec un seul `Client` (délais par site) ; options `--sites`, `--pages`, `--fiches`, `--sans-cache`, `--csv`, `--dossier`. Une source refusée ou en erreur n'arrête pas les autres ; résumé par source (offres, descriptions, statut) ; code de sortie 1 si aucune offre.
- [x] `regroupement.py` : doublon = même `id`, ou même empreinte titre + entreprise + ville (sans accents, majuscules, ponctuation ; titre avant `/`, entreprise sans « inc. », ville sans province ni « City ») **et** diffuseurs différents. Diffuseur = (source, `source_partenaire`) : une offre Talent.com reprise par le Guichet se fusionne avec celle de Talent.com ; deux offres d'un même diffuseur aux numéros différents restent séparées (règle reprise de la démo de Gregory).
- [x] Fusion : offre la plus complète gardée (1re à égalité), seuls ses champs vides sont comblés, `source_partenaire` jamais recopié, compétences réunies, `id` fusionnés dans le nouveau champ `Offre.doublons`.
- [x] Exports : `data/offres_unifiees.json` et `.csv` toujours ; un JSON par source (CSV aussi avec `--csv`).
- [x] 20 tests hors ligne (`tests/test_regroupement.py`) : normalisation, fusion, règle du diffuseur, chaîne de 3 sources, `main.py` avec faux scrapers (une source en erreur), et un test **de bout en bout** avec les 3 vrais scrapers sur les fixtures des lots 3 à 5.
- [x] README : sections `main.py` et `regroupement.py`, champ `doublons` dans `modele.py`.
- [ ] **À faire par Dan** : depuis `equipe/dan/livrable3/` : `python main.py --pages 1 --fiches 5 --csv`, garder la sortie du résumé pour le compte rendu, vérifier à la main 1 doublon signalé (« doublon : … = … »).

**Notes pour la suite**
- Le nombre de doublons réels dépend des fiches ouvertes : sur Jobboom et Talent.com, une offre sans fiche n'a ni entreprise ni ville, donc pas d'empreinte. Ouvrir plus de fiches = plus de doublons détectés.
- Règle volontairement prudente : mieux vaut un doublon oublié qu'une fusion de deux postes différents.

### Lot 7 — Compte rendu et démo *(✅ Terminé — résultats réels à compléter par Dan)*
- [x] [`compte-rendu.md`](compte-rendu.md) selon l'énoncé du L3 : sites choisis (top 3, plan B, CareerBeacon écarté), 7 contributions consultées avec liens, briques réutilisées, améliorations, commandes, vérification (107 tests, vérification croisée sur les fixtures de Kandet, Elvira, Gregory et Mamadou, bugs corrigés), avant/après, limites et suites.
- [x] Déroulé de démo de 5 minutes (section 9 du compte rendu).
- [x] Vérifications : 107 tests OK, 55 liens relatifs vérifiés (0 cassé), README final (lien vers le compte rendu, Python 3.12+).
- [ ] **À faire par Dan** : lancer `python main.py --pages 1 --fiches 5 --csv`, remplir la section 6.4 et la ligne « Offres » de la section 7, puis ajouter le lien du commit en haut du compte rendu.

### Lot 8 — `robots.txt` optionnel *(✅ Terminé, 2026-11-23)*
Remarque du prof : la vérification de `robots.txt` n'est pas nécessaire. Option A retenue : la garder, mais désactivée par défaut.
- [x] `outils.py` : `Client(respecter_robots=False)` par défaut ; plus aucune requête vers `robots.txt` sans l'option.
- [x] Délais fixes par site : `DELAIS_PAR_SITE` (Guichet-Emplois 5 s, valeur de son `Crawl-delay` ; Jobboom et Talent.com 2 s), argument `delais=` de `Client`.
- [x] Gardés dans les deux modes : `User-Agent` honnête, cache 24 h, arrêt propre sur 401/403/429.
- [x] Option `--respecter-robots` dans `main.py` et les 3 scrapers : réactive la classe `Robots` (RFC 9309) et le `Crawl-delay` s'il est plus grand.
- [x] Tests : 114 OK (`test_outils` 31, `test_talent` 16, `test_regroupement` 21) ; les tests `robots.txt` passent en mode `respecter_robots=True`.
- [x] README (section `outils.py` et options), compte rendu (sections 4, 6.1, 7, 9) mis à jour.

### Lot 9 — Bug « `, QC` » et résultats réels *(✅ Terminé, 2026-11-23)*
- [x] `guichet_emplois.lire_fiche` : région nettoyée (« `, QC` » → `QC`) avec `jsonld.province` ; texte non reconnu → `None`. 1 test (4 cas).
- [x] Compte rendu : section 6.4 (exécution du 2026-11-18 : 25 + 15 + 5 = 44 uniques, 1 doublon), section 7, limites, lien du commit `ba6f982`.
- [ ] **À faire par Dan** : relancer `python main.py --pages 1 --fiches 5 --csv` pour corriger la province dans `data/` ; vérifier 2 offres par site.

### Lot 10 — Compétences et format commun *(✅ Terminé, 2026-11-23)*
- [x] [`competences.py`](competences.py) : `detecter_competences` (motifs de Hugo et du prof, 2 faux positifs hérités corrigés, ajouts support TI) et `statut_stage` (3 valeurs du prof). `main.py` remplit `competences` et l'affiche dans le résumé. 12 tests.
- [x] [`../format-commun/convertir.py`](../format-commun/convertir.py) : `offres_unifiees.json` → `JobOffer` du prof (18 champs, rien de deviné, province nettoyée). 10 tests, dont la validation par le vrai modèle `JobOffer`.
- [x] Sur les vraies données : 10 offres avec compétences (sur 14 avec description), 1 stage possible ; 44/44 offres validées par `JobOffer`.
- [x] README (2 nouvelles sections), compte rendu (sections 4, 6.1, 6.4, 7, 8).

---

## Livrable 3 terminé (côté code)

**Reste à faire par Dan, dans cet ordre :**
1. Remplacer le dossier `equipe/dan/` par la nouvelle version (lots 8 à 10), lancer les tests (127 OK dans `livrable3/`, 10 OK dans `format-commun/`).
2. Relancer `python main.py --pages 1 --fiches 5 --csv` depuis `equipe/dan/livrable3/` (province corrigée et compétences dans `data/`), puis `python convertir.py --csv --echantillon 5` depuis `equipe/dan/format-commun/`.
3. Vérifier 2 offres par site à la main ; si Talent.com refuse (403/429) → demander le plan B (Remotive).
4. Commit et push.

---

## 6. Suivi

| Lot | Statut | Fichiers | Tests |
| --- | --- | --- | --- |
| 1 — Analyse et plan | ✅ | `plan.md`, `../README.md` | — |
| 2 — Socle commun | ✅ | `outils.py`, `modele.py` | 30 OK (0,01 s) |
| 3 — Guichet-Emplois | ✅ (échantillon à produire) | `scrapers/guichet_emplois.py` | 52 OK au total (0,09 s) |
| 4 — Jobboom | ✅ (échantillon à produire) | `scrapers/jobboom.py`, `scrapers/commun.py` | 72 OK au total (0,10 s) |
| 5 — Talent.com / Remotive | ✅ (essai réel à faire) | `scrapers/talent.py`, `scrapers/jsonld.py` | 87 OK au total (0,11 s) |
| 6 — Regroupement | ✅ (exécution réelle à faire) | `main.py`, `regroupement.py` | 107 OK au total (0,12 s) |
| 7 — Compte rendu | ✅ (résultats réels à compléter) | `compte-rendu.md` | 107 OK, 55 liens OK |
| 8 — `robots.txt` optionnel | ✅ | `outils.py`, `main.py`, 3 scrapers | 114 OK au total |
| 9 — Bug « `, QC` », résultats réels | ✅ | `scrapers/guichet_emplois.py`, `compte-rendu.md` | 115 OK au total |
| 10 — Compétences, format commun | ✅ | `competences.py`, `../format-commun/` | 127 + 10 OK |

---

## 7. Fin d'un lot

1. Lancer tous les tests :
   `python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py" -v`
2. Mettre à jour ce plan (cases cochées, statut, tableau de suivi).
3. Mettre à jour la section « Scripts Python » du README si un script a changé.
4. Commit : `feat(dan-livrable3): Lot N - <résumé>`.
5. Écrire le prompt du lot suivant.
