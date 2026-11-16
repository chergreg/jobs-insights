# Sites d’offres d’emploi et de stage

## Sources québécoises et canadiennes

- [Guichet-Emplois / Job Bank](https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois)
  - Site officiel du gouvernement du Canada, filtre par province (Québec) et beaucoup d’offres en TI.
  - Filtre dédié aux stages et emplois étudiants. Flux Atom/RSS et données ouvertes disponibles.
  - `robots.txt` : délai de 5 secondes entre deux requêtes.

- [Jobillico](https://www.jobillico.com/fr/)
  - Beaucoup de PME de Québec et Montréal. Recherche par mot-clé et par région.
  - Fiches d’offres avec données structurées JSON-LD `JobPosting`.

- [Jobboom](https://www.jobboom.com/fr)
  - Portail québécois avec une catégorie *Technologies et médias numériques*.
  - Fiches d’offres avec données structurées JSON-LD `JobPosting`.

- [Talent.com Canada](https://ca.talent.com/fr)
  - Agrégateur canadien avec des stages en informatique et des postes juniors au Québec.

- [Carrières — Gouvernement du Québec (étudiants et stagiaires)](https://www.carrieres.gouv.qc.ca/etudiants-et-stagiaires/)
  - Stages et emplois étudiants dans les ministères et organismes du Québec.

- [Remotive](https://remotive.com/remote-jobs)
  - Offres tech 100 % en télétravail, avec un filtre pour les stages. API JSON publique sans clé.

## Source internationale

- [Welcome to the Jungle](https://www.welcometothejungle.com/fr/jobs)
  - Emplois, stages et alternances tech, avec filtres contrat, lieu, télétravail et expérience.
  - Site chargé en JavaScript : les offres viennent d’une API JSON (`api.welcometothejungle.com/api/v3/public/jobs`), repérée dans l’onglet Réseau.
  - Surtout des offres en Europe : peu d’offres au Québec.
  - Difficulté : facile (les données sont déjà structurées en JSON).

## Sources exclues de la collecte automatisée

- [Indeed Canada](https://ca.indeed.com) : conditions d’utilisation interdisant le scraping, protection anti-robot.
- [LinkedIn Jobs](https://www.linkedin.com/jobs/) : `robots.txt` et conditions d’utilisation restrictifs.
- [Glassdoor](https://www.glassdoor.ca) : conditions d’utilisation interdisant les robots.

Ces sites restent en consultation manuelle uniquement.
