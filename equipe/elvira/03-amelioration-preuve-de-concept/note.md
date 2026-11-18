# Note d’évolution du projet : de L1 à L2, puis de L2 à L3

**Auteure :** Elvira  
**Projet :** `job-insights` — Cours 420-SV2-OQ (Collège O’Sullivan de Québec)

Cette note retrace la progression complète de mon travail à travers les trois jalons du projet :
1. **Du Livrable 1 au Livrable 2** : passage de l’inventaire et de l’inspection technique des sites à une première preuve de concept fonctionnelle sur **Jobboom**.
2. **Du Livrable 2 au Livrable 3** : passage d’un script mono-source à un **pipeline modulaire Multi-Sources (4 plateformes)** garantissant **100 % d’offres TI récentes de 2026 toujours valides**, testé hors ligne et doté d’un visualiseur Web.

---

## 1. Évolution du Livrable 1 au Livrable 2 (De la veille au premier prototype)

### A. Point de départ au Livrable 1 ([`01-inventaire-des-sites/sites.md`](../01-inventaire-des-sites/sites.md))
Au **Livrable 1**, j’ai recensé et analysé **8 plateformes d’offres d’emploi et de stages en TI au Québec** :
- **Portails privés et spécialisés québécois :** Jobboom, Jobillico, KebekJobs, MonTravail.ca, RIMQ (emplois municipaux).
- **Portails publics gouvernementaux :** Guichet-Emplois (Job Bank) et Québec.ca.
- **Agrégateur protégé identifié :** Indeed Canada (signalé avec protection anti-bot Cloudflare, à garder en consultation manuelle).

En inspectant **Jobboom** avec les outils de développement du navigateur (*DevTools > Network > Fetch/XHR*), j’ai fait deux observations techniques décisives :
1. La liste des offres n’est pas chargée par une API XHR externe, mais générée côté serveur (**HTML SSR**) avec des liens `/fr/offre-emploi/<slug>_p<id>`.
2. Chaque fiche d’offre individuelle contient deux balises `<script type="application/ld+json">`, dont la seconde fournit l’offre complète structurée selon le standard **Schema.org (`"@type": "JobPosting"`)** avec titre, entreprise, ville, code postal, coordonnées GPS, dates et description.

### B. Passage au Livrable 2 ([`02-preuve-de-concept-scraping/Scraper.py`](../02-preuve-de-concept-scraping/Scraper.py))
Pour transformer cette analyse du L1 en prototype fonctionnel au **Livrable 2**, j’ai développé [`Scraper.py`](../02-preuve-de-concept-scraping/Scraper.py) avec `requests` et `BeautifulSoup` :
- **Ce qui a été mis en place entre L1 et L2 :**
  - Automatisation de la recherche par mots-clés TI (`informatique`, `developpeur web`, `programmeur`, `stage informatique`) et pagination sur plusieurs pages.
  - Remplacement d’un `set` non ordonné par une liste déterministe avec déduplication des URLs.
  - Extraction automatique du bloc JSON-LD `JobPosting` sur chaque fiche.
  - Ajout d’un premier filtre métier `is_it_job()` pour écarter les offres hors informatique qui mentionnaient simplement « outils informatiques ».
  - Nettoyage du HTML en une seule description propre (`description_texte`) et détection de la modalité, des stages et des compétences TI.

### C. Limites constatées à la fin du Livrable 2
Malgré le bon fonctionnement de ce premier prototype sur Jobboom, plusieurs limites restaient à résoudre :
1. **Présence d’offres anciennes (2023) :** le tri par pertinence de Jobboom remontait certaines annonces publiées en 2023 (`datePosted: 2023-11-25`) dont les employeurs avaient prolongé la date d’expiration jusqu’en 2027.
2. **Couverture limitée à une seule source et un seul canal :** ma recherche par mots-clés ratait certains postes TI spécialisés publiés dans la catégorie *Technologies et médias numériques* (`_i10lfr`), et ne couvrait ni **Guichet-Emplois**, ni **Jobillico**, ni **Remotive**.
3. **Absence de conformité `robots.txt` automatisée et de tests unitaires :** tout le code tenait dans un seul fichier sans suite de tests `unittest` hors ligne ni export CSV/Web.

