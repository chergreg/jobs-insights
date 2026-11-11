# Synthèse — Livrable 1 : Inventaire des sites

Bilan établi après lecture des remises déposées par l’équipe (voir le référentiel consolidé dans [`inventaire.md`](inventaire.md)).

---

## 1. Tableau synthèse des remises

Sur les **11 étudiants** inscrits dans [`equipe/equipe.md`](../../equipe/equipe.md) (7 remises complètes, 2 partielles, 2 non faites) :

| Étudiant | Statut | Volume recensé | Remise |
| --- | --- | --- | --- |
| **Rayan** | ✅ Fait | 4 retenues (dont 4 ATS), 1 à vérifier, 10 exclues | [`sites.md`](../../equipe/rayan/01-inventaire-des-sites/sites.md) |
| **Kandet** | ✅ Fait | 7 entrées (8 liens) | [`sites.md`](../../equipe/kandet/01-inventaire-des-sites/sites.md) |
| **Mamadou** | ✅ Fait | 7 entrées (8 sites) | [`sites.md`](../../equipe/mamadou/01-inventaire-des-sites/sites.md) |
| **Elvira** | ✅ Fait | 8 sites | [`sites.md`](../../equipe/elvira/01-inventaire-des-sites/sites.md) |
| **Hugo** | ✅ Fait | 10 manuels + 20 pistes IA | [`sites.md`](../../equipe/hugo/01-inventaire-des-sites/sites.md) |
| **Aymerou** | ✅ Fait | 3 sites | [`sites.md`](../../equipe/aymerou/01-inventaire-des-sites/sites.md) |
| **Nonga** | ✅ Fait | 4 entrées (3 sources distinctes) | [`sites.md`](../../equipe/nonga/01-inventaire-des-sites/sites.md) |
| **Dan** | ⚠️ Partiel | 1 site détaillé + 6 noms en attente | [`sites.md`](../../equipe/dan/01-inventaire-des-sites/sites.md) |
| **Ferdinand** | ⚠️ Partiel | 1 site | [`sites.md`](../../equipe/ferdinand/01-inventaire-des-sites/sites.md) |
| **Hendrix** | ❌ Non fait | 0 site (cahier des charges) | [`info.md`](../../equipe/hendrix/info.md) |
| **Mike** | ❌ Non fait | 0 site (aucun dossier) | — |

Toutes les remises du Livrable 1 ont été normalisées sous `equipe/<membre>/01-inventaire-des-sites/sites.md` (voir [`enonce.md`](enonce.md)).

---

## 2. Fiches par remise

### Rayan (`✅ Fait`)
- **Couverture :** Québec / Canada (sources généralistes, APIs, données ouvertes et ATS).
- **Points forts :** Classement rigoureux (*Retenu / À vérifier / Exclu* avec motifs juridiques et techniques). Seul à documenter les **APIs officielles** (Adzuna, Jooble, Données ouvertes Canada) et les **pages carrières / ATS d’entreprises** (Workday, Greenhouse, Lever, Ashby).
- **À noter :** Seule remise à avoir respecté d’emblée le nom de fichier singulier demandé initialement (`site.md`).

### Kandet (`✅ Fait`)
- **Couverture :** Québec, Canada et télétravail tech (7 entrées).
- **Points forts :** Vérification réelle des `robots.txt` (délai de 5 s sur Guichet-Emplois, restrictions sur Jobillico, interdiction sur LinkedIn), observation concrète d’un `HTTP 403` sur Indeed, analyse précise des filtres et paramètres du flux Atom et de l’API Remotive.
- **À noter :** Recommande explicitement la consultation manuelle pour les sites restrictifs.

### Mamadou (`✅ Fait`)
- **Couverture :** Québec / Canada et télétravail tech (7 entrées couvrant 8 sites).
- **Points forts :** Repérage technique très précis des paramètres GET, des catégories TI (`_i10lfr` sur Jobboom), des filtres stages (`fsrc=16` sur Guichet-Emplois) et des métadonnées structurées (RDFa, JSON-LD `JobPosting` / `ItemList`).
- **À noter :** Distingue bien les sources accessibles en HTTP standard des plateformes bloquées (Québec emploi en SPA, Indeed/LinkedIn protégés).

### Elvira (`✅ Fait`)
- **Couverture :** Québec / TI et développement web (8 sites).
- **Points forts :** Apporte des sources québécoises originales absentes des autres remises (**KebekJobs**, **MonTravail.ca**, **RIMQ** pour les emplois municipaux) et une analyse détaillée de Jobboom.
- **À noter :** Caractères Markdown échappés (`\#`, `\*`, `\-`) dans le fichier ; signale la protection Cloudflare d’Indeed.

### Hugo (`✅ Fait`)
- **Couverture :** Canada et international (10 sites recherchés à la main + 20 pistes générées par IA, avec quelques recoupements).
- **Points forts :** Inventaire le plus large en volume, ouvrant sur de nombreuses APIs gratuites et sources spécialisées.
- **Points de vigilance :** Pistes issues de l’IA à vérifier manuellement selon l’énoncé ; lien erroné sur `CarrerBuilder` (copie du lien Talent.com) ; inclut des sites bloqués sans tri de conformité.

### Aymerou (`✅ Fait`)
- **Couverture :** Québec (3 sites : Indeed, Jobillico, Québec emploi).
- **Points forts :** Chaque site est appuyé par une recherche concrète et un exemple d’offre vérifiée (titre, entreprise, ville, champs à extraire).
- **Points de vigilance :** Liste courte et orientée vers un premier essai Python sur Indeed (à réorienter vers une source autorisée).

