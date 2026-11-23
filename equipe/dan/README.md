Espace personnel de partage de l'enseignant Gregory
Daniel

## Livrables

| Livrable | Dossier |
| --- | --- |
| 1 — Inventaire des sites | [`01-inventaire-des-sites/`](01-inventaire-des-sites/sites.md) |
| 2 — Preuve de concept | [`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/compte-rendu.md) |
| 3 — Amélioration (3 sites, doublons) | [`livrable3/compte-rendu.md`](livrable3/compte-rendu.md) · [plan par lots](livrable3/plan.md) |

## Scripts Python

### Installation

Python 3.12 ou plus récent (testé avec Python 3.13). Depuis le dossier du script :

```bash
pip install -r requirements.txt
```

### Résumé

| Script | Rôle | Commande |
| --- | --- | --- |
| [`poc_guichetemplois.py`](02-preuve-de-concept-scraping/poc_guichetemplois.py) | Offres TI au Québec du Guichet-Emplois (1 page) | `python poc_guichetemplois.py "developpeur"` |
| [`livrable3/main.py`](livrable3/main.py) | **Lance les 3 sites, retire les doublons, exporte le fichier unifié** | `python main.py --pages 1 --fiches 5` |
| [`livrable3/regroupement.py`](livrable3/regroupement.py) | Détection et fusion des doublons entre sources | Module importé par `main.py` |
| [`livrable3/modele.py`](livrable3/modele.py) | Modèle `Offre` + exports JSON / CSV | Module importé par les scrapers |
| [`livrable3/outils.py`](livrable3/outils.py) | robots.txt, délai, cache 24 h, arrêt sur 401/403/429 | Module importé par les scrapers |
| [`livrable3/scrapers/guichet_emplois.py`](livrable3/scrapers/guichet_emplois.py) | Guichet-Emplois : offres TI au Québec, plusieurs pages + fiches | `python -m scrapers.guichet_emplois --pages 2 --fiches 5` |
| [`livrable3/scrapers/jobboom.py`](livrable3/scrapers/jobboom.py) | Jobboom : catégorie TI, plusieurs pages + fiches JSON-LD | `python -m scrapers.jobboom --pages 2 --fiches 10` |
| [`livrable3/scrapers/talent.py`](livrable3/scrapers/talent.py) | Talent.com : recherche TI au Québec + fiches JSON-LD | `python -m scrapers.talent --pages 1 --fiches 10` |
| [`livrable3/scrapers/commun.py`](livrable3/scrapers/commun.py) | Fonctions de texte partagées (dates, HTML → texte, stage, montants) | Module importé par les scrapers |
| [`livrable3/scrapers/jsonld.py`](livrable3/scrapers/jsonld.py) | Lecture JSON-LD `JobPosting` partagée (Jobboom, Talent.com) | Module importé par les scrapers |
| Autres scrapers du livrable 3 | Ajoutés lot par lot | Voir [`livrable3/plan.md`](livrable3/plan.md) |

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

### `livrable3/main.py` (point d'entrée du livrable 3)

Lancer **depuis `equipe/dan/livrable3/`** :

```bash
cd equipe/dan/livrable3
pip install -r requirements.txt
python main.py                                        # 3 sites, 1 page et 5 fiches par site
python main.py --pages 2 --fiches 10 --csv
python main.py --sites guichet talent --sans-cache
```

**Entrée** (options de la ligne de commande)

| Option | Défaut | Rôle |
| --- | --- | --- |
| `--sites …` | `guichet jobboom talent` | Sources à lancer, dans cet ordre |
| `--pages N` | `1` | Pages de résultats par source |
| `--fiches N` | `5` | Fiches ouvertes par source |
| `--csv` | non | Écrit aussi un CSV par source |
| `--sans-cache` | non | Retélécharge tout |
| `--dossier CHEMIN` | `livrable3/data/` | Dossier des fichiers produits |

**Sortie** (dans `data/`)

| Fichier | Contenu |
| --- | --- |
| `offres_unifiees.json` | Toutes les offres, **sans doublons** |
| `offres_unifiees.csv` | La même chose pour Excel (`utf-8-sig`, `;`) |
| `offres_guichet_emplois.json`, `offres_jobboom.json`, `offres_talent.json` | Offres brutes de chaque source (seulement si elle en a donné) ; `.csv` aussi avec `--csv` |

Console : les messages de chaque scraper, puis un résumé :

```
=== Résumé ===
Source            Offres  Descriptions  Statut
Guichet-Emplois       25             5  ok
Jobboom               15             5  ok
Talent.com             0             0  0 offre (refus ou page vide : voir les messages plus haut)

Regroupement : 40 offres reçues, 2 doublons fusionnés (0 même id, 2 même titre + entreprise + ville) → 38 offres uniques
  doublon : tc-640918690502021004 = ge-50612345
```
*(chiffres d'exemple)*

**Robustesse :** une source refusée (robots.txt, 401, 403, 429) ou en erreur n'arrête pas les autres : son statut apparaît dans le résumé. Code de sortie `1` si aucune source n'a donné d'offre, sinon `0`.

**Configuration :** `SOURCES` (en haut de `main.py`) donne les sources et leur ordre : la première rencontrée d'une offre en double passe devant à égalité.

### `livrable3/regroupement.py`

Sans réseau. `regrouper(offres)` → `(offres_uniques, bilan)`.

**Deux offres sont le même poste si :**
1. elles ont le même `id` ; **ou**
2. elles ont la même empreinte **titre + entreprise + ville** (sans accents, majuscules ni ponctuation) **et** des diffuseurs différents.

| Normalisation | Exemple |
| --- | --- |
| Titre : forme masculine avant `/` | `développeur Web/développeuse Web` → `developpeur web` |
| Entreprise : sans forme juridique | `Mewlogic Inc.` → `mewlogic` |
| Ville : sans province ni « City » | `Québec City (QC)`, `Québec, QC` → `quebec` |

**Diffuseur** = (source, site partenaire). Une offre Talent.com reprise par le Guichet-Emplois (`source_partenaire` = `Talent.com`) et la même offre lue sur Talent.com ont des diffuseurs différents → fusionnées. Deux offres Jobboom identiques mais de numéros différents ont le même diffuseur → **gardées toutes les deux** (deux vrais postes possibles).

Pas de fusion par empreinte si le titre, l'entreprise ou la ville manque.

**Fusion :** l'offre gardée est la plus complète (le plus de champs remplis ; la première à égalité). Ses **champs vides seulement** sont comblés avec l'autre ; `id`, `source`, `url` et `source_partenaire` ne sont jamais recopiés ; les compétences sont réunies. Les `id` fusionnés sont listés dans le champ `doublons`.

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

Dans le CSV : `None` → cellule vide, `est_stage` → `oui` / `non`, `competences` et `doublons` → `Python, SQL`.

Le champ `doublons` (ajouté au lot 6) liste les `id` des offres fusionnées dans celle-ci par `regroupement.py`.

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

### `livrable3/scrapers/guichet_emplois.py`

Lancer **depuis `equipe/dan/livrable3/`** (pour trouver `modele.py` et `outils.py`) :

```bash
cd equipe/dan/livrable3
pip install -r requirements.txt
python -m scrapers.guichet_emplois                          # 1 page, 5 fiches
python -m scrapers.guichet_emplois --pages 3 --fiches 20 --csv
python -m scrapers.guichet_emplois --mot-cle stage --pages 1 --fiches 10
```

**Entrée** (options de la ligne de commande)

| Option | Défaut | Rôle |
| --- | --- | --- |
| `--pages N` | `1` | Pages de résultats à lire (environ 25 offres par page) |
| `--fiches N` | `5` | Fiches à ouvrir pour la description (`0` = aucune) |
| `--mot-cle TEXTE` | aucun | Mot-clé ajouté à la recherche (`searchstring`) |
| `--sortie CHEMIN` | `data/offres_guichet_emplois.json` | Fichier JSON produit |
| `--csv` | non | Écrit aussi un CSV à côté du JSON |
| `--sans-cache` | non | Retélécharge tout, sans lire ni écrire le cache |

La recherche est toujours filtrée sur le **Québec** (`fprov=QC`), les **14 codes CNP TI** (`fn21`) et triée de la plus récente à la plus ancienne (`sort=D`).

**Sortie**

- Console : une ligne par page (nombre d'offres, total annoncé), une ligne par fiche, puis le résumé.
- JSON (`modele.exporter_json`) : liste d'`Offre` avec `id` = `ge-<numéro>`, `source` = `guichet-emplois`.
- CSV (option `--csv`) : `utf-8-sig`, séparateur `;`.

| Champ | Vient de | Exemple |
| --- | --- | --- |
| `titre`, `entreprise`, `lieu`, `province` | Liste | `Vaudreuil-Dorion (QC)`, `QC` |
| `date_publication` | Liste, sinon fiche | `2026-11-16` |
| `salaire` | Liste, sinon fiche | `43,27 $ de l'heure` |
| `modalite` | Liste, sinon fiche | `Sur place`, `Hybride` |
| `source_partenaire` | Liste | `Jobillico` (`None` si publiée sur le Guichet-Emplois) |
| `type_poste` | Fiche | `Permanent, Temps plein` |
| `description` | Fiche (RDFa, sinon `#job-posting-detail`) | Texte sans HTML, une ligne par paragraphe ou puce |
| `est_stage` | Titre, titre d'origine ou type de poste | `True`, sinon `None` (inconnu) |

Un champ que le site ne donne pas reste `None` : rien n'est deviné.

**Arrêts**

- La collecte s'arrête au total annoncé par le site, sur une page vide ou après `--pages` pages.
- Si le site refuse (robots.txt, 401, 403, 429), le message s'affiche et ce qui est déjà lu est quand même enregistré.
- Une fiche illisible est ignorée ; les autres continuent.

**Configuration** (constantes en haut du module)

| Constante | Valeur | Rôle |
| --- | --- | --- |
| `PROVINCE` | `"QC"` | Province filtrée |
| `CODES_CNP_TI` | 14 codes | Professions TI filtrées (liste de Kandet) |
| `SORTIE_JSON` | `data/offres_guichet_emplois.json` | Sortie par défaut |
| `MODALITES`, `UNITES_SALAIRE` | dictionnaires | Textes reconnus et mis en forme |

**Durée :** le Guichet-Emplois impose `Crawl-delay: 5`, lu dans son `robots.txt`. Comptez environ 5 s par page et par fiche : `--pages 2 --fiches 20` ≈ 2 minutes au premier lancement, quelques secondes ensuite grâce au cache.

### `livrable3/scrapers/jobboom.py`

Lancer **depuis `equipe/dan/livrable3/`** :

```bash
cd equipe/dan/livrable3
python -m scrapers.jobboom                          # 1 page, 10 fiches
python -m scrapers.jobboom --pages 3 --fiches 30 --csv
```

**Entrée** (options de la ligne de commande)

| Option | Défaut | Rôle |
| --- | --- | --- |
| `--pages N` | `1` | Pages de la catégorie TI à lire (environ 15 offres par page) |
| `--fiches N` | `10` | Fiches à ouvrir (`0` = aucune) |
| `--sortie CHEMIN` | `data/offres_jobboom.json` | Fichier JSON produit |
| `--csv` | non | Écrit aussi un CSV à côté du JSON |
| `--sans-cache` | non | Retélécharge tout, sans lire ni écrire le cache |

Page lue : catégorie **Technologies et médias numériques** (`/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=N`), offres les plus récentes d'abord.

**Sortie**

- Console : une ligne par page, une ligne par fiche, puis le résumé.
- JSON : liste d'`Offre` avec `id` = `jb-<numéro>` (tiré de `_p<numéro>` dans l'URL), `source` = `jobboom`.
- CSV (option `--csv`) : `utf-8-sig`, séparateur `;`.

