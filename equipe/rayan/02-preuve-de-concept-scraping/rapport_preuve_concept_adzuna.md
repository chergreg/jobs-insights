# Livrable 2 — Preuve de concept de scraping

## 1. Site et source testés

- **Site :** Adzuna Canada
- **Site web :** https://www.adzuna.ca/
- **API utilisée :** `https://api.adzuna.com/v1/api/jobs/ca/search/{page}`
- **Documentation officielle :** https://developer.adzuna.com/docs/search

La preuve de concept a été réalisée avec l'API de recherche d'Adzuna plutôt qu'en analysant directement le code HTML des pages web. L'API renvoie les offres sous forme de données JSON, ce qui facilite leur lecture et leur traitement.

## 2. Méthode et outils utilisés

### Principe de fonctionnement

Le prototype envoie des requêtes HTTP à l'API Adzuna. Chaque requête précise notamment le pays (`ca`), le mot-clé (`what`), la zone géographique (`where`), la catégorie (`category`, notamment `it-jobs`) et la page de résultats.

L'API retourne une réponse JSON contenant notamment le nombre total de résultats et une liste d'offres. Le script parcourt cette liste et extrait les champs disponibles.

Deux séries d'essais ont été effectuées :

1. **Premier essai :** vérification de l'accès à l'API, récupération des catégories et recherche de quelques mots-clés.
2. **Deuxième essai :** tests plus ciblés sur deux villes québécoises, plusieurs mots-clés liés à l'informatique et plusieurs pages de résultats. Le prototype enregistre aussi les réponses JSON brutes pour permettre leur examen.

### Outils et dépendances

- Python 3
- La bibliothèque Python `requests` pour effectuer les requêtes HTTP
- Les bibliothèques standard Python pour manipuler les variables d'environnement et les fichiers JSON
- Une clé API Adzuna (`app_id` et `app_key`)

Les identifiants sont fournis au script au moyen de variables d'environnement, plutôt que d'être inscrits directement dans le code.

### Configuration et commande de lancement

Définir les variables d'environnement `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` avec les identifiants de son propre compte Adzuna, puis lancer :

```bash
python adzuna_test_2.py
```

Dépendance externe à installer :

```bash
pip install requests
```

Le deuxième prototype enregistre les réponses individuelles et un fichier récapitulatif dans le dossier `adzuna_test_output` lorsque l'exécution arrive à son terme.

> **Sécurité :** ne jamais publier `app_id` ou `app_key` dans le dépôt Git, le compte rendu ou les journaux du programme. Lors d'un essai, une URL d'erreur affichée dans la sortie contenait les paramètres d'authentification. La clé concernée doit être renouvelée et les journaux doivent masquer ces paramètres.

## 3. Données récupérées

Selon les données fournies par Adzuna, les champs disponibles peuvent comprendre :

- l'identifiant de l'offre ;
- le titre du poste ;
- le nom de l'employeur ;
- le lieu affiché et les éléments de localisation ;
- la date de publication ;
- la catégorie ;
- un extrait de la description ;
- le lien de redirection vers l'offre (`redirect_url`) ;
- parfois, une fourchette salariale (`salary_min`, `salary_max`) et l'indicateur `salary_is_predicted` ;
- parfois, le type de contrat (`contract_type`) et le temps de travail (`contract_time`).

### Exemples de résultats observés

Lors du premier essai, les recherches ont notamment retourné les volumes suivants :

| Mot-clé | Zone recherchée | Catégorie | Nombre total annoncé par l'API |
|---|---|---|---:|
| `développeur` | Montréal | `it-jobs` | 1 224 |
| `developer` | Québec | — | 4 661 |
| `devops` | Montréal | — | 1 410 |

Ces nombres correspondent aux totaux annoncés par l'API pour les recherches effectuées. Ils ne représentent pas nécessairement le nombre d'offres uniques, pertinentes et effectivement récupérées par le prototype.

Le deuxième essai a permis d'observer des annonces avec des champs salariaux renseignés. Par exemple, une annonce d'**Analyste spécialisé en informatique chez Santé Québec** présentait une fourchette de `65 478` à `120 120`. Une annonce d'**Administrateur systèmes chez TS Imagine** présentait plutôt une valeur de `1 500` à `1 500`.

Ces valeurs montrent que les champs salariaux existent, mais elles ne permettent pas à elles seules de déterminer la période de rémunération (à l'heure, au mois ou à l'année). Il ne faut donc pas les afficher ou les comparer comme des salaires annuels sans validation supplémentaire.

## 4. Difficultés, limites et observations

### 4.1 Pertinence des résultats

Les mots-clés ne renvoient pas uniquement des offres dont le titre correspond exactement à la recherche. Par exemple :

- une recherche avec `programmeur` a retourné un poste d'analyste actuariel ;
- des recherches autour de `développeur` ont aussi retourné des postes de Product Owner ;
- une recherche sur `administrateur système` a pu retourner des postes DevOps.

