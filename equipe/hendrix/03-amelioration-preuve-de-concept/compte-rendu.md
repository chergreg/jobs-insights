# Livrable 3 — Amélioration de la preuve de concept Remotive

**Étudiant :** Hendrix  
**Site choisi :** Remotive (offres d'emploi à distance)  
**Améliorations :** cache JSON de 24 heures inspiré de Kandet et correction de la classification géographique inspirée de Grégory.

## 1. Travail consulté

- [Synthèse du livrable 2](../../../livrables/02-preuve-de-concept-scraping/synthese.md) : elle compare les prototypes et mentionne le cache Remotive de Kandet. Le tableau de synthèse indique « non fait » pour mon nom, mais il est antérieur à la publication de mon livrable 2 ; ce statut n'est plus à jour.
- [Mon prototype Remotive du livrable 2](../02-preuve-de-concept-scraping/collecte_remotive.py) : API JSON Remotive, extraction du titre, entreprise, localisation, date, description, salaire et URL, puis export JSON. Le nettoyage HTML, les valeurs absentes et la suppression des doublons par URL étaient déjà présents.
- [Prototype multi-source de Kandet](../../kandet/02-preuve-de-concept-scraping/poc_multi_source.py) : la fonction `load_remotive_payload` conserve l'URL demandée, l'heure et la réponse de l'API dans un fichier JSON et réutilise le résultat pendant 24 h.
- [Collecteur Remotive de Grégory](../../gregory/livrable3/scrapers/remotive.py) : propose davantage de normalisation, notamment géographique. La fonction `classify_remotive_location()` renseigne `province = "QC"` et `is_canada_eligible = True` pour des zones comme `Worldwide` ou pour un lieu absent. Une région large ou un champ vide ne permet pourtant pas de confirmer une province précise ou une admissibilité individuelle. J'ai repris l'idée de normalisation géographique, mais pas ces valeurs par défaut.

## 2. Limite constatée et modification choisie

**Avant :** dans mon livrable 2, deux lancements en mode `--reel` faisaient deux appels à l'API, même avec la même limite. Cela peut consommer inutilement le quota conseillé par Remotive (4 requêtes par jour).

**Après :** `charger_reponse_avec_cache(limite, chemin)` est appelée seulement en mode réel :

1. Elle vérifie si `remotive-cache.json` contient une réponse correspondant à l'URL avec la même valeur `limit`.
2. Si le cache date de moins de 24 h, elle renvoie les offres déjà collectées sans nouvel appel HTTP.
3. Sinon, elle interroge Remotive et conserve `{request_url, fetched_at, payload}` dans le cache.
4. Si le cache est expiré, mal formé ou correspond à une autre limite, elle récupère une nouvelle réponse.
5. Le mode simulé lit toujours la fixture locale sans réseau.

Le principe de cache provient de Kandet ; j'ai adapté la clé de correspondance à ma requête avec `?limit=N` et conservé mon format JSON d'export du livrable 2. Les autres membres du dépôt n'ont pas été modifiés.

## 3. Deuxième amélioration : une province uniquement si elle est étayée

**Avant (approche consultée chez Grégory) :** `classify_remotive_location()`
transforme une absence de localisation ou une zone `Worldwide` en `province = "QC"`,
`pays = "Canada"` et `is_canada_eligible = True`. La précision québécoise et
l'admissibilité ainsi renseignées ne sont pas appuyées par l'information source.
Le collecteur de mon livrable 2 n'ajoutait pas de province, mais sa classification
traitait aussi `Laval` seul comme un indice suffisant pour Québec.

**Après (dans mon propre collecteur uniquement) :**

- La valeur brute `localisation` est conservée telle quelle dans l'export.
- `province_code` vaut `null` pour `Canada`, `Worldwide`, `Anywhere`,
  `North America` et les champs absents ; on ne transforme pas une zone large
  en une province.
- `province_code` vaut `QC` si l'on reconnaît clairement Québec ou Montréal,
  et `ON` pour Ontario ou Toronto ; `Laval` isolé est laissé ambigu.
- Aucune valeur `is_canada_eligible` n'est déduite automatiquement : une zone
  géographique n'établit pas toutes les conditions d'embauche ou de résidence.
- Les tests supplémentaires vérifient la classification et les valeurs `null`
  depuis des offres JSON fictives jusqu'à leur normalisation.

La fonction de Grégory a été **consultée comme point de comparaison**, pas
modifiée ; aucun autre dossier de l'équipe n'a été touché.

## 4. Vérification reproduisible

Depuis `equipe/hendrix/03-amelioration-preuve-de-concept/` :

```powershell
python -m unittest discover -v
python collecte_remotive.py --sortie demo-local.json
```

**Résultat de vérification hors ligne :** 19 tests réussis sur 19 dans la copie de travail (Python et bibliothèque standard, sans appel réseau). Cela couvre notamment la réutilisation du cache, son expiration, un changement de paramètre, un fichier corrompu, une date invalide, une réponse API invalide, le branchement du cache dans `main()` et les fonctionnalités précédentes. L'exemple simulé exporte deux offres fictives.

**Comparaison :** avant correction, la version du livrable 3 sur la branche affichait `Ran 13 tests` puis `FAILED (errors=5)` : quatre tests ne trouvaient pas la fonction de cache, et un test avait deux décorateurs `@patch` au lieu d'un. Après correction et ajout de trois tests géographiques, les 19 tests passent. Dans le test simulant deux collectes identiques sous 24 h, l'API factice est appelée une seule fois, au lieu de deux fois sans cache. Trois nouveaux tests contrôlent les provinces QC/ON, le cas ambigu Laval et l'absence de province inventée dans les offres normalisées.

Aucune collecte réelle vers Remotive n'a été effectuée pour cette dernière vérification ; l'économie d'appels est démontrée par les tests hors ligne. Le fonctionnement réel dépend aussi du réseau et des règles du fournisseur.

## 5. Limites restantes

- Le cache conserve une seule variante de requête à la fois. Passer de `--limite 1` à `--limite 2` déclenche une nouvelle requête et remplace le cache précédent.
- Il réduit les requêtes répétées mais n'impose pas un compteur quotidien strict de quatre appels ; les usages réels doivent toujours respecter le quota du fournisseur.
- La classification géographique n'est qu'indicative et limitée pour l'instant aux provinces QC et ON reconnues par quelques mots-clés. Elle ne déduit pas le droit légal de travailler et ne gère pas toutes les exclusions exprimées en langage naturel.
- Les tests utilisent des réponses fictives ou simulées ; la disponibilité de l'API externe et l'actualité des annonces ne sont pas garanties.

## 6. Documentation de la source

[Remotive — documentation officielle de l'API publique](https://github.com/remotive-com/remote-jobs-api).

## 7. Vérification avec les données réelles de Remotive

Une collecte réelle a été effectuée avec la commande :

`python collecte_remotive.py --reel --limite 10 --sortie remotive-local.json`

**Résultats obtenus :**
- 10 offres d'emploi récupérées.
- 10 offres possèdent une URL originale.
- 7 offres possèdent un salaire renseigné.
- 4 offres classées « Amérique du Nord ».
- 3 offres classées « Mondiale ».
- 3 offres classées « États-Unis ».

La collecte a confirmé que le programme extrait les informations de Remotive et conserve les données manquantes sous la valeur `null`.

La classification géographique n'a attribué aucune province canadienne sans indication précise dans les données.

**Limite observée :** certaines offres couvrant plusieurs régions du monde sont classées « Amérique du Nord ». Cette classification pourrait être améliorée ultérieurement.

Cette vérification complète les tests unitaires effectués hors ligne.
