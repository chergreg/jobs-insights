# Livrable 3 - Amélioration du POC Welcome to the Jungle

## Site choisi

- **Welcome to the Jungle** : https://www.welcometothejungle.com/fr/jobs
- API utilisée : `https://api.welcometothejungle.com/api/v3/public/jobs`

## Contributions consultées

- [Synthèse du livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md)
- [Mon POC du livrable 2 : `poc_wttj.py`](../02-preuve-de-concept-scraping/poc_wttj.py) et sa sortie [`offres_wttj.csv`](../02-preuve-de-concept-scraping/offres_wttj.csv)
- [POC de Kandet : `poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py) (idées reprises : User-Agent honnête, déduplication, tests hors ligne)

Je suis le seul à avoir travaillé sur ce site.

## Ce qui fonctionnait dans la version 1

- L'API JSON renvoie des offres déjà structurées : pas de HTML à analyser.
- La pagination marche avec `metadata.page_count`.
- 30 offres exportées en CSV (21 `full_time`, 9 `internship`).

## Limites relevées (synthèse du livrable 2)

- **Hors cible** : presque toutes les offres étaient en Europe ou aux États-Unis.
- **Pas de lieu** dans le CSV, alors que l'API donne `office` / `offices`.
- Pas de `raise_for_status()`, User-Agent générique, `os.startfile()` (Windows seulement).
- Pas de `requirements.txt`, pas de tests.

## Ce que j'ai modifié

| Changement | Pourquoi |
| --- | --- |
| Colonnes `villes`, `pays`, `au_canada` | Le lieu manquait |
| Recherche limitée à Montréal et Québec | Cibler le Québec |
| Filtre local `au_canada` | Retirer les offres hors Canada |
| Salaire, date de publication, id source | Champs disponibles dans l'API |
| Déduplication par id ou lien | Une offre peut sortir pour 2 villes |
| `raise_for_status()`, `timeout`, User-Agent honnête, pause 2 s | Collecte plus propre |
| Suppression de `os.startfile()` | Marche sur tous les systèmes |
| Code découpé en fonctions + 6 tests hors ligne | Code testable sans réseau |
| `requirements.txt` | Dépendance documentée |

Les champs absents restent vides : aucune information n'est devinée.

## Lancer

```bash
pip install -r requirements.txt
python poc_wttj_v2.py
python poc_wttj_v2.py --mot-cle "développeur"
python poc_wttj_v2.py --partout
python -m unittest test_poc_wttj_v2.py -v
```

## Vérification

### Tests hors ligne

6 tests passent (`python -m unittest test_poc_wttj_v2.py -v`), à partir d'un petit fichier d'exemple dans `fixtures/`.

### Essai réel

<!-- À compléter avec tes propres résultats -->

| Essai | Offres reçues | Offres gardées (Canada) |
| --- | --- | --- |
| v1 : `stage data`, partout | 30 | 0 identifiée (pas de colonne lieu) |
| v2 : `stage`, Québec | ... | ... |
| v2 : `développeur`, Québec | ... | ... |

Exemple de ligne obtenue :

```
titre;entreprise;villes;pays;contrat
...
```

## Limites qui restent

- **Peu d'offres au Québec** : Welcome to the Jungle est surtout européen. Ce site restera une source secondaire pour le projet.
- L'API n'est pas documentée publiquement : son format peut changer sans prévenir.
- `robots.txt` et conditions d'utilisation de l'API à vérifier avant une collecte régulière.
- Le format des lieux envoyés à l'API a été copié depuis l'onglet Réseau du navigateur.
- Pas de description complète de l'offre (il faudrait une requête par fiche).
