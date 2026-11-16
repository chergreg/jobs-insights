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
| [`offres_jobboom.json`](offres_jobboom.json) | Échantillon de **20 offres TI réelles** extraites et normalisées |
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
4. **Normalisation et enrichissement :**
   - Identifiant unique (`jb-<id>`), localisation (`ville`, `province`, `code_postal`) et coordonnées GPS (`latitude`, `longitude`).
   - Nettoyage du HTML de la description (`description_texte`).
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

# Re-normaliser le fichier JSON local existant sans requêtes réseau
python Scraper.py --normalize-existing
```

---

## 3. Données récupérées et vérification

### Résumé de l’échantillon ([`offres_jobboom.json`](offres_jobboom.json))

| Indicateur | Résultat obtenu |
| :--- | :--- |
| **Offres TI uniques extraites** | **20 offres** (dont **1 stage** confirmé) |
| **Répartition par ville** | Montréal (12), Québec (3), Laval (2), Boucherville (1), Beauharnois (1), Saint-Gédéon-de-Beauce (1) |
| **Répartition par modalité** | Sur place (12), Hybride (6), Télétravail (2) |

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
J’ai comparé un échantillon des offres de `offres_jobboom.json` (notamment *Technicien informatique* chez InnovMetric à Québec, *Stage en soutien informatique* chez Canam à Saint-Gédéon-de-Beauce et *Développeur fullstack* chez Fed IT à Montréal) avec les pages affichées sur Jobboom : le titre, l’employeur, la ville, le code postal, les dates et le texte de description correspondent exactement aux fiches en ligne.

---

## 4. Difficultés rencontrées, pistes essayées et limites observées

### Ce qui a bloqué ou nécessité des ajustements
1. **Absence d’API XHR publique pour les résultats :** dans l’onglet *Network > Fetch/XHR* des DevTools, les seules requêtes XHR étaient publicitaires (Prebid/Analytics). J’ai dû analyser le HTML généré côté serveur (SSR) pour récupérer les liens d’offres, puis lire le JSON-LD `JobPosting` dans chaque fiche.
2. **Bruit hors-TI avec le tri par date (`sortBy=date`) :** en triant la recherche par mot-clé par date, Jobboom remontait des postes de vente, comptabilité ou construction qui mentionnaient simplement « maîtrise des outils informatiques » dans leur texte.
   - *Piste appliquée :* conserver le tri par pertinence de Jobboom sur la recherche par mot-clé et ajouter le filtre strict `is_it_job()` sur l’intitulé du poste (avec liste d’exclusion pour CVC/bâtiment, comptabilité, ventes).
3. **Faux positifs sur certaines compétences courtes :** lors des premiers essais, des expressions françaises comme « assurance soins de la *vue* » déclenchaient la compétence `Vue`.
   - *Piste appliquée :* utiliser des expressions régulières strictes avec frontières de mots (`\bvue\.js\b`, `\bc#`, etc.).
4. **Ordre aléatoire des offres au premier essai :** l’utilisation initiale d’un `set` pour stocker les liens changeait l’ordre d’un lancement à l’autre.
   - *Piste appliquée :* conserver une liste ordonnée `links` doublée d’un ensemble `seen_it` pour dédupliquer sans perdre l’ordre d’apparition.

### Limites qui subsistent sur Jobboom (pistes pour le Livrable 3)
- **Une requête HTTP par fiche :** la liste de résultats ne contient pas le JSON-LD complet ; il faut visiter chaque fiche individuellement avec un délai (`--delay 1.0`) pour ne pas surcharger le serveur.
- **Salaire quasi absent :** les employeurs sur Jobboom renseignent très rarement `baseSalary` dans le bloc JSON-LD.
- **Peu de stages tagués dans `employmentType` :** même l’offre *Stage en soutien informatique* (Canam) est déclarée `["PERMANENT", "FULL_TIME"]` dans le JSON-LD de Jobboom ; la détection doit donc s’appuyer sur le titre et la description.
- **Améliorations prévues pour le Livrable 3 :** combiner la recherche par mots-clés avec la page de catégorie *Technologies et médias numériques* (`_i10lfr`, testée par Mamadou), ajouter la vérification automatique de `robots.txt` avec un `User-Agent` identifiant le projet, extraire `baseSalary` quand il existe et ajouter des tests unitaires hors ligne.
