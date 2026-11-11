# Dossier Personnel — El Hadji Konaté (`jobs-insights` - Atelier 1)

Ce dossier contient mes livrables pour l'**Atelier 1** du projet **`jobs-insights`** :

1. **[`sites.md`](sites.md)** :
   - Liste des sites d'offres d'emploi et de stages au Québec et au Canada (*Guichet-Emplois Canada, Jobillico, Talent.com Canada, Jobboom Québec, Remotive, Québec Emploi, Indeed/LinkedIn*).
   - Identification technique de ce qui est à scraper : filtres d'URL (`GET` / segments), catégories TI (`_i10lfr`), filtres stages (`fsrc=16`), balises sémantiques **RDFa Schema.org**, blocs **JSON-LD (`ItemList` et `JobPosting`)**, coordonnées GPS et APIs REST JSON.

2. **[`poc_scrapers_atelier1.py`](poc_scrapers_atelier1.py)** :
   - Script Python autonome démontrant le scraping en direct (`HTTP 200`) sur :
     - **Talent.com Canada** (`ca.talent.com/fr`) : extraction double JSON-LD (`ItemList` ➔ `JobPosting` + coordonnées GPS).
     - **Jobboom Québec** (`jobboom.com/fr`) : navigation dans le secteur Technologies (`_i10lfr`) + extraction `JobPosting`.
     - **Guichet-Emplois Canada** (`guichetemplois.gc.ca`) : recherche par ville + extraction des fiches RDFa.
     - **Jobillico Québec** (`jobillico.com`) : extraction des liens d'offres et lecture du bloc JSON-LD `JobPosting`.

## Exécution du POC

```powershell
python poc_scrapers_atelier1.py
```
