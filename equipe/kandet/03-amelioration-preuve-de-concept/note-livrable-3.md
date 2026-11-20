# Note — Livrable 3 : reprendre et améliorer une preuve de concept

**Kandet** — 17 novembre 2026

## Tester le projet (guide rapide)

Pour quelqu'un qui veut essayer le prototype sans avoir suivi le travail.

### Ce qu'il faut

- **Python 3.12 ou plus récent.** Vérifier avec `python --version`. Sous Windows, si `python` n'est pas reconnu, essayer `py --version` et remplacer `python` par `py` dans les commandes.
- **Aucune bibliothèque à installer** : tout est dans la bibliothèque standard, pas de `pip install`.
- **Une connexion Internet**, seulement pour la collecte. Les tests et l'option `--depuis` fonctionnent sans Internet.

### 1. Se placer dans le dossier du projet

Dans un terminal (PowerShell), à partir du dossier `jobs-insights` :

```powershell
cd .\equipe\kandet\03-amelioration-preuve-de-concept
```

Toutes les commandes suivantes se lancent depuis ce dossier.

### 2. Lancer les tests (1 seconde, sans Internet)

```powershell
python -m unittest discover -p "test_*.py" -v
```

La dernière ligne doit être `OK`, après `Ran 192 tests`. Deux tests comparent la page avec Python à l'aide de Node.js, l'un pour le CV et l'autre pour la lettre. Si Node.js n'est pas installé, ces deux tests sont simplement sautés (`skipped`).

### 3. Lancer la collecte

```powershell
# Essai rapide (environ 1 minute) : pages de résultats + 5 fiches seulement
python main.py --max-fiches 5

# Collecte complète
python main.py
```

**Combien de temps ça prend :**

- **Environ 17 minutes la première fois.** Le script attend 5 secondes entre chaque page, comme le demande le site (`robots.txt`).
- **Environ 1 minute les fois suivantes**, parce que les fiches déjà lues sont gardées dans `cache/fiches/`.

**Pendant la collecte :**

- Des lignes comme `Fiche 42/188` montrent l'avancement : le script tourne, il ne faut pas l'arrêter.
- Le message `HTTP 429 : nouvel essai dans 30 s` est normal : le site demande d'attendre, et le script réessaie tout seul.

À la fin, le script affiche les statistiques et la liste des offres, puis enregistre tout dans `offres.json`.

### 4. Chercher les offres dans le navigateur (le plus simple)

```powershell
python main.py --depuis offres.json --html
```

Cette commande crée `offres.html`. On l'ouvre d'un **double-clic** : la page s'affiche dans le navigateur (Edge, Chrome, Firefox), sans Internet et sans rien installer.

Dans la page :

- **Recherche par mots** (titre, employeur, technologie, ville…) et **filtres** : région, ville, technologie, niveau, salaire minimum, stages seulement, salaire indiqué, offres expirées cachées.
- **Tri** : plus récentes, salaire le plus élevé, expire bientôt, titre.
- **Technologies demandées** : un clic sur une technologie filtre les offres.
- **Chaque offre** affiche le titre de l'employeur, le salaire, le niveau, les badges (« Stage », « Expire dans 3 j »…), un résumé, les technologies et « Plus de détails » (études, expérience, langues). Elle donne aussi le lien vers l'offre et vers l'annonce d'origine.
- **« Exporter en CSV »** enregistre les offres affichées pour Excel.
- **« Copier le lien de cette recherche »** garde les filtres dans l'adresse de la page. Par exemple, `offres.html#region=Estrie&techno=SQL` rouvre la page avec ces filtres.
- La page s'adapte au téléphone (filtres repliables) et au mode sombre.
- **« Comparer les offres avec mon CV »** (en haut des résultats) :
  - choisir un CV en `.docx` ou en `.txt`, ou coller son texte ;
  - la page affiche ce qu'elle a compris du CV et trie les offres par correspondance ;
  - chaque offre montre sa note sur 100, ce qui est en commun et ce qui manque ;
  - la note est la même qu'avec `main.py --cv` ;
  - le CV reste dans le navigateur : il n'est ni envoyé ni enregistré. « Retirer le CV » efface tout.
- **« Vérifier ma lettre pour cette offre »** (sous chaque offre) :
  - ouvre une fenêtre où l'on choisit sa lettre (`.docx` ou `.txt`) ou colle son texte ;
  - la page affiche les vérifications (✓ / ✗ : zones à remplir, employeur, poste, technologies, longueur) et les suggestions. Ce sont les mêmes que `main.py --lettre` ;
  - si un CV est chargé dans la page, les suggestions séparent les technologies du CV de celles à apprendre ;
  - la lettre reste dans la fenêtre : on peut la retoucher, revérifier, ou la vérifier pour une autre offre.

### 5. Comparer son CV avec les offres (aide à la candidature)

```powershell
# Essai avec le CV fictif fourni
python main.py --depuis offres.json --cv cv-exemple.txt

# Avec son propre CV (Word ou texte), seulement les offres de la Capitale-Nationale, avec un rapport
python main.py --depuis offres.json --cv C:\Users\moi\Documents\mon-cv.docx --region capitale --rapport-cv
```

