# Inventaire commun des sites

Référentiel consolidé à partir des remises du Livrable 1 (`equipe/*/01-inventaire-des-sites/sites.md`) pour guider les prototypes de collecte du Livrable 2 et la suite du projet `job-insights`.

---

## 1. Tableaux synthèse

### Sources prioritaires (APIs, données ouvertes, flux structurés)

| Source                         | Accès technique                                    | Périmètre           |    Mentions    |
| ------------------------------ | -------------------------------------------------- | ------------------- | :------------: |
| **Guichet-Emplois / Job Bank** | Atom/RSS, RDFa/JSON-LD, CSV ouverts                | Canada / Québec     |      7/9       |
| **Remotive**                   | API REST JSON (sans clé)                           | Télétravail mondial |      3/9       |
| **Adzuna Canada**              | API REST JSON (avec clé)                           | Canada / Québec     | 2/9 (+1 piste) |
| **Jooble Canada**              | API REST JSON `POST` (avec clé)                    | Canada / Québec     |      2/9       |
| **Pages carrières (ATS)**      | Endpoints JSON (Greenhouse, Lever, Ashby, Workday) | Employeurs cibles   |      1/9       |

### Portails à vérifier avant automatisation

| Source                          | Format observé             | Périmètre               |     Mentions      |
| ------------------------------- | -------------------------- | ----------------------- | :---------------: |
| **Jobillico**                   | HTML SSR, XHR, JSON-LD     | Québec / Canada         |  6/9 (+1 piste)   |
| **Jobboom**                     | HTML SSR, JSON-LD          | Québec                  |        3/9        |
| **Talent.com Canada**           | HTML SSR, JSON-LD `@graph` | Canada / Québec         |        2/9        |
| **Carrières — Gouv. du Québec** | Portail web (à inspecter)  | Québec (secteur public) | 1/9 (+lien QC.ca) |
| **KebekJobs**                   | CMS / XHR supposées        | Québec                  |        1/9        |
| **MonTravail.ca**               | HTML / AJAX                | Québec                  |        1/9        |
| **RIMQ (Emplois municipaux)**   | HTML statique              | Québec (municipal)      |        1/9        |
| **Welcome to the Jungle**       | API JSON (Algolia)         | Europe / International  |        1/9        |

### Sources exclues de la collecte automatisée

| Source             | Motif d’exclusion                                               |     Mentions      |
| ------------------ | --------------------------------------------------------------- | :---------------: |
| **Indeed Canada**  | CGU interdisant le scraping, anti-bot / Cloudflare (`HTTP 403`) |        7/9        |
| **LinkedIn Jobs**  | `robots.txt` et CGU restrictifs, anti-bot strict                |        5/9        |
| **Québec emploi**  | CGU interdisant les robots / collecte automatisée, SPA          | 5/9 (+lien QC.ca) |
| **Glassdoor**      | CGU interdisant les agents automatisés                          |        2/9        |
| **France Travail** | Hors périmètre géographique (France)                            |        1/9        |

---

## 2. Fiches détaillées — Sources prioritaires

### Guichet-Emplois / Job Bank
- **URL :** https://www.guichetemplois.gc.ca · https://www.jobbank.gc.ca · [Jeu de données ouvertes](https://open.canada.ca/data/fr/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072)
- **Statut :** Prioritaire (socle principal du projet).
- **Couverture & intérêt :** Tout le Canada (filtre province `QC`), fort volume d’offres TI, d’emplois étudiants et de stages (`fsrc=16`).
- **Méthodes d’extraction :** Flux Atom/RSS pour les résultats de recherche, pages HTML SSR avec balises RDFa et JSON-LD `JobPosting`, fichiers CSV mensuels via Données ouvertes Canada.
- **Règles d’accès & limites :** `robots.txt` impose un `crawl-delay` de **5 secondes**. Reprend des annonces externes (dont Jobillico), d’où un risque de doublons. Les CSV ouverts ne contiennent ni le nom de l’employeur ni le lien pour postuler.
- **Citée par :** Dan, Elvira, Hugo, Kandet, Mamadou, Nonga, Rayan (7/9).

### Remotive
- **URL :** https://remotive.com/remote-jobs · [Documentation API](https://github.com/remotive-com/remote-jobs-api)
- **Statut :** Prioritaire (complément télétravail).
- **Couverture & intérêt :** Offres tech (développement, DevOps, données, QA, produit) 100 % en télétravail ; distingue explicitement les stages (`job_type=internship`).
- **Méthodes d’extraction :** API REST JSON publique sans clé (`/api/remote-jobs`), filtrage local sur les catégories TI et la localisation (`Canada`, `North America`, `Worldwide`).
- **Règles d’accès & limites :** Offres publiées avec un délai de 24 h. Limiter à **au plus 4 requêtes par jour** (cache local 24 h recommandé). Hors périmètre Québec strict si l’on exclut les postes internationaux.
- **Citée par :** Hugo, Kandet, Mamadou (3/9).

