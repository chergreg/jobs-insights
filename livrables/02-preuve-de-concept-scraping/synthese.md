# Synthèse — Livrable 2 : Preuve de concept de scraping

Bilan établi après lecture des prototypes, sorties collectées et notes techniques déposés par l’équipe (voir l’énoncé dans [`enonce.md`](enonce.md) et le référentiel des sources dans [`inventaire.md`](../01-inventaire-des-sites/inventaire.md)).

---

## 1. Tableau synthèse des remises

Sur les **11 étudiants** inscrits dans [`equipe/equipe.md`](../../equipe/equipe.md) (5 prototypes fonctionnels, 1 partiel, 5 non faits) :

| Étudiant | Statut | Sources testées | Approche technique | Sortie déposée | Compte rendu | Dossier L2 |
| --- | --- | --- | --- | --- | --- | --- |
| **Kandet** | ✅ Fait | Guichet-Emplois, Remotive | Atom XML + API JSON (`stdlib`) | — (23 tests unitaires) | Dans `sites.md` | [`02-preuve-de-concept-scraping`](../../equipe/kandet/02-preuve-de-concept-scraping) |
| **Hugo** | ✅ Fait | Guichet-Emplois | HTML SSR + fiches (Pydantic) | 87 offres (JSON) | Dans `README.md` | [`02-preuve-de-concept-scraping`](../../equipe/hugo/02-preuve-de-concept-scraping) |
| **Mamadou** | ✅ Fait | Talent.com, Jobboom, Guichet-Emplois, Jobillico | JSON-LD + RDFa (`stdlib`) | 10 offres (JSON) | Dans `README.md` / `sites.md` | [`02-preuve-de-concept-scraping`](../../equipe/mamadou/02-preuve-de-concept-scraping) |
| **Elvira** | ✅ Fait | Jobboom | HTML SSR + JSON-LD (`BS4`) | 5 offres (JSON) | Dans `sites.md` | [`02-preuve-de-concept-scraping`](../../equipe/elvira/02-preuve-de-concept-scraping) |
| **Ferdinand** | ✅ Fait | Welcome to the Jungle | API JSON publique (`requests`) | 30 offres (CSV) + 1 JSON | Sommaire (`sites.md`) | [`02-preuve-de-concept-scraping`](../../equipe/ferdinand/02-preuve-de-concept-scraping) |
| **Dan** | ⚠️ Partiel | Guichet-Emplois (Moncton) | HTML CSS (`BS4`, non vérifié) | Aucune | Absent | [`02-preuve-de-concept-scraping`](../../equipe/dan/02-preuve-de-concept-scraping) |
| **Rayan** | ❌ Non fait | — | — | — | Absent | — |
| **Aymerou** | ❌ Non fait | — | — | — | Absent | — |
| **Nonga** | ❌ Non fait | — | — | — | Absent | — |
| **Hendrix** | ❌ Non fait | — | — | — | Absent | — |
| **Mike** | ❌ Non fait | — | — | — | Absent | — |

Tous les prototypes et fichiers de sortie existants ont été déplacés dans le sous-dossier dédié `equipe/<membre>/02-preuve-de-concept-scraping/` (à l’image de `01-inventaire-des-sites/` pour le Livrable 1).

---

## 2. Fiches par remise

### Kandet (`✅ Fait`)
- **Code :** [`poc_multi_source.py`](../../equipe/kandet/02-preuve-de-concept-scraping/poc_multi_source.py) et [`test_poc_multi_source.py`](../../equipe/kandet/02-preuve-de-concept-scraping/test_poc_multi_source.py) (bibliothèque standard Python uniquement, aucune dépendance externe).
- **Sources testées :**
  - **Guichet-Emplois / Job Bank** via le flux Atom (`https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed`, codes CNP `21230`, `21232`, `21234`, filtrage province `QC`, pagination complète).
  - **Remotive** via l’API JSON publique (`https://remotive.com/api/remote-jobs`, filtrage local sur 10 catégories TI et option `--canada-remotive-only`).