Sur Jobboom, la liste ne donne que le lien et le titre. **Tout le reste vient de la fiche** (JSON-LD `JobPosting`) :

| Champ | Champ JSON-LD | Exemple |
| --- | --- | --- |
| `entreprise` | `hiringOrganization.name` | `InnovMetric Logiciels Inc.` |
| `lieu`, `province` | `jobLocation.address` | `Québec (QC)`, `QC` |
| `latitude`, `longitude` | `jobLocation.geo` | `46.817136`, `-71.312079` |
| `date_publication` | `datePosted` | `2026-09-30` |
| `type_poste` | `employmentType` | `Permanent, Temps plein` |
| `modalite` | `jobLocationType` | `Télétravail` si `TELECOMMUTE`, sinon `None` |
| `est_stage` | `employmentType` `INTERN` ou titre | `True`, sinon `None` |
| `salaire` | `baseSalary` | `52 000 $ à 60 000 $ par année` |
| `description` | `description` (HTML) | Texte sans HTML, une ligne par paragraphe ou puce |

Une offre dont la fiche n'est pas ouverte garde seulement `id`, `url` et `titre`.

**Ce qui est exclu**

- Les offres **commanditées** (carte `job_item_sponsorship`).
- Les doublons (même numéro) et les liens sans numéro `_p<chiffres>` : aucun identifiant n'est inventé.
- Les offres sans titre, ni sur la carte ni dans la fiche.

