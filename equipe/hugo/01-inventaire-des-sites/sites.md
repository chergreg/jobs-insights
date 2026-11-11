(Recherche faite à la main)
Liste des sites possible pour recherche d'emploi (site pour emploi à l'intérieur du Canada):


1.Emploi-Québec:
				-Page d'accueil:[Offres d'emploi disponibles | Québec emploi](https://www.quebecemploi.gouv.qc.ca/?lang=fr)
			
				

2.Emploi Canada:
				-Page d'accueil:[Trouver un emploi - Guichet-Emplois](https://www.guichetemplois.gc.ca/trouverunemploi)
				

3.Robert Half:
				-Page d'accueil:[Recherche d’emploi | Trouvez un emploi dans votre région avec Robert Half](https://www.roberthalf.com/ca/fr/recherche-emploi)
				

4.Indeed:
				-Page d'accueil:[Emploi | Indeed](https://ca.indeed.com/?r=us)

5.LinkedIn:
				-Page d'accueil:[S’identifier ou s’inscrire | LinkedIn](https://fr.linkedin.com/)

6.Jobboom:
				-Page d'accueil:[Offres d'emploi - Site de recherche d'emploi au Québec | Jobboom](https://www.jobboom.com/fr)

7.Workopolis:
				-Page d'accueil:[Job Search Engine | Workopolis](https://www.workopolis.com/)

8.Talent.com:
				-Page d'accueil:[Talent.com: Accédez à des milliers d'offres d'emploi près de chez vous](https://ca.talent.com/fr)

9.CarrerBuilder:
				-Page d'accueil:[Talent.com: Accédez à des milliers d'offres d'emploi près de chez vous](https://ca.talent.com/fr)

10.GlassDoor:
				-Page d'accueil:[Recherche d'emploi Glassdoor | Découvrez l’entreprise qui vous mérite](https://fr.glassdoor.ca/index.htm?countryRedirect=true)



### (Recherche à l'aide de l'IA)

### Prompt que j'ai fait:
1.Dresse moi une liste de sites de recherche d'emploi au canada au moins 10 sites les plus populaires. Sites sur lequel il me sera facile de d'extraire les données(ex: faire scraping de la page/site ou utiliser un api du site pour extraire info ou autres méthodes...)
2.Dresse moi une liste de sites de recherche d'emploi à l'international avec au moins 10 sites les plus populaire. Sites sur lequel il me sera facile de d'extraire les données(ex :faire scraping de la page/site ou utiliser un api du site pour extraire info ou autres méthodes...) 
Questions?


### Au Canada : 10 sites populaires et faciles à extraire**

|#|Site Web|Couverture|Méthode d'extraction recommandée|Format / Détails|
|---|---|---|---|---|
|1|**[Guichet-Emplois / Job Bank](https://www.jobbank.gc.ca/)**|Tout le Canada (Fédéral)|**API Données Ouvertes & Flux RSS**|Données officielles du gouvernement du Canada. Dumps CSV/XML quotidiens et flux RSS par région/métier.|
|2|**[Adzuna Canada](https://www.adzuna.ca/)**|Tout le Canada|**API REST officielle (gratuite)**|Inscription développeur gratuite. Renvoie du JSON propre (titre, salaire, localisation, description, entreprise).|
|3|**[Jooble Canada](https://ca.jooble.org/)**|Tout le Canada|**API REST officielle (gratuite)**|Clé API gratuite. Recherche par mot-clé et lieu via simple requête HTTP POST (réponse en JSON).|
|4|**[Talent.com](https://ca.talent.com/)** _(ex-Neuvoo, fondé au QC)_|Tout le Canada|**Scraping JSON-LD / Microdonnées**|Les pages d'offres intègrent la balise standard `<script type="application/ld+json">`, facile à parser avec BeautifulSoup sans analyser tout le DOM.|
|5|**[Jobillico](https://www.jobillico.com/)**|Québec / Canada|**Web Scraping HTML classique**|Structure HTML propre et stable avec pagination par URL. Très peu de restrictions anti-bot par rapport à Indeed.|
|6|**[WorkBC](https://www.workbc.ca/)**|Colombie-Britannique|**API REST publique**|Le gouvernement de la C.-B. fournit des points de terminaison JSON accessibles publiquement pour son portail d'emploi.|
|7|**[Eluta.ca](https://www.eluta.ca/)**|Tout le Canada|**Web Scraping (BeautifulSoup / Scrapy)**|Moteur de recherche d'emploi canadien (Top 100 Employers). HTML statique rendu côté serveur, simple à moissonner.|
|8|**[WowJobs.ca](https://www.wowjobs.ca/)**|Tout le Canada|**Flux RSS & Scraping**|Permet d'exporter des recherches d'emplois directement sous forme de flux RSS.|
|9|**[Craigslist Canada](https://www.craigslist.org/)** _(Toronto, Montréal, Vancouver...)_|Local / Grandes villes|**Flux RSS natif**|Ajoutez `?format=rss` à n'importe quelle URL de recherche d'emploi pour obtenir du XML structuré sans aucun blocage.|
|10|**[CharityVillage](https://charityvillage.com/)**|Canada (ONG / OBNL / Public)|**Web Scraping (Python / Requests)**|Référence canadienne du secteur associatif et parapublic. Pas de protection anti-scraping lourde.|

### **À l'international : 10 sites populaires et faciles à extraire**

|#|Site Web|Spécialité|Méthode d'extraction recommandée|Format / Détails|
|---|---|---|---|---|
|1|**[RemoteOK](https://remoteok.com/)**|Mondial / Télétravail|**API JSON publique (sans clé)**|Endpoint direct : `https://remoteok.com/api`. Renvoie toutes les offres actives directement au format JSON.|
|2|**[Remotive](https://remotive.com/)**|Mondial / Tech & Remote|**API REST publique (sans clé)**|Endpoint direct : `https://remotive.com/api/remote-jobs`. Très documentée, structurée et gratuite.|
|3|**[Arbeitnow](https://www.arbeitnow.com/)**|Europe / Télétravail|**API REST publique**|Endpoint : `https://www.arbeitnow.com/api/job-board-api`. Format JSON complet avec pagination intégrée.|
|4|**[We Work Remotely](https://weworkremotely.com/)**|Mondial / Remote|**Flux RSS thématiques**|Flux RSS complets disponibles par catégorie (ex: `/categories/remote-programming-jobs.rss`).|
|5|**[The Muse](https://www.themuse.com/)**|États-Unis / International|**API REST officielle**|Documentation développeur complète avec pagination, filtres par niveau d'expérience, lieu et entreprise.|
|6|**[USAJOBS](https://www.usajobs.gov/)**|États-Unis (Fédéral)|**API REST officielle (gratuite)**|API REST du gouvernement américain, réponse détaillée en JSON après simple demande de clé d'API.|
|7|**[Reed.co.uk](https://www.reed.co.uk/)**|Royaume-Uni & International|**API REST développeur**|Offre un accès API complet et gratuit pour rechercher des offres d'emploi par mot-clé, code postal ou rayon.|
|8|**[Adzuna International](https://developer.adzuna.com/)**|16+ pays (US, UK, FR, DE, etc.)|**API REST officielle**|Même API que pour le Canada, disponible pour une quinzaine de pays avec les mêmes paramètres JSON.|
|9|**[Hacker News (Who is Hiring?)](https://news.ycombinator.com/)**|Tech / Startups mondiales|**API Algolia HN / Firebase**|L'ensemble des commentaires du fil mensuel "Who is hiring" est requêtable via l'API publique d'Algolia (`hn.algolia.com/api`).|
|10|**[Jobicy](https://jobicy.com/)**|Mondial / Télétravail|**API REST v2 (gratuite)**|Endpoint : `https://jobicy.com/api/v2/remote-jobs`. Filtres par industrie, géographie et type de contrat.|