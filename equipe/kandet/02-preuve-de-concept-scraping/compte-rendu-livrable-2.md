# Compte rendu — Livrable 2 : preuve de concept de scraping

**Auteur :** Kandet  
**Date :** 11 novembre 2026

## 1. Sites et pages testés

Le prototype interroge deux sources :

- **Guichet-Emplois (Job Bank)** — flux Atom de recherche :  
  `https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed`
- **Remotive** — API JSON publique :  
  `https://remotive.com/api/remote-jobs`

Le Guichet-Emplois est filtré au Québec par défaut. Remotive conserve les lieux disponibles, puis le prototype filtre localement les catégories liées au domaine informatique. Les autres sources recensées dans [`sites.md`](../01-inventaire-des-sites/sites.md) ne sont pas automatisées par ce prototype.

## 2. Méthode, outils et exécution

Le script [`poc_multi_source.py`](poc_multi_source.py) utilise uniquement la bibliothèque standard de Python : `urllib` pour les requêtes HTTP, `xml.etree.ElementTree` pour lire le flux Atom, `json` pour l'API et les fichiers de résultats, et `html.parser` pour convertir les descriptions HTML en texte. Il normalise les champs communs, conserve les liens et renseignements propres à chaque source, déduplique les annonces répétées et classe les indices de stage.

Aucune dépendance externe n'est requise. Depuis la racine du dépôt, lancer le prototype avec :

```powershell
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py
```

Exemples d'options :

```powershell
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --jobbank-term developpeur --jobbank-term "stage informatique"
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --all-jobbank-locations
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --canada-remotive-only
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --refresh-remotive
```

Les tests hors ligne sont dans [`test_poc_multi_source.py`](test_poc_multi_source.py). Depuis le dossier du prototype, les lancer avec :

```powershell
Set-Location .\equipe\kandet\02-preuve-de-concept-scraping
python -m unittest -v test_poc_multi_source.py
```

Par défaut, le résultat est écrit dans `offres.json`, à côté du script. La réponse brute Remotive est réutilisée depuis `remotive-cache.json` pendant 24 heures. `--refresh-remotive` force une requête supplémentaire; la documentation de l'API recommande au plus quatre requêtes par jour.

## 3. Données récupérées et exemple

Le flux du Guichet-Emplois fournit, lorsqu'ils sont présents, le titre, le numéro d'offre, le lien, la date, le lieu, l'employeur et le salaire. Remotive fournit notamment le titre, l'employeur, le lien, le type d'emploi, la catégorie, le lieu, le salaire, les étiquettes et la description. Le programme réunit ces renseignements dans une structure commune et garde les détails par source.

L'instantané local utilisé pour cet essai a été généré le **11 novembre 2026 à 08 h 53 (heure de l'Est)**. Son résumé indique :

- **8 offres uniques** : 1 du Guichet-Emplois et 7 de Remotive;
- 4 termes de recherche du Guichet-Emplois, avec 2 pages parcourues par terme;
- 0 stage confirmé, 0 stage possible et 8 offres sans indice de stage détecté.

Exemple anonymisé de la structure produite; le titre, l'employeur, le lieu, le salaire, l'identifiant et le lien réels sont omis :

```json
{
  "title": "[titre omis]",
  "employer": "[employeur omis]",
  "location": "[lieu omis]",
  "salary": "[salaire omis]",
  "stage_status": "not_indicated",
  "search_terms": ["developpeur"],
  "source_records": [
    {
      "source": "Guichet-Emplois",
      "source_id": "[identifiant omis]",
      "url": "[lien d'origine omis]"
    }
  ]
}
```

Les 7 enregistrements Remotive de cet instantané ont été comparés hors ligne à la réponse API en cache : leur identifiant, lien, titre, employeur et catégorie correspondent. Cela vérifie la cohérence avec la réponse sauvegardée, mais pas que les offres sont toujours actives ou visibles sur le site. Une vérification manuelle d'une annonce sur son site source reste à faire.

## 4. Difficultés, limites et pistes essayées

- **Pagination :** le flux du Guichet-Emplois peut renvoyer une page courte mais non vide. Le prototype continue donc jusqu'à une page vide ou déjà rencontrée, au lieu de s'arrêter à la première page courte. Il demande 100 résultats par page, sans garantir que la source en fournisse 100.
- **Rythme des requêtes :** le `robots.txt` du Guichet-Emplois indique un délai de cinq secondes. Le prototype attend au moins cinq secondes entre les pages et les termes et utilise un `User-Agent` identifiant le projet.
- **Détails incomplets :** le flux Atom donne un résumé et le prototype ne visite pas les fiches du Guichet-Emplois. Remotive fournit la description via son API. Les champs absents restent vides au lieu d'être devinés.
- **Couverture :** la recherche par défaut emploie quatre termes et trois catégories du Guichet-Emplois, avec le Québec comme lieu par défaut. Remotive n'est pas limité géographiquement par défaut, mais reste filtré à dix catégories pertinentes. Ces sources et filtres ne couvrent pas toutes les offres existantes.
- **Détection des stages :** `confirmed_stage`, `possible_stage` et `not_indicated` reposent sur des termes et indices textuels. Des formulations inhabituelles peuvent être manquées; `not_indicated` ne prouve pas qu'un poste n'est pas un stage.
- **Conditions d'utilisation :** le cache Remotive de 24 heures limite les requêtes. Préserver l'attribution et le lien d'origine; ne pas republier ces annonces sur un site tiers. Le prototype ne contourne ni blocage, ni connexion, ni protection.
- **Pistes suivantes :** élargir les termes et catégories avec des tests; étudier une source supplémentaire uniquement si elle offre un moyen d'accès autorisé; améliorer la détection des stages; vérifier manuellement un échantillon de fiches.
Les fichiers `offres.json` et `remotive-cache.json` sont des données de travail locales; ils ne sont pas requis pour les tests et ne sont pas inclus dans ce compte rendu.
