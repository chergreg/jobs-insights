# Compte rendu — Livrable 2 : Preuve de concept de scraping

**Auteur :** Mamadou  
**Date :** Novembre 2026  
**Code et sortie :** [`poc_scrapers_atelier1.py`](poc_scrapers_atelier1.py) · [`sample_scraped_jobs.json`](sample_scraped_jobs.json)

---

## 1. Sites et URLs testés

| Site | Format exploité | Offres extraites | Statut |
| --- | --- | :---: | :---: |
| **Talent.com Canada** | JSON-LD (`ItemList` + `JobPosting`) | 3 | ✅ OK |
| **Jobboom Québec** | HTML (`data-url`) + JSON-LD | 3 | ✅ OK |
| **Guichet-Emplois** | HTML (liens) + RDFa (`property`) | 2 | ⚠️ Partiel (HTML tronqué) |
| **Jobillico Québec** | HTML (liens) + JSON-LD | 2 | ✅ OK |

### URLs de départ interrogées
- **Talent.com Canada :** `https://ca.talent.com/fr/jobs?k=stage+informatique&l=Qu%C3%A9bec%2C+QC`
- **Jobboom Québec (secteur TI) :** `https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page=1`
- **Guichet-Emplois Canada :** `https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?searchstring=d%C3%A9veloppeur&mid=22447&sort=M`
- **Jobillico Québec :** `https://www.jobillico.com/recherche-emploi?skwd=d%C3%A9veloppeur&scty=Qu%C3%A9bec%2C%20QC`

---

## 2. Méthode, outils et commande

- **Outils utilisés :** Bibliothèque standard Python uniquement (`urllib.request`, `urllib.parse`, `json`, `re`, `html`, `pathlib`). Aucune dépendance externe pour ce premier prototype.
- **Fonctionnement :**
  1. Pour chaque site, une requête HTTP récupère la page de résultats (par mot-clé ou catégorie).
  2. Le script isole les URLs des fiches individuelles (via le bloc JSON-LD `ItemList` sur Talent.com, ou par expression régulière sur les attributs `data-url` / `href` pour les trois autres sites).
  3. Chaque fiche est ouverte pour lire ses métadonnées structurées : bloc `<script type="application/ld+json">` (`@type: "JobPosting"`) sur Talent.com, Jobboom et Jobillico, ou attributs RDFa `property="..."` sur Guichet-Emplois.

### Commande d'exécution

```powershell
python .\equipe\mamadou\02-preuve-de-concept-scraping\poc_scrapers_atelier1.py
```

Le script affiche les offres collectées dans le terminal et génère le fichier [`sample_scraped_jobs.json`](sample_scraped_jobs.json) dans le même dossier.

---

## 3. Données récupérées

Au total, **10 offres réelles** ont été extraites et enregistrées dans [`sample_scraped_jobs.json`](sample_scraped_jobs.json) :
- **Talent.com Canada (3 offres) :** *Analyste en informatique* (CHU de Québec - Université Laval), *Technicien(ne) informatique* (OPEQ), *Stage marketing digital* (Umbrella). Le JSON-LD fournit également les coordonnées GPS (`lat` / `lon`).
- **Jobboom Québec (3 offres TI) :** *Administrateur - Systèmes et Centre de données* (Emballages Mitchel-Lincoln Ltée), *Ingénieur IA* (Robert Half), *Technicien.ne en gestion des données* (Totem).
- **Guichet-Emplois Canada (2 offres) :** *développeur Web/développeuse Web* (Richard & Levesque), *développeur/développeuse de logiciels* (Brainfy AI Inc.).
- **Jobillico Québec (2 offres) :** *Développeur (sr.)* et *Développeur (int.)* chez FOP Experts Conseils inc.

### Exemple d'offre extraite (Talent.com Canada)

```json
{
  "source": "Talent.com Canada",
  "title": "Technicien(ne) informatique",
  "company": "OPEQ",
  "city": "Québec City",
  "region": "QC",
  "gps": {
    "lat": 46.8127,
    "lon": -71.2193
  },
  "date_posted": "2026-10-31",
  "employment_type": "FULL_TIME",
  "url": "https://ca.talent.com/fr/view?id=634537925073176368",
  "description_preview": "Description du poste L'OPEQ est à la recherche d'une personne dynamique..."
}
```

---

## 4. Difficultés rencontrées, limites observées et pistes pour la suite

| Problème observé | Cause technique | Correction prévue au Livrable 3 |
| --- | --- | --- |
| **Description coupée (Guichet-Emplois)** | Regex `property="description".*?</div>` stoppée au 1er `</div>` interne | Utiliser `BeautifulSoup` (`bs4`) au lieu des regex HTML |
| **Faux URL `/jobsearch/pers/offredemploi/`** | L'URL interne renvoyait `HTTP 404` hors session navigateur | Utiliser l'URL publique `/rechercheemplois/offredemploi/{id}` |
| **Absence de délai et de `robots.txt`** | Enchaînement direct des requêtes avec un `User-Agent` Firefox | Ajouter `RobotFileParser`, `User-Agent` honnête et `time.sleep(5)` |
| **Peu d'offres sur mot-clé simple** | `searchstring=développeur` + `mid=22447` ne trouve que 7 offres | Filtrer par codes CNP TI (`fn21`) et province (`fprov=QC`) |
| **Schéma JSON non uniforme** | Clés différentes selon le site (`gps`, `valid_through` absents ailleurs) | Modèle unique (`dataclass`) avec `None` pour les champs absents |
| **Aucun test unitaire** | Script monolithique sans fixtures locales | Découper les fonctions et ajouter des tests `unittest` hors ligne |
