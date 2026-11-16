# Plan de travail & Repère IA — Mamadou (`job-insights`)

> **Rôle de ce fichier (`plan.md`) :** Servir de mémoire de travail synthétique pour dialoguer efficacement avec l'assistant IA sans relire tout le dépôt à chaque échange (économie de contexte et de jetons).

---

## 1. Contexte & Règles clés (Résumé de `AGENTS.md` + Synthèses Grégory)

- **Dossier personnel :** `equipe/mamadou/`
- **Cible métier :** Offres d'emploi juniors et stages en TI au Québec (`fprov=QC`).
- **Choix technique validé (Dépendances > gros script `stdlib`) :**
  - Utiliser **`requests` + `beautifulsoup4`** documentés dans un `requirements.txt` local.
  - *Pourquoi :* Remplace avantageusement 250 lignes de `HTMLParser` manuel (comme chez Kandet) et élimine les Regex HTML fragiles de notre Livrable 2 (qui tronquaient la description au premier `</div>`). Le script devient court, lisible et maintenable par toute la classe.
- **Règles de conformité obligatoires :**
  - `User-Agent` honnête : `jobs-insights-osullivan/1.0 (atelier etudiant; mamadou)`.
  - Vérification de `robots.txt` via `urllib.robotparser.RobotFileParser`.
  - Respect du `Crawl-delay: 5` sur Guichet-Emplois (avec option `--delai` en CLI).
  - Aucune donnée inventée : mettre `None` si un champ est absent.
  - Tests unitaires hors ligne (`unittest` + dossier `fixtures/`) sans appel réseau.
- **Style Markdown attendu par Grégory :**
  - Tableaux synthèse très courts (cellules de quelques mots), suivis de fiches à puces.
  - Chiffres vérifiés, liens relatifs vers les fichiers cités, et section honnête sur les limites.

---

## 2. Stratégie technique pour le Livrable 3 (Guichet-Emplois CNP + Fiches RDFa)

En croisant les travaux de **Kandet** (`equipe/kandet/02-preuve-de-concept-scraping/poc_multi_source.py`), **Hugo** (`equipe/hugo/02-preuve-de-concept-scraping/parsers.py`) et notre **Livrable 2** (`equipe/mamadou/02-preuve-de-concept-scraping/poc_scrapers_atelier1.py`) :

1. **Recherche par codes CNP TI (`fn21`) et filtres Guichet-Emplois (idée Kandet) :**
   - Au lieu d'un simple mot-clé `searchstring=développeur` (qui donnait seulement 7 offres à Québec), interroger les **codes CNP 2021 en informatique** (`21230`, `21231`, `21232`, `21233`, `21234`, `21220`, `21222`, `21223`, `22220`, `22221`, `22222`) + filtre province `fprov=QC` + option filtre étudiant/stage `fsrc=16`.
2. **Collecte en 2 niveaux (Liste `<article>` + Fiche détaillée RDFa avec `BeautifulSoup`) :**
   - **Niveau 1 (Liste de résultats) :** extraire de chaque `<article id="article-...">` l'ID, le titre normalisé CNP, l'employeur, la ville, le salaire, le mode de travail (`telework`) et le **site partenaire d'origine** (`Jobillico`, `Québec emploi`, `Talent.com`, etc.).
   - **Niveau 2 (Fiche détaillée `/rechercheemplois/offredemploi/{id}`) :** résoudre la limite principale relevée chez Kandet (qui avait 0 stage détecté et aucune description car la liste n'affiche que le titre générique CNP). Avec `BeautifulSoup`, extraire proprement `property="description"`, `property="title"`, `property="validThrough"` et détecter les **stages** dans le texte complet.

---

## 3. Feuille de route et état d'avancement

- [x] **Livrable 1 :** `01-inventaire-des-sites/sites.md` (validé par Grégory dans la synthèse L1).
- [x] **Création de `plan.md`** comme repère de contexte léger.
- [x] **Finalisation Livrable 2 :** Ajouter `02-preuve-de-concept-scraping/compte-rendu.md` (demandé par Grégory dans la synthèse L2, ligne 132).
- [x] **Livrable 3 — Code & Tests (`03-amelioration-preuve-de-concept/`) :**
  - [x] `requirements.txt` (`requests`, `beautifulsoup4`).
  - [x] `poc_guichet_cnp_v2.py` (recherche par codes CNP TI + filtres + enrichissement fiches RDFa via `BeautifulSoup` + `robots.txt` + `Crawl-delay: 5`).
  - [x] `fixtures/` + `test_poc_guichet_cnp_v2.py` (5 tests unitaires hors ligne).
  - [x] `echantillon_v2.json` (résultat d'un essai réel vérifié).
  - [x] `note.md` (comparaison Kandet / Hugo / Mamadou v1 vs v2 dans le style de Grégory).
