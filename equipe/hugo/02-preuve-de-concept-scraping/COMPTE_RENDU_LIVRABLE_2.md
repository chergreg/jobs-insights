# Compte rendu — Livrable 2 : Preuve de concept de scraping

**Auteur :** Hugo  
**Projet :** `job-insights` — Cours 420-SV2-OQ (Collège O'Sullivan de Québec)  
**Date :** Novembre 2026  

---

## 1. Site choisi et URLs testées

* **Plateforme :** Guichet-Emplois Canada / Job Bank Canada (Gouvernement du Canada).
* **URLs analysées et testées :**
  1. *Flux Atom XML officiel :* `https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed?sort=D&fprov=QC&wid=s&action=search`
  2. *Recherche HTML et pagination :* `https://www.guichetemplois.gc.ca/jobsearch/jobsearch` et `/jobsearch/job_search_loader.xhtml`
  3. *Fiches détaillées d'offres :* `https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{id}`
  4. *Fichier des règles :* `https://www.guichetemplois.gc.ca/robots.txt`

---

## 2. Méthodes, architecture et commandes d'exécution

### Approche multi-stratégies (Cascade avec repli)
Afin de concilier rapidité, fiabilité et pérennité, le collecteur met en œuvre une cascade à 3 niveaux :
1. **Niveau 1 (Flux Atom XML officiel) :** Requête HTTP rapide récupérant les annonces récentes avec métadonnées résumées (ID, titre, date, employeur, lieu, salaire) en 1 seule requête sans risque de casse de sélecteurs CSS.
2. **Niveau 2 (Recherche HTML par mots-clés) :** Si le flux Atom ne comble pas le quota souhaité (ex. 100 offres), interrogation de la recherche HTML avec un bouquet étendu de 16 métiers en informatique au Québec.
3. **Niveau 3 (Enrichissement des fiches détaillées) :** Visite des pages d'offres pour extraire la modalité (télétravail, hybride, sur place), le type de contrat (stage vs temps plein), les compétences techniques et la description complète.
   - *Priorité sémantique :* Balises Schema.org / RDFa (`property="description"`, `property="title"`).
   - *Repli DOM :* Sélecteurs CSS (`div#job-posting-detail`, `section.job-posting-detail-requirements`).

### Outils et dépendances
* **Python 3.12+**
* `requests` (gestion des sessions HTTP)
* `beautifulsoup4` (analyse HTML et extraction RDFa/DOM)
* `pydantic` (validation typée du schéma `JobOffer`)
* `xml.etree.ElementTree` (parsing du flux Atom XML)
* `urllib.robotparser` (vérification de conformité `robots.txt`)

### Commandes d'exécution

* **Installation des dépendances :**
  ```powershell
  pip install -r requirements.txt
  ```

* **Exécution des tests unitaires hors ligne (23 assertions) :**
  ```powershell
  python -m unittest test_scraper.py -v
  ```

* **Lancement en mode ligne de commande (CLI automatisable) :**
  ```powershell
  # Collecte standard conforme (délai 5s, 100 offres par défaut)
  python main.py --limit 100 --province QC

  # Collecte rapide de test (délai 1.2s)
  python main.py --limit 20 --fast
  ```

* **Lancement interactif :**
  Double-clic sur `main.py` ou commande `python main.py` sans argument.

---

## 3. Données récupérées et exemple de résultat

### Statistiques de collecte
* **Volume collecté :** 87 offres réelles uniques en TI au Québec.
* **Répartition des types de postes :** 85 postes réguliers (temps plein/partiel), 2 stages identifiés.
* **Modalités de travail :** 19 offres en mode Hybride / Télétravail, 68 sur place.
* **Descriptions :** 100 % des offres enrichies disposent désormais du texte complet de description.
* **Partenaires identifiés dans les annonces :** Guichet-Emplois (32), Jobillico (20), Québec emploi (15), Talent.com (11), JobsMedia.ca (6), indeed.com (2), CareerBeacon (1).

### Extrait JSON d'une offre normalisée
```json
{
  "id": "gc-50691239",
  "titre": "développeur/développeuse d'applications dorsales",
  "entreprise": "JobsMedia",
  "lieu": "Sainte-Thérèse (QC)",
  "province": "QC",
  "pays": "Canada",
  "salaire": "80 000,00 $ à 100 000,00 $ par année",
  "date_publication": "09 novembre 2026",
  "modalite": "Sur place",
  "type_poste": "Temps plein",
  "competences_cles": [
    "Agile",
    "MySQL",
    "PHP",
    "PostgreSQL",
    "React",
    "SQL",
    "Vue.js"
  ],
  "description": "Nous recherchons un développeur d'applications dorsales pour collaborer au sein d'une équipe agile. Vos principales tâches incluront la conception et le maintien d'API robustes...",
  "url_source": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50691239",
  "source": "Guichet-Emplois",
  "partenaire": "JobsMedia.ca",
  "methode_extraction": "HTML-Search+RDFa-Detail",
  "date_extraction": "2026-11-11T19:40:00"
}
```

---

## 4. Ce qui a mal fonctionné, limites observées et solutions apportées

| Problème / Limite observée | Impact sur la collecte | Solution apportée / Piste validée |
| :--- | :--- | :--- |
| **Description initialement vide (`null`)** | Les premières collectes n'extrayaient pas le texte descriptif de la fiche. | Implémentation d'une cascade d'extraction : détection RDFa `property="description"` puis repli sur le conteneur DOM `div#job-posting-detail`. |
| **Faux positifs sur les compétences** | La lettre `"C"` était détectée 26 fois (sur "c.", "c'est") et `"VUE"` 14 fois (sur "vue d'ensemble"). | Regex strictes limitées aux contextes informatiques (`"Vue.js"` explicite, `"langage C"` ou exclusion des mots courants français). |
| **Délai `crawl-delay` de 5 s** | Le respect strict des 5 s rend la collecte de 100 fiches longue (~8-10 min). | Utilisation prioritaire du flux Atom XML (1 seule requête pour 100 offres) et ajout d'un drapeau `--fast` pour le développement. |
| **Dépendance de session sur `job_search_loader.xhtml`** | L'endpoint de pagination AJAX requiert une session active et peut échouer hors session. | Combinaison avec la recherche multi-mots-clés qui réduit le besoin de pagination profonde. |
| **Doublons inter-partenaires** | 63 % des offres sur Guichet-Emplois pointent vers des partenaires externes (Jobillico, Talent.com). | Conservation du champ `partenaire` et déduplication rigoureuse par identifiant unique (`gc-...`). |
| **Absence d'API REST publique** | Guichet-Emplois n'a pas d'API REST directe de recherche par filtres. | Utilisation du flux Atom XML officiel comme équivalent d'une API structurée. |