### Adzuna Canada
- **URL :** https://www.adzuna.ca/ · [Portail développeur](https://developer.adzuna.com)
- **Statut :** Prioritaire (à tester en POC).
- **Couverture & intérêt :** Agrégateur canadien retournant des champs déjà structurés (titre, entreprise, lieu, salaire, description).
- **Méthodes d’extraction :** API REST officielle JSON authentifiée par `app_id` et `app_key` gratuits.
- **Règles d’accès & limites :** Quotas limités sur le palier gratuit ; couverture réelle au Québec et sur les stages TI à mesurer.
- **Citée par :** Hugo, Rayan (2/9) + piste en attente chez Dan.

### Jooble Canada
- **URL :** https://ca.jooble.org · [Demande de clé API](https://jooble.org/api/about)
- **Statut :** Prioritaire (à tester en POC).
- **Couverture & intérêt :** Agrégateur canadien interrogeable par mots-clés et localisation.
- **Méthodes d’extraction :** API REST officielle JSON (`POST https://jooble.org/api/{cle_api}` avec `keywords` et `location`).
- **Règles d’accès & limites :** Filtres limités aux mots-clés et au lieu ; ne renvoie que des extraits de description. Couverture Québec à évaluer.
- **Citée par :** Hugo, Rayan (2/9).

