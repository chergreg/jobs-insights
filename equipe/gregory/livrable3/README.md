# Guide d'exécution et documentation des scripts — Livrable 3

Ce répertoire constitue l'espace de référence de la démonstration du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**.

---

## 1. Vue d'ensemble de l'architecture

Le livrable fusionne et bonifie les travaux de l'équipe :
- **Connecteur #1 : Guichet-Emplois Canada** (Lot 2) :
  - Pagination exhaustive par codes CNP TI (approche de Kandet, 191 offres ciblées).
  - Enrichissement sémantique RDFa / repli DOM et détection de compétences contextuelles (approche de Hugo).
  - Gestionnaire de cache local et respect du délai de 5 s de `robots.txt`.
- **Connecteur #2 : Jobboom Québec** (Lot 3) :
  - Pagination ordonnée et paramétrable de la catégorie TI (surpassant la limite de 5 offres d'Elvira).
  - Extraction robuste du JSON-LD Schema.org/JobPosting via `json.loads` natif (fiabilisant l'approche de Mamadou).
  - Respect de la temporisation éthique de 2.0 s et gestion du cache local disque (search/details).
- **Connecteur #3 : Remotive** (Lot 4) :
  - Client API REST JSON (`/api/remote-jobs`) bonifié à partir des travaux de Kandet.
  - Politique stricte de cache local 24 h (respectant la limitation de 4 requêtes/jour de Remotive).
  - Moteur de classification géographique multi-niveaux ciblant le Canada, le Québec et le télétravail étudiant.
  - Détection native des stages via `job_type == "internship"` et complétée sémantiquement.
- **Modèle commun Pydantic v2 `JobOffer`** (zéro invention de données, conformité `AGENTS.md`).

---

## 2. Scripts Python : guide d'utilisation, entrées, sorties et configuration

### A. Script de démonstration et test en direct (`run_demo_guichet.py`)

Interroge Guichet-Emplois Canada en direct pour effectuer une recherche selon les 14 codes CNP du domaine informatique au Québec, enrichir les fiches détaillées et démontrer l'accélération par le cache.

- **Fichier** : `run_demo_guichet.py`
- **Configuration** :
  - `delai_secondes` : `5.0` s entre chaque requête HTTP directe vers le site officiel.
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/guichet_emplois/` (conservation 24 heures).
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre d'offres maximum à retourner (défaut : `5`).
  - `--pages P` : Nombre de pages de recherche HTML à explorer (défaut : `1`).
  - `--term MOTCLE` : Filtrage optionnel par mot-clé (ex: `python`, `stage`).
  - `--enrich` : Télécharge et analyse la fiche détaillée pour extraire la description et les compétences clés (activé par défaut).
  - `--no-cache` : Force des requêtes HTTP réelles sans lire le cache existant.
- **Sorties** :
  - **Console** : Affichage structuré pour chaque offre (ID normalisé, titre officiel + titre employeur, entreprise, lieu, modalité, salaire, compétences détectées, statut de stage, extrait de description).
  - **Cache disque** : Fichiers HTML enregistrés sous `cache/guichet_emplois/search/` et `cache/guichet_emplois/details/`.
- **Exemples de commandes** :
  ```powershell
  # 1. Test rapide par mot-clé (2 offres au Québec)
  python run_demo_guichet.py --term python --limit 2

  # 2. Recherche par défaut sur les codes CNP TI (3 offres)
  python run_demo_guichet.py --limit 3

  # 3. Forcer le rafraîchissement sans cache
  python run_demo_guichet.py --limit 2 --no-cache
  ```

---

### B. Générateur du jeu d'essai standardisé (`generate_dataset.py`)

Normalise, nettoie et consolide les données réelles issues des POCs précédents dans le schéma pivot `JobOffer`.

- **Fichier** : `generate_dataset.py`
- **Configuration** :
  - Dictionnaire de normalisation canonique des technologies (`TECH_CANONICAL`).
  - Filtrage strict éliminant les faux positifs récurrents en français (`C` isolé, `VUE`).
- **Entrées** :
  - Données sources Hugo : `../../hugo/02-preuve-de-concept-scraping/data/offres_emploi_canada.json`
  - Données sources Kandet : `../../kandet/02-preuve-de-concept-scraping/echantillon.json`
- **Sorties** :
  - Fichier JSON structuré : `data/offres_guichet_emplois.json` (97 offres TI québécoises validées par Pydantic).
- **Exemple de commande** :
  ```powershell
  python generate_dataset.py
  ```

---

### C. Suite de tests unitaires 100 % hors ligne (`test_guichet_emplois.py`)

Garantit la non-régression et la robustesse de chaque composant sans dépendre de la connexion réseau.

- **Fichier** : `test_guichet_emplois.py`
- **Configuration** :
  - Mode hors ligne forcé (`offline_mode=True`) : tout appel réseau non simulé lève immédiatement une exception.
- **Entrées** : Fixtures HTML/XML statiques intégrées au fichier de test.
- **Sorties** : Rapport d'exécution unittest (24 tests validés en ~0,03 s).
- **Exemple de commande** :
  ```powershell
  python -m unittest test_guichet_emplois.py -v
  ```

---

### D. Script de démonstration et test en direct Jobboom (`run_demo_jobboom.py`)

Interroge le portail Jobboom Québec en direct ou depuis le cache pour collecter et enrichir les offres du secteur TI via JSON-LD.

- **Fichier** : `run_demo_jobboom.py`
- **Configuration** :
  - `delai_secondes` : `2.0` s entre chaque requête HTTP directe (éthique et conforme).
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/jobboom/` (conservation 24 heures).
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre d'offres maximal à retourner (défaut : `5`).
  - `--pages P` : Nombre de pages de résultats à parcourir (défaut : `1`).
  - `--keyword MOTCLE` : Filtrage optionnel par mot-clé (ex: `python`, `stage`).
  - `--no-cache` : Force des requêtes HTTP réelles sans lire le cache existant.
  - `--save-dataset` : Sauvegarde les offres collectées dans `data/offres_jobboom.json`.
- **Sorties** :
  - **Console** : Affichage structuré pour chaque offre (ID `jb-...`, titre, employeur, lieu, type de contrat, modalité, salaire, compétences détectées, statut de stage, extrait de description).
  - **Cache disque** : Fichiers HTML enregistrés sous `cache/jobboom/search/` et `cache/jobboom/details/`.
- **Exemples de commandes** :
  ```powershell
  # 1. Test rapide sur 3 offres TI (mode cache automatique)
  python run_demo_jobboom.py --limit 3

  # 2. Recherche par mot-clé sur 2 pages
  python run_demo_jobboom.py --keyword devops --pages 2 --limit 5

  # 3. Forcer le rafraîchissement sans cache
  python run_demo_jobboom.py --limit 2 --no-cache
  ```

---

### E. Générateur du jeu d'essai Jobboom (`generate_jobboom_dataset.py`)

Consolide les contributions d'Elvira (5 offres) et Mamadou (3 offres) avec une collecte paginée sur 2 pages du connecteur Jobboom fiabilisé.

- **Fichier** : `generate_jobboom_dataset.py`
- **Entrées** :
  - Données sources Elvira : `../../elvira/02-preuve-de-concept-scraping/offres_jobboom.json`
  - Données sources Mamadou : `../../mamadou/02-preuve-de-concept-scraping/sample_scraped_jobs.json`
  - Collecte en direct/cache sur la catégorie `_i10lfr`
- **Sorties** :
  - Fichier JSON structuré : `data/offres_jobboom.json` (31 offres TI québécoises validées par Pydantic).
- **Exemple de commande** :
  ```powershell
  python generate_jobboom_dataset.py
  ```

---

### F. Suite de tests unitaires 100 % hors ligne Jobboom (`test_jobboom.py`)

Garantit la robustesse du parsing de listing et du bloc JSON-LD Schema.org/JobPosting sans connexion réseau.

- **Fichier** : `test_jobboom.py`
- **Configuration** : Mode hors ligne forcé (`offline_mode=True`).
- **Entrées** : Fixtures HTML/JSON-LD locales (JobPosting, @graph, MonetaryAmount, etc.).
- **Sorties** : Rapport d'exécution unittest (23 tests validés en ~0,03 s).
- **Exemple de commande** :
  ```powershell
  python -m unittest test_jobboom.py -v
  ```

---

### G. Script de démonstration et test en direct Remotive (`run_demo_remotive.py`)

Interroge l'API REST publique Remotive avec politique de cache local 24 h (respectant la limite stricte de 4 requêtes/jour), classification géographique fine et détection native des stages.

- **Fichier** : `run_demo_remotive.py`
- **Configuration** :
  - `cache_hours` : `24` h (utilisation prioritaire du cache disque).
  - `user_agent` : `jobs-insights-atelier/1.0 (Projet etudiant DEC Informatique; contact: gregory@jobs-insights.local)`.
  - `cache_dir` : `cache/remotive/remotive_cache.json`.
- **Entrées (Paramètres CLI)** :
  - `--limit N` : Nombre maximal d'offres à afficher (défaut : `15`).
  - `--geo-filter FILTRE` : `canada_eligible` (défaut), `canada_only`, `quebec_only`, `all`.
  - `--category CAT` : Catégorie d'emplois Remotive (ex: `software-development`, `data`).
  - `--search RECHERCHE` : Mot-clé de recherche optionnel.
  - `--stage-only` : Conserver uniquement les stages.
  - `--no-cache` : Forcer un appel réseau direct vers l'API Remotive.
  - `--save-dataset` : Exporter les offres normalisées dans `data/offres_remotive.json`.
- **Sorties** :
  - **Console** : Synthèse statistique (répartition des contrats, lieux, technologies, stages) et fiches d'offres détaillées.
  - **Cache disque** : Fichier JSON complet avec enveloppe et horodatage UTC.
- **Exemples de commandes** :
  ```powershell
  # 1. Démonstration rapide sur les offres ouvertes au Canada
  python run_demo_remotive.py --limit 5

  # 2. Filtrer uniquement les stages TI
  python run_demo_remotive.py --stage-only

  # 3. Cibler les offres strictement au Québec ou Canada
  python run_demo_remotive.py --geo-filter canada_only
  ```

---

### H. Générateur du jeu d'essai standardisé Remotive (`generate_remotive_dataset.py`)

Collecte les offres en direct/cache de Remotive et consolide les cas de référence de stages (conformité Kandet).

- **Fichier** : `generate_remotive_dataset.py`
- **Sortie** : `data/offres_remotive.json` (12 offres normalisées `JobOffer`, dont 3 stages confirmés).
- **Exemple de commande** :
  ```powershell
  python generate_remotive_dataset.py
  ```

---

### I. Suite de tests unitaires 100 % hors ligne Remotive (`test_remotive.py`)

Valide l'ensemble des règles de parsing, de classification géographique, de détection de stages et de cache sans aucun appel réseau.

- **Fichier** : `test_remotive.py`
- **Configuration** : Mode hors ligne forcé (`offline_mode=True`).
- **Entrées** : Fixtures JSON locales complètes (stages, Québec, Amérique du Nord, Monde, Hors cible).
- **Sorties** : 34 tests validés en ~0,05 s.
- **Exemple de commande** :
  ```powershell
  python -m unittest test_remotive.py -v
  ```

---

### Exécution globale de l'ensemble des tests du Livrable 3

Pour exécuter d'un coup l'ensemble des suites de tests unitaires (Guichet-Emplois + Jobboom + Remotive) :

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```
*(81 tests unitaires validés en ~0,10 s).*

---

## 3. Schéma de données unifié (`models.py`)

Chaque offre est représentée par la classe Pydantic `JobOffer` :

```python
class JobOffer(BaseModel):
    id: str                        # Ex: "ge-50701948"
    titre: str                     # Intitulé du poste
    entreprise: str                # Nom de l'employeur
    lieu: str                      # Ex: "Québec (QC)", "Montréal (QC)"
    province: str                  # Ex: "QC"
    pays: str                      # "Canada"
    url: str                       # Lien direct propre (sans session)
    source: str                    # "guichet-emplois"
    source_partenaire: Optional[str] # Partenaire d'origine (ex: "Jobillico", "Talent")
    date_publication: Optional[str]# Date au format ISO AAAA-MM-JJ
    type_poste: Optional[str]      # "Temps plein", "Stage", etc.
    modalite: Optional[str]        # "Sur place", "Hybride", "Télétravail"
    est_stage: bool                # True si stage identifié
    statut_stage: str              # "confirmed_stage", "possible_stage", "not_indicated"
    description: Optional[str]     # Description nettoyée sans HTML
    competences_cles: List[str]    # Technologies clés extraites sans faux positifs
    salaire: Optional[str]         # Rémunération textuelle brute si mentionnée
    date_extraction: str           # Horodatage ISO
```
