# Dossier Personnel — Mamadou (`job-insights`)

Organisation de mes livrables selon la structure du dépôt :

- **[`plan.md`](plan.md)** : Repère de travail synthétique et feuille de route pour le dialogue avec l'assistant IA.
- **[`01-inventaire-des-sites/sites.md`](01-inventaire-des-sites/sites.md)** : Livrable 1 — Inventaire et analyse technique des sources d'emploi et de stages au Québec / Canada.
- **[`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/)** : Livrable 2 — Prototype initial multi-sources ([`poc_scrapers_atelier1.py`](02-preuve-de-concept-scraping/poc_scrapers_atelier1.py)), échantillon ([`sample_scraped_jobs.json`](02-preuve-de-concept-scraping/sample_scraped_jobs.json)) et [`compte-rendu.md`](02-preuve-de-concept-scraping/compte-rendu.md).
- **[`03-amelioration-preuve-de-concept/`](03-amelioration-preuve-de-concept/)** : Livrable 3 — Amélioration de la collecte sur Guichet-Emplois (recherche par 14 codes CNP TI + filtres + enrichissement des fiches RDFa via `requests` et `BeautifulSoup` + respect de `robots.txt` et `Crawl-delay: 5` + 5 tests unitaires hors ligne) :
  - [`note.md`](03-amelioration-preuve-de-concept/note.md)
  - [`poc_guichet_cnp_v2.py`](03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py)
  - [`test_poc_guichet_cnp_v2.py`](03-amelioration-preuve-de-concept/test_poc_guichet_cnp_v2.py)
  - [`echantillon_v2.json`](03-amelioration-preuve-de-concept/echantillon_v2.json)