---

## 2. Évolution du Livrable 2 au Livrable 3 (Passage au Multi-Sources et maturité logicielle)

### A. Analyse et réutilisation des meilleures contributions de la classe
Conformément à l’[énoncé du Livrable 3](../../../livrables/03-amelioration-preuve-de-concept/enonce.md) et à la [synthèse du Livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md), j’ai étudié les travaux de mes camarades pour combiner leurs forces avec les miennes :

| Étudiant consulté | Fichiers analysés | Ce que j’ai repris et adapté dans mon Livrable 3 |
| :--- | :--- | :--- |
| **Elvira (mon L2)** | [`Scraper.py`](../02-preuve-de-concept-scraping/Scraper.py) | Extraction JSON-LD `JobPosting` sur Jobboom, coordonnées GPS, détection de modalité/stages et catalogue de compétences sans faux positifs |
| **Mamadou** | [`poc_scrapers_atelier1.py`](../../mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py) · [`poc_guichet_cnp_v2.py`](../../mamadou/03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py) | Navigation par catégorie TI `_i10lfr` (`sortBy=date`) sur Jobboom et extraction JSON-LD sur **Jobillico** |
| **Kandet** | [`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py) · [`03-amelioration-preuve-de-concept`](../../kandet/03-amelioration-preuve-de-concept/note-livrable-3.md) | Les 14 codes CNP TI sur **Guichet-Emplois**, détection du site partenaire, API **Remotive**, déduplication inter-sites et `User-Agent` honnête |
| **Hugo** | [`models.py`](../../hugo/02-preuve-de-concept-scraping/models.py) · [`parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py) | Séparation modulaire (`models`, `collecteurs`, `pipeline`, `main`) et enrichissement des fiches Guichet-Emplois via RDFa (`property="description"`) et repli DOM |

### B. Les 6 améliorations majeures réalisées entre L2 et L3

1. **Filtre strict de fraîcheur et de validité (`is_recent_and_valid_offer` dans [`models.py`](models.py)) :**
   - Rejette systématiquement toute offre publiée lors des années passées (`date_publication < 2026-01-01`) ainsi que toute offre dont la `date_expiration` est dépassée.
   - Aussi appliqué rétroactivement à mon échantillon L2 ([`offres_jobboom.json`](../02-preuve-de-concept-scraping/offres_jobboom.json), qui passe de 20 à **12 offres 100 % 2026 et valides**).
2. **Passage de 1 site à 4 sources complémentaires ([`collecteurs.py`](collecteurs.py)) :**
   - **`JobboomCollector`** (fusion de mes mots-clés + catégorie `_i10lfr` de Mamadou),
   - **`GuichetEmploisCollector`** (14 codes CNP TI au Québec + fiches RDFa/DOM + `Crawl-delay: 5s`),
   - **`JobillicoCollector`** (recherche TI Québec + JSON-LD `JobPosting`),
   - **`RemotiveCollector`** (API REST JSON publique + filtre Canada + détection des stages).
3. **Modèle de données unique (`JobOffer`) et description unique nettoyée :**
   - Suppression de la duplication `raw_json_ld` observée initialement : chaque offre ne contient plus qu’**une seule description propre (`description_texte`)**, et extrait le `salaire` (`baseSalary`) lorsqu’il existe sans jamais l’inventer (`None` sinon).
4. **Déduplication et fusion inter-sources ([`pipeline.py`](pipeline.py)) :**
   - Détecte lorsqu’une même offre est présente sur deux plateformes (via l’empreinte normalisée `titre + entreprise + ville`) et fusionne leurs informations (garde le salaire de Guichet-Emplois + le GPS/code postal de Jobboom + cumule les compétences et les URLs dans `urls_sources`).
