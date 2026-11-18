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
| Scrapers du livrable 3 | Ajoutés lot par lot | Voir [`livrable3/plan.md`](livrable3/plan.md) |

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
