# Livrable 3 — Amélioration de la collecte sur Guichet-Emplois (CNP TI + Fiches RDFa)

**Auteur :** Mamadou  
**Date :** 16 novembre 2026  
**Code et tests :** [`poc_guichet_cnp_v2.py`](poc_guichet_cnp_v2.py) · [`test_poc_guichet_cnp_v2.py`](test_poc_guichet_cnp_v2.py) · [`requirements.txt`](requirements.txt)

---

## 1. Site choisi et contributions consultées

- **Site choisi :** **Guichet-Emplois Canada** (`https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois`)
- **Pourquoi ce choix :** Trois étudiants ont exploré ce site au Livrable 2 avec des approches complémentaires qui, combinées, résolvent les limites de chacun.

### Contributions analysées

| Contribution | Approche technique | Point fort majeur | Limite principale observée |
| --- | --- | --- | --- |
| **Kandet** ([`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py)) | Liste HTML par 14 codes CNP TI (`html.parser`) | Capte ~190 offres TI au Québec + site partenaire | Aucune description ni stage détecté (titres CNP génériques) |
| **Hugo** ([`parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py)) | Liste par mots-clés + fiches (`BeautifulSoup`) | Repli DOM `#job-posting-detail` + modalité | Pause < 5 s, faux positifs compétences |
| **Mamadou v1** ([`poc_scrapers_atelier1.py`](../02-preuve-de-concept-scraping/poc_scrapers_atelier1.py)) | Recherche mot-clé + fiches RDFa (`re`) | Lecture des balises sémantiques RDFa | Seulement 7 offres, description coupée au 1er `</div>` |

- **Référence complémentaire :** [Synthèse du Livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md).

---

## 2. Ce que j'ai repris et modifié

J'ai combiné **la recherche par codes CNP TI de Kandet** avec **l'enrichissement des fiches RDFa de ma v1 et de Hugo**, tout en passant à **`requests` + `beautifulsoup4`** pour éliminer les regex HTML et alléger le script (~250 lignes au lieu de 840 en `stdlib` pure).

| Modification apportée | Problème résolu |
| --- | --- |
| **Passage à `requests` + `BeautifulSoup` (double passe)** | Corrige la troncature au 1er `</div>` et nettoie le HTML doublement échappé (`&lt;p&gt;`) des offres partenaires Jobillico |
| **Recherche par 14 codes CNP TI (`fn21`) + `fprov=QC`** | Passe de 7 offres (mot-clé `développeur` seul) à 25 offres dès la 1re page (~190 au total) |
| **Option `--stages` (`fsrc=16`) + détection sur la fiche** | Résout le problème des titres CNP génériques où 0 stage n'apparaissait dans la liste |
| **Extraction du partenaire (`li.source span.wb-inv`)** | Identifie si l'offre vient de `Jobillico`, `Talent.com`, `ZipRecruiter` ou `Guichet-Emplois` |
| **Vérification `robots.txt` + `User-Agent` honnête + délai 5 s** | Respecte les règles de conformité de [`AGENTS.md`](../../../AGENTS.md) |
| **Modèle `@dataclass JobBankOffer` (`None` par défaut)** | Schéma uniforme sans aucune donnée inventée |
| **5 tests unitaires hors ligne (`fixtures/`)** | Vérifie le parsing des listes, des `<div>` imbriqués, du HTML doublement échappé et des stages |

---

## 3. Commandes pour reproduire

```powershell
pip install -r .\equipe\mamadou\03-amelioration-preuve-de-concept\requirements.txt

# 1. Lancer les tests unitaires hors ligne (sans réseau)
python -m unittest discover -s .\equipe\mamadou\03-amelioration-preuve-de-concept -p "test_*.py" -v

# 2. Lancer la collecte réelle (5 offres enrichies, délai conforme robots.txt = 5s)
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --limite 5

# 3. Cibler uniquement le filtre emplois étudiants / stages (fsrc=16)
python .\equipe\mamadou\03-amelioration-preuve-de-concept\poc_guichet_cnp_v2.py --stages --limite 5
```

---

## 4. Vérification et comparaison (v1 vs v2)

### Tests unitaires hors ligne
Les **4 tests hors ligne** passent en `0.007s` à partir des fichiers locaux [`fixtures/liste_resultats_exemple.html`](fixtures/liste_resultats_exemple.html) et [`fixtures/fiche_offre_imbriquee.html`](fixtures/fiche_offre_imbriquee.html). Ils valident notamment que le texte situé après un premier `</div>` imbriqué dans `property="description"` est intégralement conservé et qu'un stage masqué derrière un titre générique CNP dans la liste est bien détecté (`confirmed_stage`) à la lecture de la fiche.

### Comparaison des résultats réels (v1 vs v2)

| Critère | v1 (Livrable 2) | v2 (Livrable 3) |
| --- | --- | --- |
| **Offres TI trouvées sur la 1re page** | 7 (mot-clé `développeur` à Québec) | **25** (14 codes CNP TI au Québec) |
| **Qualité de la description** | Tronquée au 1er `</div>` + balises `<p>` | **Complète et nettoyée** via `BeautifulSoup` |
| **Site partenaire d'origine** | Non extrait | **Extrait** (`Guichet-Emplois`, `Jobillico`, `Québec emploi`…) |
| **Salaire, modalité, études, date fin** | Absents | **Extraits** (`None` si non affiché) |
| **Conformité `robots.txt` & délai** | Aucun délai, faux `User-Agent` | **`RobotFileParser` + `Crawl-delay: 5s` + `User-Agent` honnête** |
| **Tests unitaires hors ligne** | 0 | **4 tests (`OK`)** |

Les 5 offres enrichies de l'essai réel sont enregistrées dans [`echantillon_v2.json`](echantillon_v2.json).

---

## 5. Limites qui subsistent

- **Temps de collecte des fiches détaillées :** avec le respect du `Crawl-delay: 5` demandé par `robots.txt`, l'enrichissement de 25 fiches prend environ 2 minutes (1 requête par fiche). Pour une collecte complète des ~190 offres, il faudra mettre en cache les fiches déjà lues par leur `source_id`.
- **Descriptions absentes sur certaines offres partenaires externes :** lorsque Guichet-Emplois redirige vers certains partenaires externes (ex. `Québec emploi`), la fiche Guichet-Emplois contient parfois uniquement un résumé court ou les métadonnées de base, la description détaillée étant hébergée sur le site partenaire.
- **Titres normalisés CNP :** même sur la fiche détaillée, `property="title"` conserve souvent l'intitulé de la classification CNP ; le titre exact choisi par l'employeur ne figure parfois que dans le corps de la description ou sur le site partenaire d'origine.
