# Sites d'offres d'emploi et de stages — Atelier 1 (`jobs-insights`)

**Auteur** : Mamadou  
**Profil et cibles de recherche** : Stages (Informatique / Développement logiciel / Réseaux), emplois étudiants à temps partiel et postes juniors au Québec et au Canada.

---

## 1. Liste des sites d'offres d'emploi et de stages identifiés

| # | Site | URL principale | Pertinence pour mon profil | Format technique observé | Faisabilité du scraping (POC) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **1** | **Guichet-Emplois Canada** *(Job Bank)* | `https://www.guichetemplois.gc.ca` | Site officiel fédéral, sans publicité, très riche en stages étudiants et emplois TI au Québec. | **HTML SSR + Balises RDFa Schema.org + API Solr JSON + Flux Atom XML** | ✅ **POC fonctionnel** (`HTTP 200`) |
| **2** | **Jobillico** | `https://www.jobillico.com/fr` | Très forte présence des PME et employeurs de la région de Québec (Capitale-Nationale) et Montréal. | **HTML SSR + JSON-LD (`@type: JobPosting`)** | ✅ **POC fonctionnel** (`HTTP 200`) |
| **3** | **Talent.com Canada** | `https://ca.talent.com/fr` | Agrégateur canadien affichant de nombreux stages en informatique, électronique et postes juniors au Québec. | **HTML SSR + JSON-LD (`ItemList` + `JobPosting` dans `@graph`)** | ✅ **POC fonctionnel** (`HTTP 200`) |
| **4** | **Jobboom** | `https://www.jobboom.com/fr` | Portail québécois structuré par secteurs précis, dont une catégorie dédiée aux technologies et médias numériques. | **HTML SSR (`div.job_item`) + JSON-LD (`@type: JobPosting`)** | ✅ **POC fonctionnel** (`HTTP 200`) |
| **5** | **Remotive** | `https://remotive.com` | Offres en développement logiciel, DevOps, Data et QA 100 % en télétravail accessibles depuis le Canada. | **API REST JSON publique** (`/api/remote-jobs`) | ✅ **Accessible en JSON direct** (`HTTP 200`) |
| **6** | **Québec Emploi** *(Gouv. du Québec)* | `https://quebecemploi.gouv.qc.ca` | Portail provincial officiel pour les emplois régionaux, jobs étudiants et stages au Québec. | **Application dynamique (SPA) / API interne** | ⚠️ Rendu JavaScript requis (Playwright) |
| **7** | **Indeed Canada / LinkedIn Jobs** | `https://ca.indeed.com` | Grands volumes d'offres de stages et d'emplois TI. | **Protection anti-bot stricte (Cloudflare Turnstile / `HTTP 403`)** | ❌ Bloqué en requête HTTP standard |

---

## 2. Navigation sur les sites : éléments à scraper (catégories, filtres, structure)

### 2.1. Guichet-Emplois Canada (`guichetemplois.gc.ca`)
* **URL de recherche et filtres GET** :
  * `https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?searchstring={mot_cle}&mid={id_ville}&sort=M`
  * **Paramètres de filtrage repérés** :
    * `searchstring` : mot-clé recherché (ex. `stage informatique`, `développeur`, `technicien`).
    * `mid` : identifiant géographique de la ville (ex. `22447` pour Québec, `22446` pour Montréal, `23587` pour Lévis).
    * `fprov` : filtre par province (`fprov=QC`).
    * `fper` : horaire de travail (`F` = Temps plein, `P` = Temps partiel / étudiant).
    * `fsrc=16` : filtre ciblant spécifiquement les **emplois étudiants et stages**.
* **Ce qui est à scraper** :
  1. **Dans la page de résultats** : les identifiants d'offres dans les liens `/rechercheemplois/offredemploi/{id}`.
  2. **Dans la page d'une offre** : les attributs sémantiques **RDFa (`property="..."`)** :
     * `property="title"` : titre du poste
     * `property="hiringOrganization"` ➔ `property="name"` : nom de l'entreprise
     * `property="addressLocality"` et `property="addressRegion"` : ville et province
     * `property="baseSalary"` : salaire affiché
     * `property="description"` : description complète des tâches et compétences requises

---

