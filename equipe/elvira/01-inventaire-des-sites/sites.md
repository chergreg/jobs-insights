# Liste et analyse des sites d'offres d'emploi et stages (TI / Développement Web)

## Profils et domaines recherchés

- **Informatique / Technologies de l'information (TI)**
- **Développeur(euse) Web** (Front-end, Back-end, Full-stack)
- **Programmation / Génie logiciel**
- **Stages en informatique**

---

## 1. Documentation des 8 sites identifiés

| # | Site | URL | Catégories / Filtres TI à cibler | Méthode technique de scraping |
|---|---|---|---|---|
| 1 | **Jobboom** | https://www.jobboom.com/fr | Mots-clés (`informatique`, `developpeur web`, `programmeur`, `stage informatique`), Secteur *Technologies et médias numériques* (`_i10lfr`) | **SSR (HTML) + JSON-LD** : Liste d'offres dans le HTML (`/fr/offre-emploi/...`) + objet JSON structuré `@type: "JobPosting"` dans chaque page d'offre. |
| 2 | **Guichet-Emplois (Job Bank)** | https://www.qc.guichetemplois.gc.ca/parcourirlesoffresdemploi/province/QC | Province (`QC`), Codes CNP TI : `21232` (Développeurs logiciels), `21234` (Développeurs Web), `21222` (Spécialistes TI) | **Flux Atom/RSS + HTML/RDFa** + présence de `application/ld+json` (`JobPosting`) sur les fiches d'offres. |
| 3 | **Québec.ca (Offres d'emploi)** | https://www.quebec.ca/emploi/trouver-emploi-stage/consulter-offres-emplois | Portail gouvernemental redirigeant vers Guichet-Emplois Québec et les offres de stages de la fonction publique | Même structure que Guichet-Emplois (`qc.guichetemplois.gc.ca`). |
| 4 | **Jobillico** | https://www.jobillico.com/fr/ | Catégorie *Informatique / TI*, mots-clés (`développeur`, `programmeur`), filtre télétravail / région | **HTML + Requêtes XHR** lors du filtrage/pagination + balise `application/ld+json` (`JobPosting`) sur les fiches de poste. |
| 5 | **KebekJobs** | https://www.kebekjobs.com/emplois | Recherche par mot-clé (`informatique`, `développeur`) et par ville au Québec | **CMS / API interne** : Requêtes XHR ou pages d'offres contenant les métadonnées structurées de chaque poste. |
| 6 | **Indeed Canada (Québec)** | https://emplois.ca.indeed.com/q-emploi-l-province-de-qu%c3%a9bec-emplois.html | Paramètres URL `q=developpeur+web` et `l=Québec`, filtre type d'emploi (Stage, Temps plein) | **JSON embarqué dans `<script>`** (`window.mosaic.providerData["mosaic-provider-jobcards"]`). *Note : forte protection Cloudflare / consultation manuelle privilégiée.* |
| 7 | **MonTravail.ca** | https://www.montravail.ca/ | Recherche par mot-clé (`informatique`, `programmeur`) et région | **HTML / AJAX** : Extraction des liens d'offres depuis la liste et lecture des détails sur chaque fiche. |
| 8 | **RIMQ (Emplois municipaux)** | https://rimq.qc.ca/emplois/municipal/ | Catégorie *Informatique / Technologies de l'information* dans les municipalités du Québec | **HTML statique léger** : Toutes les offres de la catégorie sont chargées directement dans le DOM HTML de la page. |

---

## 2. Analyse détaillée : Jobboom (Focus POC #1)

### A. Navigation, filtres et structure des URLs

Lors de l'exploration avec les DevTools (onglet *Network > Fetch/XHR*), nous avons constaté que Jobboom ne charge pas la liste des offres via une API XHR externe (les requêtes XHR visibles sont uniquement des régies publicitaires type Prebid/Google Analytics). La liste est générée côté serveur (SSR) dans le document HTML principal.

- **URL de recherche par mot-clé (`dk`)** :
  - Informatique : `https://www.jobboom.com/fr/emploi/informatique/_lfrk?dk=informatique`
  - Développeur Web : `https://www.jobboom.com/fr/emploi/developpeur-web/_lfrk?dk=developpeur+web`
  - Programmeur : `https://www.jobboom.com/fr/emploi/programmeur/_lfrk?dk=programmeur`
  - Stage en informatique : `https://www.jobboom.com/fr/emploi/stage-informatique/_lfrk?dk=stage+informatique`
- **URL par secteur Technologies (`_i10lfr`) avec pagination** :
  - `https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1`
- **Format des URLs des fiches d'emploi** :
  - Toutes les offres suivent le modèle :
    `https://www.jobboom.com/fr/offre-emploi/<slug-du-titre>_<slug-entreprise>_p<id_numerique>`
  - Exemple réel : `https://www.jobboom.com/fr/offre-emploi/developpeur-fullstack_fed-it_p3149892`

### B. Source de données JSON identifiée (`application/ld+json`)

Sur chaque page d'offre individuelle, Jobboom injecte deux balises `<script type="application/ld+json">` :
1. Le premier bloc (`index 0`) décrit l'organisation Jobboom (`"@type": "Organization"`).
2. Le second bloc (`index 1`) contient l'offre d'emploi complète au format standard **Schema.org (`"@type": "JobPosting"`)**.

#### Champs JSON disponibles dans chaque offre Jobboom :
- `title` : Titre exact du poste (ex. *"Développeur fullstack"*, *"Technicien(ne) informatique senior"*)
- `datePosted` : Date de publication (`YYYY-MM-DD`)
- `validThrough` : Date d'expiration de l'offre (`YYYY-MM-DD`)
- `employmentType` : Type de contrat (ex. `["PERMANENT", "FULL_TIME"]`, `["CONTRACTOR", "FULL_TIME"]`)
- `hiringOrganization` :
  - `name` : Nom de l'employeur (ex. *"Fed IT"*, *"Canam"*)
  - `logo` : URL du logo de l'entreprise
- `jobLocation` :
  - `address.addressLocality` : Ville (ex. *"Montréal"*, *"Boucherville"*)
  - `address.addressRegion` : Province (`"QC"`)
  - `address.postalCode` : Code postal
  - `geo.latitude` / `geo.longitude` : Coordonnées GPS exactes du lieu de travail
- `description` : Description complète du poste (HTML incluant les tâches, technologies requises et modalités de candidature)

---

## 3. Fonctionnement du POC Python (`Scraper.py`)

1. **Recherche multi-mots-clés & pagination (`requests`)** sur Jobboom (`informatique`, `developpeur web`, `programmeur`, `stage informatique`) avec déduplication des URLs.
2. **Parsing HTML (`BeautifulSoup`)** pour extraire tous les liens `<a href="...">` contenant `/offre-emploi/`.
3. **Extraction du JSON (`json.loads`)** sur chaque fiche d'offre à partir de la balise `<script type="application/ld+json">` où `@type == "JobPosting"`.
4. **Normalisation et enrichissement** :
   - Nettoyage du HTML de la description (`description_texte`).
   - Extraction normalisée de l'identifiant (`id`), de la localisation (`ville`, `province`, `code_postal`, `coordonnees_gps`), du type de contrat, de la modalité (`Télétravail`, `Hybride`, `Sur place`), du statut de stage (`est_stage`) et des compétences techniques (`competences_cles`).
5. **Sauvegarde** des offres structurées et normalisées dans `offres_jobboom.json`.

### Exécution du POC

```bash
pip install requests beautifulsoup4
python Scraper.py
```
