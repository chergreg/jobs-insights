# Compte rendu — Livrable 2 : preuve de concept de scraping

**Kandet** — dernière mise à jour le 12 novembre 2026

## 1. Sites et pages testés

| Source | Page ou URL utilisée | Rôle |
|---|---|---|
| Guichet-Emplois | `https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois` | Source principale |
| Remotive | `https://remotive.com/api/remote-jobs` | Source secondaire (télétravail) |

Pour le Guichet-Emplois, je cherche les offres du Québec (`fprov=QC`) dans 14 codes CNP du domaine informatique : développeurs, programmeurs, analystes, soutien technique, réseau, données, cybersécurité, etc. La liste complète des codes est au début du script (`CNP_CODES_TI`).

Exemple de page testée (première page de résultats) :
`https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fn21=21232&fn21=21234&fprov=QC&sort=D`

## 2. Méthode, outils et commande

Le script [`poc_multi_source.py`](poc_multi_source.py) utilise seulement la bibliothèque standard de Python 3.12+, sans `pip install` :

- `urllib.request` pour les requêtes HTTP ;
- `html.parser` pour lire la page de résultats ;
- `json` pour l'API Remotive et pour le fichier de sortie ;
- `dataclasses` pour le modèle commun (`SourceRecord`, puis `AggregatedOffer` après déduplication).

**Guichet-Emplois, comment ça marche :**

1. Le script demande la page 1 de la recherche, puis `page=2`, `page=3`, etc. Chaque page contient 25 offres.
2. Chaque offre est dans une balise `<article id="article-…">`. Je lis les champs selon leur classe CSS : `noctitle` (titre), `business` (employeur), `location`, `salary`, `date`, `telework` (sur place, hybride…) et `source` (numéro d'offre et site d'origine).
3. Les textes cachés pour les lecteurs d'écran (`wb-inv`), comme « Emplacement » ou « Numéro de l'offre », sont ignorés. Seule exception : le nom du site qui a publié l'offre (Jobillico, Talent.com…).
4. Je retire le `;jsessionid=…` des liens pour garder une URL propre vers la fiche.
5. Le script s'arrête quand le nombre d'offres annoncé par le site est atteint, quand une page est vide ou quand une page répète des offres déjà vues. **Il n'y a aucun plafond de pages ni d'offres.**

**Remotive :** un seul appel à l'API, réponse gardée 24 h dans `remotive-cache.json`. Je garde seulement les catégories liées à l'informatique.

**Respect des sites :**

- 5 secondes d'attente entre chaque page, comme le demande le `robots.txt` du Guichet-Emplois (`Crawl-delay: 5`) ;
- `User-Agent` qui identifie le projet ;
- un seul nouvel essai après 30 s si le serveur répond 429 ou 503 ;
- pas plus de 4 appels par jour à Remotive, comme le demande leur API.

**Commandes** (depuis la racine du dépôt) :

```powershell
# Collecte complète : Guichet-Emplois (Québec, codes TI) + Remotive
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py

# Avec un petit fichier d'exemple de 10 offres
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --echantillon .\equipe\kandet\02-preuve-de-concept-scraping\echantillon.json

# Autres options
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --toutes-provinces
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --remotive-canada
python .\equipe\kandet\02-preuve-de-concept-scraping\poc_multi_source.py --sans-remotive --sans-sauvegarde
```

Les résultats vont dans `offres.json`, à côté du script. Ce fichier et le cache Remotive ne sont pas mis dans Git.

**Tests** (33 tests, sans connexion Internet, avec des pages HTML et des réponses JSON fictives) :

```powershell
Set-Location .\equipe\kandet\02-preuve-de-concept-scraping
python -m unittest -v test_poc_multi_source.py
```

Les tests couvrent la lecture d'une page de résultats, la pagination sans plafond, l'arrêt sur page vide ou répétée, le délai de 5 s, le nouvel essai sur HTTP 429, les dates françaises, le cache Remotive, la détection des stages et la déduplication.

## 3. Données récupérées

Essai du **12 novembre 2026** (environ 45 secondes) :

| Résultat | Valeur |
|---|---|
| Offres annoncées par le Guichet-Emplois | 191 |
| Offres récupérées par le script | **191** (8 pages) |
| Offres Remotive gardées | 8 sur 14 dans l'API |
| Offres uniques après déduplication | **198** |
| Offres avec un salaire | 194 |

Le Guichet-Emplois affiche aussi des offres de sites partenaires. Répartition des 191 offres selon le site d'origine :

