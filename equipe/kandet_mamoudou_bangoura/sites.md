# Sites d'offres d'emploi et de stages

**Profil ciblé :** emplois et stages en développement logiciel / informatique au Québec, avec intérêt pour les possibilités à distance.

**Recherche effectuée le :** 9 novembre 2026.

## Sites à surveiller

| Site | Pourquoi il est pertinent | Filtres et renseignements à relever | Approche de collecte |
|---|---|---|---|
| [Guichet-Emplois (Job Bank)](https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=developpeur&locationstring=Quebec) | Site officiel fédéral; offres au Québec et emplois étudiants ou stages. | Mot-clé, province, date de publication, catégorie, étudiant/stage, temps plein ou partiel, langue, salaire, durée, lieu de travail (sur place, hybride ou à distance). Une offre contient notamment le titre, le lieu, l'employeur, le salaire et un lien. | **POC prioritaire :** le site fournit un flux Atom/RSS pour les résultats. Son `robots.txt` indique un délai de crawl de 5 secondes. Faire une requête à la fois, sans boucle de pagination; le script de cette recherche reprend les paramètres de catégorie vus dans le flux et filtre aussi les titres et lieux au Québec. |
| [Remotive](https://remotive.com/remote-jobs) | Tableau d'offres à distance avec une API publique; peut compléter les offres locales par des postes ouverts au Canada ou partout dans le monde. | Catégorie, recherche dans le titre/description, entreprise, type d'emploi, date, lieu requis, salaire, étiquettes et description complète. L'API distingue notamment les stages avec `job_type=internship`. | **Deuxième source du POC :** lire la liste complète des annonces actives sans paramètre `limit`, puis garder localement les catégories informatiques pertinentes. Les annonces sont retardées de 24 h; la documentation recommande au plus 4 requêtes par jour. Le POC met la réponse complète en cache local pendant 24 h et n'envoie qu'une requête lors du rafraîchissement. |
| [Québec emploi](https://www.quebecemploi.gouv.qc.ca/plateforme-emploi/?lang=fr) | Portail du gouvernement du Québec; il annonce des postes à temps plein, à temps partiel, saisonniers, étudiants et des stages rémunérés. | Région, type ou durée d'emploi, niveau de formation, domaine d'études et type d'offre (régulier, étudiant ou stage). Certaines fonctions demandent un profil candidat. | À consulter manuellement. Avant tout POC, vérifier les conditions du portail et l'existence d'un flux ou d'une API publique. |
| [Emplois en ligne du gouvernement du Québec](https://emplois.carrieres.gouv.qc.ca/plateforme-emploi) et [emplois étudiants et stages](https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/) | Source directe pour les postes dans les ministères et organismes, y compris les possibilités étudiantes. | Domaine, région, statut étudiant/stage et renseignements propres à chaque offre. | À consulter manuellement; vérifier les conditions d'utilisation et les possibilités de flux avant l'automatisation. |
| [Jobillico](https://www.jobillico.com/recherche-emploi?sk=developpeur&l=Qu%C3%A9bec) | Site québécois qui peut faire ressortir des employeurs et des postes locaux. | Mot-clé et lieu dans la recherche; les fiches consultées présentent notamment les exigences, le niveau d'études, l'expérience et les langues. | À consulter manuellement pour l'instant. Le `robots.txt` comporte des restrictions sur certaines URL de recherche et de pagination; ne pas automatiser sans vérifier l'URL et les conditions applicables. |
| [LinkedIn Jobs](https://ca.linkedin.com/jobs/search/?keywords=stage%20d%C3%A9veloppement%20logiciel&location=Quebec) | Utile pour repérer les stages affichés par des entreprises technologiques et suivre leurs offres. | Mot-clé, lieu, date, niveau d'expérience, type d'emploi et modalités de travail selon les résultats de recherche. | **Consultation manuelle seulement.** Le `robots.txt` de LinkedIn indique que l'accès automatisé sans autorisation expresse est interdit. |
| [Indeed Canada](https://ca.indeed.com/) | Agrégateur généraliste avec des offres de stages et de postes juniors. | Mots-clés, lieu, date, type d'emploi et autres filtres proposés dans l'interface. | À consulter manuellement. La page de recherche n'était pas accessible pendant cette vérification (HTTP 403); ne pas contourner le blocage ni automatiser sans autorisation claire. |

## POC multi-sources

Le POC est [`poc_multi_source.py`](poc_multi_source.py). Il combine le flux Atom du Guichet-Emplois avec l'API JSON publique de Remotive dans un modèle commun. Il conserve les informations et liens propres à chaque source, fusionne les occurrences d'un même identifiant dans les requêtes répétées sans supprimer les annonces distinctes d'une même source, et classe les stages comme `confirmed_stage`, `possible_stage` ou `not_indicated`.

```powershell
python .\recherche\poc_multi_source.py
python .\recherche\poc_multi_source.py --jobbank-term developpeur --jobbank-term stage
python .\equipe\kandet_mamoudou_bangoura\poc_multi_source.py --canada-remotive-only
python -m unittest discover -s .\recherche -p "test_poc_*.py"
```

Par défaut, le Guichet-Emplois est interrogé avec quatre termes — `developpeur`, `programmeur`, `stage informatique` et `internship` — en espaçant les requêtes d'au moins cinq secondes conformément au `robots.txt`. Chaque requête demande 100 résultats, mais le flux peut renvoyer une page plus courte; la pagination continue donc jusqu'à une page vide ou répétée. Il n'y a pas de nombre maximal de pages ni de plafond d'offres affichées. Le paramètre `page=2` a été vérifié sur le flux. Les résultats hors du lieu demandé sont filtrés après lecture de chaque page. Les entrées répétées entre les pages ou les termes sont fusionnées par identifiant de l'offre et conservent les termes qui les ont trouvées; des offres différentes d'une même source ne sont pas fusionnées uniquement parce que titre, employeur et lieu sont identiques. Le résumé JSON présente les résultats par terme, nombre de pages et source. Remotive est appelé sans `limit` (la documentation indique que la valeur par défaut renvoie toutes les annonces actives), puis filtré localement aux catégories liées au domaine : développement logiciel, informatique, IA, données, DevOps, assurance qualité, génie, gestion de produit, design et recherche. Le filtrage géographique Remotive est désactivé par défaut pour garder toutes les offres; `--canada-remotive-only` permet de limiter au Canada, au Québec, à l'Amérique du Nord et au monde entier. Remotive est interrogé une seule fois par rafraîchissement, et sa réponse est réutilisée depuis `remotive-cache.json` durant 24 heures. Le cache limité de l'ancienne version est invalidé au prochain appel. Le cache et `offres.json` restent dans le dossier local ignoré par Git.

```powershell
python .\equipe\kandet_mamoudou_bangoura\poc_multi_source.py --refresh-remotive
```

Le rafraîchissement forcé compte comme une requête Remotive; sa documentation recommande au plus quatre requêtes par jour. Le fichier `offres.json` garde les champs normalisés, les détails propres à chaque source, les liens d'origine, les termes ayant trouvé chaque offre et les statistiques de collecte. Un stage est « confirmé » quand le type Remotive est explicitement `internship` ou que le titre nomme clairement un stage; un rôle de stage mentionné dans la description ou une condition d'inscription étudiante est classé « possible ». Une mention d'expérience antérieure en stage ne suffit pas à classer un emploi régulier comme stage. Job Bank fournit surtout un résumé dans son flux, alors que Remotive fournit une description complète; les champs absents d'une source restent vides. Les règles textuelles peuvent manquer des stages formulés autrement. L'absence de limite de collecte ne permet pas de promettre toutes les offres existantes : le nombre dépend des annonces fournies par les sources, des catégories interrogées, de leurs règles et de la pagination disponible.

## Sources et limites de la recherche

- [Filtres de recherche du Guichet-Emplois](https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=developpeur&locationstring=Quebec) et [robots.txt](https://www.jobbank.gc.ca/robots.txt).
- [Documentation de l'API Remotive](https://github.com/remotive-com/remote-jobs-api).
- [Québec emploi — consulter les offres](https://www.quebec.ca/emploi/trouver-emploi-stage/consulter-offres-emplois).
- [Jobillico — robots.txt](https://www.jobillico.com/robots.txt).
- [LinkedIn — robots.txt](https://www.linkedin.com/robots.txt).
- [Indeed Canada — robots.txt](https://ca.indeed.com/robots.txt).

Les filtres affichés, les offres et les règles des sites peuvent changer. Cette liste sert de point de départ pour l'atelier; elle ne constitue pas une autorisation de collecte automatisée. Le dossier `recherche` est volontairement local et exclu de GitHub.
