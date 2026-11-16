# Livrable 3 — Amélioration de la preuve de concept sur Jobboom

**Auteure :** Elvira  
**Projet :** `job-insights` — Cours 420-SV2-OQ (Collège O’Sullivan de Québec)

---

## 1. Site choisi

- **Jobboom Québec** : https://www.jobboom.com/fr
- **Pages ciblées dans la v2** :
  - Catégorie *Technologies et médias numériques* : `https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1`
  - Recherche par mots-clés TI : `https://www.jobboom.com/fr/emploi/<mot-cle>/_lfrk?dk=<mot-cle>`
  - Fiches d’offres détaillées (JSON-LD `JobPosting`) : `https://www.jobboom.com/fr/offre-emploi/<slug>_p<id>`

---

## 2. Contributions consultées et comparaison des approches

J’ai consulté la synthèse et les trois contributions pertinentes du dépôt :

- [Synthèse du Livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md)
- **Mon POC du Livrable 2 :** [`Scraper.py`](../02-preuve-de-concept-scraping/Scraper.py), son compte rendu [`README.md`](../02-preuve-de-concept-scraping/README.md) et sa sortie [`offres_jobboom.json`](../02-preuve-de-concept-scraping/offres_jobboom.json) (20 offres)
- **POC de Mamadou :** [`poc_scrapers_atelier1.py`](../../mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py) (fonction `poc_scrape_jobboom_ti`, lignes 111–152) et sa sortie [`sample_scraped_jobs.json`](../../mamadou/02-preuve-de-concept-scraping/sample_scraped_jobs.json) (3 offres Jobboom)
- **POC de Kandet :** [`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py) et [`test_poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/test_poc_multi_source.py) (pour l’identification honnête `User-Agent`, la traçabilité de la source d’origine et les tests unitaires hors ligne)

### Comparatif des deux essais sur Jobboom au Livrable 2

| Critère | Elvira (`Scraper.py`) | Mamadou (`poc_scrapers_atelier1.py`) |
| :--- | :--- | :--- |
| **Point d’entrée HTML** | Recherche par mots-clés (`/fr/emploi/<slug>/_lfrk?dk=...`) | Catégorie TI (`/fr/technologies-medias-numeriques/_i10lfr?sortBy=date`) |
| **Repérage des liens** | Balises `<a href>` + `data-url` (`BeautifulSoup`) | Attributs `data-url` par regex (`re.findall`) |
| **Extraction des fiches** | JSON-LD `JobPosting` via `BeautifulSoup` | JSON-LD `JobPosting` via regex |
| **Filtrage et enrichissement** | Filtre `is_it_job`, GPS, modalité, stage, compétences | Aperçu de 220 caractères, sans GPS ni compétences |
| **Volume collecté (L2)** | **20 offres** (dont 1 stage) | **3 offres** (page 1 seulement) |

### Ce qui a fonctionné et limites observées
- **Complémentarité des deux portes d’entrée :**
  - Ma recherche par mots-clés (`stage informatique`, `developpeur web`, `programmeur`, `informatique`) avec tri par pertinence trouve bien les postes de développement et de stage, mais rate des intitulés spécialisés publiés récemment (ex. *Analyste junior en cybersécurité*, *Administrateur Systèmes Asterisk/Linux* ou *Technicien réseau*).
  - À l’inverse, l’approche de **Mamadou** par la catégorie *Technologies et médias numériques* (`_i10lfr?sortBy=date&page=1`) permet d’utiliser le tri par date sans remonter de postes de comptabilité ou de vente, car le secteur est déjà filtré sur les TI.
- **Limites techniques relevées dans la synthèse du Livrable 2 :**
  - Ni le script de Mamadou ni ma v1 ne vérifiaient automatiquement `robots.txt`, et tous deux utilisaient un `User-Agent` de navigateur simulé.
  - Le champ `baseSalary` du JSON-LD n’était pas extrait lorsqu’il était présent.
  - Aucun des deux scripts sur Jobboom n’avait de tests unitaires hors ligne.

---

## 3. Ce que j’ai réutilisé et amélioré dans `scraper_jobboom_v2.py`

J’ai créé [`scraper_jobboom_v2.py`](scraper_jobboom_v2.py) en combinant le meilleur de mon script L2, du POC de Mamadou et des bonnes pratiques de Kandet :

| Amélioration | Pourquoi |
| :--- | :--- |
| **Fusion Catégorie TI (`_i10lfr`) + Mots-clés** | Combine la fraîcheur du flux TI par date de Mamadou et la précision des mots-clés (notamment `stage informatique`) |
| **Déduplication par ID (`jb-<id>`) + `origines_decouverte`** | Évite les doublons entre la catégorie `_i10lfr` et les mots-clés tout en gardant la trace du canal qui a trouvé l’offre |
| **Vérification `robots.txt` (`RobotFileParser`) + `User-Agent` honnête** | Respecte les consignes de conformité du projet (`jobs-insights-osullivan/1.0`) |
| **Extraction du champ `salaire` (`baseSalary`)** | Extrait le salaire du JSON-LD s’il est fourni et laisse `None` sinon (sans rien inventer) |
| **Mode hors ligne `--from-v1` + 7 tests unitaires (`unittest`)** | Permet de tester et vérifier le pipeline complet sans dépendre du réseau |