Le programme :

1. lit le CV (`.docx` ou `.txt`). Les PDF ne sont pas acceptés : il faut enregistrer le CV en `.docx` depuis Word ;
2. affiche ce qu'il a compris : technologies, compétences, années d'expérience, niveau, langues, recherche de stage ;
3. classe les offres avec une note sur 100. Pour chacune, il montre ce qui est en commun avec le CV et ce qui manque ;
4. signale les stages présents dans le classement ;
5. donne des pistes pour adapter le CV aux 3 premières offres : technologies à mettre en avant, technologies demandées absentes du CV, langues, expérience et études demandées, tâches de l'offre à relier à ses projets, date limite ;
6. avec `--rapport-cv`, enregistre tout dans `rapport-candidature.md` (`--nb-offres 20` pour en voir plus).

**Le CV reste sur l'ordinateur** : rien n'est envoyé à un service extérieur. Les fichiers `.docx`, `.pdf` et `rapport-candidature*.md` de ce dossier sont ignorés par Git. Il ne faut jamais mettre un vrai CV dans le dépôt.

Les filtres de l'étape suivante (`--region`, `--stages`, `--niveau`…) choisissent les offres à comparer.

**Vérifier une lettre de motivation pour une offre précise :**

```powershell
# L'offre se donne par son lien (copié depuis offres.html) ou par son numéro du Guichet-Emplois
python main.py --depuis offres.json --lettre lettre-exemple.txt --cv cv-exemple.txt --offre 50585958 --rapport-lettre
```

Le programme ne note pas la lettre. Il repère ce qui peut être amélioré :
- zones à remplir oubliées (« [nom du poste] », « XXX ») ;
- employeur et poste cités ou non ;
- technologies et compétences de l'offre citées ou absentes. Avec `--cv`, il sépare celles qui sont dans le CV de celles à apprendre ;
- mots importants des tâches de l'offre absents de la lettre ;
- longueur (environ 200 à 450 mots).

Avec `--rapport-lettre`, le résultat est aussi enregistré dans `rapport-lettre.md`.

### 6. Garder les offres à jour (collecte régulière)

Les offres changent vite : entre le 17 et le 20 novembre, 24 offres sur 197 étaient nouvelles et 24 avaient disparu. Il faut donc refaire la collecte souvent, par exemple chaque jour ou 2 à 3 fois par semaine.

```powershell
# À la main : collecte, page à jour, ménage du cache (environ 1 minute)
python main.py --nettoyer-cache --html --resume-seulement

# Ou avec le script, qui note aussi tout dans journal-collectes.log
.\collecte-reguliere.ps1
```

À chaque collecte, le programme :
- **compare avec la collecte précédente** : « 24 nouvelle(s) offre(s), 24 disparue(s) (dont 13 retirée(s) avant leur date limite) ». Le détail est dans `offres.json` (`changes_since_previous`) ;
- **marque les nouvelles offres** : badge « Nouvelle » dans `offres.html`, case « Nouvelles offres seulement » dans les filtres, et phrase en haut de la page (« 24 nouvelles offres depuis la collecte du 17 novembre 2026 ») ;
- **ajoute une ligne à `historique-collectes.csv`** (date, offres, nouvelles, disparues…), qui s'ouvre dans Excel ;
- **avec `--nettoyer-cache`**, retire du cache les fiches des offres disparues. Il le fait seulement après une collecte complète et sans erreur, pour ne rien effacer par erreur.

**Collecte automatique avec Windows :**

```powershell
.\planifier-collecte.ps1                # chaque jour à 8 h
.\planifier-collecte.ps1 -Heure 12:30   # à une autre heure
.\planifier-collecte.ps1 -Supprimer     # arrêter la collecte automatique
```

La tâche lance `collecte-reguliere.ps1` quand la session est ouverte. Si l'ordinateur est éteint à l'heure prévue, elle se lance dès qu'il est rallumé. Une collecte par jour respecte les règles des sites : 5 s entre les pages du Guichet-Emplois, et Remotive au plus 1 fois par jour grâce au cache de 24 h.

### 7. Chercher des offres précises dans le terminal (sans retélécharger)

Après une collecte, `--depuis offres.json` relit les offres en quelques secondes, sans Internet. On peut combiner plusieurs filtres. Les accents et les majuscules ne comptent pas.

```powershell
python main.py --depuis offres.json --ville Québec
python main.py --depuis offres.json --region monteregie
python main.py --depuis offres.json --techno Python
python main.py --depuis offres.json --niveau debutant
python main.py --depuis offres.json --stages
python main.py --depuis offres.json --salaire-min 60000
python main.py --depuis offres.json --salaire-min 30 --unite-salaire heure
python main.py --depuis offres.json --techno SQL --ville Montréal --csv
```

