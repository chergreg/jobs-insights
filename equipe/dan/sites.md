# Sites d'offres d'emploi et de stages — repérage pour le scraping

> Atelier « Recherche d'emploi, des postes… » — fichier perso
> Profil visé : étudiants de l'Université de Moncton (génie, informatique / web) qui cherchent
> des **stages, emplois d'été, temps partiel et premiers emplois** au Nouveau-Brunswick.
> Dernière mise à jour : 2026-11-09

**Légende :** ✅ = vérifié · 🔍 = à confirmer en naviguant sur le site (clic droit → **Inspecter**)

---

## 1. Guichet-Emplois (Job Bank)

| Élément | Détail |
| --- | --- |
| URL | https://www.guichetemplois.gc.ca |
| Type | Site national d'emploi du gouvernement du Canada |
| Langues | Français et anglais |
| Coût / compte | Gratuit, pas de compte nécessaire pour chercher ✅ |
| Volume | Environ 70 000 offres affichées en même temps ✅ |
| Priorité | ⭐⭐⭐ (premier site du projet) |
| Méthode prévue | Scraping HTML (`poc_guichetemplois.py`) + Alertes-Emplois par courriel |

### Pourquoi ce site est intéressant pour nous

- Il couvre tout le Nouveau-Brunswick, y compris Moncton.
- Il reprend aussi des offres d'autres sites (ex. Jobillico) ✅ : une seule source donne déjà beaucoup d'offres.
- Les offres publiées directement sur le Guichet-Emplois viennent d'employeurs vérifiés ✅.
- Il existe un filtre pour les **étudiants** et les **jeunes** 🔍.

### Catégories et filtres à repérer

| Filtre | Exemple de valeur | Paramètre dans l'URL |
| --- | --- | --- |
| Mots-clés | `technicien`, `stage génie` | `searchstring` 🔍 |
| Emplacement | `Moncton, NB` | `locationstring` 🔍 |
| Date de publication | dernières 24 h, 7 jours | 🔍 |
| Type d'emploi | temps plein, temps partiel | 🔍 |
| Durée | permanent, temporaire, saisonnier | 🔍 |
| Salaire | salaire minimum | 🔍 |
| Groupes ciblés | étudiants, jeunes | 🔍 |
| Source de l'offre | Guichet-Emplois ou sites partenaires | 🔍 |
| Tri | pertinence, date | 🔍 |
| Parcourir par employeur / province | `/parcourirlesoffresdemploi/employeur/...` | ✅ |

> **Méthode :** cocher un seul filtre à la fois et noter comment l'adresse change dans la barre du navigateur.

### Structure des URL

| Page | Forme de l'URL |
| --- | --- |
| Recherche | `/jobsearch/rechercheemplois?searchstring=<mots>&locationstring=<lieu>` 🔍 |
| Fiche d'une offre | `/jobsearch/jobposting/<numéro>` ✅ |
| Pagination | paramètre `page` ou bouton « Afficher plus de résultats » 🔍 |

### Champs à extraire

**Sur la page de résultats** (liste d'offres) :

| Champ | Sélecteur CSS supposé |
| --- | --- |
| Bloc d'une offre | `article` 🔍 |
| Titre | `.noctitle` 🔍 |
| Employeur | `.business` 🔍 |
| Lieu | `.location` 🔍 |
| Date de publication | `.date` 🔍 |
| Salaire | `.salary` 🔍 |
| Lien vers la fiche | `a` (attribut `href`) 🔍 |

**Sur la fiche d'une offre** (vus sur une vraie fiche ✅) : titre, employeur, lieu, salaire, type d'emploi (permanent, temps plein…), date de début, nombre de postes à pourvoir, date de publication, date « affichée jusqu'au », numéro d'offre, source de l'offre.

### Règles et limites

- [ ] Lire `https://www.guichetemplois.gc.ca/robots.txt` 🔍
- [ ] Lire les conditions d'utilisation du site 🔍
- Ne pas envoyer plus d'une requête toutes les 2 secondes (`time.sleep(2)` dans le script).
- Alternative sans scraping : les **Alertes-Emplois**, un courriel gratuit envoyé jusqu'à deux fois par jour ✅.
- Le site partage un fil XML de ses offres, mais seulement avec d'autres sites d'emploi qui en font la demande ✅ : ce n'est pas pour nous.

### Grille de navigation (à remplir en atelier)

- [ ] Faire une recherche « technicien » à « Moncton, NB » et copier l'URL obtenue
- [ ] Noter le nom du paramètre ajouté par chaque filtre (tableau plus haut)
- [ ] Vérifier comment passer à la page 2
- [ ] Ouvrir « Afficher le code source » : les offres sont-elles dans le HTML ?
- [ ] Avec **Inspecter**, confirmer la balise et la classe de chaque champ
- [ ] Mettre à jour `SELECTEURS` dans `poc_guichetemplois.py` et lancer le script

---

## Prochains sites à ajouter

EmploisNB · Offres d'emploi du GNB · Jobillico · Adzuna · BEC coop (U de M) · pages carrières d'employeurs du N.-B.
