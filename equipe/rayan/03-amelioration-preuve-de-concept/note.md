# Livrable 3 — Amélioration et enrichissement du POC Adzuna Canada

**Auteur :** Rayan Dimitri Motchebe Ngoubo  
**Site choisi :** Adzuna Canada (`https://api.adzuna.com/v1/api/jobs/ca/search/{page}`)  
**Dossier :** `equipe/rayan/03-amelioration-preuve-de-concept/`

---

## 1. Problème initial et constats sur le Livrable 2

Lors du Livrable 2 ([`adzuna_test_2.py`](../02-preuve-de-concept-scraping/adzuna_test_2.py) et [`rapport_preuve_concept_adzuna.md`](../02-preuve-de-concept-scraping/rapport_preuve_concept_adzuna.md)), nous avons collecté **10 fichiers JSON** dans [`adzuna_test_output/`](../02-preuve-de-concept-scraping/adzuna_test_output/) totalisant **321 annonces brutes**. L'inspection approfondie de ces données a mis en évidence six limites majeures :

1. **Champs salariaux et contractuels très incomplets dans l'API structurée** :
   - Sur **229 offres uniques**, l'API Adzuna ne renseigne `salary_min` que sur **22 offres (9,6 %)**, `contract_type` sur **51 offres (22,3 %)**, `contract_time` sur **58 offres (25,3 %)** et ne fournit **aucun champ** pour la période salariale (`heure`, `année`, etc.), la devise ni la modalité de travail (`Présentiel`, `Hybride`, `Télétravail`).
   - Parmi les 22 salaires de l'API, **2 offres de la SODEC** (`5965086256` et `5962245023`) contiennent une valeur symbolique `salary_min = 1` alors que leur description indique clairement `SALAIRE : Minimum : 56 647 $ Maximum : 103 015 $`.
   - Sur l'offre `5966889227`, l'API affiche `93 600` à `104 000` (sans unité) tandis que la description indique `Pay Range: $45.00hr - $50.00hr` (équivalence sur une base de `2 080 h/an`).
2. **Informations riches présentes dans les extraits de description mais ignorées** :
   - Les extraits `description` (~500 caractères) et `title` contiennent des fourchettes salariales en français et en anglais, des durées de contrat (`12 mois`, `6-12 mois`, `2 ans`), des mentions de stages (`stage de 3 mois`), de remplacement (`Remplacement congé de maternité`), d'horaires (`35 h/semaine`, `40 h / semaine`, `80 heures par période de paie`, `2 à 3 jours par semaine`) et de modalités hybrides ou à distance.
3. **Doublons inter-recherches (28,7 %)** :
   - Les 321 annonces brutes contiennent **92 occurrences redondantes** (83 identifiants présents dans plusieurs recherches) et **12 republications** d'un même poste sous des identifiants distincts.
4. **Imprécision géographique de `where="Québec, Québec"`** :
   - Une recherche sur Québec retourne aussi des offres à Montréal, Saint-Hyacinthe, Brossard ou localisées à l'échelle provinciale `["Canada", "Québec"]` (`Québec, Canada`).
5. **Bruit hors-TI dans la catégorie `it-jobs`** :
   - Présence d'annonces hors informatique (`Actuarial Analyst`, `Chauffeur classe 1 -Plancher mobile`, `Chargé de projets immobiliers`).
6. **Interruption sur erreur HTTP 503 et risque d'exposition des clés API** :
   - La 11e recherche du Livrable 2 a échoué avec une erreur `HTTP 503`, interrompant le script avant la création de `summary.json`, et `response.raise_for_status()` dans `requests` inclut l'URL complète (avec `app_id` et `app_key`) dans le message d'exception.

---

## 2. Travaux de l'équipe consultés et réutilisés

Conformément à l'[énoncé du Livrable 3](../../../livrables/03-amelioration-preuve-de-concept/enonce.md) et à la [synthèse du Livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md), nous avons examiné et testé les fonctions de nos collègues avant de les adapter à Adzuna :