| Option | Ce qu'elle garde |
|---|---|
| `--ville Montréal` | Les offres de cette ville |
| `--region monteregie` | Les offres de cette région administrative. Le début du nom suffit : `capitale`, `chaudiere`, `laurentides`… |
| `--techno SQL` | Les offres qui mentionnent cette technologie (SQL, Python, C#, Azure…) |
| `--niveau débutant` | `débutant`, `intermédiaire` ou `avancé` |
| `--stages` | Les stages confirmés ou possibles |
| `--salaire-min 60000` | Les offres dont le bas de la fourchette atteint ce montant. L'unité est l'année par défaut ; ajouter `--unite-salaire heure` pour un taux horaire |
| `--employeur desjardins` | Les offres dont le nom de l'employeur contient ce mot |
| `--csv` | Enregistre les offres affichées dans `offres.csv`, qui s'ouvre directement dans Excel |
| `--html` | Crée la page `offres.html` avec les offres affichées (toutes, s'il n'y a pas de filtre) |
| `--resume-seulement` | Affiche les statistiques sans la liste |

Les filtres changent ce qui est affiché, ce qui va dans le CSV et ce qui va dans la page HTML. `offres.json` garde toujours toutes les offres.

La liste complète des options s'obtient avec `python main.py --help`.

### Fichiers produits

| Fichier | Contenu | Dans Git ? |
|---|---|---|
| `offres.json` | Toutes les offres avec tous les champs, et les statistiques | Non |
| `offres.csv` | Les offres affichées, pour Excel | Non |
| `offres.html` | La page de recherche à ouvrir dans le navigateur | Non |
| `echantillon.json` | 10 offres d'exemple | Oui |
| `cv-exemple.txt` | CV fictif pour essayer l'aide à la candidature | Oui |
| `rapport-candidature.md` | Classement des offres selon un CV, avec les suggestions | Non |
| `lettre-exemple.txt` | Lettre fictive pour essayer la vérification de lettre | Oui |
| `rapport-lettre.md` | Vérification d'une lettre pour une offre | Non |
| `historique-collectes.csv` | Une ligne par collecte : offres, nouvelles, disparues | Non |
| `journal-collectes.log` | Ce qu'a affiché chaque collecte lancée par `collecte-reguliere.ps1` | Non |
| `collecte-reguliere.ps1`, `planifier-collecte.ps1` | Scripts de collecte régulière et automatique | Oui |
| `regions_quebec.csv` | Municipalités et arrondissements du Québec avec leur région (source officielle, voir plus bas) | Oui |
| `cache/fiches/` | Les fiches déjà téléchargées | Non |

### Si ça ne marche pas

- **`python` n'est pas reconnu** : utiliser `py`, ou installer Python depuis python.org en cochant « Add Python to PATH ».
- **`No such file or directory: main.py`** : la commande n'est pas lancée depuis le dossier du projet (voir l'étape 1).
- **`Format .pdf non pris en charge`** : ouvrir le CV dans Word, puis « Enregistrer sous » au format `.docx`.
- **« Technologies trouvées dans le CV : aucune »** : écrire les technologies clairement dans le CV, par exemple « Langages : Python, Java, SQL ».
- **`Impossible de lire offres.json`** : faire d'abord une collecte (étape 3) avant d'utiliser `--depuis`.
- **La page `offres.html` ne montre pas les dernières offres** : refaire la commande `--html` après une nouvelle collecte. La page est une photo de `offres.json` au moment où elle est créée.
- **`Offres affichées : 0`** : les filtres sont trop stricts. Par exemple, `--ville` demande le nom exact de la ville, comme `Québec` et non `Qc`.

## 1. Site choisi

**Guichet-Emplois** (`https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois`), offres TI au Québec : 14 codes CNP, `fprov=QC`. Remotive reste une source d'appoint pour le télétravail.

J'ai choisi ce site parce que c'est celui qui a été le plus exploré dans la classe (Hugo, Mamadou, Dan, moi), et parce qu'il affiche aussi les offres de Jobillico, Québec emploi, Talent.com et d'autres partenaires.

## 2. Contributions consultées

| Contribution | Méthode | Données obtenues | Difficultés |
|---|---|---|---|
| [Mon L2](../02-preuve-de-concept-scraping/compte-rendu-livrable-2.md) | Pages de résultats HTML, 14 codes CNP | 191 offres, toutes les pages | Pas de description, titres CNP, 0 stage |
| [Hugo](../../hugo/02-preuve-de-concept-scraping/COMPTE_RENDU_LIVRABLE_2.md) | Atom + recherche par mots-clés + fiches (RDFa, repli DOM) | 87 offres avec description | Liste fixe de mots-clés, pas toutes les pages |
| [Mamadou (L3)](../../mamadou/03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py) | Codes CNP + fiches RDFa (BeautifulSoup), cache 24 h | Échantillon de 22 offres (5 sources) | Nombre de pages à choisir (`--pages N`), dépendances externes |
| [Gregory (démo L3)](../../gregory/livrable3/scrapers/guichet_emplois.py) | Ma pagination + l'enrichissement de Hugo, cache des fiches | 140 offres unifiées (3 sources) | Démonstration du prof |
| [Dan](../../dan/02-preuve-de-concept-scraping/compte-rendu.md) | Page de résultats HTML (BeautifulSoup), mes 14 codes CNP | 25 offres (1re page, CSV) | Pas de pagination, pas de description ni de site d'origine |

