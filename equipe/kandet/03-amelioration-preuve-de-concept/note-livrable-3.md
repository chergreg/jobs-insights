# Note — Livrable 3 : reprendre et améliorer une preuve de concept

**Kandet** — 17 novembre 2026

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
- Le prototype est découpé en modules : `guichet`, `fiches`, `remotive`, `normalisation`, `competences`, `fusion`, `analyse`, `main`.
- Nouveaux champs :
  - titre de l'employeur, description, tâches ;
  - date d'expiration et date de début ;
  - type d'emploi, études, expérience, langues ;
  - ville, province, code postal ;
  - salaire en chiffres (minimum, maximum, unité, devise, « à négocier ») ;
  - technologies, compétences, années d'expérience, niveau et description courte.
- Stages : le champ « Stage: Ce poste est un stage… » du Guichet-Emplois est reconnu, et la détection se fait aussi sur le vrai titre et la description.
- Statistiques : top technologies, salaires par unité (jamais mélangés), villes, expirations proches, champs remplis.
- Deux défauts de la source sont corrigés : `é` écrit tel quel dans 10 fiches, et `&amp;` encodé deux fois.

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

Depuis la racine du dépôt, avec Python 3.12+ et aucune dépendance :

```powershell
# Collecte complète : environ 17 min la première fois (5 s par fiche), environ 1 min ensuite grâce au cache
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --echantillon .\equipe\kandet\03-amelioration-preuve-de-concept\echantillon.json

# Essai court sur 5 fiches
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --max-fiches 5

# Sans les fiches (comme au L2)
python .\equipe\kandet\03-amelioration-preuve-de-concept\main.py --sans-fiches

# Tests hors ligne (102 tests)
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
| Études, expérience, langues | 0 | 71 |
| Technologies détectées | 0 | 83 offres |
| Niveau (débutant, intermédiaire, avancé) | 0 | 124 offres |
| Stages détectés | 0 | 1 confirmé |
| Tests hors ligne | 33 | 102 |

Les compteurs de la dernière colonne viennent du résumé de `offres.json` (`summary.filled_fields`).

### Contrôle des données

- **Salaire :** pour les 188 offres, le montant lu dans le texte de la liste est identique à celui des balises RDFa de la fiche. 0 différence.
- **5 fiches ouvertes en ligne le 17 novembre**, comparées aux données collectées : 2 du Guichet-Emplois, 1 de Jobillico, 1 de Québec emploi, 1 de Talent.com.
  - Le titre, l'employeur, la date d'expiration et le salaire correspondent pour les 5.
  - La description correspond pour 4. La 5e, celle de Québec emploi, est une offre fusionnée avec sa copie Jobillico : sa description vient de la fiche Jobillico, comme prévu.
  - Les technologies détectées sont bien écrites dans les pages. Par exemple, « Postgres » donne PostgreSQL.
- **Détections risquées :** j'ai relu le texte autour des technologies les plus risquées (Windows, Oracle, SAP, Swift, Rust, Cisco, Git, Java). Toutes correspondent à de vraies mentions.

### Ce que les données montrent (17 novembre)

- **Salaire médian** (valeur basse de la fourchette) : 70 000 $ par année (111 offres), 36 $ de l'heure (68 offres).
- **Technologies les plus demandées :** SQL (32), JavaScript (21), Windows (19), HTML/CSS (19), Azure (18), Python (18).
- **Villes :** Montréal (50), Brossard (39, surtout une firme de recrutement), Québec (20), Sherbrooke (13).
- **Expirations :** 71 offres expirent d'ici le 24 novembre. Les offres restent en ligne peu de temps.

## 6. Limites qui restent

- **Québec emploi, Indeed et ZipRecruiter :** le Guichet-Emplois n'affiche presque jamais leur description (Québec emploi : 2 sur 40). On garde le lien vers l'annonce d'origine. Je n'ai pas lu Québec emploi, car ses conditions d'accès ne sont pas vérifiées.
- **Stages :** un seul confirmé sur 194 offres. Il y a très peu de stages TI sur le Guichet-Emplois en ce moment, et `fsrc=16` n'est pas un filtre de stages.
- **Caractères des partenaires :** des `?` remplacent les apostrophes dans leurs textes (« d?ordinateur »). Ils sont laissés tels quels, car un `?` peut être une vraie question.
- **Salaires :**
  - pas de conversion entre heure, jour, mois et année ;
  - pour Remotive, la devise n'est pas écrite. 2 montants sans unité (`$170k - $200k`) sont gardés dans l'offre, mais ne sont pas comptés dans le tableau des salaires.
- **Niveau :** c'est une règle simple. « Architecte » dans un titre CNP donne « avancé ». 70 offres n'ont aucun indice de niveau.
- **Cache :** il ne se périme pas. Pour relire une fiche, il faut supprimer son fichier dans `cache/fiches/`.
- **Dépendance au site :** si le Guichet-Emplois change ses classes CSS ou ses balises RDFa, il faudra adapter `guichet.py` et `fiches.py`. Les tests utilisent une copie du balisage de novembre 2026.

**À faire ensuite :**
- filtres en ligne de commande (`--ville`, `--techno`, `--niveau`, `--stages`) ;
- export CSV pour Excel ;
- vérifier les conditions de Québec emploi pour récupérer ses descriptions.
