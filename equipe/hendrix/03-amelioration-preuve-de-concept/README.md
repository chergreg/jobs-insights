# Livrable 3 — Collecteur Remotive : cache 24 h et géographie prudente

Projet scolaire JOBS-INSIGHTS. Ce dossier reprend le collecteur Python du livrable 2, avec un cache JSON local et une normalisation géographique prudente. **Aucune dépendance externe** : Python 3.12+ suffit.

## Utilisation (PowerShell)

Depuis la racine du dépôt :

```powershell
cd equipe/hendrix/03-amelioration-preuve-de-concept
python -m unittest discover -v
python collecte_remotive.py --sortie demo-local.json
```

Le mode simulé exporte **deux offres fictives**. La collecte réelle est optionnelle :

```powershell
python collecte_remotive.py --reel --limite 2 --sortie remotive-local.json
```

Le résultat réel utilise `remotive-cache.json` pour éviter de refaire une requête identique pendant 24 heures. Les caches et exports locaux sont ignorés par Git ; la réponse simulée dans `fixtures/` peut être committée.

Le cache dépend de la limite (`--limite` de 1 à 10). Changer la limite, dépasser 24 heures ou fournir un cache invalide déclenche une nouvelle requête. Le script ne garantit pas le respect du quota journalier : limiter les exécutions réelles conformément aux règles de l'API Remotive. Il ne fait aucune relance automatique en cas d'erreur.

### Amélioration géographique inspirée de Grégory

Le JSON exporté conserve `localisation` telle que Remotive la fournit, et ajoute
`categorie_localisation` et `province_code` (qui vaut `null` si la province
n'est pas établie). Contrairement à une classification qui place par défaut
`Worldwide`, `North America`, `Canada` ou une localisation absente au Québec,
ce collecteur n'attribue **pas `QC`** à ces cas. `QC` et `ON` sont reconnus
seulement avec des indices plus précis (Québec, Montréal, Ontario, Toronto,
Laval accompagné de Canada). « Laval » seul reste ambigu. Le prototype ne
prétend pas déterminer l'admissibilité juridique à un emploi au Canada.

Pour la comparaison des contributions et les résultats des tests, consulter [le compte rendu](compte-rendu.md).
