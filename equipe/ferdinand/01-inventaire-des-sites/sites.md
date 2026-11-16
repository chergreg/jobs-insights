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

# Compte rendu - Livrable 2

## Site testé
- Welcome to the Jungle : https://www.welcometothejungle.com/fr/jobs
- API : https://api.welcometothejungle.com/api/v3/public/jobs

## Méthode
- Repérage de l'API dans l'onglet Réseau (F12) : le site charge les offres en JavaScript.
- Appel direct de l'API JSON avec `requests` (pas de HTML à analyser).
- Pagination avec `metadata.page_count`, export CSV.

## Lancer
pip install requests
python poc_wttj.py

## Données récupérées
30 offres (mot-clé « stage data ») : titre, entreprise, secteur, contrat, télétravail, date, lien.

Exemple :
Data Analyst Intern;Cafeyn;internship

## Limites
- Offres presque toutes en Europe : peu utile pour le Québec.
- Le lieu n'est pas extrait dans le CSV.
- API non documentée, son format peut changer.
- `os.startfile()` ne marche que sous Windows.