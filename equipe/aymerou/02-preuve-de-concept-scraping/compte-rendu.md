# Livrable 2 - Preuve de concept scraping

## 1. Objectif

L'objectif est de récupérer automatiquement des offres d'emploi
dans le domaine de l'informatique avec Python.

## 2. Premier test avec Indeed

J'ai commencé par tester le site Indeed avec la bibliothèque
requests. Malheureusement, le site a retourné un statut HTTP 403,
ce qui signifie que l'accès à la page a été refusé.

J'ai donc décidé de tester un autre site.

## 3. Test avec Guichet-Emplois

J'ai ensuite testé le site Guichet-Emplois. La requête a retourné
un statut HTTP 200, ce qui signifie que la requête a réussi.

Avec BeautifulSoup, j'ai analysé le HTML de la page pour
récupérer les informations suivantes :

- Le titre de l'offre
- Le nom de l'entreprise
- La ville
- Le salaire
- La date de publication

## 4. Nettoyage des données

Certaines informations contenaient des mots et des espaces
inutiles. J'ai utilisé replace() et strip() pour les supprimer.

## 5. Résultat

J'ai réussi à récupérer 25 offres d'emploi et à les enregistrer
dans un fichier JSON nommé offres_guichet.json.

## 6. Bibliothèques utilisées

- requests : pour envoyer la requête HTTP.
- beautifulsoup4 : pour analyser le HTML.
- json : pour enregistrer les données.
- pathlib : pour gérer le chemin du fichier.

## 7. Exécution du programme

Depuis le dossier du livrable 2 :

```bash
python -m pip install -r requirements.txt
python scraping_guichet.py
```

## 8. Limites et améliorations possibles

Pour le moment, mon programme récupère les offres d'une seule
page du site Guichet-Emplois.

Les salaires et les dates sont encore sous forme de texte.

Pour le prochain livrable, je pourrai améliorer la structure
des données et la gestion des erreurs.