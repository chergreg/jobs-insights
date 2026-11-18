
# Livrable 2 — Preuve de concept de scraping Web

## 1. Présentation du projet

L'objectif de ce livrable est de développer une preuve de concept de scraping Web permettant d'extraire automatiquement des informations provenant d'une offre d'emploi publiée sur Internet.

Pour cette expérimentation, j'ai choisi le site Guichet-Emplois du gouvernement du Canada.

Le prototype est développé en Python avec les bibliothèques Requests et BeautifulSoup.

L'objectif est de récupérer trois informations :
- Le titre du poste
- Le nom de l'employeur
- Le lien de l'offre d'emploi

## 2. Site et offre testés

- **Site Web :** Guichet-Emplois
- **Adresse du site :** https://www.guichetemplois.gc.ca/
- **URL de l'offre testée :** https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50703263
- **Titre du poste :** administrateur/administratrice de base de données
- **Employeur :** imperial truck & trailer repair ltd

Cette offre a été sélectionnée pour vérifier si les informations affichées dans le navigateur pouvaient également être récupérées automatiquement à partir du HTML.

## 3. Technologies utilisées

| Technologie | Utilisation |
|---|---|
| Python 3.13 | Développement du script |
| Requests | Envoi de la requête HTTP |
| BeautifulSoup | Analyse et extraction des données HTML |
| Visual Studio Code | Écriture et exécution du programme |
| Git et GitHub | Gestion et publication des fichiers |

## 4. Méthodologie

### 4.1 Inspection du HTML

J'ai commencé par ouvrir l'offre d'emploi dans un navigateur et inspecter son code HTML.

Cette inspection m'a permis d'identifier les éléments suivants :

- Le titre du poste se trouve dans une balise `span` avec l'attribut `property="title"`.
- Le nom de l'employeur apparaît dans une balise `strong`.

### 4.2 Premier test local

Avant d'effectuer une requête HTTP, j'ai créé un extrait HTML contenant le titre et l'employeur de l'offre.

J'ai ensuite utilisé BeautifulSoup pour analyser cet extrait et extraire les deux informations.

Le premier test a réussi et a confirmé que les sélecteurs utilisés permettaient de lire les données de l'extrait HTML.

### 4.3 Récupération du HTML réel

J'ai ensuite utilisé la bibliothèque Requests pour envoyer une requête HTTP GET vers l'offre d'emploi.

Le serveur a retourné les informations suivantes :

- **Statut HTTP :** 200
- **Type de contenu :** text/html;charset=UTF-8
- **Taille de la réponse :** 201052 octets

Le code HTTP 200 indique que la requête a été traitée avec succès.

### 4.4 Extraction automatique

Le HTML récupéré a été analysé avec BeautifulSoup.

Le script a ensuite :
1. Recherché le titre du poste dans une balise `span`.
2. Recherché l'employeur dans une balise `strong` contenant le texte « imperial truck ».
3. Affiché l'URL de l'offre à partir de la réponse HTTP.

Les trois informations ont été affichées dans le terminal.

## 5. Instructions d'installation et d'exécution

### 5.1 Prérequis

- Python 3
- Une connexion Internet
- Les bibliothèques `requests` et `beautifulsoup4`

### 5.2 Installation des dépendances

Depuis un terminal, exécuter :

    python -m pip install requests beautifulsoup4

### 5.3 Exécution du script

Depuis le dossier racine du dépôt `jobs-insights`, exécuter :

    python "equipe/nonga/02-preuve-de-concept-scraping/scraper.py"

Le programme effectue une requête vers l'offre sélectionnée et affiche les résultats dans le terminal.

## 6. Résultats obtenus

Voici le résultat observé lors de l'exécution du programme :

    Statut HTTP : 200
    Type de contenu : text/html;charset=UTF-8
    Taille de la réponse : 201052 octets
    Titre extrait du site : administrateur/administratrice de base de données
    Employeur extrait du site : imperial truck & trailer repair ltd
    Lien de l'offre : https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50703263

