# Guide d'exécution et documentation des scripts — Livrable 3

Ce répertoire constitue l'espace de référence de la démonstration du **Livrable 3** (*Reprendre et améliorer une preuve de concept*) pour le projet **`jobs-insights`**.

---

## 1. Vue d'ensemble de l'architecture

Le connecteur fusionne et bonifie les travaux de l'équipe :
- **Pagination exhaustive par codes CNP TI** (approche de Kandet, 191 offres ciblées).
- **Enrichissement sémantique RDFa / repli DOM et détection de compétences contextuelles** (approche de Hugo).
- **Modèle commun Pydantic v2 `JobOffer`** (zéro invention de données, conformité `AGENTS.md`).
- **Gestionnaire de cache local** et respect du délai de 5 s de `robots.txt`.

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
