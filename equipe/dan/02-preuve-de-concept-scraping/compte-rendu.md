# Compte rendu — Livrable 2 : Guichet-Emplois

## Site et page testée

- **Guichet-Emplois** : https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois
- Filtres utilisés dans l'URL :
  - `fprov=QC` : offres au Québec ;
  - `fn21=<code>` : 14 codes CNP 2021 du domaine informatique (liste reprise de Kandet) ;
  - `sort=D` : plus récentes d'abord ;
  - `searchstring=<mot>` : mot-clé facultatif.

## Méthode et commande

- `requests` télécharge la page de résultats, `BeautifulSoup` lit le HTML.
- Chaque offre est un bloc `<article id="article-…">`. Les champs sont repérés par leur classe CSS :

| Champ | Sélecteur |
| --- | --- |
| Lien | `a.resultJobItem` |
| Titre | `.noctitle` |
| Employeur | `.business` |
| Lieu | `.location` |
| Date | `.date` |
| Salaire | `.salary` |

- Règles respectées : lecture de `robots.txt` avant la requête, délai de 5 s (`Crawl-delay: 5`), `User-Agent` honnête.

```bash
pip install -r requirements.txt
python poc_guichetemplois.py                 # tous les postes TI au Québec
python poc_guichetemplois.py "developpeur"   # avec un mot-clé
```

Le résultat est enregistré dans `offres_guichetemplois.csv` (`utf-8-sig`, lisible dans Excel).

## Données récupérées

Titre, employeur, lieu, date, salaire et lien de chaque offre de la première page (25 offres au plus).

_Échantillon : guichetemplois,développeur Web/développeuse Web,Mewlogic Inc.,Vaudreuil-Dorion (QC),16 novembre 2026,"43,27 $ de l'heure",https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50738681
guichetemplois,ingénieur/ingénieure en infonuagique,Astra North Infoteck Inc.,Montréal (QC),14 novembre 2026,"10 000,00 $ par mois",https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50726925
guichetemplois,développeur/développeuse de logiciels,Astra North Infoteck Inc.,Montréal (QC),14 novembre 2026,"10 000,00 $ par mois",https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50726939

## Limites et essais

- **Une seule page** : pas de pagination (Kandet parcourt toutes les pages avec le paramètre `page`).
- **Pas de description** : elle se trouve dans la fiche de chaque offre, qu'il faudrait ouvrir une par une.
- **Pas de site d'origine** : une partie des offres vient de sites partenaires (Jobillico, Talent.com…), ce que le script ne conserve pas encore.
- **Premier essai hors cible** : ciblé sur Moncton (N.-B.), puis recentré sur le Québec et le domaine TI.
- **Sélecteurs** : d'abord supposés, puis remplacés par ceux vérifiés dans le POC de Kandet.
- **Essai sur CareerBeacon** : `robots.txt` permet la recherche, mais le serveur répond `403` (protection Cloudflare). Arrêt sans contournement. Détails dans [`sites.md`](../01-inventaire-des-sites/sites.md).