### Comparaison avec le site Web

| Information | Résultat du script | Vérification |
|---|---|---|
| Titre | administrateur/administratrice de base de données | Correspond au titre observé |
| Employeur | imperial truck & trailer repair ltd | Correspond à l'employeur observé |
| Lien | URL de l'offre 50703263 | Correspond à l'offre testée |

Les informations extraites correspondent aux éléments observés sur la page lors de l'expérimentation.

Cette preuve de concept démontre qu'il est possible de récupérer automatiquement les informations recherchées pour cette offre précise.

## 7. Difficultés rencontrées

### Identification des éléments HTML

Il a d'abord fallu inspecter la structure HTML pour déterminer où se trouvaient les informations recherchées.

L'utilisation de BeautifulSoup a facilité l'analyse des balises et l'extraction des données.

### Passage du HTML local au site réel

Le premier test utilisait un extrait HTML écrit manuellement.

Ce test ne suffisait pas à démontrer un scraping réel. J'ai donc ajouté Requests pour récupérer directement le contenu HTML depuis le site.

### Sélection de l'employeur

La balise `strong` n'est pas nécessairement unique sur une page HTML.

Pour éviter de sélectionner un élément incorrect, j'ai limité la recherche à une balise contenant le texte « imperial truck ».

Cette solution fonctionne pour l'offre testée, mais elle n'est pas encore généralisable à toutes les offres.

## 8. Limites du prototype

Le prototype présente plusieurs limites :

- **Une seule offre testée :** le fonctionnement n'a pas été vérifié sur plusieurs annonces.
- **Employeur spécifique :** la recherche du nom de l'employeur dépend du texte « imperial truck ».
- **Structure HTML :** si le site modifie ses balises, les sélecteurs pourraient ne plus fonctionner.
- **Disponibilité des annonces :** une offre peut expirer ou être retirée.
- **Aucune sauvegarde :** les résultats sont affichés dans le terminal, sans exportation vers un fichier ou une base de données.
- **Aucune collecte massive :** le prototype effectue une seule requête par exécution.

### Considérations liées au scraping

J'ai consulté le fichier `robots.txt` du site, qui affichait les directives suivantes lors de la vérification :

    User-agent: *
    Crawl-delay: 5

Ces directives indiquent notamment un délai demandé de cinq secondes entre les requêtes des robots qui prennent en charge cette directive.

L'absence de directive `Disallow` dans le contenu consulté ne constitue pas une autorisation générale de scraping. Les conditions d'utilisation du site doivent également être respectées.

## 9. Améliorations possibles

Plusieurs améliorations pourraient être envisagées :

1. Développer un sélecteur permettant d'extraire le nom de l'employeur sans connaître celui-ci à l'avance.
2. Tester le programme sur plusieurs offres.
3. Ajouter l'extraction du lieu de travail, du salaire et de la date de publication.
4. Enregistrer les résultats dans un fichier JSON ou CSV.
5. Ajouter une gestion plus détaillée des erreurs et des changements de structure HTML.
6. Respecter les restrictions du site et les délais applicables avant toute automatisation répétée.

## 10. Conclusion

Cette preuve de concept m'a permis de découvrir et de mettre en pratique les principales étapes du scraping Web avec Python.

J'ai appris à inspecter une page HTML, identifier des balises pertinentes, récupérer une page avec Requests et extraire des informations avec BeautifulSoup.

Les tests ont permis de récupérer le titre, le nom de l'employeur et le lien d'une offre réelle de Guichet-Emplois.

Le prototype atteint donc son objectif pour l'offre sélectionnée, même si des améliorations seraient nécessaires pour traiter automatiquement plusieurs annonces.

## 11. Fichiers du livrable

Les fichiers sont regroupés dans le dossier :

    equipe/nonga/02-preuve-de-concept-scraping/

- `scraper.py` : script Python de récupération et d'extraction des données.
- `rapport.md` : documentation de l'expérimentation, des résultats et des limites.
