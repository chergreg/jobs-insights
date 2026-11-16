# Sites d'offres d'emploi et de stage

> Profil visé : étudiants du DEC en informatique (Collège O'Sullivan de Québec) qui cherchent
> des **stages et des postes TI en début de carrière au Québec**.
> Dernière mise à jour : 2026-11-16

**Légende :** ✅ = vérifié · 🔍 = à confirmer

## Résumé

| Site | Méthode | Résultat |
| --- | --- | --- |
| Guichet-Emplois | HTML (sélecteurs CSS) | POC fonctionnel |
| CareerBeacon | HTML | Bloqué (403, Cloudflare) |

---

## 1. Guichet-Emplois (Job Bank)

- **URL de recherche :** https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois
- **Type :** site national d'emploi du gouvernement du Canada, gratuit, sans compte pour chercher ✅
- **Script :** [`poc_guichetemplois.py`](../02-preuve-de-concept-scraping/poc_guichetemplois.py)

### Pourquoi ce site

- Couvre tout le Québec, avec un filtre par province et par code de profession (CNP) ✅.
- Reprend aussi des offres de sites partenaires (Jobillico, Talent.com, CareerBeacon…) ✅.
- Les offres publiées directement viennent d'employeurs vérifiés ✅.

### Paramètres d'URL

| Paramètre | Rôle | Exemple |
| --- | --- | --- |
| `searchstring` | Mot-clé | `developpeur` ✅ |
| `fprov` | Province | `QC` ✅ |
| `fn21` | Code CNP 2021 (répétable) | `21232` ✅ |
| `sort` | Tri | `D` = date ✅ |
| `page` | Page de résultats | `2` ✅ |
| `fsrc` | Source de l'offre | `16` 🔍 |

Codes CNP TI utilisés : 21211, 21220 à 21223, 21230 à 21234, 21311, 22220 à 22222 (liste de Kandet).

### Sélecteurs de la page de résultats ✅

| Champ | Sélecteur |
| --- | --- |
| Bloc d'une offre | `article[id^='article-']` |
| Lien | `a.resultJobItem` |
| Titre | `.noctitle` |
| Employeur | `.business` |
| Lieu | `.location` |
| Date | `.date` |
| Salaire | `.salary` |
| Site d'origine | `.job-source .wb-inv` |

Sources : POC de Kandet (vérifiés sur le site) et POC de Hugo.

### Formes d'URL

- Fiche d'une offre : `/rechercheemplois/offredemploi/<numéro>` ✅
- Le lien contient un identifiant de session (`;jsessionid=…`) à retirer ✅

### Règles

- `robots.txt` : `Crawl-delay: 5` → au moins **5 s** entre deux requêtes ✅
- `User-Agent` honnête qui identifie le projet.
- Alternative sans scraping : les **Alertes-Emplois** (courriel jusqu'à deux fois par jour) ✅.

---

## 2. CareerBeacon

- **URL :** https://www.careerbeacon.com (offres surtout dans les provinces de l'Atlantique)
- **Résultat :** non utilisable pour la collecte automatique.

### robots.txt (lu le 2026-11-16) ✅

- Permis : recherche (`/fr/rechercher/…`) et fiches (`/en/job/…`, `/fr/emplois/…`).
- Interdit : `/jobs/`, `/rss/`, `/feed/`, `/en/apply`, URL avec un filtre de salaire (`/*filter-salary_min=`)…

### Test du POC (2026-11-16) ✅

- `robots.txt` lu (code 200), mais la page de recherche répond **403 Forbidden**.
- Protection identifiée : **Cloudflare** (anti-robot).
- Décision : arrêt, **aucun contournement** (pas de faux navigateur).
- Ses offres apparaissent en partie sur le Guichet-Emplois (« Source : CareerBeacon ») ✅.

> **Leçon :** `robots.txt` dit ce qui est *permis*, mais le serveur peut quand même *refuser*. Un robot responsable respecte les deux.
>
> **Piège Python :** `urllib.robotparser` ne comprend pas les `*` dans les règles (ex. `/*filter-salary_min=`). Avec `read()`, il se présente comme « Python-urllib » ; si le serveur refuse, il conclut que tout est interdit.

---

## Prochains sites à explorer (Québec)

Repris de l'[inventaire commun](../../../livrables/01-inventaire-des-sites/inventaire.md) :

- Jobboom et Jobillico (JSON-LD `JobPosting`, après vérification de `robots.txt`)
- Talent.com Canada
- Adzuna Canada (API officielle gratuite)
- Carrières Gouv. du Québec (stages de la fonction publique)
