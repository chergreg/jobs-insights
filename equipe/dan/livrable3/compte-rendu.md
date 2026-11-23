# Livrable 3 — Reprendre et améliorer une preuve de concept (Dan)

> **Cours :** 420-SV2-OQ, Collège O'Sullivan de Québec — projet `jobs-insights`
> **Cible :** stages et postes TI en début de carrière au Québec
> **Code :** [`equipe/dan/livrable3/`](.) · **Plan par lots :** [`plan.md`](plan.md) · **Commit :** _lien à ajouter après publication sur GitHub_

En bref : mon POC du livrable 2 lisait **1 page d'un seul site** (25 offres, sans description). Au livrable 3, j'ai réutilisé le meilleur de l'équipe pour collecter **3 sites**, ouvrir les **fiches** des offres, retirer les **doublons** entre sources et respecter **réellement** les règles des sites. Le tout est vérifié par **107 tests hors ligne**. L'exécution réelle reste à faire (section 6.4).

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

### Vérificateur `robots.txt` ([`outils.py`](outils.py))
- Applique la norme RFC 9309 : groupe qui nomme notre robot, sinon `*` ; **la règle la plus longue gagne** ; jokers `*` et `$` compris.
- Lit le `Crawl-delay` dans le fichier (5 s sur le Guichet-Emplois) au lieu de l'écrire dans le code.
- Lit `robots.txt` avec notre `User-Agent` (`RobotFileParser.read()` se présente comme « Python-urllib »).
- Preuve : un test montre que `RobotFileParser` autorise `?filter-salary_min=` chez CareerBeacon alors que c'est interdit.

### Aucune valeur devinée ([`modele.py`](modele.py))
- Un champ absent reste `None` : pas de ville, de province ou de type de poste par défaut.
- `est_stage` vaut `True` ou `None`, jamais `False` sans preuve.
- Aucun identifiant fabriqué : une URL sans numéro est ignorée.
- La modalité vient seulement d'un champ structuré, pas du texte libre.

### Arrêt propre et cache ([`outils.py`](outils.py))
- Refus (`robots.txt`, 401, 403 avec détection de Cloudflare, 429 avec `Retry-After`) → message clair, **aucun contournement** ; les offres déjà lues sont gardées et les autres sources continuent.
- Une page lue depuis moins de 24 h est reprise du cache : aucune requête, aucune attente.

### Doublons entre sources ([`regroupement.py`](regroupement.py))
- Même `id`, ou même titre + entreprise + ville (sans accents, majuscules, « inc. », « City »).
- Fusion seulement entre **diffuseurs différents** : une offre Talent.com reprise par le Guichet est fusionnée avec l'originale ; deux postes Jobboom identiques aux numéros différents restent séparés.
- L'offre la plus complète est gardée ; seuls ses champs vides sont comblés ; les `id` fusionnés sont listés dans `doublons`.