- **Points forts :**
  - Respecte explicitement la conformité : `User-Agent` transparent (`jobs-insights-atelier/1.0`), `crawl-delay` de **5 s** sur Guichet-Emplois et cache local 24 h (`remotive-cache.json`) pour respecter la limite de 4 requêtes/jour sur Remotive.
  - Modèle typé (`SourceRecord` et `AggregatedOffer` via `dataclasses`), déduplication intra-source (par `source_id` ou URL) et inter-source (`titre` + `employeur` + `lieu` normalisés), et classification des stages (`confirmed_stage`, `possible_stage`, `not_indicated`) avec test d’exclusion des simples mentions d’expérience passée.
  - **23 tests unitaires hors ligne** (fixtures XML/JSON et mocks) qui passent tous (`python -m unittest discover -s equipe/kandet/02-preuve-de-concept-scraping -p "test_*.py" -v`).
- **À noter / limites :**
  - La documentation du prototype (commandes, fonctionnement, limites entre résumé Atom et description complète Remotive) est encore logée dans [`equipe/kandet/01-inventaire-des-sites/sites.md`](../../equipe/kandet/01-inventaire-des-sites/sites.md) au lieu d’un compte rendu dédié dans `02-preuve-de-concept-scraping/`.
  - Aucun fichier JSON de sortie réelle (`offres.json`) n’est commité dans le dépôt (export conservé localement).

### Hugo (`✅ Fait`)
- **Code :** [`main.py`](../../equipe/hugo/02-preuve-de-concept-scraping/main.py), [`poc_emploi_canada.py`](../../equipe/hugo/02-preuve-de-concept-scraping/poc_emploi_canada.py), [`models.py`](../../equipe/hugo/02-preuve-de-concept-scraping/models.py) (modèle Pydantic `JobOffer`) et [`requirements.txt`](../../equipe/hugo/02-preuve-de-concept-scraping/requirements.txt) (`requests`, `beautifulsoup4`, `pydantic`).
- **Source testée :** **Guichet-Emplois Canada** (`https://www.guichetemplois.gc.ca/jobsearch/jobsearch`, pagination `/jobsearch/job_search_loader.xhtml`, puis visite de chaque fiche pour la modalité et les mots-clés techniques).
- **Données récupérées :**
  - Trois jeux JSON déposés dans `data/` : `offres_test.json` (5 offres), `offres_details_test.json` (3 offres) et [`offres_emploi_canada.json`](../../equipe/hugo/02-preuve-de-concept-scraping/data/offres_emploi_canada.json) (**87 offres uniques** au Québec : 85 temps plein, 2 stages ; 68 sur place, 19 hybrides).
  - Répartition vérifiée des partenaires dans cet échantillon : `Guichet-Emplois` (32), `Jobillico` (20), `Québec emploi` (15), `Talent.com` (11), `JobsMedia.ca` (6), `indeed.com` (2), `CareerBeacon` (1).
- **Points de vigilance / limites :**
  - Auto-installation `pip` exécutée dès l’import (`verifier_et_installer_dependances()`), script interactif bloquant sur `input()` (menu et pause finale), et absence de tests unitaires hors ligne.
  - Rotation de `User-Agent` de navigateurs et pauses aléatoires de `1,0` à `2,2 s` (inférieures au `crawl-delay` de 5 s de Guichet-Emplois, bien qu’une pause de 6 s soit prévue sur `HTTP 429`), sans lecture de `robots.txt`.
  - Appel à `job_search_loader.xhtml` sans paramètre de page (dépendant de la session), champ `description` toujours `null` dans les 87 offres, et faux positifs fréquents dans `competences_cles` sur le texte complet de la page (`"C"` détecté dans 26/87 offres, `"VUE"` dans 14/87).
  - Documentation dans [`equipe/hugo/README.md`](../../equipe/hugo/README.md) sans section dédiée aux difficultés ou limites observées.

### Mamadou (`✅ Fait`)
- **Code :** [`poc_scrapers_atelier1.py`](../../equipe/mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py) (bibliothèque standard Python uniquement : `urllib.request`, `json`, `re`, `html`, `pathlib`).
- **Sources testées (4 sites dans un seul script) :**
  - **Talent.com Canada** (`ca.talent.com/fr/jobs`) : double JSON-LD `@graph` (`ItemList` -> `JobPosting`) + coordonnées GPS (`lat`/`lon`).
  - **Jobboom Québec** (`jobboom.com/fr/technologies-medias-numeriques/_i10lfr`) : extraction des liens `data-url` + JSON-LD `JobPosting`.
  - **Guichet-Emplois Canada** (`guichetemplois.gc.ca/jobsearch/rechercheemplois`, `mid=22447`) : IDs dans les liens + balises RDFa (`property="..."`).
  - **Jobillico Québec** (`jobillico.com/recherche-emploi`) : liens d’offres + JSON-LD `JobPosting`.
