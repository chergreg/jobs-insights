# Synthèse — Livrable 1 : Inventaire des sites

Bilan établi après lecture des remises déposées par l’équipe (voir la liste consolidée des sources dans [`inventaire.md`](inventaire.md)).

---

## 1. État des remises

Sur les **11 étudiants** inscrits dans [`equipe/equipe.md`](../../equipe/equipe.md) :

| Statut | Nb | Étudiants | Observations principales |
| --- | :-: | --- | --- |
| **Fait (multi-sites)** | 7 | Rayan, Kandet, Mamadou, Elvira, Hugo, Aymerou, Nonga | Inventaires exploitables allant de 3 à ~27 sources distinctes, avec niveaux d’analyse variés. |
| **Partiel (1 site)** | 2 | Dan, Ferdinand | Dan ne documente que Guichet-Emplois (ciblé Moncton / N.-B.) ; Ferdinand ne documente que Welcome to the Jungle. |
| **Non fait** | 2 | Hendrix, Mike | Hendrix a déposé un cahier des charges (`info.md`, ex-`Sites.md`) sans liste de sites ; Mike n’a ni dossier ni contribution. |

Toutes les remises du Livrable 1 ont été normalisées sous `equipe/<membre>/01-inventaire-des-sites/sites.md` (voir [`enonce.md`](enonce.md)).

---

## 2. Constats après lecture des remises

### Convergence sur un socle québécois et canadien
- Les plateformes les plus fréquemment identifiées sont **Guichet-Emplois / Job Bank** (7 remises sur 9), **Indeed** (7/9), **Jobillico** (6/9), **Québec emploi** (5/9, ou 6/9 en incluant le portail **Québec.ca** cité par Elvira), **LinkedIn** (5/9), **Jobboom** (3/9), **Remotive** (3/9) et **Talent.com** (2/9).
- Plusieurs étudiants ont déjà repéré des formats d’extraction fiables sans scraping HTML fragile : **flux Atom/RSS** (Guichet-Emplois), **JSON-LD `JobPosting`** (Jobboom, Jobillico, Talent.com), **RDFa** (Guichet-Emplois), **API JSON publiques** (Remotive, Adzuna, Jooble, Algolia sur WTTJ) et **données ouvertes CSV** (Canada ouvert).

### Complémentarité des apports individuels
- **Conformité et APIs :** **Rayan** propose le tri le plus rigoureux (*Retenu / À vérifier / Exclu*) et est le seul à couvrir les **API officielles** (Adzuna, Jooble, Données ouvertes Canada) ainsi que les **pages carrières / ATS d’entreprises** (Workday, Greenhouse, Lever, Ashby), comme suggéré dans l’énoncé.
- **Vérification technique :** **Kandet** et **Mamadou** combinent l’analyse des filtres URL, la vérification des `robots.txt` / codes HTTP et le repérage précis des structures de données.
- **Sources locales originales :** **Elvira** apporte des plateformes québécoises moins connues (**KebekJobs**, **MonTravail.ca**, **RIMQ** pour les municipalités) et une analyse détaillée de Jobboom.
- **Ouverture à vérifier :** **Hugo** fournit la liste la plus large (10 recherches manuelles + 20 pistes générées par IA au Canada et à l’international), mais plusieurs entrées issues de l’IA restent à vérifier en ouvrant réellement les sites (ex. erreur de lien sur `CarrerBuilder`, couverture réelle d’Eluta/WowJobs/WorkBC).

### Points de vigilance relevés
- **Conformité juridique et anti-bot :** Si Rayan, Kandet et Mamadou écartent explicitement **Indeed**, **LinkedIn**, **Glassdoor** et **Québec emploi** de la collecte automatisée (conditions d’utilisation restrictives, `robots.txt`, Cloudflare / HTTP 403), d’autres remises listent encore ces sites comme cibles de scraping (Aymerou prévoit même de commencer son prototype sur Indeed).
- **Recoupement entre sources :** Dan et Rayan soulignent que **Guichet-Emplois** republie des annonces provenant de sites partenaires (dont **Jobillico**), ce qui imposera une stratégie de déduplication dès les premiers prototypes multi-sources.
- **Qualité formelle et alignement :**
  - Quelques traces de brouillon ou de modèle subsistent (conflit Git dans [`equipe/dan/README.md`](../../equipe/dan/README.md), caractères Markdown échappés dans [`equipe/elvira/01-inventaire-des-sites/sites.md`](../../equipe/elvira/01-inventaire-des-sites/sites.md), champs `oui / non` ou `🔍` non tranchés chez Ferdinand et Dan).
  - La remise de **Dan** cible le Nouveau-Brunswick (Université de Moncton) plutôt que le Québec, et celles de **Hugo** / **Ferdinand** incluent des sources internationales. Le périmètre géographique commun doit donc être fixé clairement.