### Nonga (`✅ Fait`)
- **Couverture :** Canada (Guichet-Emplois / Job Bank, Indeed Canada, LinkedIn Jobs).
- **Points forts :** Note justement que Job Bank et Guichet-Emplois sont les versions anglaise et française d’une même source ; prévoit la vérification des `robots.txt` et conditions d’utilisation.
- **Points de vigilance :** Inventaire limité à 3 sources distinctes, dont 2 sont interdites au scraping.

### Dan (`⚠️ Partiel`)
- **Couverture :** Guichet-Emplois uniquement, ciblé sur **Moncton / Nouveau-Brunswick** (Université de Moncton), avec 6 noms simplement listés en attente sans liens.
- **Points forts :** Analyse détaillée des filtres, URLs et règles (`time.sleep(2)`, `robots.txt` à lire).
- **Points de vigilance :** Contient des cases non vérifiées (`🔍`), est hors cible géographique Québec, et laisse un conflit Git non résolu dans [`equipe/dan/README.md`](../../equipe/dan/README.md).

### Ferdinand (`⚠️ Partiel`)
- **Couverture :** Welcome to the Jungle uniquement.
- **Points forts :** Repérage de l’API JSON (Algolia) derrière le rendu JavaScript.
- **Points de vigilance :** Inventaire limité à une seule plateforme plutôt européenne ; deux lignes de modèle restent non tranchées (`oui / non`, `facile / moyenne / difficile`).

### Hendrix & Mike (`❌ Non fait`)
- **Hendrix :** [`equipe/hendrix/info.md`](../../equipe/hendrix/info.md) (ex-`Sites.md`) contient un cahier des charges complet (429 lignes) et aucune liste de sites.
- **Mike :** Aucun dossier ni commit dans le dépôt.

---

## 3. Constats transversaux

- **Socle commun identifié :** **Guichet-Emplois / Job Bank** (7/9), **Indeed** (7/9), **Jobillico** (6/9), **Québec emploi** (5/9, ou 6/9 avec **Québec.ca**), **LinkedIn** (5/9), **Jobboom** (3/9), **Remotive** (3/9) et **Talent.com** (2/9).
- **Formats structurés déjà repérés :** flux Atom/RSS (Guichet-Emplois), JSON-LD `JobPosting` (Jobboom, Jobillico, Talent.com), RDFa (Guichet-Emplois), APIs JSON (Remotive, Adzuna, Jooble, Algolia sur WTTJ) et données ouvertes CSV (Canada ouvert).
- **Maturité inégale sur la conformité :** Rayan, Kandet et Mamadou écartent explicitement les sites protégés ou interdits, alors que d’autres envisagent encore de scraper Indeed ou LinkedIn.
- **Doublons inter-sources :** Dan et Rayan constatent que Guichet-Emplois reprend des offres de sites partenaires (dont Jobillico), ce qui rend la déduplication indispensable dès les essais multi-sources.

---

## 4. Sources à explorer et décisions pour la suite

### Sources à prioriser
1. **Socle officiel et APIs (Priorité 1) :**
   - **Guichet-Emplois / Job Bank** (flux Atom/RSS, RDFa/JSON-LD avec délai de 5 s, et CSV Données ouvertes Canada pour les statistiques).
   - **Adzuna** et **Jooble** (tester la couverture réelle au Québec et sur les stages TI avec clés API gratuites).
   - **Pages carrières via ATS** (Greenhouse, Lever, Ashby, Workday) en constituant une liste d’entreprises TI cibles au Québec et au Canada.
2. **Portails québécois structurés (Priorité 2 — après vérification `robots.txt` / CGU) :**
   - **Jobboom**, **Jobillico** (vérifier les restrictions de pagination/recherche) et **Talent.com Canada** pour leurs balises JSON-LD `JobPosting`.
   - **Carrières Gouv. du Québec (`carrieres.gouv.qc.ca`)** pour les stages de la fonction publique, distinct de `quebecemploi.gouv.qc.ca`.
3. **Compléments à évaluer (Priorité 3) :**
   - **Remotive** (API JSON publique, télétravail tech) si le périmètre inclut le télétravail accessible depuis le Canada.
   - **KebekJobs**, **MonTravail.ca**, **RIMQ**, **Welcome to the Jungle** et pistes canadiennes issues de l’IA (Eluta, WowJobs, CharityVillage) après vérification manuelle.

### Décisions structurantes
- **Périmètre cible :** prioriser les **stages et postes TI début de carrière au Québec**, avec ouverture possible au Canada et au télétravail accessible depuis le Canada.
- **Exclusion stricte :** **Indeed**, **LinkedIn**, **Glassdoor** et **Québec emploi** (`quebecemploi.gouv.qc.ca`) restent **exclus de toute collecte automatisée** (consultation manuelle uniquement ; aucun contournement).
- **Ordre de préférence technique (Livrable 2) :** (1) APIs officielles / données ouvertes, (2) flux RSS/Atom, (3) HTML avec JSON-LD ou RDFa, plutôt que le parsing fragile de sélecteurs CSS ou de SPA.
- **Normalisation et déduplication :** prévoir dès la mise en commun du Livrable 2 un schéma uniforme conservant la source, l’identifiant externe et laissant vides (`None`) les champs absents.
- **Suivi de l’équipe :** relancer **Mike** et **Hendrix** pour le Livrable 1 ; inviter **Dan** (recentrage Québec/Canada), **Ferdinand** (ajout de sources locales) et **Aymerou** (abandon d’Indeed pour son POC) à ajuster leur choix pour le Livrable 2.
