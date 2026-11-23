# Compte rendu — Livrable 2 : Preuve de concept de scraping

**Auteur :** Hugo  
**Projet :** `job-insights` — Cours 420-SV2-OQ (Collège O'Sullivan de Québec)  
**Date :** Novembre 2026  

---

## 1. Site choisi et URLs testées

* **Plateforme :** Guichet-Emplois Canada / Job Bank Canada (Gouvernement du Canada).
* **URLs analysées et testées :**
  1. *Flux Atom XML officiel (ciblé TI et en français) :* `https://www.guichetemplois.gc.ca/jobsearch/feed/jobSearchRSSfeed?sort=D&fprov=QC&wid=s&action=search&lang=fra&term=informatique`
  2. *Recherche HTML avec codes CNP TI 2021 :* `https://www.guichetemplois.gc.ca/rechercheemplois/rechercheemplois?searchstring=programmeur&fn21=21230&fn21=21232&fn21=21234&fn21=22220&lang=fra`
  3. *Fiches détaillées d'offres :* `https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{id}?lang=fra`
  4. *Fichier des règles :* `https://www.guichetemplois.gc.ca/robots.txt`

---

## 2. Méthodes, architecture et commandes d'exécution

### Périmètre ciblé : DEC en informatique
Le collecteur est spécialement calibré pour couvrir l'ensemble des branches du DEC en Techniques de l'informatique :
1. **Développement logiciel & Web** : Programmeurs, Développeurs Web/Mobile/Jeux vidéo, Analystes, DevOps.
2. **Infrastructure, Réseaux & Sécurité** : Techniciens réseau, Soutien technique / Helpdesk TI, Administrateurs systèmes, Spécialistes cybersécurité.
3. **Assurance qualité & Données** : Testeurs logiciels (QA), Administrateurs et analystes de bases de données.
4. **Stages informatiques** : Détection des offres de stages et contrats étudiants en TI.

> 🛡️ **Filtre de garde anti-parasites (`est_metier_dec_informatique`)** : Élimine formellement les offres hors informatique (ex. *cleaning man/woman*, entretien ménager, restauration, etc.) qui pourraient survenir dans les flux généralistes.

### Priorisation de la langue française
* Domaine officiel francophone : `www.guichetemplois.gc.ca`.
* Ajout systématique du paramètre `lang=fra` sur toutes les requêtes (Atom, recherche HTML et fiches détaillées).
* En-tête HTTP d'acceptation de langue : `Accept-Language: fr-CA,fr;q=1.0,en-CA;q=0.5`.

### Approche multi-stratégies (Cascade avec repli)
1. **Niveau 1 (Flux Atom XML ciblé TI) :** Requête rapide récupérant les annonces TI récentes avec métadonnées en français.
2. **Niveau 2 (Recherche HTML par mots-clés et codes CNP) :** Si le quota souhaité (ex. 100 offres) n'est pas atteint, recherche ciblée sur les codes CNP de l'informatique (21230, 21232, 21234, 22220, 22221, etc.).
3. **Niveau 3 (Enrichissement des fiches détaillées) :** Visite des pages d'offres pour extraire la modalité (télétravail, hybride, sur place), le type de contrat (stage vs temps plein), les compétences techniques et la description complète.
   - *Priorité sémantique :* Balises Schema.org / RDFa (`property="description"`, `property="title"`).
   - *Repli DOM :* Sélecteurs CSS (`div#job-posting-detail`, `section.job-posting-detail-requirements`).

### Commandes d'exécution

* **Installation des dépendances :**
  ```powershell
  pip install -r requirements.txt
  ```

* **Exécution des tests unitaires hors ligne (8 tests, validation du filtrage DEC et parsing) :**
  ```powershell
  python -m unittest test_scraper.py -v
  ```

* **Lancement en mode ligne de commande (CLI automatisable) :**
  ```powershell
  python main.py --limit 100 --fast
  ```

* **Lancement en mode interactif (Double-clic) :**
  ```powershell
  python main.py
  ```

---

## 3. Données extraites et structure de données

Chaque offre est validée par le modèle Pydantic `JobOffer` garantissant les types et valeurs :
* `id` : Identifiant unique de l'offre (ex. `gc-50738681`).
* `titre` : Intitulé du poste TI.
* `entreprise` : Nom de l'employeur.
* `lieu` : Ville ou région.
* `province` : Code provincial (`QC`, etc.).
* `pays` : `Canada`.
* `salaire` : Montant brut ou taux horaire.
* `date_publication` : Date de publication de l'offre.
* `modalite` : `Télétravail`, `Hybride`, `Sur place` ou `Non spécifié`.
* `type_poste` : `Stage`, `Temps plein`, `Temps partiel` ou `Étudiant`.
* `competences_cles` : Liste filtrée de mots-clés techniques sans faux positifs français (ex. `["Python", "FastAPI", "Docker"]`).
* `description` : Texte complet des responsabilités et exigences du poste en français.
* `url_source` : Lien direct vers l'annonce avec `lang=fra`.
* `source` : Plateforme source (`Guichet-Emplois`).
* `partenaire` : Partenaire émetteur (`Guichet-Emplois direct`, `Jobillico`, etc.).
* `methode_extraction` : Traçabilité de la stratégie (`Atom-XML`, `HTML-Search+RDFa-Detail`, `HTML-Search+DOM-Detail`).
* `date_extraction` : Horodatage ISO complet de la collecte.

---

## 4. Conformité, éthique et bonnes pratiques

1. **Vérification automatique de `robots.txt`** : Le collecteur interroge `robots.txt` avant toute opération réseau avec `urllib.robotparser`.
2. **Identification transparente** : Envoi systématique d'un en-tête `User-Agent` honnête identifiant le projet étudiant du Collège O'Sullivan de Québec avec courriel de contact.
3. **Respect du serveur (`crawl-delay`)** : Délai par défaut fixé à 5,0 secondes entre les requêtes vers le domaine fédéral. Un mode `--fast` (1,2s) est prévu pour le développement local.
4. **Prise en charge du code HTTP 429** : En cas de limitation de débit par le serveur, pause automatique de sécurité de 10 secondes.
5. **Protection de la vie privée** : Aucune donnée personnelle d'étudiant ou de candidat n'est collectée ni stockée.