5. **Conformité `robots.txt` (`RobotGuard`) et suite de 11 tests unitaires hors ligne ([`test_scraper_jobboom_v2.py`](test_scraper_jobboom_v2.py)) :**
   - Tous les parseurs, le filtre d’exclusion des offres `< 2026`, la vérification `robots.txt` et la fusion inter-sources sont validés hors ligne en `0,03 s`.
6. **Double export (JSON + CSV Excel) et Visualiseur Web interactif ([`visualiseur.html`](visualiseur.html)) :**
   - Génération automatique de [`offres_multi_sources.json`](offres_multi_sources.json), de [`offres_multi_sources.csv`](offres_multi_sources.csv) (`utf-8-sig` pour Excel) et d’une page Web autonome permettant d’explorer et filtrer les 118 offres par source, ville, modalité, compétence TI et stage.

---

## 3. Tableau récapitulatif de la progression (L1 → L2 → L3)

| Critère | Livrable 1 (`sites.md`) | Livrable 2 (`Scraper.py`) | **Livrable 3 (`main.py` Multi-Sources)** |
| :--- | :--- | :--- | :--- |
| **Objectif atteint** | Inventaire de 8 sites + analyse DevTools Jobboom | Premier prototype Python sur 1 site (Jobboom) | **Agrégateur modulaire sur 4 sources + Visualiseur Web** |
| **Sources automatisées** | 0 (analyse manuelle) | 1 source (Jobboom par mots-clés) | **4 sources** (Guichet-Emplois, Jobboom, Remotive, Jobillico) |
| **Offres TI 2026 valides** | Exemples manuels | **12 offres** Jobboom (2026) | **118 offres uniques de 2026** (dont **6 stages**) |
| **Offres des années passées** | — | 7 offres de 2023 filtrées | **0 offre** (filtre strict `date_publication >= 2026`) |
| **Architecture du code** | Document Markdown | 1 script monolithique (`Scraper.py`) | **4 modules découplés** (`models`, `collecteurs`, `pipeline`, `main`) |
| **Déduplication** | — | Par URL sur Jobboom uniquement | **Intra-source (ID) + Inter-sources (`titre + entreprise + ville`)** |
| **Sorties produites** | `sites.md` | `offres_jobboom.json` | **`offres_multi_sources.json` + `.csv` (Excel) + `visualiseur.html`** |
| **Tests automatisés** | — | 0 test | **11 tests unitaires hors ligne (`OK` en `0,03 s`)** |

---

## 4. Vérification et commandes de reproduction

```powershell
# 1. Exécuter les 11 tests unitaires hors ligne
python -m unittest discover -s equipe/elvira/03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Exécuter le pipeline multi-sources (génère JSON, CSV Excel et visualiseur.html)
python equipe/elvira/03-amelioration-preuve-de-concept/main.py

# 3. Ouvrir le visualiseur Web interactif
Start-Process .\equipe\elvira\03-amelioration-preuve-de-concept\visualiseur.html
```

---

## 5. Limites qui subsistent et pistes pour la suite (Piste 4 — Aide à la candidature)

- **Délai réseau lors d’une collecte complète en direct :** le respect du `Crawl-delay: 5` sur Guichet-Emplois impose une pause de 5 secondes entre chaque page/fiche lors d’un rafraîchissement en direct.
- **Salaire non systématique sur Jobboom et Jobillico :** contrairement à Guichet-Emplois, les employeurs sur Jobboom et Jobillico renseignent rarement `baseSalary` dans le JSON-LD (laissé à `null` sans supposition).
- **Prochaine étape (Piste 4 du projet) :** utiliser la liste normalisée `competences_cles` et `description_texte` des 118 offres de 2026 pour comparer automatiquement les offres avec le CV d’un étudiant dans le visualiseur.