---

## 3. Sources à explorer pour la suite

1. **Priorité 1 — Socle officiel et structuré (Québec / Canada) :**
   - **Guichet-Emplois / Job Bank** : flux Atom/RSS et fiches RDFa/JSON-LD (avec délai de 5 s par requête selon `robots.txt`), complétés au besoin par les jeux CSV mensuels de **Données ouvertes Canada** pour des analyses de volume.
   - **APIs gratuites avec clé (Adzuna, Jooble)** : tester la qualité et la couverture réelle des offres TI et stages au Québec.
   - **Pages carrières d’employeurs via ATS (Greenhouse, Lever, Ashby, Workday)** : constituer une première liste d’employeurs TI du Québec/Canada publiant des stages et postes juniors.
2. **Priorité 2 — Portails québécois avec métadonnées structurées :**
   - **Jobboom**, **Jobillico** et **Talent.com Canada** : vérifier systématiquement leurs `robots.txt` et conditions d’utilisation (notamment les restrictions de recherche/pagination signalées sur Jobillico) avant d’étendre la collecte sur leurs balises JSON-LD `JobPosting`.
   - **Emplois et stages du gouvernement du Québec (`carrieres.gouv.qc.ca`)** : distinguer ce portail de `quebecemploi.gouv.qc.ca` et vérifier s’il existe un flux ou une autorisation d’accès pour les stages de la fonction publique.
3. **Priorité 3 — Compléments à évaluer selon le périmètre :**
   - **Remotive** (API publique, télétravail tech, cache 24 h / max 4 requêtes par jour) si les postes à distance accessibles depuis le Canada sont retenus.
   - **KebekJobs**, **MonTravail.ca**, **RIMQ**, **Welcome to the Jungle** et les pistes canadiennes de la liste IA (**Eluta.ca**, **WowJobs.ca**, **CharityVillage**) : vérifier manuellement le volume d’offres TI/stages au Québec et les règles d’accès.

---

## 4. Décisions qui orientent la suite

1. **Périmètre cible du projet :** prioriser les **stages et postes TI début de carrière au Québec** (avec ouverture possible aux offres canadiennes et au télétravail accessible depuis le Canada selon la richesse des sources).
2. **Exclusion stricte des sites interdits ou verrouillés :** **Indeed**, **LinkedIn**, **Glassdoor** et **Québec emploi** (`quebecemploi.gouv.qc.ca`) restent **exclus de toute collecte automatisée** (consultation manuelle uniquement). Aucun contournement technique ne sera tenté.
3. **Hiérarchie des méthodes de collecte (Livrable 2) :** privilégier dans l’ordre (1) APIs officielles et données ouvertes, (2) flux RSS/Atom, (3) HTML avec JSON-LD `JobPosting` ou RDFa, plutôt que le parsing fragile de sélecteurs CSS ou de pages SPA.
4. **Préparation de l’étape de normalisation et déduplication :** concevoir un modèle commun d’offre dès le passage en commun des prototypes du Livrable 2 (champs absents laissés vides / `None`, conservation de la source et de l’identifiant d’origine pour repérer les reprises entre agrégateurs).
5. **Suivi des remises :**
   - Demander à **Mike** et **Hendrix** de déposer leur inventaire sous `equipe/<nom>/01-inventaire-des-sites/sites.md`.
   - Inviter **Dan** (recentrage Québec/Canada), **Ferdinand** (ajout d’autres sources locales) et **Aymerou** (abandon d’Indeed au profit d’une source autorisée pour son POC) à ajuster leur sélection pour le Livrable 2.
