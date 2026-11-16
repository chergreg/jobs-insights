# Livrable 3 — Reprendre et améliorer une preuve de concept

## Site choisi

- **Guichet-Emplois** : https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois
- Site de mon livrable 2, et site le plus exploré par l'équipe (4 étudiants).

## Contributions consultées

- [Synthèse du livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md)
- Mon POC : [`poc_guichetemplois.py`](../02-preuve-de-concept-scraping/poc_guichetemplois.py)
- Kandet : [`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py) et [`test_poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/test_poc_multi_source.py)
- Hugo : [`collecte.py`](../../hugo/02-preuve-de-concept-scraping/collecte.py), [`parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py), [`offres_emploi_canada.json`](../../hugo/02-preuve-de-concept-scraping/data/offres_emploi_canada.json)
- Mamadou : [`poc_scrapers_atelier1.py`](../../mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py) et [`sample_scraped_jobs.json`](../../mamadou/02-preuve-de-concept-scraping/sample_scraped_jobs.json)

## Comparaison des approches

| Critère | Dan | Kandet | Hugo | Mamadou |
| --- | --- | --- | --- | --- |
| Page lue | Résultats | Résultats | Résultats + fiches | Résultats + fiches |
| Outil | `BS4` | `html.parser` | `BS4` | regex |
| Cible | Moncton ❌ | QC + codes CNP TI | QC | Ville de Québec |
| Pagination | Non | Oui (`page`) | Partielle | Non |
| Délai | 2 s ❌ | 5 s ✅ | 1–2,2 s ❌ | Aucun ❌ |
| Site d'origine | Non | Oui | Oui | Non |
| Description | Non | Non | `null` | Oui (HTML brut) |
| Tests hors ligne | Non | 33 ✅ | Oui | Non |
| Résultat déposé | Aucun | — | 87 offres | 2 offres GE |

## Ce que chacun a fait de mieux

### Kandet — la page de résultats
- Confirme les vrais sélecteurs : `<article id="article-…">`, `a.resultJobItem`, `.noctitle`, `.business`, `.location`, `.salary`, `.date`, `.telework`.
- Cible le Québec et l'informatique avec des paramètres d'URL : `fprov=QC`, `fn21=<code CNP>` (14 codes TI), `sort=D`.
- Parcourt **toutes les pages** (`page=2, 3…`) et s'arrête au total annoncé.
- Respecte le `Crawl-delay: 5` de `robots.txt`, réessaie une fois après un `HTTP 429` ou `503`.
- Garde le **site d'origine** (ex. Jobillico) et déduplique.
- 33 tests hors ligne qui passent (relancés le 2026-11-16).

### Hugo — les fiches d'offres
- Visite chaque fiche pour ajouter la modalité (sur place, hybride) et le type de poste.
- Son échantillon de 87 offres montre que **63 %** viennent de sites partenaires.
- Limite : `description` vaut `null` dans les 87 offres, et la détection de compétences donne des faux positifs (`C`, `VUE`).

### Mamadou — les métadonnées RDFa
- Montre que les fiches contiennent des balises RDFa Schema.org : `property="title"`, `hiringOrganization`, `addressLocality`, `description`.
- C'est la seule approche qui a obtenu une **description** (ex. offre `50684844`).
- Limite : lecture par expressions régulières, donc description coupée au premier `</div>` et balises `<p>` conservées.

## Ce qui manquait dans mon POC

- Cible Moncton au lieu du Québec et de l'informatique.
- Délai de 2 s au lieu de 5 s.
- Aucune exécution ni échantillon.
- Une seule page, sans site d'origine ni description.
- Nom de fichier avec espace et conflit Git dans `README.md`.

## Amélioration proposée

**Combiner la liste de Kandet et la description RDFa repérée par Mamadou.**

1. Reprendre le parseur de résultats de Kandet (bibliothèque standard, pagination, filtres QC + CNP TI, délai 5 s).
2. Ajouter la lecture des **fiches** par RDFa, avec `html.parser` au lieu de regex, pour obtenir une description complète en texte propre.
3. Limiter le nombre de fiches visitées (une requête par fiche, 5 s chacune).
4. Ajouter des tests hors ligne sur une fiche HTML d'exemple.

Pourquoi : c'est la limite commune à tous les essais. La liste ne donne qu'un résumé, Hugo n'obtient aucune description, et Mamadou en obtient une mais mal nettoyée.

## Reste à vérifier

- Les propriétés RDFa exactes d'une fiche (à confirmer en ouvrant une vraie fiche avec Inspecter).
- Que `robots.txt` autorise toujours les fiches `/rechercheemplois/offredemploi/…`.

## Vérification

_À compléter après l'essai._
