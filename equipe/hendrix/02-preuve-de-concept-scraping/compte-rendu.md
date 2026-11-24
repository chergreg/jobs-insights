# Compte rendu — Livrable 2, Hendrix

## Source et méthode

J'ai choisi [Remotive](https://remotive.com/remote-jobs), un site d'offres en télétravail. Le prototype interroge l'[URL de test](https://remotive.com/api/remote-jobs?limit=1), qui répond en JSON selon la documentation. Le fichier [robots.txt](https://remotive.com/robots.txt) exclut les chemins `/api/*` de l'exploration par les robots. Le prototype utilise uniquement l'endpoint que [Remotive documente comme API publique](https://remotive.com/remote-jobs/api) et ne parcourt aucune page HTML.

J'ai utilisé Python 3.13.7 pour l'essai, avec `urllib.request` pour la requête, `json` pour la lecture et l'export et `unittest` pour les tests. Le prototype utilise la bibliothèque standard et se lance depuis son dossier.

```powershell
python collecte_remotive.py --reel --limite 1 --sortie remotive-local.json
```

## Résultats simulés

La commande `python collecte_remotive.py --sortie exemple-simule.json` a produit [un export de deux offres fictives](exemple-simule.json). L'offre « Développeur junior » contient les sept champs attendus. Dans l'offre « Stage en informatique », le salaire vide et les champs absents sont exportés sous forme de `null`. Les six tests hors ligne passent et couvrent l'extraction, les structures invalides, la limite, la requête simulée, l'export et les erreurs réseau ou JSON.

## Essai réel du 24 novembre 2026

J'ai lancé une collecte d'une offre. L'environnement n'a pas résolu le nom de domaine de Remotive (`getaddrinfo failed`). Je n'ai reçu aucune réponse HTTP ni généré d'export réel. La comparaison avec une annonce affichée sur le site reste à faire. Si l'API répond lors d'un essai effectué depuis un réseau accessible, je pourrai ouvrir manuellement l'URL retournée et comparer le titre, l'entreprise, la localisation et le salaire lorsqu'il est indiqué.

## Limites

Le contenu de la description est conservé sous forme de HTML dans le JSON. La localisation est le texte fourni par Remotive sur le lieu de résidence des candidats. Elle ne constitue pas une vérification de l'admissibilité d'une personne. Remotive indique que les offres de l'API sont diffusées avec un délai de 24 heures. [Documentation officielle](https://github.com/remotive-com/remote-jobs-api)