### 2.2. Jobillico (`jobillico.com`)
* **URL de recherche et filtres GET** :
  * `https://www.jobillico.com/recherche-emploi?skwd={mot_cle}&scty={ville}&sort=date`
  * **Paramètres de filtrage repérés** :
    * `skwd` : mot-clé (ex. `développeur`, `stage informatique`).
    * `scty` : ville et province (ex. `Québec, QC`, `Montréal, QC`).
    * `sort=date` : tri par date de publication.
* **Ce qui est à scraper** :
  1. **Dans la page de résultats** : les liens permanents `/fr/offre-d-emploi/{entreprise}/{slug}/{id}`.
  2. **Dans la page d'une offre** : la balise `<script type="application/ld+json">` contenant l'objet **`@type: "JobPosting"`** :
     * `title`, `datePosted`, `validThrough`, `employmentType`.
     * `hiringOrganization.name` (employeur).
     * `jobLocation.address.addressLocality` (ville).
     * `description` (code HTML avec listes `<li>` décrivant les responsabilités et profil recherché).

---

### 2.3. Talent.com Canada (`ca.talent.com/fr`)
* **URL de recherche et filtres GET** :
  * `https://ca.talent.com/fr/jobs?k={mot_cle}&l={ville}`
  * **Paramètres de filtrage repérés** :
    * `k` : mot-clé (ex. `stage informatique`, `développeur python`).
    * `l` : lieu (ex. `Québec, QC`, `Montréal, QC`).
* **Ce qui est à scraper** :
  1. **Dans la page de résultats** : un bloc `<script type="application/ld+json">` contient un `@graph` avec un objet `"@type": "ItemList"` (`#jobList`) qui fournit directement la liste des URLs individuelles (`https://ca.talent.com/fr/view?id={id}`).
  2. **Dans la page d'une offre (`/fr/view?id=...`)** : le `@graph` JSON-LD contient l'objet `"@type": "JobPosting"` avec :
     * `title`, `description`, `datePosted`, `employmentType`, `industry`.
     * `hiringOrganization.name` (entreprise).
     * `jobLocation.address` (ville, région) ainsi que `jobLocation.geo` (`latitude` et `longitude`).

---

### 2.4. Jobboom (`jobboom.com/fr`)
* **Navigation par catégories et filtres d'URL** :
  * **Filtres par secteur (`_i{ID}lfr`)** :
    * `_i10lfr` : **Technologies et médias numériques** (`/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1`)
    * `_i11lfr` : Génie, sciences et techniques scientifiques
    * `_i8lfr` : Vente, achat et service à la clientèle
    * `_i7lfr` : Soutien administratif
  * **Filtres par sous-métier TI (`_i10m{ID}lfr`)** :
    * `_i10m751lfr` : Développeur / Intégrateur Web
    * `_i10m695lfr` : Analyste de données
    * `_i10m90lfr` : Analyste en assurance qualité (QA)
    * `_i10m92lfr` : Analyste en sécurité TI
    * `_i10m97lfr` : Administrateur de réseaux
    * `_i10m100lfr` : Administrateur de systèmes
* **Ce qui est à scraper** :
  1. **Dans la page de résultats** : chaque carte `<div class="job_item" data-url="/fr/offre-emploi/{slug}_p{id}">`.
  2. **Dans la page d'une offre** : le bloc `<script type="application/ld+json">` de type `"@type": "JobPosting"` (titre, employeur, ville, date de publication, date d'expiration et description).

---

### 2.5. Remotive (`remotive.com`)
* **Point d'entrée API** : `https://remotive.com/api/remote-jobs?category=software-dev&search={mot_cle}&limit=20`
* **Champs JSON à extraire** : `title`, `company_name`, `candidate_required_location` (filtrer sur `Canada`, `North America` ou `Worldwide`), `job_type`, `publication_date`, `url`, `description`.

---

## 3. POC Python réalisé

Le script [`poc_scrapers_atelier1.py`](poc_scrapers_atelier1.py) teste la récupération et l'extraction des données sur les 4 premiers sites identifiés (**Talent.com Canada**, **Jobboom**, **Guichet-Emplois Canada** et **Jobillico**) en utilisant uniquement la bibliothèque standard Python (`urllib`, `json`, `re`) :

```powershell
python poc_scrapers_atelier1.py
```

Les offres extraites lors du test sont enregistrées au format structuré dans `sample_scraped_jobs.json`.
