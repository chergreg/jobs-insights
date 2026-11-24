# Livrable 2 — Prototype Remotive

## Installation

Installez Python 3.12 ou plus récent. Le prototype utilise uniquement la bibliothèque standard. Le fichier `requirements.txt` documente cette absence de dépendances externes.

Depuis la racine du dépôt, ouvrez le dossier du prototype.

```powershell
cd equipe/hendrix/02-preuve-de-concept-scraping
python --version
```

## Exécution

```powershell
# Démonstration locale avec deux offres fictives
python collecte_remotive.py --sortie demo-local.json

# Collecte ponctuelle d'une seule offre
python collecte_remotive.py --reel --limite 1 --sortie remotive-local.json

# Tests hors ligne
python -m unittest discover -v
```

Indiquez un fichier de sortie dans un dossier existant. Une exécution réussie remplace le fichier s'il existe déjà. Le nombre maximal d'offres vaut trois par défaut et peut être réglé de 1 à 10.

## Fonctionnement

1. Sans `--reel`, le script lit une réponse fictive dans `fixtures/`. En mode réel, il envoie une requête GET à l'API publique avec le paramètre `limit` et un délai d'attente de 15 secondes.
2. Il lit la liste `jobs` du JSON et extrait le titre, l'entreprise, la localisation exigée des candidats, la date, la description, le salaire et l'URL. Un champ absent ou vide donne `null`. Les descriptions HTML sont nettoyées pour obtenir du texte lisible. Les autres informations sont conservées sans invention de données.
3. Il exporte le résultat en JSON UTF-8 avec le nom de la source, le mode de collecte et le nombre d'offres. Une erreur produit un message et un code de sortie 1, sans relance automatique.

Gardez les exports réels en local pour cet essai. Pour toute présentation d'une offre, attribuez-la à Remotive et gardez le lien fourni par l'API. Limitez les essais réels à quatre requêtes par jour au maximum, conformément à la recommandation du fournisseur. Utilisez le mode simulé pour les exécutions répétées. [Documentation officielle de Remotive](https://github.com/remotive-com/remote-jobs-api)

L'[exemple JSON simulé](exemple-simule.json) et le [compte rendu](compte-rendu.md) accompagnent le script.
