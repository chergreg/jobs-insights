# Format commun

Ce dossier convertit mes offres vers le **format commun** proposé par Gregory pour réunir le travail de la classe : le modèle `JobOffer` de son [plan du livrable 3](../../gregory/livrable3/plan.md) (section 4) et de son [`models.py`](../../gregory/livrable3/models.py).

Il est **à part** de mon projet. Il lit seulement le fichier `offres.json` produit par [`03-amelioration-preuve-de-concept/main.py`](../03-amelioration-preuve-de-concept/main.py) et ne modifie rien ailleurs. On peut supprimer ce dossier à tout moment sans rien casser.

## Utilisation

Depuis ce dossier, après une collecte :

```powershell
python convertir.py                    # offres_format_commun.json
python convertir.py --csv              # + offres_format_commun.csv pour Excel
python convertir.py --echantillon 10   # + echantillon_format_commun.json
python -m unittest -v test_convertir.py
```

Seul [`echantillon_format_commun.json`](echantillon_format_commun.json) (10 offres) est dans Git. Les fichiers complets se recréent avec la commande ci-dessus.

## Correspondance des champs

| Format commun | Vient de `offres.json` |
|---|---|
| `id` | `ge-` + numéro du Guichet-Emplois, ou `rem-` + numéro Remotive |
| `titre` | titre CNP (`title`), comme dans le jeu de Gregory |
| `entreprise`, `lieu`, `province` | `employer`, `location`, `province` |
| `pays` | « Canada » pour le Guichet-Emplois, sinon « Non spécifié » |
| `source`, `source_partenaire` | `guichet-emplois` ou `remotive`, et site d'origine (Jobillico, Québec emploi…) |
| `type_poste` | Temps plein, Temps partiel, Contrat, Stage ou Pigiste / Freelance |
| `est_stage`, `statut_stage` | `stage_status` (seul un stage confirmé donne `est_stage = true`) |
| `competences_cles` | technologies, puis compétences générales |
| `description`, `salaire`, `modalite`, `date_publication` | mêmes informations, texte d'origine |
| `date_extraction` | date de la collecte |

## Vérification (20 novembre 2026)

- Les 195 offres de ma collecte sont acceptées telles quelles par le modèle `JobOffer` de Gregory (Pydantic). Le test `ModeleDeGregoryTests` refait cette vérification ; il est sauté si Pydantic n'est pas installé.
- 157 de ces offres sont aussi dans le jeu de Gregory (`offres_unifiees.json`), avec le même `id`. Le titre, l'employeur et le lien sont identiques pour les 157.

## Différences volontaires avec le jeu de Gregory

- **Rien n'est deviné.** Son modèle met « QC » et « Canada » par défaut. Ici, une offre Remotive « USA, Canada » garde `province` et `pays` à « Non spécifié ». Son `lieu` est aussi gardé tel quel (pas « Amérique du Nord (Télétravail) »).
- **`type_poste` vide quand l'offre ne le dit pas**, au lieu de « Temps plein ».
- **Salaire** : même montant, avec des espaces normaux au lieu d'espaces insécables.
- Le titre écrit par l'employeur (« Développeur full-stack »), les régions et les autres champs enrichis restent dans `offres.json` : ils ne font pas partie du format commun.