---

## 4. Commandes pour reproduire et vérifier

```powershell
# 1. Installer les dépendances
pip install -r equipe/Elvira/03-amelioration-preuve-de-concept/requirements.txt

# 2. Lancer les 7 tests unitaires hors ligne (sans connexion Internet)
python -m unittest discover -s equipe/Elvira/03-amelioration-preuve-de-concept -p "test_*.py" -v

# 3. Exécuter la fusion et normalisation hors ligne (échantillon Elvira + échantillon Jobboom de Mamadou)
python equipe/Elvira/03-amelioration-preuve-de-concept/scraper_jobboom_v2.py --from-v1 equipe/Elvira/02-preuve-de-concept-scraping/offres_jobboom.json

# 4. Lancer une collecte en direct sur Jobboom (Catégorie _i10lfr + Mots-clés)
python equipe/Elvira/03-amelioration-preuve-de-concept/scraper_jobboom_v2.py
```

---

## 5. Résultats de la vérification et comparaison v1 vs v2

### A. Tests unitaires hors ligne
Les **7 tests unitaires** dans [`test_scraper_jobboom_v2.py`](test_scraper_jobboom_v2.py) (appuyés sur [`fixtures/jobboom_fixture.json`](fixtures/jobboom_fixture.json)) passent tous en `0,01 s` :
- extraction combinée `<a href>` + `data-url` et exclusion des offres hors-TI ;
- validation positive et négative du filtre `is_it_job` ;
- extraction et normalisation complète d’un bloc JSON-LD `JobPosting` (sans faux positif sur « soins de la vue ») ;
- extraction du salaire (`baseSalary` présent vs `None` quand absent) ;
- déduplication inter-canaux par identifiant `jb-<id>` et fusion de `origines_decouverte` ;
- respect des règles `robots.txt` ;
- fusion réelle des échantillons L2 d’Elvira (20 offres) et de Mamadou (3 offres Jobboom).

### B. Comparaison des résultats obtenus (Livrable 2 vs Livrable 3)

| Critère | Elvira v1 (`offres_jobboom.json`) | Mamadou v1 (`sample_scraped_jobs.json`) | **Version combinée v2 (`offres_jobboom_v2.json`)** |
| :--- | :--- | :--- | :--- |
| **Canaux utilisés** | 4 mots-clés seulement | Catégorie `_i10lfr` (p.1) seulement | **Catégorie `_i10lfr` + 4 mots-clés** |
| **Offres TI uniques sur Jobboom** | 20 offres | 3 offres | **23 offres uniques** (+3 postes TI spécialisés) |
| **Couverture des spécialités TI** | Dév. Web, Soutien TI, BI, Analyse | Cybersécurité, SysAdmin Linux, Réseau | **Complète** (inclut Cybersécurité, Linux et Réseau) |
| **Traçabilité du canal (`origines_decouverte`)** | Non | Non | **Oui** (`mots_cles_elvira`, `categorie_ti:_i10lfr`) |
| **Champ `salaire` (`baseSalary`)** | Non extrait | Non extrait | **Extrait si présent (`None` sinon)** |
| **Conformité `robots.txt` & `User-Agent`** | Non | Non | **Oui** (`RobotFileParser` + UA projet) |
| **Tests unitaires hors ligne** | 0 test | 0 test | **7 tests unitaires (`OK`)** |

Les 3 offres issues de l’approche `_i10lfr` de Mamadou qui enrichissent désormais [`offres_jobboom_v2.json`](offres_jobboom_v2.json) n’avaient pas été trouvées par mes seuls mots-clés :
- `jb-3718101` — *Analyste junior en cybersécurité - Laval* (Régulvar inc., Laval) ;
- `jb-3718119` — *Administrateur(trice) Systèmes (Spécialisation Asterisk 1.4 & Linux)* (Connect it Networks, Laval) ;
- `jb-3718778` — *Technicien réseau, support aux technologies opérationnelles* (Totem recruteur de talent, Saint-Joseph-de-Sorel).

---

## 6. Limites qui subsistent

- **1 requête HTTP par fiche détaillée :** le JSON-LD `JobPosting` n’étant présent que sur la page de chaque offre, il faut toujours visiter chaque fiche individuellement en respectant un délai (`--delay 1.0`).
- **Salaire très rarement publié sur Jobboom :** dans les 23 offres réelles de `offres_jobboom_v2.json`, les employeurs n’ont pas renseigné `baseSalary` dans le JSON-LD (le champ vaut donc `null` conformément à la règle d’intégrité des données, tandis que le parseur est validé par test unitaire sur fixture).
- **Faible volume de stages affichés hors période de recrutement :** une seule offre sur 23 est explicitement un stage (*Stage en soutien informatique* chez Canam), bien que plusieurs postes juniors soient présents (ex. *Analyste junior en cybersécurité*).
