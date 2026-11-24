# Livrable 3 (Mike) — Améliorer le POC Jobillico

## 1. Site choisi : Jobillico

Dans la [synthèse du livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md), seul Mamadou avait essayé Jobillico, et le Livrable 2 rapportait seulement 2 offres. En relançant son script le 18 nov., j'ai constaté qu'il trouvait 9 offres sur la page 1, mais n'en gardait que 2. Depuis, Hugo et Mamadou (L3) ont aussi travaillé sur ce site, ce qui m'a permis de comparer trois approches.

## 2. Contributions consultées

| Contribution | Méthode | Offres | Pages | robots.txt | Pause |
| --- | --- | --- | --- | --- | --- |
| Mamadou L2 | HTML + JSON-LD | 2 | 1 | Non | Aucune |
| Hugo | HTML + JSON-LD | 47 | `ipg` | Non | 1 s |
| Mamadou L3 | HTML + JSON-LD | 42 | 1 × 6 recherches | Non (Jobillico) | 0,25 s |

**Mamadou L2** — [`poc_scrapers_atelier1.py`](../../mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py), [commit e9ad415](https://github.com/chergreg/jobs-insights/commit/e9ad415725f944acb3280c900d2d1d14ddcec143)
- Il lit la page `/recherche-emploi?skwd=…&scty=…`, relève les liens `/fr/offre-d-emploi/…` par expressions régulières, puis lit le JSON-LD `JobPosting` de chaque offre.
- Ce qui a fonctionné : la méthode est simple, en bibliothèque standard, et le JSON-LD est fiable.
- Limites :
  - la page 1 seulement, et 2 offres sur 9 gardées (`max_items=2`) ;
  - aucune pause et aucun `robots.txt`, avec un `User-Agent` Firefox simulé ;
  - des valeurs inventées : « Employeur Jobillico » et « Québec » par défaut.

**Hugo** — [`equipe/hugo/04-Scrapping Jobillico/`](../../hugo/04-Scrapping%20Jobillico/)
- Même méthode, avec `requests`, BeautifulSoup et Pydantic. La pagination utilise `ipg`, et la collecte s'arrête quand une page n'apporte rien de nouveau.
- Ce qui a fonctionné : 47 offres, et un code découpé en modules.
- Limites :
  - pas de `robots.txt`, une pause de 1 s et un `User-Agent` qui imite Chrome ;
  - `lieu = "Québec"` et `province = "QC"` par défaut ;
  - pas de test sur la pagination.

**Mamadou L3** — [`poc_guichet_cnp_v2.py`](../../mamadou/03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py)
- Six recherches (mots-clés × villes), lues en page 1 seulement, puis un filtre TI (CNP) et un cache de 24 h.
- Ce qui a fonctionné : 42 offres TI sur 56 fiches, avec un `User-Agent` honnête.
- Limites :
  - le `robots.txt` est vérifié pour Guichet-Emplois seulement, pas pour Jobillico ;
  - la pause par défaut est de 0,25 s ;
  - `region = "QC"` par défaut.

## 3. Ce que j'ai réutilisé

- **De Mamadou :** l'adresse de recherche, les liens `/fr/offre-d-emploi/`, la lecture du JSON-LD, ainsi que `fetch_html()` et `clean_html()`.
- **De Hugo :** la pagination `ipg` et l'arrêt quand une page n'apporte rien de nouveau.

## 4. Ce que j'ai modifié

- Toutes les offres de la page sont gardées, sans doublon.
- **`RobotsAvecJokers`** lit le `robots.txt` une fois, puis le vérifie avant chaque adresse, avec mon `User-Agent`. Elle suit la règle de la plus longue correspondance (RFC 9309). J'ai remplacé `urllib.robotparser` parce qu'il ignore les jokers `*` et `$`. Verdicts sur le vrai fichier :

  | Adresse | `RobotsAvecJokers` | `urllib.robotparser` |
  | --- | --- | --- |
  | Recherche, page 1 | Autorisé | Autorisé |
  | Recherche, page 2 et + | **Interdit** | Autorisé ❌ |
  | Recherche vide | **Interdit** | Autorisé ❌ |
  | Fiche d'offre | Autorisé | Autorisé |

- Une pause de 5 s entre les requêtes, ou plus si le `robots.txt` donne un `Crawl-delay` plus long.
- Un `User-Agent` honnête : `jobs-insights-atelier/1.0 (projet etudiant 420-SV2-OQ)`.
- Aucune valeur inventée : `None` si une donnée manque.
- Une page en erreur ne fait plus perdre les offres déjà trouvées.
- Le JSON-LD est lu aussi quand il est en liste ou en `@graph`.
- 23 tests hors ligne, dont des tests sur les vraies règles de Jobillico.

## 5. Découverte : la pagination est interdite

Le `robots.txt` de Jobillico (lu le 23 nov. 2026) contient `Disallow: /*&ipg=` (commenté « to prevent crawling deep pagination ») et `Allow: /*&ipg=1$`. **Seule la page 1 d'une recherche est permise.** La pagination de Hugo demande `ipg=2` et les pages suivantes sans lire le `robots.txt`. L'outil standard de Python ne l'aurait pas détecté non plus : il répond « autorisé ». J'ai donc gardé l'idée de Hugo dans le code, mais elle s'arrête à la page 1, comme le demande le site.

## 6. Vérification

Depuis `equipe/mike/03-amelioration-preuve-de-concept/` :

```powershell
python -m unittest test_poc_jobillico.py -v
```

```powershell
python poc_jobillico.py --pages 3
```

Résultat : 23 tests sur 23 réussis. L'essai réel s'arrête de lui-même à la page 1.

| Mesure | Avant (Mamadou L2) | Après |
| --- | --- | --- |
| Offres gardées (page 1) | 2 sur 9 | **9 sur 9** |
| Pages de recherche lues | 1 | 1 (page 2 interdite) |
| robots.txt | Non | Oui, avant chaque URL |
| Pause | Aucune | 5 s |
| Valeurs inventées | Possible (valeurs par défaut dans le code) | Non (`None` si absent ; aucun champ manquant dans cet essai) |
| Requêtes / durée | 3 / non mesurée | 11 / 151 s |

Fichiers : [`avant_mamadou.json`](avant_mamadou.json) (18 nov.) et [`offres_jobillico_v2.json`](offres_jobillico_v2.json) (23 nov.). Les 2 offres d'avant figurent dans les 9 d'après.

Comparaison de 3 offres avec leur page sur Jobillico :

| Offre | Entreprise et ville | Date | Description |
| --- | --- | --- | --- |
| Groupe CFR | ✅ Sainte-Claire | ✅ | ⚠️ Partielle |
| CGI, Lead .Net | ✅ Québec | ✅ | ✅ Complète |
| Idexia | ✅ Québec | ✅ | ⚠️ Partielle |

Partielle : la description du JSON-LD ne contient pas les sections Compétences et Exigences de la page (voir les limites).

## 7. Limites restantes

- Une seule page est permise : au plus 9 offres par recherche. Pour en avoir plus, il faudrait lancer plusieurs recherches, comme Mamadou L3.
- Les sections « Compétences recherchées » et « Exigences » de la page ne sont pas dans le JSON-LD, donc absentes des données.
- Le salaire n'est pas lu.
- La casse des titres vient du JSON-LD et diffère parfois de la page (« .net » au lieu de « .Net »).
- Le HTML est encore lu par expressions régulières, pour rester proche du code de Mamadou.
