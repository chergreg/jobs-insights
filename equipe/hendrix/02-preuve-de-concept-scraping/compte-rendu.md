# Compte rendu — Livrable 2, Hendrix

## 1. Source et méthode

J'ai choisi [Remotive](https://remotive.com/remote-jobs), une plateforme spécialisée dans les offres d'emploi en télétravail.

Mon prototype Python utilise l'[API publique Remotive](https://remotive.com/api/remote-jobs?limit=1) pour récupérer automatiquement des offres au format JSON.

Le fichier [robots.txt](https://remotive.com/robots.txt) exclut les chemins `/api/*` de l'exploration par les robots. Le prototype utilise uniquement l'API publique documentée par Remotive et ne réalise pas de scraping des pages HTML.

### Technologies utilisées

- Python 3.13.7
- `urllib.request` : envoi des requêtes HTTP
- `json` : lecture et exportation des données
- `unittest` : tests automatisés
- Bibliothèque standard Python uniquement, sans dépendance externe

### Commande d'exécution

```powershell
python collecte_remotive.py --reel --limite 1 --sortie remotive-local.json
```

Le programme interroge l'API, récupère une offre et exporte les informations dans un fichier JSON.

## 2. Résultats simulés

Avant de réaliser une collecte réelle, j'ai testé le programme avec des données fictives.

Commande utilisée :

```powershell
python collecte_remotive.py --sortie exemple-simule.json
```

Le programme a généré un fichier JSON contenant deux offres fictives.

La première offre, « Développeur junior », contient les sept champs prévus par le prototype. La seconde, « Stage en informatique », permet de vérifier la gestion des données absentes : celles-ci sont représentées par `null`.

Six tests automatisés hors ligne ont été exécutés avec succès. Ils couvrent l'extraction, la validation des structures, la limitation du nombre d'offres, la simulation des requêtes, l'export JSON et la gestion des erreurs.

## 3. Essai réel du 24 novembre 2026

J'ai ensuite exécuté le prototype sur mon ordinateur en utilisant l'API publique de Remotive.

```powershell
python collecte_remotive.py --reel --limite 1 --sortie remotive-local.json
```

**Résultat : la collecte a réussi.** Le programme a exporté une véritable offre d'emploi au format JSON.

### Offre récupérée

| Information | Valeur |
|---|---|
| Titre | Content Reviewer - United States |
| Entreprise | TELUS Digital |
| Localisation | USA |
| Date de publication | 19 novembre 2026 |
| Rémunération affichée | 14 USD/heure |
| Description | Description récupérée, puis nettoyée en texte |
| Source | Remotive |

[Lien vers l'annonce originale](https://remotive.com/remote-jobs/all-others/content-reviewer-united-states-2091177)

### Comparaison avec l'annonce originale

Les informations extraites ont été comparées avec celles présentées sur Remotive.

Le titre du poste, le nom de l'entreprise, la localisation, la date de publication et la rémunération affichée correspondent.

Le programme récupère les données disponibles dans l'API et les transforme dans une structure JSON contenant sept champs :

1. `titre`
2. `entreprise`
3. `localisation`
4. `date_publication`
5. `description`
6. `salaire`
7. `url_originale`

## 4. Difficultés et limites observées

### Problème de connexion initial

Lors de la première tentative, la résolution DNS du domaine Remotive a échoué. Le programme n'a donc reçu aucune réponse HTTP.

Une nouvelle exécution sur mon ordinateur a permis de récupérer une offre réelle avec succès.

### Nettoyage des descriptions HTML

Lors de la collecte réelle, les descriptions contenaient des balises HTML et de nombreux attributs CSS.

J'ai amélioré le collecteur avec `HTMLParser`, une classe de la bibliothèque standard Python, afin de convertir ces descriptions en texte lisible.

Cette amélioration a été validée par un test automatisé. Les sept tests du prototype passent avec succès.

### Informations sur la rémunération

L'API affiche une rémunération de 14 USD/heure pour l'offre récupérée. Toutefois, l'annonce précise qu'il s'agit d'un potentiel estimé, puisque la rémunération dépend des tâches réalisées.

Le prototype conserve la valeur fournie par l'API sans l'interpréter comme un salaire garanti.

### Localisation des offres

L'offre récupérée concerne les États-Unis et comporte des exigences de résidence.

Le prototype ne filtre pas encore les offres selon leur admissibilité au Canada. Une amélioration serait d'ajouter un système de filtrage géographique.

### Limitation de la collecte

Le prototype limite volontairement la récupération à un maximum de dix offres par exécution afin de rester adapté à une démonstration pédagogique.

### Amélioration de la classification géographique

J'ai ajouté une fonction `classifier_localisation()` pour classer les indications géographiques fournies par Remotive.

Le programme distingue notamment le Canada, le Québec, les États-Unis, les offres mondiales, l'Amérique du Nord et les localisations inconnues.

La localisation originale est conservée dans le JSON et une nouvelle propriété `categorie_localisation` est ajoutée.

Cette amélioration a été vérifiée par des tests automatisés couvrant plusieurs cas géographiques. Les huit tests du prototype passent.

La classification est indicative : elle ne confirme ni la localisation physique du poste ni l'admissibilité d'un candidat à l'offre.

### Amélioration : suppression des doublons

J'ai ajouté un mécanisme de détection des doublons afin d'éviter l'exportation répétée d'une même offre.

Le programme mémorise les URL des offres déjà rencontrées. Lorsqu'une URL apparaît plusieurs fois, seule la première offre correspondante est conservée.

Les offres dont l'URL est absente restent conservées, car il n'est pas possible de confirmer qu'elles sont identiques.

Un nouveau test automatisé vérifie cette fonctionnalité. Le prototype comporte désormais neuf tests automatisés réussis.

Cette méthode possède une limite : deux offres identiques utilisant des URL différentes ne seront pas détectées comme doublons.

## 5. Conclusion

Ce Livrable 2 m'a permis d'expérimenter la collecte automatique de données depuis une source d'offres d'emploi.

J'ai développé un prototype Python capable d'interroger une API publique, de récupérer des informations, de gérer les valeurs manquantes et d'exporter les résultats au format JSON.

Les tests simulés et la collecte réelle montrent que cette approche fonctionne.

Les principales améliorations possibles concernent le filtrage géographique et l'exploitation des données récupérées.

Ce prototype constitue une première étape vers un système de collecte et de normalisation d'offres d'emploi.
