# Livrable 3 — Reprendre et améliorer une preuve de concept (Dan)

> **Cours :** 420-SV2-OQ, Collège O'Sullivan de Québec — projet `jobs-insights`
> **Cible :** stages et postes TI en début de carrière au Québec
> **Code :** [`equipe/dan/livrable3/`](.) · **Plan par lots :** [`plan.md`](plan.md) · **Commit :** [`ba6f982`](https://github.com/chergreg/jobs-insights/commit/ba6f9827754135fe9365d5b54160862b7e2c0140) (publication du 2026-11-23)

En bref : mon POC du livrable 2 lisait **1 page d'un seul site** (25 offres, sans description). Au livrable 3, j'ai réutilisé le meilleur de l'équipe pour collecter **3 sites**, ouvrir les **fiches** des offres, retirer les **doublons** entre sources et m'arrêter proprement si un site refuse. Le tout est vérifié par **137 tests hors ligne**. Exécution réelle : **44 offres uniques** (section 6.4).

---

## 1. Sites choisis

| Rang | Site | Méthode | Pourquoi |
| :-: | --- | --- | --- |
| 1 | Guichet-Emplois | Liste HTML paginée + fiches RDFa | Mon site du L2 ; le plus de volume au Québec ; reprend des partenaires |
| 2 | Jobboom | Catégorie TI + fiches JSON-LD | Portail québécois, PME absentes du Guichet |
| 3 | Talent.com | JSON-LD `ItemList` + `JobPosting` | Agrégateur canadien avec GPS |
| Plan B | Remotive | API officielle | Si Talent.com refuse les robots |

### Pourquoi ces trois sites
- Ce sont les trois sites où l'équipe a déjà obtenu de **vraies offres** (Kandet, Hugo, Elvira, Mamadou, Gregory).
- Ils offrent des **données structurées** (RDFa, JSON-LD), plus stables que des sélecteurs CSS.
- Leur accès est **public**, sans compte ni contournement.

### Site écarté : CareerBeacon
- Testé au L2 : `robots.txt` permet la recherche, mais le serveur répond **403 (Cloudflare)**.
- Décision : arrêt, aucun contournement ([`sites.md`](../01-inventaire-des-sites/sites.md)).

### Plan B : pas encore déclenché
- Talent.com n'est pas connu comme bloqué : Mamadou y a lu 4 vraies offres le 2026-11-16.
- Mon scraper vérifie l'accès à chaque lancement et conseille Remotive en cas de refus.

---

## 2. Contributions consultées

| Auteur | Fichiers | Ce qui a fonctionné | Limites observées |
| --- | --- | --- | --- |
| Synthèses | [L2](../../../livrables/02-preuve-de-concept-scraping/synthese.md), [L3](../../../livrables/03-amelioration-preuve-de-concept/synthese.md) | Vue d'ensemble, remarques du prof | — |
| Dan (moi) | [`poc_guichetemplois.py`](../02-preuve-de-concept-scraping/poc_guichetemplois.py), [`offres_guichetemplois.csv`](../02-preuve-de-concept-scraping/offres_guichetemplois.csv) | 25 offres TI au Québec | 1 page, pas de description |
| Kandet | [`poc_multi_source.py`](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py), [`fixtures.py`](../../kandet/03-amelioration-preuve-de-concept/fixtures.py) | Pagination CNP, site d'origine, 33 tests | Pas de fiches |
| Hugo | [`parsers.py`](../../hugo/02-preuve-de-concept-scraping/parsers.py) | Fiches RDFa du Guichet | Mots-clés fixes |
| Elvira | [`Scraper.py`](../../elvira/02-preuve-de-concept-scraping/Scraper.py), [`scraper_jobboom_v2.py`](../../elvira/03-amelioration-preuve-de-concept/scraper_jobboom_v2.py), [fixture](../../elvira/03-amelioration-preuve-de-concept/fixtures/jobboom_fixture.json) | JSON-LD Jobboom, GPS | `RobotFileParser` |
| Mamadou | [`poc_guichet_cnp_v2.py`](../../mamadou/03-amelioration-preuve-de-concept/poc_guichet_cnp_v2.py), [`echantillon_v2.json`](../../mamadou/03-amelioration-preuve-de-concept/echantillon_v2.json) | Talent.com réel, commandites Jobboom | Valeurs par défaut, `hash()` |
| Gregory (démo) | [`guichet_emplois.py`](../../gregory/livrable3/scrapers/guichet_emplois.py), [`jobboom.py`](../../gregory/livrable3/scrapers/jobboom.py), [`pipeline.py`](../../gregory/livrable3/pipeline.py) | Stratégie RDFa + repli, règle des doublons | Valeurs par défaut, délais fixés |

### Ce qui revient chez plusieurs auteurs
- **Valeurs devinées** : « Non spécifié », « Québec (QC) », « Temps plein », `est_stage = False` par défaut (Gregory, Mamadou).
- **`robots.txt` mal lu** : `RobotFileParser` ne comprend pas les `*` (Elvira, Mamadou) ; délais écrits dans le code au lieu d'être lus (Gregory).
- **Descriptions** : HTML encodé deux fois sur les offres partenaires du Guichet (repéré par Kandet).

---

## 3. Ce que j'ai réutilisé

| Brique | Origine | Où dans mon code |
| --- | --- | --- |
| Filtres `fprov=QC` + 14 codes CNP `fn21` + `sort=D` | Kandet, mon L2 | [`guichet_emplois.py`](scrapers/guichet_emplois.py) |
| Sélecteurs de la liste (`article`, `.noctitle`…) | Kandet | `guichet_emplois.lire_resultats` |
| Description RDFa + repli `#job-posting-detail` | Hugo, Mamadou, Gregory | `guichet_emplois.lire_fiche` |
| HTML encodé deux fois | Kandet | [`commun.html_vers_texte`](scrapers/commun.py) |
| Catégorie `_i10lfr`, exclusion `job_item_sponsorship` | Mamadou | [`jobboom.py`](scrapers/jobboom.py) |
| JSON-LD `JobPosting` (bloc `Organization` à ignorer, GPS) | Elvira | [`jsonld.py`](scrapers/jsonld.py) |
| Recherche Talent.com, `ItemList`, `/fr/view?id=` | Mamadou | [`talent.py`](scrapers/talent.py) |
| Total « 1 - 15 de 131 résultats » | Gregory | `jobboom.lire_categorie` |
| Ne pas fusionner deux offres du même diffuseur | Gregory | [`regroupement.py`](regroupement.py) |

Les fixtures de mes tests reprennent le balisage relevé sur les vrais sites par Kandet, Mamadou et Elvira (en-tête de chaque fichier dans [`tests/fixtures/`](tests/fixtures/)).

---

## 4. Améliorations apportées

| Amélioration | Problème résolu |
| --- | --- |
| Vérificateur `robots.txt` complet | `RobotFileParser` laisse passer des URL interdites |
| Aucune valeur devinée | Fausses données dans les sorties existantes |
| Arrêt propre sur 401/403/429 | Plantage ou insistance après un refus |
| Cache disque 24 h | 5 s par requête : relancer coûte cher |
| Doublons entre sources | La même offre comptée deux fois |
| Description en texte propre | Phrases coupées, HTML encodé, balises restantes |
| Socle commun pour les 3 sites | Code recopié d'un script à l'autre |

### Vérificateur `robots.txt`, devenu optionnel ([`outils.py`](outils.py))
- **Remarque du prof (2026-11-23) :** la vérification de `robots.txt` n'est pas nécessaire. Elle est donc **désactivée par défaut** ; les délais sont fixés par site dans `DELAIS_PAR_SITE` (5 s pour le Guichet-Emplois, la valeur de son `Crawl-delay`, 2 s pour Jobboom et Talent.com). Le `User-Agent` honnête, le cache et l'arrêt sur 401/403/429 restent actifs.
- Elle reste disponible avec l'option `--respecter-robots` (ou `Client(respecter_robots=True)`). Dans ce mode :
- Applique la norme RFC 9309 : groupe qui nomme notre robot, sinon `*` ; **la règle la plus longue gagne** ; jokers `*` et `$` compris.
- Applique le `Crawl-delay` du fichier s'il est plus grand que le délai fixe.
- Lit `robots.txt` avec notre `User-Agent` (`RobotFileParser.read()` se présente comme « Python-urllib »).
- Preuve : un test montre que `RobotFileParser` autorise `?filter-salary_min=` chez CareerBeacon alors que c'est interdit.

### Aucune valeur devinée ([`modele.py`](modele.py))
- Un champ absent reste `None` : pas de ville, de province ou de type de poste par défaut.
- `est_stage` vaut `True` ou `None`, jamais `False` sans preuve.
- Aucun identifiant fabriqué : une URL sans numéro est ignorée.
- La modalité vient seulement d'un champ structuré, pas du texte libre.

### Arrêt propre et cache ([`outils.py`](outils.py))
- Refus (401, 403 avec détection de Cloudflare, 429 avec `Retry-After`, et `robots.txt` avec `--respecter-robots`) → message clair, **aucun contournement** ; les offres déjà lues sont gardées et les autres sources continuent.
- Une page lue depuis moins de 24 h est reprise du cache : aucune requête, aucune attente.

### Doublons entre sources ([`regroupement.py`](regroupement.py))
- Même `id`, ou même titre + entreprise + ville (sans accents, majuscules, « inc. », « City »).
- Fusion seulement entre **diffuseurs différents** : une offre Talent.com reprise par le Guichet est fusionnée avec l'originale ; deux postes Jobboom identiques aux numéros différents restent séparés.
- L'offre la plus complète est gardée ; seuls ses champs vides sont comblés ; les `id` fusionnés sont listés dans `doublons`.

### Description en texte propre ([`scrapers/commun.py`](scrapers/commun.py))
- Une ligne par paragraphe ou puce ; `<strong>` et `<a>` ne coupent plus les phrases (bug trouvé en testant les fixtures d'Elvira).
- HTML encodé deux fois (`&lt;p&gt;`) relu correctement.

### Compétences et statut de stage ([`competences.py`](competences.py))
- Motifs « sans faux positifs » repris de Hugo et du prof, statut de stage à 3 valeurs repris du prof.
- Deux faux positifs hérités corrigés : « Node.js » comptait aussi pour JavaScript (à cause de « .js »), et le mot « node » seul donnait Node.js.
- « agile » seul (adjectif) n'est plus pris pour la méthode Agile ; ajouts utiles au support TI (Windows, Active Directory, Microsoft 365, TCP/IP).
- Sur les 44 vraies offres : compétences repérées dans **10 offres sur les 14 qui ont une description** (Windows 6, Microsoft 365 4, Linux 3, SQL 3…), et **1 stage possible** trouvé dans la description (`tc-634537925073176368`, « Statut : Stage rémunéré ») que le titre ne montrait pas.

### Format commun de la classe ([`../format-commun/convertir.py`](../format-commun/convertir.py))
- Convertit `offres_unifiees.json` vers le modèle `JobOffer` du prof (18 champs), comme Kandet et Ferdinand.
- Aucune valeur devinée : « Non spécifié » au lieu de « QC », « Canada » ou « Temps plein » par défaut ; `pays` = Canada seulement si la province est connue.
- Les 44 offres sont **validées par le vrai modèle `JobOffer`** du prof (test avec `pydantic`).

---

## 5. Commandes pour reproduire

Depuis la racine du dépôt (Python 3.12+) :

```powershell
pip install -r equipe/dan/livrable3/requirements.txt

# Tests hors ligne (aucun appel réseau)
python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py" -v

# Collecte réelle des 3 sites (depuis le dossier du livrable)
cd equipe/dan/livrable3
python main.py --pages 1 --fiches 5 --csv

# Conversion au format commun JobOffer
cd ../format-commun
python convertir.py --csv --echantillon 5
python -m unittest test_convertir -v
```

Chaque site peut aussi être lancé seul (`python -m scrapers.guichet_emplois`, `scrapers.jobboom`, `scrapers.talent`). Toutes les options sont décrites dans le [README](../README.md#scripts-python).

---

## 6. Vérification

### 6.1 Tests hors ligne : 137 tests réussis (127 dans `livrable3/`, 10 dans `format-commun/`)

| Fichier | Tests | Ce qui est vérifié |
| --- | :-: | --- |
| [`test_outils.py`](tests/test_outils.py) | 31 | Délais fixes par site, refus, cache ; `robots.txt` en option (vrai fichier de CareerBeacon) |
| [`test_modele.py`](tests/test_modele.py) | 4 | Exports JSON et CSV pour Excel |
| [`test_guichet_emplois.py`](tests/test_guichet_emplois.py) | 23 | Liste, pagination, fiches RDFa, repli DOM |
| [`test_jobboom.py`](tests/test_jobboom.py) | 20 | Commandites, JSON-LD, salaire, texte |
| [`test_talent.py`](tests/test_talent.py) | 16 | `ItemList`, porte d'entrée (403 par défaut, `robots.txt` en option) |
| [`test_regroupement.py`](tests/test_regroupement.py) | 21 | Doublons, fusion, `main.py`, test de bout en bout |
| [`test_competences.py`](tests/test_competences.py) | 12 | Compétences, faux positifs évités, statut de stage |
| [`../format-commun/test_convertir.py`](../format-commun/test_convertir.py) | 10 | Correspondance des 18 champs, rien de deviné, validation par `JobOffer` |

### 6.2 Vérification croisée sur les fixtures de l'équipe
Mes scrapers ont lu, **sans adaptation**, les pages d'exemple écrites par d'autres :
- **Kandet** (Guichet-Emplois) : 3 offres, sites d'origine, salaires, modalité, stage et 2 fiches lus correctement.
- **Elvira** et **Gregory** (Jobboom) : listes et fiches lues correctement (GPS, salaire, type de poste).
- **Mamadou** (Talent.com) : fiche lue correctement (GPS, stage).

### 6.3 Ce que la vérification a corrigé
- Les balises en ligne coupaient les descriptions (« un(e)↵stagiaire en développement Web↵en mode… »).
- En repli sur les liens `<a>`, le titre de l'offre Jobboom était perdu.

### 6.4 Exécution réelle (2026-11-18, `python main.py --pages 1 --fiches 5 --csv`)

Fichiers produits : [`data/`](data/) (`offres_unifiees.json` et `.csv`, plus un fichier par source).

| Source | Offres | Fiches ouvertes | Descriptions | Statut |
| --- | :-: | :-: | :-: | --- |
| Guichet-Emplois | 25 | 5 | 4 | ok (14 offres venant d'un site partenaire) |
| Jobboom | 15 | 5 | 5 | ok |
| Talent.com | 5 | 5 | 5 | ok, aucun refus ; GPS sur les 5 offres |
| **Unifié** | **44** | — | 14 | 45 offres reçues, **1 doublon fusionné** |

**Le doublon :** « technicien/technicienne en informatique », Université du Québec, Québec. Publié directement (`ge-50746071`) et par le partenaire « Québec emploi » (`ge-50739894`, entreprise écrite « Universite du quebec »). Les deux diffuseurs sont différents, donc l'offre a été fusionnée ; c'est la plus complète qui est gardée.

**Ce que montrent les vraies données :**
- Une fiche du Guichet-Emplois (`ge-50750365`) n'a pas donné de description : ni RDFa, ni `#job-posting-detail`.
- Jobboom : 10 offres sur 15 n'ont ni entreprise ni lieu, parce que ces informations ne sont que dans la fiche et que seules 5 fiches ont été ouvertes (`--fiches 5`).
- Une offre Jobboom date de 2023 (`jb-3132854`, publiée le 2023-10-25) : le site garde des offres anciennes. Un filtre de fraîcheur, comme chez Elvira et Mamadou, serait utile.
- Bug trouvé et corrigé (lot 9) : l'offre `ge-50753589` (« Différentes régions ») avait la province « `, QC` ». La région de la fiche est maintenant nettoyée, et un texte qui n'est pas une province reconnue donne `None`. La correction s'applique à la prochaine collecte.
- À la collecte, `competences` et `est_stage` étaient vides (0/44). Depuis le lot 10, les compétences et le statut de stage sont repérés (voir section 4).

À vérifier :
- [ ] 2 offres par site comparées à la main avec le site.
- [x] 1 doublon signalé, vérifié (ci-dessus).
- [ ] Si le paramètre `p=2` de Talent.com donne de nouvelles offres (non testé : `--pages 1`).

---

## 7. Avant / après

| Critère | L2 (mesuré) | L3 |
| --- | --- | --- |
| Sites | 1 | 3 (+ plan B) |
| Offres | 25 | 44 uniques (25 + 15 + 5, 1 doublon fusionné) |
| Pages lues | 1 | `--pages N`, arrêt au total annoncé |
| Description | Aucune | 14 sur 44 (fiches ouvertes) |
| Champs | 7 | 18 (modèle commun) |
| Dates | Texte (« 16 novembre 2026 ») | ISO (`2026-11-16`) |
| Site d'origine | Non | Oui (`source_partenaire`) |
| GPS | Non | Jobboom, Talent.com |
| Doublons | Non traités | Fusionnés entre sources |
| `robots.txt` | `RobotFileParser` | Non lu par défaut (remarque du prof) ; vérificateur RFC 9309 avec `--respecter-robots` |
| Délai | 5 s écrit dans le code | Fixé par site (5 s Guichet, 2 s Jobboom et Talent.com) |
| Cache | Non | 24 h |
| Compétences | Non | 10 offres sur 14 avec description |
| Format commun `JobOffer` | Non | Oui, 44 offres validées |
| Tests | 0 | 137 hors ligne |

---

## 8. Limites et suites possibles

| Limite | Suite possible |
| --- | --- |
| Offres anciennes (Jobboom, 2023) | Filtre de fraîcheur, comme Elvira et Mamadou |
| Compétences et stages lus seulement dans les fiches ouvertes | Ouvrir plus de fiches (`--fiches`) |
| Sur Jobboom et Talent.com, une offre sans fiche n'a ni entreprise ni ville | Ouvrir plus de fiches ; le cache limite le coût |
| Pagination Talent.com (`p`) non vérifiée | Confirmer sur le site |
| Doublons : titres trop différents entre sites non reconnus | Comparer aussi les coordonnées GPS ou la date |
| Plan B (Remotive) non écrit | Le faire si Talent.com refuse |

---

## 9. Déroulé de la démo (5 minutes)

| Temps | Quoi montrer | Commande ou fichier |
| :-: | --- | --- |
| 0:00 | Le problème : mon L2 (1 site, 25 offres, pas de description) | [`offres_guichetemplois.csv`](../02-preuve-de-concept-scraping/offres_guichetemplois.csv) |
| 0:45 | Le plan par lots et le top 3 | [`plan.md`](plan.md) |
| 1:30 | Les 137 tests, sans Internet | `python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py"` |
| 2:15 | La collecte réelle et son résumé | `python main.py --pages 1 --fiches 5 --csv` |
| 3:30 | Le résultat dans Excel : description, site d'origine, colonne `doublons` | `data/offres_unifiees.csv` |
| 4:15 | La conformité : le test CareerBeacon (`RobotFileParser` se trompe) | `tests/test_outils.py`, `test_robotparser_de_python_se_trompe_sur_le_joker` |
| 4:45 | Limites et suites | Section 8 |

### Conseils pour la démo
- **Lancer `main.py` une première fois avant la démo** : grâce au cache, la relance en direct prend quelques secondes au lieu de plusieurs minutes.
- Si le réseau de la classe bloque : les tests et le CSV déjà produit suffisent pour la démonstration.
- Phrase à retenir : *« Ce qui compte, c'est la réponse du serveur : s'il refuse (403, 429), on s'arrête. robots.txt reste disponible en option. »*