**Arrêts :** au total annoncé (« 1 - 15 de 131 résultats »), sur une page vide ou après `--pages`. Si le site refuse (robots.txt, 401, 403, 429), le message s'affiche et ce qui est déjà lu est enregistré.

**Configuration** (constantes en haut du module)

| Constante | Valeur | Rôle |
| --- | --- | --- |
| `URL_CATEGORIE_TI` | catégorie `_i10lfr` | Page de départ |
| `SORTIE_JSON` | `data/offres_jobboom.json` | Sortie par défaut |

La traduction de `employmentType` (`TYPES_POSTE`) et des provinces est dans `scrapers/jsonld.py`.

**Durée :** délai de 2 s entre deux requêtes (minimum de `outils.py`), ou plus si le `robots.txt` de Jobboom fixe un `Crawl-delay`.

### `livrable3/scrapers/talent.py`

Lancer **depuis `equipe/dan/livrable3/`** :

```bash
cd equipe/dan/livrable3
python -m scrapers.talent                                      # « informatique » à « Québec, QC »
python -m scrapers.talent --mot-cle "stage informatique" --fiches 15 --csv
python -m scrapers.talent --lieu "Montréal, QC" --pages 2
```

**Entrée** (options de la ligne de commande)

| Option | Défaut | Rôle |
| --- | --- | --- |
| `--mot-cle TEXTE` | `informatique` | Mots-clés de la recherche (`k`) |
| `--lieu TEXTE` | `Québec, QC` | Lieu de la recherche (`l`) |
| `--pages N` | `1` | Pages de résultats à lire |
| `--fiches N` | `10` | Fiches à ouvrir (`0` = aucune) |
| `--sortie CHEMIN` | `data/offres_talent.json` | Fichier JSON produit |
| `--csv` | non | Écrit aussi un CSV à côté du JSON |
| `--sans-cache` | non | Retélécharge tout, sans lire ni écrire le cache |

