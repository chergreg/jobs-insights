# Dossier Personnel — Mamadou (`jobs-insights`)

Organisation de mes livrables selon la structure du dépôt :

- **[`plan.md`](plan.md)** : Plan directeur et suivi par lots du Livrable 3 (Lots 1 à 4 terminés).
- **[`01-inventaire-des-sites/sites.md`](01-inventaire-des-sites/sites.md)** : Livrable 1 — Inventaire et analyse technique des sources d'emploi et de stages TI au Québec / Canada.
- **[`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/)** : Livrable 2 — Prototype initial multi-sources ([`poc_scrapers_atelier1.py`](02-preuve-de-concept-scraping/poc_scrapers_atelier1.py)), échantillon ([`sample_scraped_jobs.json`](02-preuve-de-concept-scraping/sample_scraped_jobs.json)) et [`compte-rendu.md`](02-preuve-de-concept-scraping/compte-rendu.md).
- **[`03-amelioration-preuve-de-concept/`](03-amelioration-preuve-de-concept/)** : Livrable 3 Final — Collecteur et pipeline multi-sources enrichi sur **5 plateformes** (Guichet-Emplois, Jobboom, Talent.com, Jobillico, Remotive), classification automatique sur les **14 codes CNP 2021 TI** (0 faux positif hors TI), enrichissement `JobTailor_V3` à 36 champs, cache disque 24 h, déduplication inter-sources et **368 offres TI réelles uniques** sous [`data/`](03-amelioration-preuve-de-concept/data/) :
  - [`note.md`](03-amelioration-preuve-de-concept/note.md) & [`README.md`](03-amelioration-preuve-de-concept/README.md) & [`plan.md`](03-amelioration-preuve-de-concept/plan.md)
  - [`poc_guichet_cnp_v2.py`](03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py) & [`test_poc_guichet_cnp_v2.py`](03-amelioration-preuve-de-concept/test_poc_guichet_cnp_v2.py) (**16 tests unitaires hors ligne**)
  - [`data/offres_unifiees.json`](03-amelioration-preuve-de-concept/data/offres_unifiees.json), [`data/offres_unifiees.csv`](03-amelioration-preuve-de-concept/data/offres_unifiees.csv) & [`data/rapport_collecte.json`](03-amelioration-preuve-de-concept/data/rapport_collecte.json)