| Site d'origine | Offres |
|---|---|
| Guichet-Emplois (publiées par l'employeur) | 68 |
| Jobillico | 44 |
| Québec emploi | 38 |
| Talent.com | 19 |
| JobsMedia.ca | 13 |
| CareerBeacon | 5 |
| indeed.com | 3 |
| Jobboom | 1 |

Une même offre (« architecte de solutions - TI », Fop experts conseils, Brossard) était publiée à la fois par Québec emploi et par Jobillico : le script l'a regroupée en une seule offre qui garde les deux liens.

Les 10 premières offres sont dans [`echantillon.json`](echantillon.json). Exemple d'une offre (champs principaux) :

```json
{
  "title": "agent/agente de soutien aux utilisateurs",
  "employer": "GolfIn - Saint-Georges",
  "location": "Saint-Georges (QC)",
  "salary": "52 000,00 $ à 60 000,00 $ par année",
  "published_at": "2026-11-12",
  "stage_status": "not_indicated",
  "source_records": [
    {
      "source": "Guichet-Emplois",
      "source_id": "50711091",
      "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091",
      "origin_site": "Jobillico",
      "source_data": { "job_number": "17086532", "displayed_date": "12 novembre 2026" }
    }
  ]
}
```

**Vérification avec le site.** J'ai ouvert 6 fiches : 4 prises au hasard (toutes publiées directement sur le Guichet-Emplois), plus 1 offre Jobillico et 1 offre Québec emploi. Pour les 6, le titre, l'employeur, la ville et le salaire collectés sont les mêmes que sur la fiche. J'ai aussi vérifié que le total récupéré (191) est égal au nombre de résultats affiché en haut de la page de recherche.

## 4. Difficultés, limites et pistes essayées

**Première version avec le flux Atom (abandonnée).** Au début, j'utilisais le flux Atom du Guichet-Emplois (`/jobsearch/feed/jobSearchRSSfeed`) avec 4 mots-clés. Mon essai du 11 novembre ne donnait qu'**une seule offre** au Québec. En testant, j'ai compris pourquoi :

- le flux ignore le paramètre `rows=100` et renvoie une dizaine d'offres pour tout le Canada, alors je filtrais le Québec après coup ;
- même avec le filtre `fprov=QC` et les 14 codes CNP, le flux donne seulement 12 offres ;
- la page de recherche HTML, avec les mêmes filtres, en annonce 191.

Le flux ne contient que les offres publiées directement sur le Guichet-Emplois, sans celles des partenaires. J'ai donc remplacé le flux par la page de recherche HTML. On passe de 1 à 191 offres pour le Québec.

**Autres limites observées :**

- **Titres CNP.** La liste affiche le titre normalisé de la CNP, pas le titre écrit par l'employeur. Par exemple, une offre Jobillico « Technicien(ne) de service » apparaît comme « agent/agente de soutien aux utilisateurs ». C'est pour ça qu'aucun stage n'est détecté (0 sur 198).
- **Recherche de stages.** J'ai essayé `--terme stage` et `--terme stagiaire` avec les codes CNP. « stage » donne 0 résultat et « stagiaire » renvoie les mêmes 191 offres que sans mot-clé, donc le site ignore ce mot dans cette combinaison. Pour repérer les stages, il faudrait lire chaque fiche (description, lien vers l'annonce d'origine). Avec 5 s par fiche, ça prendrait environ 16 minutes pour 191 offres. Je le garde pour la suite.
- **Pas de description complète.** La page de résultats ne donne ni la description ni les exigences. Le champ `description` reste vide plutôt que d'être inventé.
- **Offres en série.** Une firme de recrutement (Fop experts conseils) publie 42 des 191 offres via Québec emploi, dont 8 fois le même titre. Je ne fusionne pas les offres identiques d'un même site, car rien ne prouve que ce sont des doublons.
- **Lieux variés.** La plupart des lieux sont au format « Ville (QC) », mais certains sont « Longueuil, QC » ou « Différentes régions ».
- **Remotive.** L'API publique ne renvoie que 14 offres au total, avec 24 h de retard. Le paramètre `category` ne change rien au résultat. C'est une source d'appoint. Il faut garder le lien et le nom de Remotive, et ne pas republier ces offres ailleurs.
- **Dépendance au HTML.** Si le Guichet-Emplois change ses classes CSS, le script devra être adapté. Les tests utilisent une copie du balisage observé le 12 novembre 2026.

**Pistes pour la suite :**

- lire les fiches pour avoir la description, le vrai titre et le lien vers l'annonce d'origine, puis détecter les stages ;
- uniformiser le format des lieux ;
- comparer avec les essais de Hugo et Mamadou sur le Guichet-Emplois (fiches HTML et RDFa).
