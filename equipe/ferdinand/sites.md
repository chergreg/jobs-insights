# Sites d'offres d'emploi et de stages

## Welcome to the Jungle
- URL : https://www.welcometothejungle.com/fr/jobs
- Type : emploi + stage
- Catégories : Tech, Marketing, Design...
- Filtres : contrat, lieu, télétravail, expérience
- Pagination : oui (`page=` dans l'URL)
- Données à récupérer : titre, entreprise, lieu, contrat, date, lien
- Chargé en JavaScript ? oui / non
- Difficulté : facile / moyenne / difficile
### Observations techniques
- Le site est chargé en JavaScript : le HTML de base ne contient pas les offres.
- Les offres viennent d'une API JSON (Algolia) visible dans l'onglet Réseau.
- Requêtes inutiles repérées : `axeptio` = bandeau de cookies (à ignorer).
- Piste pour le POC : rejouer la requête Algolia avec `requests` en Python.

### Difficulté
- Facile
### POC
- Fichier : `poc_wttj.py`
- Méthode : appel direct de l'API JSON (pas de HTML à analyser)
- Résultat : titre, entreprise, secteur, contrat, télétravail, date, lien → export CSV
- Pagination gérée avec `metadata.page_count`
- Statut : fonctionne