**Observation :** la recherche par mot-clé de l'API constitue un premier filtre, mais elle ne suffit pas pour garantir la pertinence des annonces. Une étape de filtrage complémentaire à partir du titre et de la description sera nécessaire.

### 4.2 Précision géographique

Une recherche effectuée avec `where="Québec, Québec"` a retourné des offres situées à Québec, mais aussi à Montréal, Boisbriand, Trois-Rivières et Saint-Hyacinthe.

**Observation :** le paramètre géographique ne garantit pas que toutes les annonces retournées se trouvent dans la ville exacte demandée. Il faudra examiner les informations de localisation de chaque offre et appliquer un filtre géographique complémentaire. Les offres à distance ou dont le lieu est imprécis devront être traitées séparément.

### 4.3 Salaire et contrat

Les informations salariales et contractuelles ne sont pas présentes dans toutes les annonces.

- Les champs `salary_min` et `salary_max` sont parfois absents.
- Lorsqu'ils sont présents, les montants ne précisent pas toujours leur période de référence.
- `salary_is_predicted` indique si le salaire est estimé par Adzuna ; il ne confirme pas, à lui seul, que le montant est exact ou que sa période est connue.
- `contract_type` et `contract_time` sont également renseignés de façon irrégulière.

**Observation :** ces champs doivent rester facultatifs. Une valeur manquante doit être considérée comme inconnue, et non remplacée par une supposition. Il faudra distinguer les informations fournies directement par l'API de celles qui pourraient être extraites ultérieurement du texte de l'annonce.

### 4.4 Doublons

Une même offre peut apparaître dans les résultats de plusieurs recherches effectuées avec des mots-clés différents.

**Observation :** il faudra dédupliquer les annonces avant de les présenter. Une clé basée sur la source et l'identifiant externe de l'offre (par exemple `(source, external_id)`) est préférable à l'utilisation de l'identifiant seul si plusieurs plateformes sont intégrées.

### 4.5 Pagination et disponibilité de l'API

Le deuxième essai a parcouru plusieurs pages de résultats. Certaines recherches ont retourné moins de résultats que le nombre maximal demandé par page. Une requête a également échoué avec une réponse HTTP **503** (service temporairement indisponible).

**Observation :** une erreur 503 ne signifie pas nécessairement que la clé API ou le prototype est incorrect. Le programme devra prévoir des tentatives limitées avec un délai progressif pour les erreurs temporaires, notamment les réponses 429 et 5xx. Il devra aussi sauvegarder les résultats au fur et à mesure afin de ne pas perdre les données déjà collectées lorsqu'une requête échoue.

### 4.6 Description des annonces

La documentation de l'API indique que le champ de description fourni dans les résultats de recherche peut être un extrait plutôt que le texte intégral de l'annonce.

**Observation :** cet extrait peut être insuffisant pour analyser précisément les compétences demandées, les conditions de travail ou les informations salariales. Il faudra tenir compte de cette limite avant de concevoir un système de classement fondé sur la description.

## 5. Pistes d'amélioration

À la suite de ces essais, les améliorations suivantes sont envisagées :

1. Ajouter un mécanisme de reprise limité pour les erreurs temporaires HTTP (429 et 5xx), avec un délai progressif.
2. Sauvegarder chaque réponse dès qu'elle est reçue afin de conserver les résultats même si une requête ultérieure échoue.
3. Dédupliquer les offres à partir de la source et de l'identifiant externe.
4. Ajouter un filtre de pertinence fondé sur le titre et, lorsque disponible, la description.
5. Vérifier la localisation réelle des annonces avant de les associer à une ville précise.
6. Traiter le salaire et les informations contractuelles comme des données facultatives et ne pas supposer leur signification lorsqu'elle n'est pas explicitement indiquée.
7. Prévoir l'affichage de l'attribution **« Jobs by Adzuna »** et utiliser le champ `redirect_url` pour rediriger l'utilisateur vers l'annonce d'origine.

## 6. Conclusion

La preuve de concept confirme qu'il est techniquement possible de récupérer automatiquement des offres d'emploi d'Adzuna au moyen de son API officielle. Le prototype a réussi à obtenir des résultats pour plusieurs mots-clés et zones géographiques, et à extraire des informations utiles comme le titre, l'employeur, la localisation, la date et le lien de l'annonce.

Les essais montrent toutefois que les données ne sont pas toujours complètes ou parfaitement précises : les résultats peuvent être peu pertinents, la localisation peut dépasser la ville recherchée, les informations salariales et contractuelles sont irrégulières, et des doublons peuvent apparaître.

**Bilan :** Adzuna est une source exploitable pour collecter des annonces, mais les données récupérées devront être nettoyées, filtrées et validées avant d'être utilisées dans un agrégateur d'offres d'emploi.
