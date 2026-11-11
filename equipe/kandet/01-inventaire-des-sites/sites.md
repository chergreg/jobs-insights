# Inventaire des sites d'emplois et de stages

**Profil ciblé :** emplois et stages en développement logiciel et en informatique, en priorité au Québec. Les postes à distance ouverts au Canada ou à l'international complètent les résultats locaux.

**Mise à jour :** 11 novembre 2026.

## Sources et état d'intégration

| Source | Intérêt et renseignements disponibles | État dans le POC et précautions |
|---|---|---|
| [Guichet-Emplois (Job Bank)](https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=developpeur&locationstring=Quebec) | Source fédérale d'offres au Canada. Le flux fournit le titre, le lieu, l'employeur, le salaire, la date, le numéro d'offre et le lien lorsqu'ils sont présents. Les recherches par catégories peuvent inclure des postes informatiques et des stages. | **Intégré.** Le POC lit le flux Atom, demande 100 résultats par page et suit les pages jusqu'à une page vide ou déjà rencontrée. Il attend au moins cinq secondes entre les requêtes conformément au délai indiqué dans le [`robots.txt`](https://www.jobbank.gc.ca/robots.txt). La recherche cible le Québec par défaut. Le flux fournit un résumé, pas nécessairement la description complète. |
| [Remotive](https://remotive.com/remote-jobs) | Source d'emplois à distance avec catégorie, entreprise, type d'emploi, lieu requis, salaire, date, étiquettes et description. Le type d'emploi peut indiquer explicitement un stage. | **Intégré.** Le POC appelle l'[API publique](https://github.com/remotive-com/remote-jobs-api) sans paramètre `limit` et filtre localement dix catégories liées à l'informatique, au génie, aux données, à l'IA et aux domaines connexes. Tous les lieux sont conservés par défaut; `--canada-remotive-only` applique un filtre géographique. La réponse est mise en cache 24 heures; la documentation recommande au plus quatre requêtes par jour. Conserver l'attribution et le lien d'origine; ne pas republier les annonces Remotive sur un site tiers. |
| [Québec emploi](https://www.quebecemploi.gouv.qc.ca/plateforme-emploi/?lang=fr) | Portail québécois proposant des emplois réguliers, étudiants et des stages, avec des filtres par région et domaine. | **Non intégré.** À consulter manuellement en attendant de confirmer une API ou un flux public et les conditions d'utilisation. |
| [Emplois du gouvernement du Québec](https://emplois.carrieres.gouv.qc.ca/plateforme-emploi) et [emplois étudiants et stages](https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/) | Source directe de postes dans les ministères et organismes, y compris les possibilités étudiantes. | **Non intégré.** À consulter manuellement; vérifier les moyens d'accès autorisés avant toute automatisation. |
| [Jobillico](https://www.jobillico.com/recherche-emploi?sk=developpeur&l=Qu%C3%A9bec) | Site québécois utile pour repérer les employeurs, les exigences, les études, l'expérience et les langues demandées. | **Non intégré.** Consultation manuelle pour l'instant. Vérifier les conditions et les règles de `robots.txt` pour chaque type de page avant toute collecte automatisée. |
| [LinkedIn Jobs](https://ca.linkedin.com/jobs/search/?keywords=stage%20d%C3%A9veloppement%20logiciel&location=Quebec) | Offre des filtres par mot-clé, lieu, date, niveau d'expérience, type d'emploi et modalités de travail. | **Non intégré.** Consultation manuelle seulement; ne pas automatiser sans autorisation expresse. Voir le [`robots.txt`](https://www.linkedin.com/robots.txt). |
| [Indeed Canada](https://ca.indeed.com/) | Agrégateur généraliste avec des offres de stages et de postes juniors; filtres par mot-clé, lieu, date et type d'emploi. | **Non intégré.** Consultation manuelle. Une recherche était inaccessible (HTTP 403) lors d'une vérification antérieure; ne pas contourner les blocages. Revalider l'accès et les conditions avant tout projet d'intégration. |

## Fonctionnement actuel du POC

Le code, les tests et les résultats locaux se trouvent dans [`02-preuve-de-concept-scraping/`](../02-preuve-de-concept-scraping/). Le collecteur fusionne les occurrences répétées d'une même annonce, conserve les liens et données par source et évite de fusionner deux annonces distinctes d'une source uniquement parce que leur titre et leur employeur se ressemblent.

### Collecte du Guichet-Emplois

- Quatre termes sont recherchés par défaut : `developpeur`, `programmeur`, `stage informatique` et `internship`.
- Le flux est interrogé avec trois codes de catégories informatiques (`21230`, `21232`, `21234`) et jusqu'à 100 résultats demandés par page.
- La pagination continue jusqu'à une page vide ou répétée; une page courte ne suffit pas à arrêter la recherche. Il n'y a pas de plafond configuré de pages ou d'offres.
- Les offres hors du lieu demandé sont filtrées après lecture de la page. Le Québec (`QC`) est le lieu par défaut; `--all-jobbank-locations` retire ce filtre.
- Le résumé fournit généralement le titre, le lieu, l'employeur, le salaire et le lien. La fiche de chaque annonce n'est pas visitée par le POC; les descriptions et exigences absentes du flux ne sont donc pas récupérées.

### Collecte de Remotive

- L'API est appelée sans paramètre `limit`, puis les annonces sont filtrées localement selon dix catégories pertinentes : développement logiciel, informatique, intelligence artificielle, données et analytique, DevOps, assurance qualité, génie, gestion de produit, design et recherche.
- Le lieu n'est pas filtré par défaut afin de conserver les postes à distance ouverts dans d'autres régions. `--canada-remotive-only` permet de limiter les résultats au Canada, au Québec, à l'Amérique du Nord et aux offres mondiales.
- La réponse complète de l'API est gardée dans `remotive-cache.json` pendant 24 heures. `--refresh-remotive` force une nouvelle requête; l'utiliser avec modération conformément à la recommandation de l'API.
- La description de l'offre est récupérée depuis l'API. Les champs absents restent vides plutôt que d'être devinés.

### Détection des stages et résultats

Le collecteur attribue l'un de ces états :

- `confirmed_stage` : le type de poste indique explicitement un stage, ou le titre contient un terme de stage reconnu;
- `possible_stage` : la description indique un rôle de stage ou une condition d'inscription étudiante;
- `not_indicated` : aucun de ces indices n'a été trouvé.

Cette classification repose sur des règles textuelles : une formulation inhabituelle peut ne pas être reconnue. Une offre « non indiquée » n'est donc pas nécessairement un poste sans stage.

Lancer la collecte depuis la racine du dépôt :

```powershell
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py
```

Exemples pour élargir les termes, les lieux ou rafraîchir la source distante :

```powershell
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --jobbank-term developpeur --jobbank-term stage
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --all-jobbank-locations
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --canada-remotive-only
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --refresh-remotive
```

Les résultats sont écrits dans `offres.json`, à côté du script. Exécuter les tests depuis le dossier du POC :

```powershell
Set-Location .\equipe\kandet\02-preuve-de-concept-scraping
python -m unittest -v test_poc_multi_source.py
```

## Limites et prochaines améliorations

« Sans limite » signifie qu'aucun plafond arbitraire de résultats n'est imposé par le POC; cela ne garantit pas de récupérer toutes les offres existantes. La couverture dépend des annonces fournies par les sources, des quatre termes et catégories interrogés, des filtres géographiques, des pages disponibles et des conditions d'accès. Les deux sources intégrées ne représentent pas tout le marché de l'emploi.

Priorités proposées :

1. Élargir et tester les mots-clés français et anglais ainsi que les catégories du Guichet-Emplois, tout en gardant la pagination complète et le délai de requête.
2. Étudier une intégration autorisée pour Québec emploi ou une autre source ayant une API ou un flux public; garder les sites sans accès automatisé autorisé en consultation manuelle.
3. Enrichir les fiches du Guichet-Emplois avec les descriptions et exigences seulement après vérification des règles d'accès et des limites de requêtes.
4. Améliorer la détection des stages avec davantage de formulations bilingues et des tests, sans classifier automatiquement un poste régulier sur la seule mention d'une expérience de stage antérieure.
5. Continuer à vérifier les doublons, les liens d'origine, les champs manquants et les conditions d'utilisation avant de réutiliser ou partager des données.

Les fichiers `offres.json` et `remotive-cache.json` sont des données de travail locales, conservées à côté du POC et exclues de Git localement. Les offres Remotive doivent garder leur attribution et ne doivent pas être republiées sur un site tiers.
