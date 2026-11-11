# Sources d'offres d'emploi (Québec)

Dernière mise à jour : 2026-11-09

Légende du statut :
- **Retenu** : source choisie pour le projet.
- **À vérifier** : à confirmer avant usage (robots.txt, conditions d'utilisation, couverture).
- **Exclu** : à ne pas utiliser.

Avant de scraper une source en HTML : lire son `robots.txt` et ses conditions d'utilisation, limiter le débit (1 requête toutes les 2 à 3 secondes), utiliser un `User-Agent` honnête, mettre les pages en cache.

---

## 1. Sources retenues

### Job Bank / Guichet-Emplois (gouvernement du Canada)
- **Statut** : Retenu (base du projet)
- **Site (EN)** : https://www.jobbank.gc.ca
- **Site (FR)** : https://www.guichetemplois.gc.ca
- **Accès** : données ouvertes (fichiers CSV mensuels) ou scraping HTML (robots.txt et conditions à vérifier)
- **Données ouvertes** : https://open.canada.ca/data/fr/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072
- **API du catalogue** : https://open.canada.ca/data/api/action/package_show?id=ea639e28-c0fc-48bf-b5dd-b8899bd43072
- **Licence des données ouvertes** : https://ouvert.canada.ca/fr/licence-du-gouvernement-ouvert-canada
- **Filtre Québec** : province = QC
- **Limites** : les fichiers ouverts n'ont ni nom d'employeur ni lien pour postuler. Une partie des annonces vient de sites externes (dont Jobillico).

### Adzuna (API)
- **Statut** : Retenu (couverture du Québec à tester)
- **Portail développeur** : https://developer.adzuna.com
- **Base de l'API** : https://api.adzuna.com/v1/api
- **Exemple de recherche Canada** : `https://api.adzuna.com/v1/api/jobs/ca/search/1?app_id=APP_ID&app_key=APP_KEY&what=developpeur&where=Quebec`
- **Accès** : clé gratuite (app_id et app_key), quotas limités

### Jooble (API)
- **Statut** : Retenu (couverture du Québec à tester)
- **Site** : https://ca.jooble.org
- **Demande de clé API** : https://jooble.org/api/about
- **Endpoint** : `POST https://jooble.org/api/{cle_api}` avec un corps JSON (`keywords`, `location`)
- **Limites** : filtres limités aux mots-clés et au lieu, extraits de description seulement

### Pages carrières d'entreprises (ATS)
- **Statut** : Retenu (pour une liste d'employeurs québécois ciblés)
- **Workday** : `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
  - Corps : `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`
  - Endpoint interne non documenté, susceptible de changer. Pas de champ salaire structuré.
- **Greenhouse** : `https://boards-api.greenhouse.io/v1/boards/{token}/jobs`
- **Lever** : `https://api.lever.co/v0/postings/{site}?mode=json`
- **Ashby** : `https://api.ashbyhq.com/posting-api/job-board/{organization}`
- **À prévoir** : une liste d'entreprises cibles avec leur tenant ou leur identifiant

---

## 2. À vérifier

### Jobillico
- **Statut** : À vérifier
- **Site** : https://www.jobillico.com
- **Remarque** : aucune API officielle publique trouvée. Robots.txt et conditions d'utilisation non vérifiés. Une partie de ses offres apparaît déjà dans Job Bank. Option : contacter Jobillico pour un accès partenaire.

---

## 3. Sources exclues

| Source | URL | Raison |
|---|---|---|
| Québec emploi | https://www.quebec.ca/emploi/quebec-emploi | Les conditions interdisent les robots et la collecte automatisée |
| LinkedIn | https://www.linkedin.com/jobs | Conditions d'utilisation interdisant le scraping, anti-bot strict |
| Indeed | https://ca.indeed.com | Conditions d'utilisation interdisant le scraping, protection anti-bot |
| Glassdoor | https://www.glassdoor.ca | Conditions d'utilisation interdisant les agents automatisés |
| France Travail | https://francetravail.io | Offres françaises seulement, hors périmètre Québec |
| Sources de télétravail (RemoteOK, Jobicy, Arbeitnow, We Work Remotely, Working Nomads) | n/a | Hors périmètre, le projet est limité au Québec |