- **Données récupérées :** [`sample_scraped_jobs.json`](../../equipe/mamadou/02-preuve-de-concept-scraping/sample_scraped_jobs.json) contenant **10 offres réelles** (3 Talent.com, 3 Jobboom, 2 Guichet-Emplois, 2 Jobillico).
- **Points de vigilance / limites :**
  - Aucun délai (`time.sleep`) entre les requêtes ni vérification de `robots.txt` (alors que Guichet-Emplois impose 5 s et que Jobillico restreint certaines URL de recherche), avec un `User-Agent` Firefox simulé.
  - Parsing HTML effectué par expressions régulières plutôt qu’avec un parseur HTML (`html.parser` / `BeautifulSoup`) : dans l’échantillon Guichet-Emplois, une description conserve des balises `<p>`/`<strong>` tronquées au premier `</div>` et des artefacts d’encodage (`?`) venant de la source.
  - Schéma JSON variable selon la source (`gps` sur Talent.com seulement, `valid_through` sur Jobboom seulement) ; pas de tests unitaires ; compte rendu réparti entre [`equipe/mamadou/README.md`](../../equipe/mamadou/README.md) et [`equipe/mamadou/01-inventaire-des-sites/sites.md`](../../equipe/mamadou/01-inventaire-des-sites/sites.md).

### Elvira (`✅ Fait`)
- **Code :** [`Scraper.py`](../../equipe/elvira/02-preuve-de-concept-scraping/Scraper.py) (`requests` + `BeautifulSoup`).
- **Source testée :** **Jobboom** (`https://www.jobboom.com/fr/emploi/informatique/_lfrk?dk=informatique`), extraction des liens `/offre-emploi/` sur la 1re page puis lecture du bloc JSON-LD `@type: "JobPosting"` sur 5 fiches.
- **Données récupérées :** [`offres_jobboom.json`](../../equipe/elvira/02-preuve-de-concept-scraping/offres_jobboom.json) contenant **5 offres complètes** (4 à Montréal, 1 à Boucherville, publiées entre `2023-10-25` et `2026-10-07`) avec `titre`, `entreprise`, `date_publication`, `url` et `raw_json_ld` complet.
- **Points de vigilance / limites :**
  - Pas de `requirements.txt` dans son dossier (dépendances documentées uniquement dans `sites.md`).
  - L’usage d’un `set` pour collecter les URLs rend l’ordre des 5 offres non déterministe ; aucune pagination ; descriptions conservées en HTML brut ; `User-Agent` Chrome simulé et pause de `1 s` sans vérification du `robots.txt` / CGU de Jobboom ; pas de tests unitaires.
  - Compte rendu détaillé (analyse DevTools SSR/JSON-LD et commande `py Scraper.py`) présent dans [`equipe/elvira/01-inventaire-des-sites/sites.md`](../../equipe/elvira/01-inventaire-des-sites/sites.md), mais avec échappements Markdown (`\#`, `\*`, `\-`) et sans bilan des limites propres à Jobboom.

### Ferdinand (`✅ Fait`)
- **Code :** [`poc_wttj.py`](../../equipe/ferdinand/02-preuve-de-concept-scraping/poc_wttj.py) (`requests` + `csv` en `utf-8-sig` avec séparateur `;`).
- **Source testée :** **Welcome to the Jungle** via l’API JSON publique `https://api.welcometothejungle.com/api/v3/public/jobs` (mot-clé `"stage data"`, `MAX_PAGES = 3`).
- **Données récupérées :** [`reponse_wttj.json`](../../equipe/ferdinand/02-preuve-de-concept-scraping/reponse_wttj.json) (1 offre brute d’exemple) et [`offres_wttj.csv`](../../equipe/ferdinand/02-preuve-de-concept-scraping/offres_wttj.csv) (**30 offres** : 21 `full_time`, 9 `internship`).
- **Points de vigilance / limites :**
  - **Hors cible Québec :** la quasi-totalité des 30 offres exportées se situent en Europe ou aux États-Unis (Paris, Bruz, Barcelone, Londres, Boston…) et **le CSV n’extrait pas la ville ni le pays**, pourtant présents dans `office` / `offices` du JSON.
  - Écart entre la note de [`equipe/ferdinand/01-inventaire-des-sites/sites.md`](../../equipe/ferdinand/01-inventaire-des-sites/sites.md) (qui mentionne Algolia) et le script qui interroge `/api/v3/public/jobs`.
  - Absence de `requirements.txt`, pas de `raise_for_status()` avant `.json()`, `User-Agent` générique (`Mozilla/5.0`), et appel à `os.startfile(FICHIER)` spécifique à Windows en fin de script.
  - Compte rendu dans `sites.md` très succinct : pas de commande d’exécution, pas de dépendances listées, pas d’exemple ni de limites, et lignes de modèle non tranchées (`oui / non`).