### Pages carrières d’employeurs (ATS)
- **Accès identifiés :**
  - Greenhouse : `https://boards-api.greenhouse.io/v1/boards/{token}/jobs`
  - Lever : `https://api.lever.co/v0/postings/{site}?mode=json`
  - Ashby : `https://api.ashbyhq.com/posting-api/job-board/{organization}`
  - Workday : `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
- **Statut :** Prioritaire (source directe d’employeurs).
- **Couverture & intérêt :** Permet de capter des stages et postes juniors publiés uniquement sur les sites carrières d’entreprises tech/TI.
- **Règles d’accès & limites :** Nécessite de constituer une liste d’employeurs cibles au Québec/Canada avec leur identifiant/tenant. L’endpoint Workday est interne (non documenté, susceptible d’évoluer, sans champ salaire structuré).
- **Citée par :** Rayan (1/9).

---

## 3. Fiches détaillées — Portails à vérifier

### Jobillico
- **URL :** https://www.jobillico.com/fr/
- **Statut :** À vérifier.
- **Couverture & intérêt :** Très forte présence des PME et employeurs de Québec et Montréal.
- **Format observé :** Pages HTML SSR + requêtes XHR lors du filtrage/pagination + balise JSON-LD `JobPosting` sur les fiches d’offres.
- **Règles d’accès & limites :** Kandet signale des restrictions dans `robots.txt` sur certaines URL de recherche et de pagination ; Rayan note l’absence d’API publique officielle et le fait qu’une partie des offres remonte déjà dans Guichet-Emplois.
- **Citée par :** Aymerou, Elvira, Hugo, Kandet, Mamadou, Rayan (6/9) + piste en attente chez Dan.

### Jobboom
- **URL :** https://www.jobboom.com/fr
- **Statut :** À vérifier.
- **Couverture & intérêt :** Portail québécois structuré par secteurs, dont une catégorie dédiée *Technologies et médias numériques* (`_i10lfr`) et des sous-métiers TI.
- **Format observé :** HTML SSR (`div.job_item`, liens `/fr/offre-emploi/...`) + bloc JSON-LD `@type: "JobPosting"` complet sur chaque fiche.
- **Règles d’accès & limites :** `robots.txt` et conditions d’utilisation à vérifier formellement avant d’intégrer un collecteur commun.
- **Citée par :** Elvira, Hugo, Mamadou (3/9).

### Talent.com Canada
- **URL :** https://ca.talent.com/fr
- **Statut :** À vérifier.
- **Couverture & intérêt :** Agrégateur canadien affichant des stages en informatique et postes juniors au Québec.
- **Format observé :** HTML SSR contenant un bloc JSON-LD `@graph` avec `ItemList` sur la page de résultats et `JobPosting` (avec géolocalisation) sur les fiches.
- **Règles d’accès & limites :** `robots.txt` et conditions d’utilisation à vérifier formellement avant intégration commune.
- **Citée par :** Hugo, Mamadou (2/9).

### Carrières — Gouvernement du Québec
- **URL :** https://emplois.carrieres.gouv.qc.ca/plateforme-emploi · https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/
- **Statut :** À vérifier.
- **Couverture & intérêt :** Source directe pour les emplois et stages étudiants dans les ministères et organismes du gouvernement du Québec.
- **Règles d’accès & limites :** Portail distinct de Québec emploi (`quebecemploi.gouv.qc.ca`) ; consulter les conditions d’utilisation et vérifier l’existence d’un flux ou d’une API avant toute automatisation.
- **Citée par :** Kandet (1/9) *(également accessible via Québec.ca cité par Elvira)*.

### KebekJobs
- **URL :** https://www.kebekjobs.com/emplois
- **Statut :** À vérifier.
- **Couverture & intérêt :** Offres d’emploi au Québec par mot-clé et par ville.
- **Format & limites :** CMS / requêtes XHR supposées ; vérifier le volume réel d’offres TI/stages, la structure HTML/API et le `robots.txt`.
- **Citée par :** Elvira (1/9).

### MonTravail.ca
- **URL :** https://www.montravail.ca/
- **Statut :** À vérifier.
- **Couverture & intérêt :** Portail québécois avec recherche par mot-clé et région.
- **Format & limites :** HTML / AJAX ; vérifier le volume d’offres TI/stages et le `robots.txt`.
- **Citée par :** Elvira (1/9).

### RIMQ (Emplois municipaux)
- **URL :** https://rimq.qc.ca/emplois/municipal/
- **Statut :** À vérifier.
- **Couverture & intérêt :** Offres dans les municipalités du Québec, avec catégorie *Informatique / Technologies de l’information*.
- **Format & limites :** HTML statique léger ; vérifier le `robots.txt`, les conditions d’utilisation et la présence de postes juniors ou de stages.
- **Citée par :** Elvira (1/9).

### Welcome to the Jungle
- **URL :** https://www.welcometothejungle.com/fr/jobs
- **Statut :** À vérifier.
- **Couverture & intérêt :** Offres d’emplois et de stages tech avec filtres (contrat, télétravail, expérience).
- **Format & limites :** Page chargée en JavaScript alimentée par une API JSON (Algolia). Couverture réelle au Québec/Canada et conditions d’utilisation de l’API à vérifier (plateforme principalement européenne).
- **Citée par :** Ferdinand (1/9).

---

## 4. Pistes secondaires à valider

Sources issues principalement de recherches exploratoires (dont listes assistées par IA), non encore vérifiées techniquement ni juridiquement :

- **Pistes canadiennes :**
  - [Robert Half Canada](https://www.roberthalf.com/ca/fr/recherche-emploi) *(Hugo)*
  - [Workopolis](https://www.workopolis.com/) *(Hugo)*
  - CareerBuilder *(cité par Hugo sous `CarrerBuilder`, avec lien erroné vers Talent.com à corriger)*
  - [Eluta.ca](https://www.eluta.ca/) *(Hugo, piste IA)*
  - [WowJobs.ca](https://www.wowjobs.ca/) *(Hugo, piste IA)*
  - [CharityVillage](https://charityvillage.com/) *(Hugo, piste IA — secteur OBNL / parapublic)*
  - [WorkBC](https://www.workbc.ca/) *(Hugo, piste IA — Colombie-Britannique, hors Québec)*
  - [Craigslist Canada](https://www.craigslist.org/) *(Hugo, piste IA)*
- **Pistes internationales / télétravail (hors périmètre Québec strict) :**
  - [RemoteOK](https://remoteok.com/), [Arbeitnow](https://www.arbeitnow.com/), [We Work Remotely](https://weworkremotely.com/), [Jobicy](https://jobicy.com/), [The Muse](https://www.themuse.com/), [Hacker News (Who is Hiring?)](https://news.ycombinator.com/), [USAJOBS](https://www.usajobs.gov/), [Reed.co.uk](https://www.reed.co.uk/) *(Hugo, pistes IA)* ; Working Nomads *(cité dans les exclusions de Rayan)*.

---

## 5. Fiches détaillées — Sources exclues (consultation manuelle uniquement)

### Indeed Canada
- **URL :** https://ca.indeed.com · https://emplois.ca.indeed.com
- **Motif d’exclusion :** Conditions d’utilisation interdisant le scraping ; protection anti-bot / Cloudflare (`HTTP 403` constaté).
- **Citée par :** Aymerou, Elvira, Hugo, Kandet, Mamadou, Nonga, Rayan (7/9).

### LinkedIn Jobs
- **URL :** https://www.linkedin.com/jobs/ · https://ca.linkedin.com/jobs/
- **Motif d’exclusion :** `robots.txt` et conditions d’utilisation interdisant l’accès automatisé sans autorisation ; anti-bot strict.
- **Citée par :** Hugo, Kandet, Mamadou, Nonga, Rayan (5/9).

### Québec emploi
- **URL :** https://www.quebecemploi.gouv.qc.ca · https://www.quebec.ca/emploi/quebec-emploi
- **Motif d’exclusion :** Conditions d’utilisation interdisant les robots et la collecte automatisée (et application SPA nécessitant un navigateur complet).
- **Citée par :** Aymerou, Hugo, Kandet, Mamadou, Rayan (5/9) *(+ redirection depuis Québec.ca citée par Elvira)*.

### Glassdoor
- **URL :** https://www.glassdoor.ca · https://fr.glassdoor.ca
- **Motif d’exclusion :** Conditions d’utilisation interdisant les agents automatisés.
- **Citée par :** Hugo, Rayan (2/9).

### France Travail
- **URL :** https://francetravail.io
- **Motif d’exclusion :** Offres situées en France uniquement, hors périmètre Québec / Canada.
- **Citée par :** Rayan (1/9).