**Sortie**

- JSON (et CSV avec `--csv`) : liste d'`Offre` avec `id` = `tc-<numéro>` (le `id=` de l'URL `/fr/view?id=…`), `source` = `talent`.
- Les offres viennent du JSON-LD `ItemList` de la page de résultats ; leurs champs viennent du JSON-LD `JobPosting` de la fiche, avec les mêmes règles que Jobboom (tableau plus haut). Particularités observées : région en anglais (`Quebec` → `QC`), ville `Québec City` gardée telle quelle.
- Une offre sans titre (ni dans la liste ni dans sa fiche) est retirée.

**Porte d'entrée :** la 1re requête vérifie `robots.txt`. Si Talent.com interdit la recherche ou répond 401/403/429, le script affiche le refus, conseille le **plan B (Remotive)** et rend 0 offre, sans autre tentative.

**Configuration** (constantes en haut du module)

| Constante | Valeur | Rôle |
| --- | --- | --- |
| `MOT_CLE`, `LIEU` | `informatique`, `Québec, QC` | Recherche par défaut |
| `PARAM_PAGE` | `p` | Paramètre de pagination — **à confirmer** sur le site ; s'il est ignoré, la collecte s'arrête à la page 2 (mêmes offres) |
| `SORTIE_JSON` | `data/offres_talent.json` | Sortie par défaut |

### `livrable3/scrapers/jsonld.py`

Lecture JSON-LD sans réseau, partagée par Jobboom et Talent.com (aucune configuration) :

| Fonction | Entrée → sortie |
| --- | --- |
| `objets_jsonld(html)` | Page HTML → tous les objets JSON-LD (`@graph` déplié, bloc invalide ignoré) |
| `jobposting(html)` | Page HTML → premier `JobPosting`, ou `None` |
| `champs_jobposting(job)` | `JobPosting` → champs d'`Offre` présents (titre, entreprise, lieu, GPS, date, type, modalité, stage, salaire, description) |
| `province(texte)` | `Quebec`, `Québec`, `qc`, `Ontario` → `QC`, `QC`, `QC`, `ON` ; inconnu → `None` |
| `salaire(job)` | `baseSalary` → `52 000 $ à 60 000 $ par année` |

### `livrable3/scrapers/commun.py`

Fonctions de texte sans réseau, utilisées par les scrapers (aucune configuration) :

| Fonction | Entrée → sortie |
| --- | --- |
| `html_vers_texte(html)` | HTML, même encodé deux fois (`&lt;p&gt;`) → texte, une ligne par paragraphe ou puce |
| `texte_multiligne(balise)` | Bloc BeautifulSoup → texte ; `<strong>` ou `<a>` ne coupent pas la phrase |
| `date_iso(texte)` | `Publiée le 16 novembre 2026`, `2026-11-10T08:30` → `2026-11-16`, `2026-11-10` |
| `est_un_stage(*textes)` | `True` si « stage », « stagiaire », « intern », « co-op »… ; sinon `None` |
| `montant(valeur)` | `52000` → `52 000`, `22.5` → `22,50` |