### Dan (`⚠️ Partiel`)
- **Code :** [`Poc guichetemploi.py`](../../equipe/dan/02-preuve-de-concept-scraping/Poc%20guichetemploi.py) (`requests`, `BeautifulSoup`, `RobotFileParser`, `csv`).
- **Source visée :** **Guichet-Emplois** (`https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois`), recherche par défaut `"technicien"` à `"Moncton, NB"`.
- **Points positifs d’intention :** vérifie `robots.txt` via `RobotFileParser`, utilise un `User-Agent` dédié (`ProjetEtudiantUMoncton-RechercheEmploi/0.1`) et prévoit `time.sleep(2)`.
- **Manques et points de vigilance :**
  - Tous les sélecteurs CSS (`SELECTEURS`) et la vérification `robots.txt` restent non confirmés (`🔍`), et toute la grille de vérification dans [`equipe/dan/01-inventaire-des-sites/sites.md`](../../equipe/dan/01-inventaire-des-sites/sites.md) est non cochée (`- [ ]`).
  - **Aucun fichier de résultats** (`offres_guichetemplois.csv`) ni preuve d’exécution ; aucun compte rendu Livrable 2.
  - Nom de fichier avec espace (`Poc guichetemploi.py`) différent du docstring et de `sites.md` (`poc_guichetemplois.py`) ; `requirements.txt` mentionné mais absent ; cible Moncton (N.-B.) hors périmètre Québec ; conflit Git toujours non résolu dans [`equipe/dan/README.md`](../../equipe/dan/README.md).

### Rayan, Aymerou, Nonga, Hendrix & Mike (`❌ Non fait`)
- **Rayan, Aymerou et Nonga :** seule la remise du Livrable 1 (`sites.md`) est présente, sans script Python ni compte rendu de scraping (à noter : Aymerou mentionnait vouloir tester Indeed — source exclue à remplacer).
- **Hendrix :** uniquement un cahier des charges ([`info.md`](../../equipe/hendrix/info.md)) et un `README.MD` d’architecture cible ([`README.MD`](../../equipe/hendrix/README.MD)), sans prototype fonctionnel.
- **Mike :** aucun dossier ni contribution dans le dépôt.

---

## 3. Constats techniques transversaux

### Comparatif des méthodes d’extraction expérimentées

| Méthode testée                | Sites concernés                                 | Fiabilité observée            | Limites principales                                         |
| ----------------------------- | ----------------------------------------------- | ----------------------------- | ----------------------------------------------------------- |
| **API REST JSON**             | Remotive, Welcome to the Jungle                 | Élevée (données déjà typées)  | Dépend des filtres/couverture (WTTJ peu québécois)          |
| **Flux Atom XML**             | Guichet-Emplois                                 | Élevée et rapide (1 req/page) | Résumé court sans description HTML complète                 |
| **HTML SSR + JSON-LD / RDFa** | Jobboom, Jobillico, Talent.com, Guichet-Emplois | Élevée sur les fiches         | 1 requête par fiche ; nécessite un contrôle strict du débit |
| **HTML SSR + sélecteurs CSS** | Guichet-Emplois                                 | Moyenne (sensible au DOM)     | Plus lourd en requêtes ; parsing texte/compétences bruyant  |