| Membre | Fichiers consultés | Briques réutilisées et adaptations apportées pour Adzuna |
| --- | --- | --- |
| **Kandet** | [`normalisation.py`](../../kandet/03-amelioration-preuve-de-concept/normalisation.py)<br>[`regions.py`](../../kandet/03-amelioration-preuve-de-concept/regions.py)<br>[`regions_quebec.csv`](../../kandet/03-amelioration-preuve-de-concept/regions_quebec.csv)<br>[`format-commun/convertir.py`](../../kandet/format-commun/convertir.py) | - Conversion numérique `_to_number` et unités `TEXT_UNITS` : **adaptées avec ancrage contextuel**, car `parse_salary_text()` appliqué tel quel à une description complète capturait `12` (`12 mois`), `4955` (`Réf n°: 4955`) ou `4278` (`ÉCHELLE : 4278`) comme salaires.<br>- Référentiel officiel des municipalités et régions du Québec (`regions_quebec.csv`), adapté pour ne pas confondre `["Canada", "Québec"]` (province) avec la ville de Québec (`"Québec City"`). |
| **Dan** | [`livrable3/modele.py`](../../dan/livrable3/modele.py)<br>[`livrable3/outils.py`](../../dan/livrable3/outils.py)<br>[`livrable3/regroupement.py`](../../dan/livrable3/regroupement.py) | - Architecture `@dataclass` avec liste `doublons_ids` et export CSV `utf-8-sig` (`;`).<br>- Injection de dépendances (`session`, `attendre`) dans `ClientAdzuna` pour tester les retries HTTP `429`/`503` hors ligne en `0,00 s`.<br>- Détection des republications par empreinte `(titre, entreprise, ville)`. |
| **Hugo** | [`02-preuve-de-concept-scraping/parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py) | - Catalogue de compétences `TECH_PATTERNS` sans faux positifs français (`C` isolé, `vue d'ensemble`).<br>- Filtre de pertinence TI adapté aux titres bilingues et aux pluriels (`Administrateur Systèmes`). |
| **Elvira** | [`03-amelioration-preuve-de-concept/models.py`](../../elvira/03-amelioration-preuve-de-concept/models.py) | - Normalisation sans accents (`strip_accents`), exclusions hors-TI (`chauffeur`, `cvc`, `comptable`) et détection des modalités (`Présentiel`, `Hybride`, `Télétravail`). |
| **Ferdinand** | [`format-commun/convertir.py`](../../ferdinand/format-commun/convertir.py) | - Conversion stricte vers les 18 champs du format commun (`JobOffer` de [`equipe/gregory/livrable3/models.py`](../../gregory/livrable3/models.py)) sans jamais inventer de valeur par défaut absente. |

---

## 3. Améliorations apportées et règles d'extraction

### A. Modèle à triple niveau et conservation de la provenance ([`models.py`](models.py))
Chaque `OffreAdzuna` conserve séparément :
1. **Les valeurs brutes de l'API** : `api_salary_min`, `api_salary_max`, `api_salary_is_predicted`, `api_contract_type`, `api_contract_time`.
2. **Les valeurs extraites du texte** : `texte_salaire_min`, `texte_salaire_max`, `texte_devise`, `texte_periode_salaire`, `texte_type_mention_salaire`, `texte_paliers_salariaux`, `texte_segment_salaire`, `texte_type_contrat`, `texte_duree_contrat`, `texte_horaire`, `texte_heures_valeur`, `texte_heures_unite`, `texte_modalite`.
3. **Les valeurs consolidées, leur provenance et les anomalies** : `provenance_salaire`, `provenance_contrat`, `provenance_horaire`, `provenance_modalite` et `anomalies`.

### B. Règles déterministes d'extraction et d'arbitrage ([`extraction_texte.py`](extraction_texte.py))
- **Salaires** :
  - Extraction uniquement sur segments ancrés (`SALAIRE : Minimum ... Maximum ...`, `Base (min.): ... Base (max.): ...`, `ÉCHELLE : \d+ - ...`, fourchettes avec devise `$ / CAD / CA$`, plafonds `Salary – Up to ...` et grilles multi-échelons `Base Compensation For This Role`).
  - **Arbitrage des valeurs suspectes (`< 10 $`)** : Sur les 2 offres SODEC (`api_salary_min = 1.0`), `api_salary_min` est conservé intact, l'anomalie `salaire_api_suspect` est enregistrée, et la fourchette du texte (`56 647 $ à 103 015 $`) est retenue avec `provenance_salaire = "description_remplace_api_suspect"`.
  - **Équivalence annuel / horaire (2 080 h/an)** : Sur l'offre `5966889227` (`API = 93 600–104 000` vs `Texte = $45.00hr - $50.00hr`), les deux valeurs sont conservées et la relation $45 \times 2080 = 93\,600$ est signalée avec `provenance_salaire = "equivalence_probable_annuel_horaire_2080h"`.
  - **Grilles multi-niveaux** : Sur l'offre BCG X (`5964819008`), les 4 paliers (`110 000`, `150 000`, `157 000`, `210 000 CAD`) sont conservés dans `texte_paliers_salariaux` et signalés par l'anomalie `grille_salariale_multi_niveaux`.
  - **Aucune période inventée** : Lorsque l'extrait n'indique pas d'unité (`$100000 - $120000`, `Minimum : 56 647 $ Maximum : 103 015 $`, `Base (min.): 31.51`), `periode_salaire` reste `None`.
- **Contrats, Horaires et Modalités (strictement séparés)** :
  - **Exclusion des faux positifs** : Rejet vérifié par tests de *« vision de détention permanente »* (Valsoft), *« 2 mandats ... au cours des 6 dernières années »* (`5636065186`) et du préfixe *« intern »* dans `international` / `internes`.
  - **Horaire vs Modalité hybride** : `2 jours/semaine au bureau` ou `Hybrid work: 2 days in the office per week` renseigne `modalite = "Hybride"` et ne déclenche jamais `Temps partiel`.
  - **Heures par période de paie** : `Nombre d'heures par période de paie: 80` est conservé avec `texte_heures_valeur = 80.0` et `texte_heures_unite = "période de paie"`, sans conversion arbitraire en `40 h/semaine`.

---

## 4. Résultats mesurés Avant / Après sur les données du Livrable 2

Exécution hors ligne reproductible avec :
```powershell
python equipe/rayan/03-amelioration-preuve-de-concept/main.py
```

### Tableau synthèse Avant (API seule) vs Après (API + Extraction Description)

| Indicateur mesuré | Avant (Livrable 2 — API brute) | Après (Livrable 3 — Enrichi) | Gain / Détail vérifié |
| --- | --- | --- | --- |
| **Annonces / Offres uniques** | 321 annonces dans 10 fichiers | **229 offres uniques** | **92 doublons d'ID** fusionnés + **12 republications** liées |
| **Salaires exploitables** | **20 offres** (22 brutes dont 2 à `1 $`) | **32 offres** (+60,0 %) | +10 nouvelles offres + 2 offres SODEC corrigées (`56 647–103 015 $`) |
| **Périodes salariales connues** | **0 offre** (absente de l'API) | **7 offres** | 4 annuelles, 3 horaires (+ 1 équivalence 2 080 h/an identifiée) |
| **Types de contrat renseignés** | **51 offres** (22,3 %) | **60 offres** (26,2 %) | **+9 offres** via le texte + **20 confirmations** + **1 nuance** (`Permanent or Contract`) |
| **Durées de contrat extraites** | **0 offre** (absente de l'API) | **7 offres** | `12 mois` (×4), `6-12 mois` (×1), `3 mois` (stage ×1), `2 ans` (×1) |
| **Horaires (Temps plein/partiel)** | **58 offres** (25,3 %) | **66 offres** (28,8 %) | **+8 offres** via le texte (7 temps plein, 1 temps partiel) + **4 volumes d'heures** |
| **Modalités de travail** | **0 offre** (absente de l'API) | **34 offres** (14,8 %) | 25 `Hybride`, 5 `Télétravail`, 4 `Présentiel` |
| **Précision géographique** | `display_name` non filtré | **198 villes**, **3 régions**, **28 province** | 12 régions administratives du Québec identifiées sans faux positif |
| **Pertinence métier TI** | Aucun filtre (229/229) | **225 offres TI**, **4 hors-TI signalées** | `Actuarial Analyst`, `Chauffeur classe 1`, `Chargé de projets immobiliers`, `Gouvernance` isolés |
| **Sécurité & Résilience HTTP** | Arrêt au 1er `503` ; clés dans l'URL | Retry progressif (3 essais) + `app_id=***` | 0 clé exposée, campagne isolée par recherche |

### Détail de la provenance des valeurs consolidées (sur les 229 offres uniques)

- **Provenance des salaires (`provenance_salaire`)** :
  - `api` : **19 offres**
  - `description` : **9 offres**
  - `description_remplace_api_suspect` : **2 offres** (SODEC `5965086256` et `5962245023`)
  - `description_grille_multi_niveaux` : **1 offre** (BCG X `5964819008`, 4 paliers)
  - `equivalence_probable_annuel_horaire_2080h` : **1 offre** (CYNET `5966889227`)
  - `aucune` : **197 offres**
- **Provenance des types de contrat (`provenance_contrat`)** :
  - `api` : **30 offres**
  - `api+description` (concordance) : **20 offres**
  - `description` (nouveaux contrats : 2 permanents, 3 CDD, 2 stages, 1 remplacement, 1 pigiste) : **9 offres**
  - `nuance_api_description` (`contract` API vs `Permanent or Long Term Contract` texte) : **1 offre**
  - `aucune` : **169 offres**
- **Provenance des horaires (`provenance_horaire`)** :
  - `api` : **53 offres**
  - `description` (7 temps plein, 1 temps partiel) : **8 offres**
  - `api+description` (concordance) : **5 offres**
  - `aucune` : **163 offres**

---

## 5. Vérification par tests unitaires hors ligne

Commande d'exécution :
```powershell
python -m unittest discover -s equipe/rayan/03-amelioration-preuve-de-concept -p "test_*.py" -v
```

**Résultat :** **15 tests unitaires hors ligne** exécutés en **~0,50 s (`OK`)**, couvrant :
1. Les deux offres SODEC avec le salaire API à `1 $` et la fourchette texte `56 647 $ – 103 015 $`.
2. Les fourchettes annuelles en français (`92 000$ à 115 000$`) et en anglais (`CAD 108,100 - CAD 222,800 - yearly`, `CA$110,600.00–CA$166,000.00 yearly`).
3. Les taux horaires (`28,40 à 40,88 $/heure`, `$70- $110 per hour`) sans capturer les numéros d'échelle (`4278`) ni les durées (`12 months`).
4. L'équivalence probable `2 080 h/an` entre le salaire annuel de l'API (`93 600–104 000`) et le taux horaire du texte (`$45.00hr - $50.00hr`).
5. Les montants décimaux `Base (min.): 31.51 Base (max.): 57.81` sans capturer `Réf n°: 4955` ni `80` heures.
6. Les salaires sans période explicite (`salary$100000 - $120000statusPermanent`, `Up to $210,000`) où `periode` reste `None`.
7. La grille salariale à 4 niveaux de BCG X (`110 000` à `210 000 CAD`) et son anomalie.
8. L'exclusion des faux positifs sur `"permanente"` (*vision de détention permanente*), `"mandat"` (*2 mandats au cours des 6 dernières années*) et `"intern"` (*internationaux*, *équipes internes*).
9. L'extraction des stages (`stage de 3 mois`), remplacements (`Remplacement congé de maternité`), contrats de `2 ans` et cas mixtes (`Permanent or Long Term Contract`).
10. La distinction stricte entre temps partiel (`2 à 3 jours par semaine`) et modalité hybride (`2 jours/semaine au bureau de Québec`).
11. La conservation de `80 heures par période de paie` avec son unité `"période de paie"` sans conversion arbitraire.
12. La distinction géographique entre `["Canada", "Québec"]` (`precision_lieu = "province"`) et `["Canada", "Québec", "Québec City"]` (`ville = "Québec"`, `region = "Capitale-Nationale"`).
13. Le filtrage TI (`Actuarial Analyst` et `Chauffeur` exclus ; `Administrateur.trice systèmes` retenu) et l'absence de faux positifs `C` / `Vue.js`.
14. Le masquage systématique des clés API (`app_id=***&app_key=***`) et le retry progressif sur erreur `HTTP 503`.
15. La déduplication complète des 321 annonces du Livrable 2 vers les 229 offres uniques et la validité des 3 exports (`JSON`, `CSV utf-8-sig`, `Format commun`).

---

## 6. Limites restantes

1. **Descriptions tronquées à ~500 caractères par l'API Adzuna** : L'endpoint de recherche d'Adzuna ne renvoie qu'un extrait. Toute information salariale, contractuelle ou technique située plus bas dans le corps de l'annonce originale n'est pas visible dans la réponse JSON de l'API (ce qui explique que 197 offres sur 229 restent sans salaire connu et 169 sans type de contrat). Conformément aux règles d'[`AGENTS.md`](../../../AGENTS.md), nous ne scrapons pas les sites tiers vers lesquels pointent les liens `redirect_url`.
2. **Périodes salariales non précisées sur 25 des 32 offres avec salaire** : Ni l'API Adzuna (19 offres) ni certains extraits textuels (`$100000 - $120000`, `56 647 $ à 103 015 $`, `Base (min.): 31.51`) n'indiquent explicitement l'unité (`année` ou `heure`). Nous laissons `periode_salaire` à `None` plutôt que de la supposer.
3. **28 offres localisées uniquement à l'échelle provinciale (`"Québec, Canada"`)** : Lorsque `location.area` vaut `["Canada", "Québec"]`, l'annonce ne précise pas la ville dans les métadonnées Adzuna (`precision_lieu = "province"`).
