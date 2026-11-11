# Inventaire commun des sites

Référentiel consolidé à partir des remises du Livrable 1 (`equipe/*/01-inventaire-des-sites/sites.md`) pour guider les prototypes de collecte du Livrable 2 et la suite du projet `job-insights`.

> **Rappel de conformité (`AGENTS.md`) :** avant d’automatiser une source marquée *À vérifier*, consulter son `robots.txt` et ses conditions d’utilisation, utiliser un `User-Agent` honnête, respecter les délais de requête et ne jamais contourner de protection anti-bot ou d’authentification.

---

## 1. Sources prioritaires (APIs, données ouvertes, flux structurés)

| Source                                 | URL / Accès                                                                                                                                                                | Couverture / Intérêt                                                                                    | Méthode d’extraction                                                                             | Remarques et règles d’accès                                                                                                                                                           | Citée par                                              |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **Guichet-Emplois / Job Bank**         | [FR](https://www.guichetemplois.gc.ca) · [EN](https://www.jobbank.gc.ca) · [Données ouvertes](https://open.canada.ca/data/fr/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) | Tout le Canada (filtre `QC`), nombreux emplois TI, étudiants et stages (`fsrc=16`).                     | Flux Atom/RSS, HTML SSR + RDFa / JSON-LD `JobPosting`, fichiers CSV mensuels (Données ouvertes). | Respecter le `crawl-delay` de **5 s** (`robots.txt`). Reprend aussi des offres partenaires (ex. Jobillico). Les CSV ouverts omettent le nom de l’employeur et le lien de candidature. | Dan, Elvira, Hugo, Kandet, Mamadou, Nonga, Rayan (7/9) |
| **Remotive**                           | [Site](https://remotive.com/remote-jobs) · [Doc API](https://github.com/remotive-com/remote-jobs-api)                                                                      | Offres tech (dev, data, DevOps, QA) en télétravail ; inclut des stages (`job_type=internship`).         | API REST JSON publique sans clé (`/api/remote-jobs`).                                            | Annonces décalées de 24 h. Limiter à **max 4 requêtes/jour** et mettre la réponse en cache local (24 h). Filtrer localement sur Canada / Amérique du Nord / Worldwide.                | Hugo, Kandet, Mamadou (3/9)                            |
| **Adzuna Canada**                      | [Portail](https://developer.adzuna.com) · [Site CA](https://www.adzuna.ca/)                                                                                                | Agrégateur canadien ; résultats structurés (titre, salaire, lieu, entreprise).                          | API REST officielle JSON (`app_id` + `app_key` gratuits).                                        | Quotas limités ; couverture réelle au Québec et sur les stages TI à valider par un essai.                                                                                             | Hugo, Rayan (2/9) + piste Dan                          |
| **Jooble Canada**                      | [Site](https://ca.jooble.org) · [API](https://jooble.org/api/about)                                                                                                        | Agrégateur canadien interrogeable par mots-clés et lieu.                                                | API REST officielle JSON (`POST` avec clé gratuite).                                             | Filtres limités (`keywords`, `location`) et descriptions tronquées (extraits seulement).                                                                                              | Hugo, Rayan (2/9)                                      |
| **Pages carrières d’employeurs (ATS)** | `boards-api.greenhouse.io`, `api.lever.co`, `api.ashbyhq.com`, Workday (`wday/cxs`)                                                                                        | Accès direct aux offres d’entreprises tech/TI (souvent absentes des portails publics), dont des stages. | Endpoints JSON publics (Greenhouse, Lever, Ashby) ou internes (Workday).                         | Nécessite de constituer une liste d’entreprises québécoises/canadiennes cibles avec leur identifiant/tenant. Endpoint Workday non documenté et sans salaire structuré.                | Rayan (1/9)                                            |

---

## 2. Portails québécois et canadiens à vérifier ou cadrer

| Source | URL | Couverture / Intérêt | Format technique repéré | État de vérification | Citée par |
| --- | --- | --- | --- | --- | --- |
| **Jobillico** | https://www.jobillico.com/fr/ | Forte présence de PME et employeurs de Québec et Montréal. | HTML SSR + XHR (filtrage/pagination) + JSON-LD `JobPosting`. | **À vérifier :** `robots.txt` comporte des restrictions sur certaines URL de recherche/pagination (Kandet) ; pas d’API publique officielle trouvée (Rayan). | Aymerou, Elvira, Hugo, Kandet, Mamadou, Rayan (6/9) + piste Dan |
| **Jobboom** | https://www.jobboom.com/fr | Portail québécois structuré par secteurs, dont Technologies (`_i10lfr`). | HTML SSR + JSON-LD `JobPosting` sur les fiches. | **À vérifier :** `robots.txt` et conditions d’utilisation à valider formellement avant intégration commune. | Elvira, Hugo, Mamadou (3/9) |
| **Talent.com Canada** | https://ca.talent.com/fr | Agrégateur canadien incluant stages et postes juniors au Québec. | HTML SSR + JSON-LD `@graph` (`ItemList` et `JobPosting`). | **À vérifier :** `robots.txt` et conditions d’utilisation à valider avant intégration commune. | Hugo, Mamadou (2/9) |
| **Carrières — Gouv. du Québec** | [Portail emplois](https://emplois.carrieres.gouv.qc.ca/plateforme-emploi) · [Étudiants et stages](https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/) | Emplois et stages étudiants dans les ministères et organismes du Québec. | À inspecter (portail web distinct de Québec emploi). | **À vérifier :** consulter les conditions d’utilisation et rechercher un flux ou une API avant toute automatisation. | Kandet (1/9) *(aussi lié depuis Québec.ca cité par Elvira)* |
| **KebekJobs** | https://www.kebekjobs.com/emplois | Offres d’emploi au Québec (recherche par mot-clé et ville). | CMS / requêtes XHR supposées. | **À vérifier :** volume d’offres TI/stages, structure réelle et `robots.txt`. | Elvira (1/9) |
| **MonTravail.ca** | https://www.montravail.ca/ | Offres d’emploi au Québec par mot-clé et région. | HTML / AJAX. | **À vérifier :** volume d’offres TI/stages, structure réelle et `robots.txt`. | Elvira (1/9) |
| **RIMQ (Emplois municipaux)** | https://rimq.qc.ca/emplois/municipal/ | Postes en informatique dans les municipalités du Québec. | HTML statique. | **À vérifier :** conditions d’utilisation, `robots.txt` et pertinence pour des profils juniors/stagiaires. | Elvira (1/9) |
| **Welcome to the Jungle** | https://www.welcometothejungle.com/fr/jobs | Emplois et stages tech avec filtres contrat, télétravail, expérience. | Rendu JS alimenté par une API JSON (Algolia). | **À vérifier :** couverture réelle au Québec et au Canada (plateforme surtout européenne), conditions d’utilisation de l’API. | Ferdinand (1/9) |

---

## 3. Pistes secondaires à valider (recherches complémentaires)

Ces sources proviennent principalement d’une recherche exploratoire (dont pistes assistées par IA) et n’ont pas encore fait l’objet d’une vérification technique et juridique complète dans le dépôt :

- **Pistes canadiennes :**
  - [Robert Half Canada](https://www.roberthalf.com/ca/fr/recherche-emploi) *(Hugo)*
  - [Workopolis](https://www.workopolis.com/) *(Hugo)*
  - CareerBuilder *(cité par Hugo sous `CarrerBuilder`, lien à corriger car pointant vers Talent.com)*
  - [Eluta.ca](https://www.eluta.ca/) *(Hugo, piste IA)*
  - [WowJobs.ca](https://www.wowjobs.ca/) *(Hugo, piste IA)*
  - [CharityVillage](https://charityvillage.com/) *(Hugo, piste IA — secteur OBNL/parapublic)*
  - [WorkBC](https://www.workbc.ca/) *(Hugo, piste IA — Colombie-Britannique, hors Québec)*
  - [Craigslist Canada](https://www.craigslist.org/) *(Hugo, piste IA)*
- **Pistes internationales / télétravail (hors périmètre Québec strict) :**
  - [RemoteOK](https://remoteok.com/), [Arbeitnow](https://www.arbeitnow.com/), [We Work Remotely](https://weworkremotely.com/), [Jobicy](https://jobicy.com/), [The Muse](https://www.themuse.com/), [Hacker News (Who is Hiring?)](https://news.ycombinator.com/), [USAJOBS](https://www.usajobs.gov/), [Reed.co.uk](https://www.reed.co.uk/) *(Hugo, pistes IA)* ; Working Nomads *(cité dans les exclusions de Rayan)*.

---

## 4. Sources exclues de la collecte automatisée

| Source | URL | Raison de l’exclusion | Citée par |
| --- | --- | --- | --- |
| **Indeed Canada** | https://ca.indeed.com | Conditions d’utilisation interdisant le scraping ; protection anti-bot / Cloudflare (`HTTP 403` observé). **Consultation manuelle uniquement.** | Aymerou, Elvira, Hugo, Kandet, Mamadou, Nonga, Rayan (7/9) |
| **LinkedIn Jobs** | https://www.linkedin.com/jobs/ | `robots.txt` et conditions d’utilisation interdisant l’accès automatisé ; anti-bot strict. **Consultation manuelle uniquement.** | Hugo, Kandet, Mamadou, Nonga, Rayan (5/9) |
| **Québec emploi** | https://www.quebecemploi.gouv.qc.ca | Conditions d’utilisation interdisant les robots et la collecte automatisée (et portail SPA). **Consultation manuelle uniquement.** | Aymerou, Hugo, Kandet, Mamadou, Rayan (5/9) *(+ redirection via Québec.ca citée par Elvira)* |
| **Glassdoor** | https://www.glassdoor.ca | Conditions d’utilisation interdisant les agents automatisés. **Consultation manuelle uniquement.** | Hugo, Rayan (2/9) |
| **France Travail** | https://francetravail.io | Offres françaises uniquement, hors périmètre Québec / Canada. | Rayan (1/9) |