Je me suis aussi appuyé sur la [synthèse du L2](../../../livrables/02-preuve-de-concept-scraping/synthese.md), la [synthèse du L3](../../../livrables/03-amelioration-preuve-de-concept/synthese.md) et le [plan de Gregory](../../gregory/livrable3/plan.md). Tous ces documents relèvent la même limite pour mon L2 : les fiches n'étaient pas lues.

**Ce que j'ai vérifié moi-même :**

- J'ai ouvert 3 fiches (Guichet-Emplois, Jobillico, Québec emploi). Elles contiennent les balises RDFa utilisées par Hugo et Mamadou : `description`, `validThrough`, `minValue`/`maxValue`/`unitText`, `employmentType`, `educationRequirements`, `experienceRequirements`, `postalCode`.
- Les fiches des partenaires affichent aussi le titre écrit par l'employeur (`span.source-title-inner`) et un lien vers l'annonce d'origine (`a#externalJobLink`). Mamadou utilisait aussi ce titre.
- Le plan de Mamadou présente `fsrc=16` comme un « filtre stages ». Je l'ai testé : il donne 71 offres, toutes publiées directement sur le Guichet-Emplois. C'est donc un filtre de **source** (16 est aussi le numéro de l'icône du Guichet-Emplois dans le HTML), pas un filtre de stages.
- Il n'y a pas de latitude/longitude sur les fiches du Guichet-Emplois, seulement le code postal. Mamadou obtient le GPS sur Talent.com, un autre site.

## 3. Amélioration choisie

**Lire la fiche de chaque offre trouvée par ma pagination**, pour compléter les données de la liste. C'est exactement l'exemple de l'énoncé : une approche trouve les liens, une autre lit le détail.

**Ce que j'ai repris :**

- de mon L2 : la pagination sans plafond par codes CNP, le site d'origine des offres, la déduplication et la détection des stages ;
- de Hugo et Mamadou : l'idée de lire les balises RDFa de la fiche et de décoder le HTML encodé deux fois des partenaires ;
- de Hugo : sa liste de technologies `TECH_PATTERNS`, sans faux positifs sur « C » seul ni sur « vue d'ensemble » ;
- de Gregory et Mamadou : un cache des fiches sur disque, pour respecter les 5 s du `robots.txt` sans attendre 16 minutes à chaque essai.

**Ce que j'ai modifié :**

- Tout est réécrit avec la bibliothèque standard (`html.parser`) : pas de BeautifulSoup ni de Pydantic, donc aucune installation.
- Le prototype est découpé en modules : `guichet`, `fiches`, `remotive`, `normalisation`, `competences`, `fusion`, `analyse`, `regions`, `filtres`, `export`, `interface` (avec `interface_cv.js`), `candidature`, `lettre`, `historique`, `main`.
- Nouveaux champs :
  - titre de l'employeur, description, tâches ;
  - date d'expiration et date de début ;
  - type d'emploi, études, expérience, langues ;
  - ville, province, code postal ;
  - salaire en chiffres (minimum, maximum, unité, devise, « à négocier ») ;
  - technologies, compétences, années d'expérience, niveau et description courte.
- Stages : le champ « Stage: Ce poste est un stage… » du Guichet-Emplois est reconnu, et la détection se fait aussi sur le vrai titre et la description.
- Statistiques : top technologies, salaires par unité (jamais mélangés), villes, expirations proches, champs remplis.
- Deux défauts de la source sont corrigés :
  - dans 10 fiches, des séquences d'échappement Unicode écrites telles quelles (barre oblique inverse + `u00E9` au lieu de « é ») ;
  - des `&amp;` encodés deux fois.
- Région administrative de chaque offre (module `regions`) : la ville est cherchée dans le Répertoire des municipalités du Québec (ministère des Affaires municipales et de l'Habitation, données ouvertes sous licence CC-BY 4.0). La liste officielle des arrondissements sert pour Saint-Laurent, Lachine, etc. Le fichier `regions_quebec.csv` garde seulement le nom, le type et la région, sans aucun nom d'élu. Il est recréé par `preparer_regions.py`.
- Page de recherche `offres.html` (module `interface` et modèle `interface_modele.html`) : un seul fichier qui s'ouvre dans le navigateur, avec les offres incluses. Il n'y a ni serveur, ni Internet, ni bibliothèque externe. Le JavaScript affiche les textes des offres avec `textContent`, jamais comme du HTML : un texte d'offre ne peut pas devenir du code.
- Aide à la candidature, piste 4 du projet (module `candidature`) :
  - le CV (`.docx` ou `.txt`) est lu sur l'ordinateur, sans service extérieur ;
  - il est comparé aux offres avec les mêmes listes de technologies et de compétences que pour les offres, et une note sur 100 dont chaque partie est expliquée ;
  - le programme donne des suggestions pour adapter le CV à une offre, sans jamais rien inventer sur le candidat ;
  - options `--cv`, `--nb-offres` et `--rapport-cv`.
- Comparaison avec le CV dans la page `offres.html` (script `interface_cv.js`) :
  - au moment de créer la page, `interface.py` y copie les expressions de `competences.py` et `candidature.py`. La page et `main.py --cv` utilisent donc les mêmes règles ;
  - le `.docx` est lu dans le navigateur, sans bibliothèque (`DecompressionStream`).
- Vérification d'une lettre de motivation (module `lettre`), options `--lettre`, `--offre` et `--rapport-lettre`. Elle se fait aussi dans la page, avec le bouton « Vérifier ma lettre pour cette offre ». La page reçoit les listes de mots de `lettre.py`.
- Collecte régulière (module `historique`) :
  - comparaison avec la collecte précédente : offres nouvelles et disparues ;
  - badge « Nouvelle » et filtre dans la page ;
  - historique CSV et ménage du cache (`--nettoyer-cache`) ;
  - scripts PowerShell `collecte-reguliere.ps1` et `planifier-collecte.ps1` (Planificateur de tâches de Windows).
- Filtres et export : `--ville`, `--region`, `--techno`, `--niveau`, `--stages`, `--salaire-min`, `--employeur`, export `--csv` pour Excel, et `--depuis` pour filtrer une collecte déjà faite sans Internet (modules `filtres` et `export`).

Le code est dans ce dossier. Le prototype du L2 reste tel quel dans `02-preuve-de-concept-scraping/`.

Commits sur `main` :

| Étape | Commit |
|---|---|
| Plan | [`0dc34f1`](https://github.com/chergreg/jobs-insights/commit/0dc34f1) |
| Modules | [`d298b96`](https://github.com/chergreg/jobs-insights/commit/d298b96) |
| Fiches | [`e1dbea9`](https://github.com/chergreg/jobs-insights/commit/e1dbea9) |
| Salaire et lieu | [`c781672`](https://github.com/chergreg/jobs-insights/commit/c781672) |
| Technologies et niveau | [`7aa7e60`](https://github.com/chergreg/jobs-insights/commit/7aa7e60) |
| Statistiques | [`c1f687e`](https://github.com/chergreg/jobs-insights/commit/c1f687e) |

## 4. Commandes

Le guide au début de cette note explique tout pas à pas, filtres et CSV compris. Les mêmes commandes, lancées depuis la racine du dépôt :

```powershell
# Collecte complète : environ 17 min la première fois (5 s par fiche), environ 1 min ensuite grâce au cache
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --echantillon .\equipe\kandet\03-amelioration-preuve-de-concept\echantillon.json

# Essai court sur 5 fiches
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --max-fiches 5

# Sans les fiches (comme au L2)
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --sans-fiches

# Filtrer une collecte déjà faite, sans Internet, et exporter pour Excel
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --depuis .\equipe\kandet\03-amelioration-preuve-de-concept\offres.json --techno Python --csv

# Page de recherche à ouvrir dans le navigateur
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --depuis .\equipe\kandet\03-amelioration-preuve-de-concept\offres.json --html

# Comparer un CV avec les offres (aide à la candidature)
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --depuis .\equipe\kandet\03-amelioration-preuve-de-concept\offres.json --cv .\equipe\kandet\03-amelioration-preuve-de-concept\cv-exemple.txt --rapport-cv

# Vérifier une lettre de motivation pour une offre
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --depuis .\equipe\kandet\03-amelioration-preuve-de-concept\offres.json --lettre .\equipe\kandet\03-amelioration-preuve-de-concept\lettre-exemple.txt --offre 50585958

# Collecte régulière : comparaison avec la collecte précédente, page à jour, ménage du cache
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --nettoyer-cache --html --resume-seulement

# Tests hors ligne (192 tests)
python -m unittest discover -s equipe/kandet/03-amelioration-preuve-de-concept -p "test_*.py" -v
```

Sorties :
- `offres.json` : toutes les offres et les statistiques. Ce fichier n'est pas dans Git.
- [`echantillon.json`](echantillon.json) : 10 offres enrichies.
- `cache/fiches/` : fiches déjà lues, pas dans Git.

## 5. Vérification

### Avant / après

| Mesure | L2 (12 nov.) | L3 (17 nov.) |
|---|---|---|
| Offres du Guichet-Emplois récupérées | 191 / 191 | 188 / 189 (1 offre retirée pendant la collecte) |
| Fiches lues | 0 | 188 / 188, 0 erreur |
| Description | 0 | 132 / 186 |
| Titre de l'employeur | 0 | 114 |
| Date d'expiration | 0 | 184 |
| Salaire en chiffres | 0 (texte seulement) | 186 / 186 |
| Ville et province séparées | 0 | 179 / 186 |
| Région administrative | 0 | 178 / 179 offres avec ville (Saint-Antoine-Abbé, un hameau, n'est pas une municipalité) |
| Études, expérience, langues | 0 | 71 |
| Technologies détectées | 0 | 83 offres |
| Niveau (débutant, intermédiaire, avancé) | 0 | 124 offres |
| Stages détectés | 0 | 1 confirmé |
| Tests hors ligne | 33 | 192 |

Les compteurs de la dernière colonne viennent du résumé de `offres.json` (`summary.filled_fields`).

### Contrôle des données

- **Salaire :** pour les 188 offres, le montant lu dans le texte de la liste est identique à celui des balises RDFa de la fiche. 0 différence.
- **5 fiches ouvertes en ligne le 17 novembre**, comparées aux données collectées : 2 du Guichet-Emplois, 1 de Jobillico, 1 de Québec emploi, 1 de Talent.com.
  - Le titre, l'employeur, la date d'expiration et le salaire correspondent pour les 5.
  - La description correspond pour 4. La 5e, celle de Québec emploi, est une offre fusionnée avec sa copie Jobillico : sa description vient de la fiche Jobillico, comme prévu.
  - Les technologies détectées sont bien écrites dans les pages. Par exemple, « Postgres » donne PostgreSQL.
- **Détections risquées :** j'ai relu le texte autour des technologies les plus risquées (Windows, Oracle, SAP, Swift, Rust, Cisco, Git, Java). Toutes correspondent à de vraies mentions.

### Vérification de la page HTML

Les tests Python vérifient le contenu de la page :
- les offres incluses ;
- un titre piégé `</script>` qui ne casse pas la page ;
- aucune ressource externe ;
- aucun `innerHTML`.

J'ai aussi ouvert la vraie page (195 offres) dans Edge en mode sans fenêtre (`--headless --dump-dom`), avec des filtres passés dans l'adresse. La page donne les mêmes nombres que les filtres de `main.py` :

| Filtre | Page HTML | `main.py` |
|---|---|---|
| Région Montérégie | 48 | 48 |
| Capitale-Nationale + SQL | 6 | 6 |
| Python | 18 | 18 |
| Niveau débutant | 27 | 27 |
| Stages | 1 | 1 |
| Salaire ≥ 90 000 $ / an | 29 | 29 |
| Montréal + ≥ 40 $ / h | 9 | 9 |

Une copie de test de la page a aussi cliqué elle-même sur les boutons :
- « Afficher plus » : 30, puis 60, puis 90 offres ;
- choix de l'Estrie : seules Sherbrooke, Coaticook et Valcourt sont proposées comme villes ;
- export CSV : 5 offres, et le fichier commence par les octets `EF BB BF` pour qu'Excel lise les accents ;
- « Effacer les filtres » : retour à 195 ;
- clic sur « SQL » : 32 offres.

Des captures d'écran sur ordinateur, sur téléphone (375 pixels) et en mode sombre ont permis de corriger trois défauts avant l'ajout :
- un bouton « Afficher plus (0 restantes) » visible à tort ;
- un titre de filtres mal espacé ;
- un texte de bouton peu lisible en mode sombre.

### Vérification de l'aide à la candidature (20 novembre)

J'ai fait l'essai avant d'écrire le module, avec deux CV fictifs comparés aux 195 vraies offres :
- une étudiante en développement qui cherche un stage ;
- un technicien en soutien et réseau avec 2 ans d'expérience.

L'essai a montré trois défauts de la première règle de note, corrigés avant l'ajout :

| Défaut observé | Correction |
|---|---|
| Une offre qui ne liste que « Python » avait la note maximale sur les technologies avec 1 seule technologie en commun | La note tient compte aussi du nombre de technologies en commun (jusqu'à 4) |
| L'étudiante recevait des postes « avancés » (chef de projet, administrateur de bases de données senior) | Moins de points quand l'offre est d'un niveau au-dessus du CV, aucun quand elle est deux niveaux au-dessus |
| Pour le technicien, les 5 premières offres ne listaient qu'un seul élément (« Réseaux ») : 100/100 sans vraie information | Une offre avec peu d'éléments garde 70 % à 90 % de sa note |

**Résultat après correction :**

- **Étudiante :** 1re offre « développeur Web full-stack », niveau débutant, 6 technologies sur 7 en commun (95/100). Le seul stage trouvé est signalé à part.
- **Technicien :** 1res offres « administrateur réseaux », avec 4 ou 5 éléments en commun (Windows, Active Directory, VMware…).

**Lecture des CV :**

- un vrai `.docx` créé par Word se lit sans bibliothèque externe, et son texte est identique à la version `.txt` ;
- un PDF est refusé avec un message qui explique quoi faire.

**Tests :** 21 nouveaux tests dans `test_candidature.py`. Ils vérifient notamment :
- un `.docx` construit dans le test (avec un tableau et des sauts de ligne) ;
- un ancien stage, sans recherche de stage, qui ne doit pas être compté comme recherche ;
- « Bilingue » compris comme français et anglais ;
- aucune suggestion inventée.

### Vérification du CV dans la page et de la lettre (20 novembre)

**CV dans la page.** Essai fait avant de modifier la page :
- les 72 expressions de Python fonctionnent telles quelles en JavaScript ;
- pour 3 CV fictifs et les 195 vraies offres, le calcul JavaScript (exécuté avec Node.js) donne le même profil et la même note que Python pour chaque offre (0 différence) ;
- un vrai `.docx` créé par Word est lu dans Edge sans bibliothèque, avec le même texte que la version `.txt`.

Une fois la page faite, une copie de test a rempli le panneau elle-même dans Edge :
- CV collé (2 profils) et vrai fichier Word : les 10 premières offres et leurs notes sont identiques à `main.py --cv` ;
- avec le filtre région Montréal, le tri par correspondance est gardé ;
- « Retirer le CV » efface tout, et le CV n'apparaît jamais dans l'adresse de la page ;
- un PDF est refusé avec un message.

Captures sur ordinateur et sur téléphone (375 pixels) : rien ne dépasse de l'écran.

Le test `test_interface_cv.py` compare automatiquement les notes JavaScript et Python. Pour vérifier qu'il sert à quelque chose, je lui ai donné une copie du script avec une seule règle changée (50 points au lieu de 55) : il a échoué, comme il le devait.

**Lettre.** Essai avec une lettre fictive (`lettre-exemple.txt`) pour l'offre « développeur Web full-stack ». Deux défauts trouvés et corrigés avant l'ajout :
- l'employeur était déclaré « cité » parce que la lettre contenait le mot « les » (« Les technologies Duologiq »). On compare maintenant les mots distinctifs du nom ;
- le titre était déclaré « cité » à cause du seul mot « développer ». Il faut maintenant 2 mots importants sur 3 du titre.

Après correction, la lettre fictive est bien signalée : `[nom du poste]` oublié, employeur et poste absents, 4 technologies de l'offre absentes, lettre courte (114 mots). Une fois la lettre corrigée, ces remarques disparaissent.

**Lettre dans la page.** Essai fait avant de modifier la page : la vérification écrite en JavaScript donne les mêmes vérifications et les mêmes phrases que `lettre.py` dans **780 cas sur 780** (4 lettres × 195 vraies offres, avec et sans CV).

Ensuite, dans Edge, une copie de test de la vraie page a fait elle-même les étapes :
- ouvrir la fenêtre d'une offre et coller la lettre : 7 suggestions, identiques à Python ;
- charger le CV puis choisir la lettre en vrai fichier Word : 8 suggestions, identiques à Python ;
- fermer et rouvrir : la lettre est gardée ;
- un PDF est refusé avec un message.

Les captures sur ordinateur et sur téléphone ont fait corriger un champ « Choisir un fichier » qui dépassait sur téléphone.

Le test automatique de la lettre a d'abord été trop faible : avec un script volontairement modifié (mots comparés sur 4 lettres au lieu de 5), il passait encore. J'ai ajouté un cas où cette différence compte (« partenaires » et « participé »). Maintenant, il échoue avec le script modifié.

### Vérification de la collecte régulière (20 novembre)

Essai d'abord : une nouvelle collecte le 20 novembre, enregistrée à part et comparée à celle du 17 novembre.

| Mesure | Résultat |
|---|---|
| Annonces le 17 / le 20 | 197 / 197 |
| Nouvelles | 24 (12 %) |
| Disparues | 24, dont 14 avant leur date limite (sans doute des postes déjà pourvus) |
| Fiches du cache devenues inutiles | 23 |

Sans nouvelle collecte, la page aurait donc montré 24 offres qui n'existent plus et caché 24 nouvelles.

Une fois le code ajouté, j'ai lancé `collecte-reguliere.ps1` pour de vrai, comme le ferait le Planificateur :
- collecte en 58 s, sans erreur ;
- 24 nouvelles et 24 disparues, mêmes chiffres que l'essai ;
- 23 fiches retirées du cache (de 213 à 190) ;
- historique et journal écrits, avec les accents intacts.

J'ai aussi vérifié dans Edge :
- l'en-tête indique « 24 nouvelles offres depuis la collecte du 17 novembre 2026 » ;
- le filtre « Nouvelles offres seulement » donne exactement 24 offres, et 12 avec la région Montréal.

`planifier-collecte.ps1` a seulement été vérifié (syntaxe PowerShell correcte). Il n'a pas été lancé : la tâche s'ajoute à l'ordinateur seulement quand on l'exécute soi-même.

Les 13 nouveaux tests (`test_historique.py`) vérifient notamment :
- deux collectes simulées de suite (1 nouvelle, 1 disparue) ;
- une offre retrouvée chez un autre partenaire, qui ne doit pas être comptée comme nouvelle ;
- un `offres.json` précédent absent ou abîmé ;
- l'historique, avec une seule ligne d'en-tête ;
- le ménage du cache, qui ne se fait pas après une collecte partielle ;
- le marqueur UTF-8 des scripts PowerShell.

### Ce que les données montrent (17 novembre)

- **Salaire médian** (valeur basse de la fourchette) : 70 000 $ par année (111 offres), 36 $ de l'heure (68 offres).
- **Technologies les plus demandées :** SQL (32), JavaScript (21), Windows (19), HTML/CSS (19), Azure (18), Python (18).
- **Villes :** Montréal (50), Brossard (39, surtout une firme de recrutement), Québec (20), Sherbrooke (13).
- **Expirations :** 71 offres expirent d'ici le 24 novembre. Les offres restent en ligne peu de temps.

## 6. Limites qui restent

- **Québec emploi, Indeed et ZipRecruiter :** le Guichet-Emplois n'affiche presque jamais leur description (Québec emploi : 2 sur 40). On garde le lien vers l'annonce d'origine.
  - J'ai vérifié Québec emploi le 17 novembre. Techniquement, ce serait facile : ses pages d'offres contiennent un bloc JSON-LD `JobPosting` avec la description complète, et le `robots.txt` les autorise.
  - Mais ses [conditions d'utilisation](https://www.quebecemploi.gouv.qc.ca/conditions-d-utilisation) disent : « Il est interdit d'avoir recours à des robots ou à tout autre procédé automatisé pour accéder au site Québec emploi ou pour y collecter, extraire, générer ou exploiter des données ».
  - Je ne l'ai donc pas ajouté. Pour ces offres, il faut lire la description sur Québec emploi en suivant le lien.
- **Jobboom (vérifié le 20 novembre) :**
  - le `robots.txt` autorise les pages d'offres, et les fiches contiennent des données structurées ;
  - mais les [conditions d'utilisation](https://www.jobboom.com/carriere/conditions-utilisation) interdisent de « modifier, copier, distribuer, transmettre, diffuser, représenter, reproduire, publier […] tout information […] obtenu à partir du site ». Or notre projet copie les offres (`offres.json`) et les republie (`offres.html`, échantillons sur GitHub) ;
  - je ne l'ai donc pas ajouté. Ce point est à vérifier pour toute collecte de Jobboom dans le projet commun.
- **Stages :** un seul confirmé sur 194 offres. Il y a très peu de stages TI sur le Guichet-Emplois en ce moment, et `fsrc=16` n'est pas un filtre de stages.
- **Caractères des partenaires :** des `?` remplacent les apostrophes dans leurs textes (« d?ordinateur »). Ils sont laissés tels quels, car un `?` peut être une vraie question.
- **Salaires :**
  - pas de conversion entre heure, jour, mois et année ;
  - pour Remotive, la devise n'est pas écrite. 2 montants sans unité (`$170k - $200k`) sont gardés dans l'offre, mais ne sont pas comptés dans le tableau des salaires.
- **Niveau :** c'est une règle simple. « Architecte » dans un titre CNP donne « avancé ». 70 offres n'ont aucun indice de niveau.
- **Cache :** il ne se périme pas. Pour relire une fiche, il faut supprimer son fichier dans `cache/fiches/`.
- **Dépendance au site :** si le Guichet-Emplois change ses classes CSS ou ses balises RDFa, il faudra adapter `guichet.py` et `fiches.py`. Les tests utilisent une copie du balisage de novembre 2026.

- **Régions :** la région est trouvée à partir du nom de la ville. Un lieu qui n'est pas une municipalité ni un arrondissement (hameau, quartier, « Différentes régions ») reste sans région. Un nom porté par des municipalités de deux régions différentes reste aussi sans région, sans qu'on en choisisse une.

- **Page HTML :** c'est une photo des offres au moment de sa création. Pour la mettre à jour, il faut refaire une collecte, puis `--html`. Le bouton « Copier le lien » demande l'accès au presse-papiers : certains navigateurs le refusent pour un fichier ouvert en local, et la page affiche alors « Copiez l'adresse de la page ».

- **Aide à la candidature :**
  - la note vient de règles simples. Elle ne comprend que les technologies et compétences de nos listes (51 et 14), écrites clairement dans le CV ;
  - 70 offres sur 195 ne listent ni technologie ni compétence : elles ne sont pas classées, et le programme le dit ;
  - pas de PDF : il faut enregistrer le CV en `.docx` ;
  - les suggestions aident à savoir quoi mettre en avant, mais il faut toujours relire l'offre complète.

- **Lettre de motivation :**
  - les règles ne jugent ni le style ni l'orthographe ;
  - les mots-clés sont comparés par leur début (5 lettres) : un synonyme (« tester » au lieu de « mettre à l'essai ») n'est pas reconnu.

- **Collecte régulière :**
  - la comparaison se fait seulement avec le dernier `offres.json`. Si une collecte a des erreurs, des offres peuvent paraître « disparues » à tort ; le programme l'écrit alors en avertissement ;
  - le Planificateur ne lance la collecte que si la session Windows est ouverte.

**Pour la mise en commun :** le dossier [`../format-commun/`](../format-commun/README.md), à part de ce projet, convertit `offres.json` au format `JobOffer` de Gregory. Les 195 offres sont acceptées telles quelles par son modèle.

**À faire ensuite :**
- recueillir l'avis des camarades de classe qui testeront la page et l'aide à la candidature.
