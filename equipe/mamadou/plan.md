# Plan Directeur — Livrable 3 (`jobs-insights` — Mamadou)

> **Rôle de ce fichier (`plan.md`) :** Mémoire de travail et repère entre les conversations IA pour travailler **Lot par Lot** (1 conversation = 1 lot = 1 commit) sans saturer la fenêtre de contexte ni brûler les tokens.  
> **Dossier de travail :** `equipe/mamadou/03-amelioration-preuve-de-concept/`

---

## 1. Analyse de l'existant & Sélection des 5 Sources

Plutôt que de nous limiter à 3 sites, nous exploitons **les 5 sources concluantes** de nos recherches initiales en fusionnant nos acquis avec les meilleures briques de la classe (Kandet, Hugo, Elvira) :

| # | Source | Mode d'accès | Forces combinées dans notre Livrable 3 |
| :-: | --- | --- | --- |
| **1** | **Guichet-Emplois Canada** | 14 codes CNP TI (`fn21`) + Fiches RDFa/DOM | Couverture exhaustive QC (Kandet) + cascade RDFa/DOM/bandeau (Hugo + Mamadou) + vrai titre employeur `.source-title-inner` |
| **2** | **Talent.com Canada** | Double JSON-LD `@graph` (`ItemList` ➔ `JobPosting`) | URLs propres + coordonnées GPS (`latitude`, `longitude`) + descriptions complètes |
| **3** | **Jobboom Québec** | Catégorie TI `_i10lfr` + JSON-LD `JobPosting` | Exclusion des commandites (`job_item_sponsorship`), ordre préservé et nettoyage HTML |
| **4** | **Jobillico Québec** | Recherche TI Québec + JSON-LD `JobPosting` | Fiches PME/grandes entreprises québécoises riches en compétences TI |
| **5** | **Remotive** | API REST JSON (`/api/remote-jobs`) | Postes TI 100 % télétravail ouverts au Canada |

---

## 2. Schéma de données unifié (`JobBankOffer`)

Chaque offre collectée sur l'une des 5 sources est normalisée dans la `@dataclass JobBankOffer` (21 champs, `None` si absent, zéro donnée inventée) :
- **Identifiants & Liens :** `id` (`ge-...`, `tc-...`, `jb-...`, `ji-...`, `rem-...`), `source_id`, `url`, `source`, `source_partenaire`
- **Titres :** `titre`, `titre_employeur` (intitulé réel de l'employeur), `cnp_title` (intitulé officiel CNP)
- **Entreprise & Lieu :** `entreprise`, `lieu`, `province`, `pays`, `latitude`, `longitude`
- **Dates & Conditions :** `date_publication` (ISO `AAAA-MM-JJ`), `date_fin`, `type_poste`, `modalite` (`Sur place`, `Hybride`, `Télétravail`), `niveau_etudes`, `salaire`
- **Qualification TI & Stage :** `est_stage` (`bool`), `statut_stage` (`confirmed_stage`, `possible_stage`, `not_indicated`), `competences_cles` (`list[str]` — 32 technos sans faux positifs), `description` (texte intégral nettoyé), `date_extraction`

---

## 3. Feuille de route par Lots (1 Lot = 1 Conversation = 1 Commit)

### Lot 1 — Cadrage, analyse de la classe et plan directeur *(✅ Terminé)*
- [x] Analyser les travaux du dépôt (Kandet, Hugo, Elvira, Ferdinand, Rayan, Grégory).
- [x] Définir la stack (`requests` + `beautifulsoup4` dans `requirements.txt`).
- [x] Rédiger le compte rendu manquant du Livrable 2 (`02-preuve-de-concept-scraping/compte-rendu.md`).
- [x] Créer `plan.md` pour piloter les itérations.

### Lot 2 — Collecteur 5 sources enrichi, Codes CNP TI, Tests hors ligne & Documentation *(✅ Terminé)*
- [x] Implémenter la recherche Guichet-Emplois par **14 codes CNP TI (`fn21`)** + filtre stages (`fsrc=16`).
- [x] Implémenter la cascade d'enrichissement des fiches Guichet-Emplois (RDFa `property="description"` avec décodage du HTML doublement échappé Jobillico + repli DOM `#job-posting-detail` + bandeau `ul.job-posting-brief` + vrai titre `.source-title-inner`).
- [x] Intégrer les 4 autres sources (**Talent.com GPS**, **Jobboom TI**, **Jobillico**, **Remotive API**) dans le même schéma riche `JobBankOffer` avec dates ISO et extraction de 32 compétences TI.
- [x] Créer **7 tests unitaires hors ligne** (`test_poc_guichet_cnp_v2.py` + `fixtures/`).
- [x] Générer le jeu d'essai vérifié [`echantillon_v2.json`](03-amelioration-preuve-de-concept/echantillon_v2.json) (**22 offres riches, 693 lignes, 0 description `null`**).
- [x] Documenter l'usage des scripts (Configuration / Entrées / Sorties) dans [`03-amelioration-preuve-de-concept/README.md`](03-amelioration-preuve-de-concept/README.md) et [`note.md`](03-amelioration-preuve-de-concept/note.md).

### Lot 3 — Cache disque local & Pagination multi-pages *(⏳ Prochain lot)*
- [ ] Ajouter un gestionnaire de cache local sur disque (`cache/` avec TTL 24 h, ignoré par Git) pour ne pas re-télécharger les fiches déjà lues et respecter le `Crawl-delay: 5s` sans attente inutile.
- [ ] Ajouter la pagination multi-pages (`--pages N`) sur Guichet-Emplois CNP et Jobboom TI.
- [ ] Ajouter les tests unitaires hors ligne du cache et de la pagination.
- [ ] Mettre à jour `README.md` et `plan.md`.

### Lot 4 — Déduplication inter-sources & Export CSV Excel (`utf-8-sig`) *(⏳ À venir)*
- [ ] Implémenter la déduplication inter-sources (ex. lorsqu'une offre Jobillico ou Talent.com est également présente sur Guichet-Emplois via `source_partenaire` ou par empreinte normalisée `titre_employeur + entreprise + ville`).
- [ ] Ajouter l'export CSV compatible Excel sous Windows (`utf-8-sig`, séparateur `;`) en complément de l'export JSON.
- [ ] Ajouter les tests unitaires hors ligne de déduplication.

---

## 4. Matrice de suivi

| Lot | Description | Statut | Fichiers principaux | Tests hors ligne |
| :-: | --- | :-: | --- | :-: |
| **Lot 1** | Cadrage, analyse & `compte-rendu.md` L2 | ✅ Fait | `plan.md`, `02-.../compte-rendu.md` | S/O |
| **Lot 2** | Collecteur 5 sources CNP + Fiches + Doc | ✅ Fait | `poc_guichet_cnp_v2.py`, `README.md`, `note.md`, `echantillon_v2.json` | **7 tests OK (0,01 s)** |
| **Lot 3** | Cache disque local 24 h & Pagination | ⏳ À faire | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py` | À ajouter |
| **Lot 4** | Déduplication inter-sources & Export CSV | ⏳ À faire | `poc_guichet_cnp_v2.py`, `test_poc_guichet_cnp_v2.py` | À ajouter |
