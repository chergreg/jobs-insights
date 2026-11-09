# Sites d'offres d'emploi et de stages

**Profil ciblé :** emplois et stages en développement logiciel / informatique au Québec, avec intérêt pour les possibilités à distance.


## Sites à surveiller

| Site | Pourquoi il est pertinent | Filtres et renseignements à relever | Approche de collecte |
|---|---|---|---|
| [Guichet-Emplois (Job Bank)](https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=developpeur&locationstring=Quebec) | Site officiel fédéral; offres au Québec et emplois étudiants ou stages. | Mot-clé, province, date de publication, catégorie, étudiant/stage, temps plein ou partiel, langue, salaire, durée, lieu de travail (sur place, hybride ou à distance). Une offre contient notamment le titre, le lieu, l'employeur, le salaire et un lien. | **POC prioritaire :** le site fournit un flux Atom/RSS pour les résultats. Son `robots.txt` indique un délai de crawl de 5 secondes. Faire une requête à la fois, sans boucle de pagination; le script de cette recherche reprend les paramètres de catégorie vus dans le flux et filtre aussi les titres et lieux au Québec. |
| [Québec emploi](https://www.quebecemploi.gouv.qc.ca/plateforme-emploi/?lang=fr) | Portail du gouvernement du Québec; il annonce des postes à temps plein, à temps partiel, saisonniers, étudiants et des stages rémunérés. | Région, type ou durée d'emploi, niveau de formation, domaine d'études et type d'offre (régulier, étudiant ou stage). Certaines fonctions demandent un profil candidat. | À consulter manuellement. Avant tout POC, vérifier les conditions du portail et l'existence d'un flux ou d'une API publique. |
| [Emplois en ligne du gouvernement du Québec](https://emplois.carrieres.gouv.qc.ca/plateforme-emploi) et [emplois étudiants et stages](https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/) | Source directe pour les postes dans les ministères et organismes, y compris les possibilités étudiantes. | Domaine, région, statut étudiant/stage et renseignements propres à chaque offre. | À consulter manuellement; vérifier les conditions d'utilisation et les possibilités de flux avant l'automatisation. |
| [Jobillico](https://www.jobillico.com/recherche-emploi?sk=developpeur&l=Qu%C3%A9bec) | Site québécois qui peut faire ressortir des employeurs et des postes locaux. | Mot-clé et lieu dans la recherche; les fiches consultées présentent notamment les exigences, le niveau d'études, l'expérience et les langues. | À consulter manuellement pour l'instant. Le `robots.txt` comporte des restrictions sur certaines URL de recherche et de pagination; ne pas automatiser sans vérifier l'URL et les conditions applicables. |
| [LinkedIn Jobs](https://ca.linkedin.com/jobs/search/?keywords=stage%20d%C3%A9veloppement%20logiciel&location=Quebec) | Utile pour repérer les stages affichés par des entreprises technologiques et suivre leurs offres. | Mot-clé, lieu, date, niveau d'expérience, type d'emploi et modalités de travail selon les résultats de recherche. | **Consultation manuelle seulement.** Le `robots.txt` de LinkedIn indique que l'accès automatisé sans autorisation expresse est interdit. |
| [Indeed Canada](https://ca.indeed.com/) | Agrégateur généraliste avec des offres de stages et de postes juniors. | Mots-clés, lieu, date, type d'emploi et autres filtres proposés dans l'interface. | À consulter manuellement. La page de recherche n'était pas accessible pendant cette vérification (HTTP 403); ne pas contourner le blocage ni automatiser sans autorisation claire. |


## Plan d’évolution du POC

## 1 Explorer les possibilités de la source

Vérifier les filtres disponibles dans le flux et dans la recherche du Guichet-Emplois : mots-clés français et anglais, catégories informatiques, régions, stages et emplois étudiants.
Déterminer comment obtenir davantage de résultats que ceux d’une seule requête, et si le flux permet une pagination ou un nombre maximal d’annonces.
Vérifier les règles de collecte applicables avant de visiter les fiches d’offres.

## 2 Élargir la recherche d’offres

Rechercher avec plusieurs termes, par exemple développeur, programmeur, software developer, programmeur-analyste, et des termes propres aux stages.
Explorer les catégories pertinentes et les régions du Québec, en conservant les résultats hors Québec seulement si tu le souhaites.
Combiner les résultats, supprimer les doublons et garder le lien vers chaque annonce.
Respecter les délais et limites du site : le POC ne doit pas tenter de contourner un blocage ni provoquer un grand nombre de requêtes.

## 3 Récupérer les renseignements de chaque annonce

Extraire d’abord les champs fournis par le flux : titre, employeur, lieu, salaire, date et URL.
Si les règles du site le permettent, visiter ensuite chaque fiche et ajouter les renseignements disponibles : description, responsabilités, exigences, études, expérience, langues, durée, type d’emploi, horaire et modalités de travail.
Garder une valeur vide ou « non précisé » lorsqu’un renseignement n’est pas publié, plutôt que de l’inventer.

## 4 Détecter les stages

Analyser le titre et le contenu de l’annonce, en français et en anglais : stage, stagiaire, intern, internship, co-op, student et variantes.
Chercher aussi des indices comme la durée déterminée, la mention d’un programme d’études ou l’obligation d’être étudiant.
Classer les résultats en stage probable, non-stage ou à vérifier. Un mot-clé seul ne suffit pas toujours à trancher.

## 5 Enregistrer et vérifier les résultats

Définir une structure commune pour toutes les annonces, afin de comparer celles qui viennent de recherches différentes.
Ajouter des tests pour les champs extraits, les doublons et la classification des stages, avec des exemples français et anglais.
Vérifier le POC sur quelques annonces réelles, puis documenter les champs absents et les limites rencontrées.

## Le POC
Le script Python est une petite démonstration de collecte d’offres depuis le flux Atom/RSS public du Guichet-Emplois. Concrètement, il :

envoie une requête au flux avec un mot-clé et des catégories liées à l’informatique;
lit les résultats XML;
extrait le titre, le lieu, l’employeur, le salaire, la date et le lien de l’offre;
filtre les titres pertinents et les lieux au Québec;
affiche les offres trouvées dans le terminal.
Il ne visite pas chaque fiche d’emploi et ne contourne ni connexion ni protection. C’est volontairement une première expérience limitée : il ne récupère pas encore les descriptions complètes et ne détecte pas spécifiquement les stages.

## Pourquoi le Guichet-Emplois ?

Je l’ai choisi pour commencer parce que c’est une source officielle qui fournit déjà un flux de résultats lisible par programme. C’est plus simple et moins fragile que d’extraire les données directement depuis le HTML des pages. Son robots.txt indique un délai de crawl de cinq secondes; le POC se limite à une requête par lancement et n’automatise pas une collecte répétée.

D’autres sites intéressants sont recensés dans sites.md. Certains sont indiqués comme sources à consulter manuellement, notamment lorsque leurs règles ne permettent pas clairement l’automatisation.

## À quoi servent les deux autres fichiers ?

sites.md est la liste des sites ciblés, des filtres à explorer et des précautions de collecte.
test_poc_jobbank_rss.py vérifie le parseur avec un petit flux XML fictif : extraction des champs, filtre de lieu, reconnaissance des accents et paramètres de recherche. Ces tests vérifient la logique sans faire de requête Internet.

## Comment les données sont extraits ?

poc_multi_source.py interroge le Guichet-Emplois avec quatre termes — développeur, programmeur et des termes de stage — puis Remotive pour des offres en développement logiciel et en informatique. J’ai choisi Remotive parce qu’il fournit une API publique documentée; le POC respecte son attribution et son lien source.
Il rassemble les données dans un format commun, conserve les liens et les détails par source, dédoublonne les annonces répétées et classe les indices de stage comme « probable », « possible » ou « non indiqué ».