# Compte rendu — Livrable 2 : Preuve de concept de scraping (Jobboom)

**Auteure :** Elvira  
**Projet :** `job-insights` — Cours 420-SV2-OQ (Collège O’Sullivan de Québec)

Ce dossier regroupe ma preuve de concept (Volet 1) et mon compte rendu d’expérimentation (Volet 2) pour la collecte d’offres d’emploi et de stages en informatique sur **Jobboom**.

---

## 📂 Contenu du dossier

| Fichier | Rôle |
| :--- | :--- |
| [`Scraper.py`](Scraper.py) | Collecteur et normalisateur Python pour Jobboom (SSR + JSON-LD `JobPosting`) |
| [`requirements.txt`](requirements.txt) | Dépendances Python (`requests`, `beautifulsoup4`) |
| [`offres_jobboom.json`](offres_jobboom.json) | Échantillon de **12 offres TI réelles de 2026 toujours valides** |
| [`sites.md`](../01-inventaire-des-sites/sites.md) | Inventaire du Livrable 1 et analyse DevTools initiale |

---

## 1. Site choisi et URLs testées

- **Site testé :** [Jobboom](https://www.jobboom.com/fr) (portail d’emploi québécois).
- **Pages de recherche testées (HTML SSR) :**
  - `https://www.jobboom.com/fr/emploi/informatique/_lfrk?dk=informatique`
  - `https://www.jobboom.com/fr/emploi/developpeur-web/_lfrk?dk=developpeur+web`
  - `https://www.jobboom.com/fr/emploi/programmeur/_lfrk?dk=programmeur`
  - `https://www.jobboom.com/fr/emploi/stage-informatique/_lfrk?dk=stage+informatique`
- **Format des fiches d’offres testées (JSON-LD `JobPosting`) :**
  - `https://www.jobboom.com/fr/offre-emploi/<slug-titre>_<slug-entreprise>_p<id>`
  - Exemple : `https://www.jobboom.com/fr/offre-emploi/technicien-informatique_innovmetric-logiciels-inc_p3698100`

---

## 2. Méthode, outils et commandes d’exécution

### Fonctionnement technique (`Scraper.py`)
1. **Recherche multi-mots-clés et pagination (`requests`) :** interroge Jobboom sur les 4 mots-clés TI avec pagination (`page=1..3`) et déduplication ordonnée des liens (`seen_it` + liste `links`).
2. **Parsing HTML (`BeautifulSoup`) :** repère les liens `/offre-emploi/` dans les balises `<a href="...">` et les attributs `data-url` des cartes d’offres, puis filtre la pertinence TI du titre (`is_it_job`).
3. **Extraction des métadonnées structurées (`json.loads`) :** sur chaque fiche, extrait la balise `<script type="application/ld+json">` où `"@type": "JobPosting"`.
4. **Filtre de fraîcheur et de validité (`is_recent_and_valid_offer`) :** écarte toute offre publiée avant 2026 (`date_publication < 2026`) ou déjà expirée (`date_expiration < aujourd'hui`).
5. **Normalisation et enrichissement :**
   - Identifiant unique (`jb-<id>`), localisation (`ville`, `province`, `code_postal`) et coordonnées GPS (`latitude`, `longitude`).
   - Nettoyage du HTML de la description (`description_texte`, une seule description propre sans doublon HTML).
   - Détection de la modalité (`Télétravail`, `Hybride`, `Sur place`), du statut de stage (`est_stage`) et des compétences techniques (`competences_cles`).

### Installation et lancement

```powershell
pip install -r requirements.txt
python Scraper.py
```

Options en ligne de commande :
```powershell
# Rechercher plusieurs mots-clés avec limite par mot-clé
python Scraper.py --keywords "informatique" "developpeur web" "stage informatique" --max-per-keyword 5

# Re-normaliser et filtrer le fichier JSON local existant sans requêtes réseau
python Scraper.py --normalize-existing
```

---

## 3. Données récupérées et vérification

### Résumé de l’échantillon ([`offres_jobboom.json`](offres_jobboom.json))

| Indicateur | Résultat obtenu |
| :--- | :--- |
| **Offres TI 2026 valides retenues** | **12 offres** (dont **1 stage** confirmé, 0 offre des années passées) |
| **Villes représentées** | Montréal, Québec, Laval, Boucherville, Saint-Gédéon-de-Beauce |
| **Modalités** | Sur place, Hybride et Télétravail |

### Exemple d’offre extraite

```json
{
  "id": "jb-3698100",
  "source": "Jobboom",
  "titre": "Technicien informatique",
  "entreprise": "InnovMetric Logiciels Inc.",
  "ville": "Québec",
  "province": "QC",
  "pays": "CA",
  "code_postal": "G1N4N6",
  "coordonnees_gps": {
    "latitude": 46.817136,
    "longitude": -71.312079
  },
  "type_contrat": ["PERMANENT", "FULL_TIME"],
  "modalite": "Télétravail",
  "est_stage": false,
  "competences_cles": ["Azure", "Jira", "Confluence", "Windows"],
  "date_publication": "2026-09-30",
  "date_expiration": "2026-12-01",
  "url": "https://www.jobboom.com/fr/offre-emploi/technicien-informatique_innovmetric-logiciels-inc_p3698100",
  "description_texte": "Vous aimez résoudre des problèmes, offrir un service de qualité..."
}
```

### Vérification avec le site
J’ai comparé un échantillon des offres de `offres_jobboom.json` (notamment *Technicien informatique* chez InnovMetric à Québec et *Stage en soutien informatique* chez Canam à Saint-Gédéon-de-Beauce) avec les pages affichées sur Jobboom : le titre, l’employeur, la ville, le code postal, les dates et le texte de description correspondent exactement aux fiches en ligne.

---

## 4. Difficultés rencontrées, pistes essayées et limites observées

### Ce qui a bloqué ou nécessité des ajustements
1. **Absence d’API XHR publique pour les résultats :** dans l’onglet *Network > Fetch/XHR* des DevTools, les seules requêtes XHR étaient publicitaires. J’ai donc analysé le HTML SSR pour récupérer les liens d’offres, puis lu le JSON-LD `JobPosting` dans chaque fiche.
2. **Offres anciennes (2023) remontées par le tri par pertinence :** sur Jobboom, certaines entreprises renouvellent la date d’expiration (`validThrough: 2027`) d’annonces publiées en 2023 (`datePosted: 2023-11-25`).
   - *Piste appliquée :* ajout de `is_recent_and_valid_offer()` pour rejeter toute offre publiée avant 2026 ou expirée.
3. **Bruit hors-TI et faux positifs :** exclusion des postes hors informatique (comptabilité, ventes, CVC, journalier) via `is_it_job()` et regex strictes sur les compétences (`\bvue\.js\b` pour ne pas matcher « soins de la vue »).

### Limites qui subsistent (corrigées dans le Livrable 3 Multi-Sources)
- Une seule source explorée au Livrable 2 (Jobboom) : le [Livrable 3](../03-amelioration-preuve-de-concept/note.md) étend la collecte à **4 sources complémentaires** (**Jobboom**, **Guichet-Emplois**, **Jobillico** et **Remotive**) avec déduplication inter-sites, export CSV et visualiseur Web.
