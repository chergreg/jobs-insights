# Livrable 3 - Reprendre et améliorer une preuve de concept

Vous rejoignez un projet qui a déjà du code. À partir de la [synthèse du livrable 2](../02-preuve-de-concept-scraping/synthese.md) et des contributions dans le [dépôt GitHub](https://github.com/chergreg/jobs-insights), choisissez un site d’offres d’emploi ou de stage déjà exploré. Votre objectif est de comprendre ce qui a été essayé, de réutiliser le code pertinent et de faire avancer la collecte sur ce site.

## 1. Prendre connaissance du travail existant

Lisez la synthèse du livrable 2, puis ouvrez les scripts et les notes qui concernent votre site. Si deux ou trois étudiants ont travaillé sur ce même site, comparez leurs essais. L’analyse peut se limiter aux éléments qui vous aideront à choisir la prochaine amélioration.

Pour chaque approche pertinente, repérez comment les offres sont récupérées (HTML, API ou autre), quelles données ont été obtenues et quelles difficultés ont été rencontrées. Appuyez vos observations sur les fichiers et, si possible, sur un essai que vous avez relancé. Indiquez les résultats qui restent à vérifier.

Vous pouvez demander à votre assistant de code d’examiner les contributions. Voici une consigne à adapter à votre site.

> Lis la synthèse du livrable 2 et les scripts qui concernent [site]. Compare les approches. Cite les fichiers qui montrent ce qui a fonctionné, les limites observées et le code que je pourrais réutiliser. Indique ce qui reste à vérifier et propose une amélioration ciblée avant de modifier le code.

## 2. Faire évoluer le code

Choisissez une amélioration qui découle de votre analyse. Expliquez quel code vous reprenez et pourquoi. Prolongez une preuve de concept existante ou combinez des éléments de plusieurs essais si cela répond à une limite précise.

Par exemple, si un script trouve les offres de la première page, ajoutez la récupération de la page suivante. Si une approche trouve les liens et qu’une autre récupère le détail des offres, réutilisez les deux pour compléter les données collectées.

Vérifiez l’amélioration avec un essai ciblé. Notez la commande ou les étapes pour le reproduire, puis comparez le résultat obtenu avec celui de départ. Signalez les limites qui subsistent.

## À remettre dans GitHub

- **Le code Python mis à jour**, accessible par un lien vers le commit ou la demande de fusion.
- **Une courte note Markdown** indiquant le site choisi, les contributions consultées avec leurs liens, ce qui a fonctionné et les limites observées. Précisez ce que vous avez réutilisé ou modifié et présentez le résultat de votre vérification.
