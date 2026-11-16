# Livrable 3 — Amélioration et Enrichissement Multi-Sources (5 Plateformes Québec / Canada)

**Auteur :** Mamadou  
**Date :** 16 novembre 2026  
**Code, documentation et tests :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) · [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py) · [`README.md`](README.md) · [`requirements.txt`](requirements.txt)

---

## 1. Sources retenues (5 sites) et contributions consultées

Au lieu de nous limiter à un seul site ou à 3 sources, nous avons consolidé et fiabilisé **les 5 sources concluantes** de nos recherches initiales en les intégrant aux meilleures trouvailles de la classe :

| # | Source | Méthode d'accès en v2 | Apport spécifique | Offres dans `echantillon_v2.json` |
| :-: | --- | --- | --- | :-: |
| **1** | **Guichet-Emplois Canada** | 14 codes CNP TI (`fn21`) + fiches RDFa / DOM | Socle officiel fédéral + vrai titre employeur (`.source-title-inner`) | 6 (sur 25 en p. 1) |
| **2** | **Talent.com Canada** | Double JSON-LD `@graph` (`ItemList` ➔ `JobPosting`) | Offres TI à Québec + coordonnées GPS (`latitude`, `longitude`) | 4 (sur 17 en p. 1) |
| **3** | **Jobboom Québec** | Catégorie TI (`_i10lfr`) hors commandites + JSON-LD | PME et grandes entreprises du Québec | 4 (sur 15 en p. 1) |
| **4** | **Jobillico Québec** | Recherche TI Québec + JSON-LD `JobPosting` | Descriptions très détaillées et nombreuses compétences TI | 4 (sur 9 en p. 1) |
| **5** | **Remotive** | API REST JSON publique (`/api/remote-jobs`) | Postes TI 100 % télétravail ouverts au Canada | 4 |

### Contributions de la classe analysées et réutilisées

| Contribution | Ce qui a été repris | Limite corrigée dans notre v2 |
| --- | --- | --- |
| **Kandet** ([`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py)) | Les 14 codes CNP 2021 TI (`fn21`), l'extraction du partenaire (`li.source span.wb-inv`) et le respect de `robots.txt` | Sa collecte restait sur la page de liste (titres CNP génériques, aucune description, 0 stage détecté) |
| **Hugo** ([`parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py)) | Le repli DOM (`#job-posting-detail`, `ul.job-posting-brief`) et le dictionnaire de compétences sans faux positifs (`C`, `Vue`) | Ses regex capturaient `.js` dans `Vue.js` et n'utilisaient pas les 14 codes CNP TI |
| **Elvira** ([`Scraper.py`](../../elvira/02-preuve-de-concept-scraping/Scraper.py)) | L'utilisation de `requests` + `BeautifulSoup` pour lire les blocs JSON-LD sur Jobboom | Son `set()` rendait l'ordre aléatoire et incluait les annonces commanditées (`job_item_sponsorship`) |
| **Mamadou v1** ([`poc_scrapers_atelier1.py`](../02-preuve-de-concept-scraping/poc_scrapers_atelier1.py)) | Le scraping multi-sources (Talent.com GPS, Jobboom, Guichet-Emplois, Jobillico) | Les regex HTML coupaient la description au 1er `</div>` imbriqué et laissaient du HTML doublement échappé |

---

## 2. Améliorations techniques apportées en v2

| Amélioration | Détail technique |
| --- | --- |
| **1. Recherche par 14 codes CNP TI (`fn21`) + filtre stages (`fsrc=16`)** | Passe de 7 offres (mot-clé `développeur` seul en v1) à 25 offres TI dès la 1re page (~190 au Québec). |
| **2. Cascade à 3 niveaux sur les fiches Guichet-Emplois** | (A) RDFa `property="description"` (avec double passe `BeautifulSoup` pour nettoyer le HTML doublement échappé `&lt;p&gt;` des offres partenaires Jobillico), (B) Repli DOM `#job-posting-detail`, (C) Synthèse du bandeau `ul.job-posting-brief` + vrai titre employeur `.source-title-inner`. **Résultat : 0 description `null` sur les 22 offres.** |
| **3. Schéma unifié riche (`JobBankOffer`)** | 21 champs normalisés sur les 5 sources : `id` préfixé (`ge-`, `tc-`, `jb-`, `ji-`, `rem-`), `titre`, `titre_employeur`, `cnp_title`, `date_publication` en ISO `AAAA-MM-JJ`, `modalite`, `competences_cles` (32 technos sans faux positifs), `est_stage`, `statut_stage`, `latitude`, `longitude`. |
| **4. Conformité réseau (`AGENTS.md`)** | Vérification automatique de `robots.txt` via `RobotFileParser`, `User-Agent` honnête (`jobs-insights-osullivan/1.0`) et délai configurable (`--delai`). |
| **5. Suite de 7 tests unitaires hors ligne** | Exécution en `0.010s` sur les fixtures HTML locales (`fixtures/`) sans aucun appel réseau. |

---

## 3. Commandes de vérification

Voir également la documentation détaillée des entrées/sorties/configuration dans [`README.md`](README.md).

```powershell
pip install -r .\equipe\mamadou\03-amelioration-preuve-de-concept\requirements.txt

# 1. Exécuter les 7 tests unitaires hors ligne
python -m unittest discover -s .\equipe\mamadou\03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Exécuter la collecte enrichie sur les 5 sources
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --limite-guichet 6 --limite-autres 4 --delai 2
```

---

## 4. Comparaison des résultats (v1 vs v2)

| Critère | v1 (Livrable 2) | v2 (Livrable 3) |
| --- | --- | --- |
| **Sources actives dans le script** | 4 sources (schémas différents) | **5 sources** (schéma `JobBankOffer` 100 % unifié) |
| **Volume de l'échantillon vérifié** | 10 offres (130 lignes JSON) | **22 offres riches (693 lignes JSON)** dans [`echantillon_v2.json`](echantillon_v2.json) |
| **Offres avec description complète** | Partielle (tronquée au 1er `</div>` + `<p>` bruts) | **22 / 22 (100 %)** nettoyées sans aucune balise HTML |
| **Vrai titre employeur vs titre CNP** | Confondus | Séparés (`cnp_title` vs `titre_employeur` via `.source-title-inner`) |
| **Extraction des compétences TI** | Aucune | **32 compétences détectées** sans faux positifs (ex. 13 sur CGI, 8 sur Quantum) |
| **Dates de publication** | Format texte variable | Normalisées en **ISO `AAAA-MM-JJ`** (`2026-11-16`) |
| **Tests unitaires hors ligne** | 0 | **7 tests (`OK` en `0.010s`)** |

---

## 5. Limites qui subsistent et suite du plan

- **Enrichissement des offres partenaires externes sans texte sur Guichet-Emplois :** pour certaines offres provenant de `Talent.com` ou `ZipRecruiter` affichées sur Guichet-Emplois, la balise `property="description"` est vide (`<span class="hidden">`). Notre niveau C récupère le vrai titre employeur (`.source-title-inner`), le bandeau de conditions (`ul.job-posting-brief`) et l'identifiant externe (ex. `#646042410191948306`), ce qui permettra au lot suivant de croiser directement l'offre avec notre connecteur Talent.com.
- **Temps de collecte sur gros volumes :** pour enrichir les ~190 fiches CNP de Guichet-Emplois avec un `Crawl-delay: 5s`, l'ajout d'un cache disque local par `id` d'offre (prévu au Lot suivant dans [`plan.md`](../plan.md)) évitera de re-télécharger les fiches déjà connues.
