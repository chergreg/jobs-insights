# Kandet — offres d'emploi et de stage en informatique au Québec

Mon travail pour le projet `jobs-insights` :
- collecter les offres TI du Québec ;
- les enrichir et les rechercher dans une page Web ;
- comparer un CV et une lettre de motivation avec les offres.

Python 3.12 ou plus récent suffit : **rien à installer**.

## Essayer en 3 commandes

Dans PowerShell, depuis le dossier `jobs-insights` :

```powershell
cd .\equipe\kandet\03-amelioration-preuve-de-concept
python main.py --html                                      # collecte (environ 17 min la 1re fois, environ 1 min ensuite)
python main.py --depuis offres.json --cv cv-exemple.txt    # classement des offres pour un CV fictif
```

Ouvrez ensuite **`offres.html`** d'un double-clic. Dans la page, vous pouvez :
- filtrer par région, ville, technologie, niveau, salaire ou stage ;
- comparer les offres avec votre CV ;
- vérifier votre lettre pour une offre.

Le CV et la lettre restent dans le navigateur : rien n'est envoyé.

Pour vérifier que tout fonctionne (environ 1 seconde, sans Internet) :

```powershell
python -m unittest discover -p "test_*.py" -v
```

**Le guide complet** est au début de la [note du livrable 3](03-amelioration-preuve-de-concept/note-livrable-3.md#tester-le-projet-guide-rapide). Il couvre toutes les options, la collecte régulière et quoi faire si ça ne marche pas.

## Contenu du dossier

| Dossier | Contenu |
|---|---|
| [`01-inventaire-des-sites/`](01-inventaire-des-sites/sites.md) | Livrable 1 : sites d'offres d'emploi et de stage |
| [`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/compte-rendu-livrable-2.md) | Livrable 2 : premier prototype (Guichet-Emplois et Remotive) et son compte rendu |
| [`03-amelioration-preuve-de-concept/`](03-amelioration-preuve-de-concept/note-livrable-3.md) | Livrable 3 et suite : le projet actuel, sa [note](03-amelioration-preuve-de-concept/note-livrable-3.md) et son [plan de travail](03-amelioration-preuve-de-concept/plan.md) |
| [`format-commun/`](format-commun/README.md) | Mes offres converties au format commun de la classe (modèle `JobOffer` de Gregory). Dossier à part |

## Sources et règles

- **Sources :** le [Guichet-Emplois](https://www.guichetemplois.gc.ca/) (et les offres de ses partenaires) et l'API publique de [Remotive](https://remotive.com/).
- **Respect des sites :** 5 s entre deux requêtes au Guichet-Emplois (`robots.txt`), et Remotive au plus une fois par jour.
- **Sites écartés :** Québec emploi et Jobboom ne sont pas collectés, parce que leurs conditions d'utilisation l'interdisent.
- **Rien n'est deviné :** une information absente d'une offre reste vide.
- **Données personnelles :** aucun vrai CV dans le dépôt. `cv-exemple.txt` et `lettre-exemple.txt` sont fictifs.
