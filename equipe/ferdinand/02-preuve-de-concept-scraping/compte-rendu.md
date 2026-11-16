# Compte rendu — Livrable 2 : preuve de concept Welcome to the Jungle

## Site testé

- **Welcome to the Jungle** : https://www.welcometothejungle.com/fr/jobs
- **API appelée** : `https://api.welcometothejungle.com/api/v3/public/jobs`

## Méthode et outils

- Le site charge les offres en JavaScript : le HTML de la page ne contient pas les offres.
- Dans l’onglet Réseau du navigateur (F12, filtre Fetch/XHR, « Preserve log » coché), j’ai fait une recherche sur le site et repéré la requête qui renvoie les offres en JSON.
- Les autres requêtes vues (`axeptio` = bandeau de cookies, `algolia ... organizations` = entreprises mises en avant) ne servent pas pour les offres.
- Le script [`poc_wttj.py`](poc_wttj.py) appelle directement cette API avec `requests`. Il n’y a pas de HTML à analyser.
- La réponse contient `data` (les offres) et `metadata` (`total`, `page`, `per_page`, `page_count`). Le script parcourt les pages grâce à `page_count`, avec un maximum de 3 pages et une pause d’1 seconde entre les requêtes.
- Export en CSV (`;` comme séparateur, encodage `utf-8-sig` pour Excel).

## Lancer le prototype

```bash
pip install requests
python poc_wttj.py
```

Dépendance : `requests`. Le mot-clé se change dans la variable `MOT_CLE`.

## Données récupérées

- **30 offres** pour le mot-clé « stage data » : 21 `full_time` et 9 `internship`.
- Champs extraits : titre, entreprise, secteur, contrat, télétravail, date de mise à jour, lien vers l’offre.
- Fichiers : [`offres_wttj.csv`](offres_wttj.csv) et [`reponse_wttj.json`](reponse_wttj.json) (exemple de réponse brute de l’API).

Exemple de lignes :

```
titre;entreprise;secteur;contrat;teletravail
Data Analyst Intern;Cafeyn;Mobile Apps, Media, Print Media;internship;partial
DATA ANALYST (ANALYSTE DE DONNEES);Civils de la Défense - Ministère des Armées;IT / Digital, Cyber Security, Public Administration;full_time;punctual
```

J’ai comparé quelques titres du CSV avec les offres affichées sur le site : ce sont bien les mêmes.

## Difficultés et limites

- **Trouver la bonne requête** a été le plus long : la page envoie beaucoup de requêtes, et la liste de l’onglet Réseau se vidait à chaque recherche tant que « Preserve log » n’était pas coché.
- **Hors cible Québec** : presque toutes les offres sont en Europe ou aux États-Unis. Avec le filtre Montréal, je n’ai obtenu qu’une seule offre.
- **Le lieu n’est pas extrait** dans le CSV, alors que l’API le donne dans `office` / `offices`.
- **API non documentée** : son format peut changer sans prévenir, et ses conditions d’utilisation restent à vérifier.
- Le script n’arrête pas proprement en cas d’erreur HTTP (pas de `raise_for_status()`), utilise un User-Agent générique et appelle `os.startfile()`, qui ne marche que sous Windows.

Ces limites sont corrigées dans le [livrable 3](../03-amelioration-preuve-de-concept/note.md).
