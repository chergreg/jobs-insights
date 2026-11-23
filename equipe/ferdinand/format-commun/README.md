# Format commun — Welcome to the Jungle

Ce dossier convertit mes offres Welcome to the Jungle vers le **format commun** de la classe : le modèle `JobOffer` de Gregory ([`models.py`](../../gregory/livrable3/models.py), [`plan.md`](../../gregory/livrable3/plan.md) section 4). L'idée vient du dossier [`format-commun` de Kandet](../../kandet/format-commun/README.md).

Il réutilise la collecte de mon [livrable 3](../03-amelioration-preuve-de-concept/poc_wttj_v2.py) sans la modifier. On peut supprimer ce dossier sans rien casser.

## Utilisation

Depuis ce dossier :

```bash
pip install -r ../03-amelioration-preuve-de-concept/requirements.txt
python convertir.py                                  # mots-clés : stage, développeur, data, informatique
python convertir.py --mot-cle stage --mot-cle data   # mots-clés choisis
python convertir.py --csv                            # + offres_format_commun.csv pour Excel
python convertir.py --echantillon 10                 # + echantillon_format_commun.json
python -m unittest -v test_convertir.py
```

Seul `echantillon_format_commun.json` va dans Git. Les fichiers complets se recréent avec la commande.

## Correspondance des champs

| Format commun | Vient de l'API WTTJ |
| --- | --- |
| `id` | `wttj-` + `reference` |
| `titre`, `entreprise` | `name`, `organization.name` |
| `lieu`, `pays` | villes et pays de `offices` (bureaux au Canada en priorité) |
| `province` | `QC` si toutes les villes sont des villes connues du Québec |
| `url` | construit avec les deux `slug` |
| `source` | `welcome-to-the-jungle` |
| `date_publication` | `published_at` (AAAA-MM-JJ) |
| `type_poste` | `contract_type` (`internship` → Stage, `full_time` → Temps plein…) |
| `modalite` | `remote` (`no` → Sur place, `partial` → Hybride…) |
| `est_stage`, `statut_stage` | stage confirmé si le contrat est un stage ; « possible » si le titre parle de stage |
| `salaire` | `salary_min`, `salary_max`, devise et période |
| `description`, `competences_cles` | vides : la liste de résultats de l'API ne donne pas la description |

## Règles suivies

- **Rien n'est deviné.** Le modèle de Gregory met « QC », « Canada » et « Temps plein » par défaut. Ici, chaque champ est rempli explicitement : une ville canadienne hors de la liste (ex. Toronto) donne `province = "Non spécifié"`.
- Une offre sans identifiant, titre ou lien est ignorée, car le modèle commun exige ces champs.
- Par défaut, seules les offres au **Canada** sont gardées, sans doublon (même `id`).

## Vérification

- 14 tests hors ligne, dont un qui vérifie que mes offres sont **acceptées par le modèle `JobOffer` de Gregory** sans que ses valeurs par défaut remplacent les miennes. Ce test est sauté si Pydantic n'est pas installé.
- Résultat de la collecte réelle : _à compléter après le premier lancement_ (nombre d'offres reçues, uniques au Canada, stages).

## Limites

- Peu d'offres au Québec : Welcome to the Jungle est surtout européen.
- Pas de description ni de compétences (il faudrait une requête par fiche).