- **Confirmation concrète des doublons inter-sources :** la collecte de 87 offres réalisée par Hugo sur Guichet-Emplois montre que **55 annonces sur 87 (63 %)** proviennent de partenaires externes (Jobillico 20, Québec emploi 15, Talent.com 11, JobsMedia.ca 6, indeed.com 2, CareerBeacon 1). Ce résultat confirme l’importance de conserver l’identifiant/partenaire d’origine et de dédupliquer comme l’a amorcé Kandet.
- **Sources prioritaires du Livrable 1 encore non testées :** aucun prototype n’a encore testé les APIs gratuites **Adzuna Canada** et **Jooble Canada**, ni les endpoints **ATS d’employeurs** (Greenhouse, Lever, Ashby, Workday) ou **Carrières Gouv. du Québec**.
- **Qualité logicielle et conformité inégales :**
  - Seul **Kandet** combine bibliothèque standard sans dépendance, respect strict du `crawl-delay` de 5 s et du cache API 24 h, `User-Agent` honnête et **tests unitaires hors ligne**.
  - Plusieurs scripts contournent ou ignorent encore les bonnes pratiques de [`AGENTS.md`](../../AGENTS.md) : absence de `robots.txt` et de délais (Mamadou), délais inférieurs à 5 s sur Guichet-Emplois (Hugo, Dan), auto-installation `pip` à l’import et `input()` bloquant (Hugo), parsing HTML par regex (Mamadou), ou appel Windows-only `os.startfile()` (Ferdinand).
- **Documentation Volet 2 dispersée :** comme ces prototypes ont été produits lors de l’Atelier 1 avant la création formelle du Livrable 2, aucun étudiant n’a encore déposé de compte rendu dédié dans `02-preuve-de-concept-scraping/` couvrant explicitement les 4 points demandés (en particulier les difficultés rencontrées et limites observées).

---

## 4. Décisions et suivi pour la suite

### Actions attendues par membre
1. **Rayan, Aymerou, Nonga, Hendrix et Mike (`❌ Non fait`) :** déposer un premier prototype Python et son compte rendu dans `equipe/<nom>/02-preuve-de-concept-scraping/`.
   - Inviter **Rayan** à prototyper **Adzuna**, **Jooble** ou une liste d’employeurs **ATS** (Greenhouse/Lever/Ashby).
   - Inviter **Aymerou** (en abandonnant Indeed) et **Nonga** à cibler **Guichet-Emplois** (flux Atom) ou **Jobboom / Jobillico** (JSON-LD après vérification `robots.txt`).
   - Inviter **Hendrix** à passer du cahier des charges à un premier script concret.
2. **Dan (`⚠️ Partiel`) :** résoudre le conflit Git dans `README.md`, recentrer le script sur le Québec, vérifier les sélecteurs réels, exécuter le script pour produire un échantillon et ajouter le compte rendu dans `02-preuve-de-concept-scraping/`.
3. **Kandet, Hugo, Mamadou, Elvira et Ferdinand (`✅ Fait`) :** ajouter un court compte rendu dédié dans `02-preuve-de-concept-scraping/` (ou y regrouper les notes existantes) en précisant les difficultés/limites, et corriger les points techniques relevés :
   - **Hugo :** supprimer l’auto-installation `pip`, respecter le `crawl-delay` de 5 s, corriger le parsing de `description` et réduire les faux positifs sur `competences_cles`.
   - **Mamadou :** ajouter un délai entre requêtes, vérifier `robots.txt` (notamment Jobillico) et remplacer les regex HTML par `html.parser` ou `BeautifulSoup`.
   - **Elvira :** ajouter un `requirements.txt`, vérifier `robots.txt`/CGU de Jobboom et remplacer le `set` par une liste ordonnée.
   - **Ferdinand :** extraire la localisation (`office`/`offices`), filtrer ou évaluer la couverture réelle au Québec/Canada et retirer `os.startfile()`.
   - **Kandet :** joindre un petit échantillon JSON anonymisé/reproductible si utile et déplacer la section POC dans `02-preuve-de-concept-scraping/`.

### Cap pour la mise en commun
- **Schéma commun unifié :** converger vers un modèle typé commun inspiré de `SourceRecord`/`AggregatedOffer` (Kandet) et `JobOffer` (Hugo), en gardant les champs absents à `None` ou `""` sans jamais les deviner.
- **Architecture modulaire partagée :** séparer la collecte réseau (avec `User-Agent` honnête, cache local et délais conformes), le parsing (Atom / API JSON / JSON-LD), la normalisation/déduplication (partenaire + identifiant / empreinte titre-employeur-lieu) et les tests unitaires hors ligne sur fixtures locales.