### Description en texte propre ([`scrapers/commun.py`](scrapers/commun.py))
- Une ligne par paragraphe ou puce ; `<strong>` et `<a>` ne coupent plus les phrases (bug trouvé en testant les fixtures d'Elvira).
- HTML encodé deux fois (`&lt;p&gt;`) relu correctement.

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
```

Chaque site peut aussi être lancé seul (`python -m scrapers.guichet_emplois`, `scrapers.jobboom`, `scrapers.talent`). Toutes les options sont décrites dans le [README](../README.md#scripts-python).

---

## 6. Vérification

### 6.1 Tests hors ligne : 107 tests réussis (0,12 s)

| Fichier | Tests | Ce qui est vérifié |
| --- | :-: | --- |
| [`test_outils.py`](tests/test_outils.py) | 26 | `robots.txt` (vrai fichier de CareerBeacon), délais, refus, cache |
| [`test_modele.py`](tests/test_modele.py) | 4 | Exports JSON et CSV pour Excel |
| [`test_guichet_emplois.py`](tests/test_guichet_emplois.py) | 22 | Liste, pagination, fiches RDFa, repli DOM |
| [`test_jobboom.py`](tests/test_jobboom.py) | 20 | Commandites, JSON-LD, salaire, texte |
| [`test_talent.py`](tests/test_talent.py) | 15 | `ItemList`, porte d'entrée `robots.txt` |
| [`test_regroupement.py`](tests/test_regroupement.py) | 20 | Doublons, fusion, `main.py`, test de bout en bout |

### 6.2 Vérification croisée sur les fixtures de l'équipe
Mes scrapers ont lu, **sans adaptation**, les pages d'exemple écrites par d'autres :
- **Kandet** (Guichet-Emplois) : 3 offres, sites d'origine, salaires, modalité, stage et 2 fiches lus correctement.
- **Elvira** et **Gregory** (Jobboom) : listes et fiches lues correctement (GPS, salaire, type de poste).
- **Mamadou** (Talent.com) : fiche lue correctement (GPS, stage).

### 6.3 Ce que la vérification a corrigé
- Les balises en ligne coupaient les descriptions (« un(e)↵stagiaire en développement Web↵en mode… »).
- En repli sur les liens `<a>`, le titre de l'offre Jobboom était perdu.

### 6.4 Exécution réelle : _à compléter_

_Je n'ai pas encore lancé la collecte réelle. Après `python main.py --pages 1 --fiches 5 --csv`, coller ici le résumé affiché :_

| Source | Offres | Descriptions | Statut |
| --- | :-: | :-: | --- |
| Guichet-Emplois | _à compléter_ | _à compléter_ | _à compléter_ |
| Jobboom | _à compléter_ | _à compléter_ | _à compléter_ |
| Talent.com | _à compléter_ | _à compléter_ | _à compléter_ |
| **Unifié** | _à compléter_ | — | _doublons fusionnés : à compléter_ |

À vérifier en même temps :
- [ ] 2 offres par site comparées à la main avec le site.
- [ ] 1 doublon signalé (« doublon : … = … ») vérifié sur les deux sites.
- [ ] Ce que disent les `robots.txt` de Jobboom et de Talent.com.
- [ ] Si le paramètre `p=2` de Talent.com donne de nouvelles offres.

---

## 7. Avant / après

| Critère | L2 (mesuré) | L3 |
| --- | --- | --- |
| Sites | 1 | 3 (+ plan B) |
| Offres | 25 | _à compléter_ (6.4) |
| Pages lues | 1 | `--pages N`, arrêt au total annoncé |
| Description | Aucune | Oui, pour les fiches ouvertes |
| Champs | 7 | 18 (modèle commun) |
| Dates | Texte (« 16 novembre 2026 ») | ISO (`2026-11-16`) |
| Site d'origine | Non | Oui (`source_partenaire`) |
| GPS | Non | Jobboom, Talent.com |
| Doublons | Non traités | Fusionnés entre sources |
| `robots.txt` | `RobotFileParser` | Vérificateur RFC 9309 |
| Délai | 5 s écrit dans le code | Lu dans `robots.txt` (min. 2 s) |
| Cache | Non | 24 h |
| Tests | 0 | 107 hors ligne |

---

## 8. Limites et suites possibles

| Limite | Suite possible |
| --- | --- |
| Exécution réelle pas encore faite | Lancer `main.py`, compléter 6.4 |
| `est_stage` ne lit pas la description | Règle ciblée (« Statut : stage »), sans faux positifs |
| Sur Jobboom et Talent.com, une offre sans fiche n'a ni entreprise ni ville | Ouvrir plus de fiches ; le cache limite le coût |
| Pagination Talent.com (`p`) non vérifiée | Confirmer sur le site |
| Doublons : titres trop différents entre sites non reconnus | Comparer aussi les coordonnées GPS ou la date |
| Plan B (Remotive) non écrit | Le faire si Talent.com refuse |
| `competences` toujours vide | Reprendre la détection sans faux positifs de Hugo |

---

## 9. Déroulé de la démo (5 minutes)

| Temps | Quoi montrer | Commande ou fichier |
| :-: | --- | --- |
| 0:00 | Le problème : mon L2 (1 site, 25 offres, pas de description) | [`offres_guichetemplois.csv`](../02-preuve-de-concept-scraping/offres_guichetemplois.csv) |
| 0:45 | Le plan par lots et le top 3 | [`plan.md`](plan.md) |
| 1:30 | Les 107 tests, sans Internet | `python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py"` |
| 2:15 | La collecte réelle et son résumé | `python main.py --pages 1 --fiches 5 --csv` |
| 3:30 | Le résultat dans Excel : description, site d'origine, colonne `doublons` | `data/offres_unifiees.csv` |
| 4:15 | La conformité : le test CareerBeacon (`RobotFileParser` se trompe) | `tests/test_outils.py`, `test_robotparser_de_python_se_trompe_sur_le_joker` |
| 4:45 | Limites et suites | Section 8 |

### Conseils pour la démo
- **Lancer `main.py` une première fois avant la démo** : grâce au cache, la relance en direct prend quelques secondes au lieu de plusieurs minutes.
- Si le réseau de la classe bloque : les tests et le CSV déjà produit suffisent pour la démonstration.
- Phrase à retenir : *« robots.txt dit ce qui est permis, le serveur peut quand même refuser : un robot responsable respecte les deux. »*
