Espace personnel de partage de l'enseignant Gregory
Daniel

## Livrables

| Livrable | Dossier |
| --- | --- |
| 1 — Inventaire des sites | [`01-inventaire-des-sites/`](01-inventaire-des-sites/sites.md) |
| 2 — Preuve de concept | [`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/compte-rendu.md) |
| 3 — Amélioration (plan par lots) | [`livrable3/plan.md`](livrable3/plan.md) |

## Scripts Python

### Installation

Python 3.10 ou plus récent. Depuis le dossier du script :

```bash
pip install -r requirements.txt
```

### Résumé

| Script | Rôle | Commande |
| --- | --- | --- |
| [`poc_guichetemplois.py`](02-preuve-de-concept-scraping/poc_guichetemplois.py) | Offres TI au Québec du Guichet-Emplois (1 page) | `python poc_guichetemplois.py "developpeur"` |
| [`livrable3/modele.py`](livrable3/modele.py) | Modèle `Offre` + exports JSON / CSV | Module importé par les scrapers |
| [`livrable3/outils.py`](livrable3/outils.py) | robots.txt, délai, cache 24 h, arrêt sur 401/403/429 | Module importé par les scrapers |
| Scrapers du livrable 3 | Ajoutés lot par lot | Voir [`livrable3/plan.md`](livrable3/plan.md) |

### Tests (livrable 3)

Hors ligne, aucun appel réseau. Depuis la racine du dépôt :

```bash
python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py" -v
```

### `poc_guichetemplois.py` (livrable 2)

Dossier : `02-preuve-de-concept-scraping/`. Lancer le script **depuis ce dossier**, car le CSV est écrit dans le dossier courant.

```bash
cd equipe/dan/02-preuve-de-concept-scraping
python poc_guichetemplois.py                  # tous les postes TI au Québec
python poc_guichetemplois.py "developpeur"    # avec un mot-clé
```

**Entrée**

| Entrée | Obligatoire | Défaut | Rôle |
| --- | --- | --- | --- |
| 1er argument | Non | aucun | Mot-clé ajouté à la recherche (`searchstring`) |

Aucune autre saisie : le script ne pose pas de question.

**Sortie**

- Console : URL de la page lue, nombre d'offres, les 10 premières offres.
- Fichier `offres_guichetemplois.csv` (`utf-8-sig`, lisible dans Excel), **remplacé** à chaque exécution :

| Colonne | Contenu |
| --- | --- |
| `source` | Toujours `guichetemplois` |
| `titre` | Titre du poste |
| `employeur` | Nom de l'employeur |
| `lieu` | Ville et province, ex. `Québec (QC)` |
| `date` | Date de publication, ex. `16 novembre 2026` |
| `salaire` | Texte du salaire, vide s'il n'est pas affiché |
| `lien` | URL de la fiche, sans `;jsessionid` |

- Si `robots.txt` interdit la page : message d'arrêt, aucun fichier écrit.
- Si 0 offre : message invitant à vérifier les sélecteurs.

**Configuration** (constantes en haut du script)

| Constante | Valeur | Rôle |
| --- | --- | --- |
| `PROVINCE` | `"QC"` | Province filtrée (`fprov`) |
| `CODES_CNP_TI` | 14 codes | Professions TI filtrées (`fn21`), liste de Kandet |
| `DELAI` | `5` | Secondes d'attente (`Crawl-delay` du site) |
| `ENTETES` | `User-Agent` du projet | Identification honnête du robot |
| `SELECTEURS` | Sélecteurs CSS | À corriger si le site change son HTML |

**Réseau :** 2 requêtes par exécution (`robots.txt`, puis 1 page de résultats), séparées de 5 s.

### `livrable3/modele.py` (socle du livrable 3)

Module sans réseau, importé par les scrapers. Dépendances : bibliothèque standard.

```python
from modele import Offre, exporter_json, exporter_csv, lire_json

offre = Offre(id="ge-50738681", source="guichet-emplois", titre="développeur Web", url="https://…")
exporter_json([offre], "data/offres.json")
exporter_csv([offre], "data/offres.csv")
```

**Entrée :** des objets `Offre`. Seuls `id`, `source`, `titre` et `url` sont obligatoires ; les autres champs valent `None` (ou `[]` pour `competences`) si la source ne les donne pas.

**Sortie**

| Fonction | Fichier produit | Format |
| --- | --- | --- |
| `exporter_json` | `.json` | UTF-8, accents lisibles, `date_export`, `nombre`, `offres` |
| `exporter_csv` | `.csv` | `utf-8-sig` + séparateur `;` (Excel Windows) |
| `lire_json` | — | Relit un `.json` en liste d'`Offre` |

Dans le CSV : `None` → cellule vide, `est_stage` → `oui` / `non`, `competences` → `Python, SQL`.

**Configuration :** aucune. Les dossiers de sortie sont créés au besoin.

### `livrable3/outils.py` (socle du livrable 3)

Module importé par les scrapers. Dépendance : `requests`.

```python
from outils import AccesRefuse, Client

client = Client()
try:
    html = client.telecharger("https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fprov=QC")
except AccesRefuse as refus:
    print(refus)          # message clair, puis on arrête cette source
```

**Entrée :** une URL. `telecharger(url, utiliser_cache=False)` force un nouveau téléchargement.

**Sortie**

- Le texte de la page (`str`).
- Ou l'exception `AccesRefuse`, sans contournement, si :
  - `robots.txt` interdit l'URL ;
  - le serveur répond 401 (connexion), 403 (ex. Cloudflare) ou 429 (trop de requêtes, avec `Retry-After`) ;
  - `robots.txt` lui-même est refusé (401/403/429) ou en erreur (5xx).
- Fichiers de cache dans `livrable3/cache/` (ignoré par Git).

**Ce que fait `telecharger`, dans l'ordre**

1. Cherche la page dans le cache (moins de 24 h) : si elle y est, aucune requête.
2. Lit `robots.txt` du site une seule fois : groupe qui nomme notre robot, sinon `*` ; règle la plus longue gagne ; `*` et `$` compris ; `Crawl-delay` lu.
3. Attend le délai du site : le plus grand entre 2 s et le `Crawl-delay`.
4. Envoie la requête avec notre `User-Agent`, puis met la page en cache.

**Configuration** (constantes en haut du module, ou arguments de `Client`)

| Constante | Valeur | Rôle |
| --- | --- | --- |
| `USER_AGENT` | `jobs-insights-dan/0.3 (…)` | Identification honnête |
| `DELAI_MIN` | `2.0` | Délai minimal entre deux requêtes au même site (s) |
| `CACHE_DOSSIER` | `livrable3/cache/` | Dossier du cache (`None` = pas de cache) |
| `CACHE_DUREE` | `86400` | Durée de validité du cache (s) |
| `TIMEOUT` | `20` | Délai maximal d'une requête (s) |
