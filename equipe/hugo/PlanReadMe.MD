# 🧭 PLAN DE BORD DU PROJET (PlanReadMe.MD) — ESPACE HUGO

> **Rôle de ce fichier** : Ce document est la boussole et le tableau de bord modulaire du projet d'Hugo. À chaque reprise de session, sa lecture permet d'identifier instantanément :
> 1. Où nous nous situons dans le projet (**Module actif**).
> 2. Ce qui est complété, en cours ou à venir.
> 3. L'alignement continu avec les exigences du coordinateur (Grégory / cours `420-SV2-OQ`).

---

## 📍 1. Localisation actuelle dans le projet

| Indicateur | Valeur actuelle |
| :--- | :--- |
| **Module en cours** | **En pause (Fin de session)** — Prêt pour reprise sur Module 06 (Remotive) ou Module 07 (Talent) |
| **Dernière étape validée** | ✅ **Modules 04 (Jobillico) et 05 (Jobboom) entièrement réparés, filtrés 100% TI et testés en direct** |
| **Prochaine étape ciblée** | Vérification Module 06 (Remotive) / 07 (Talent) OU consolidation finale dans `ProjetFinal_V.0.0.0` |
| **Dernière mise à jour** | 22 novembre 2026 (Fin de séance) |

---

## 🗺️ 2. Matrice d'avancement modulaire

| N° | Section / Dossier | Rôle / Périmètre | Statut | Documentation associée |
| :-: | :--- | :--- | :-: | :--- |
| **01** | [`01-inventaire-des-sites/`](01-inventaire-des-sites/sites.md) | Recensement et analyse des plateformes d'emploi (QC/CA/Intl) | ✅ Terminé | [`sites.md`](01-inventaire-des-sites/sites.md) |
| **02** | [`02-preuve-de-concept-scraping/`](02-preuve-de-concept-scraping/COMPTE_RENDU_LIVRABLE_2.md) | POC initial Guichet-Emplois (Livrable 2) | ✅ Terminé | [`COMPTE_RENDU_LIVRABLE_2.md`](02-preuve-de-concept-scraping/COMPTE_RENDU_LIVRABLE_2.md) |
| **03** | [`03-Scrapping Guichet-Emploi/`](03-Scrapping Guichet-Emploi/README.md) | Collecteur Guichet-Emplois (Atom + HTML + RDFa, 100% descriptions) | ✅ Terminé | [`README.md`](03-Scrapping Guichet-Emploi/README.md) |
| **04** | [`04-Scrapping Jobillico/`](04-Scrapping Jobillico/README.md) | Collecteur dédié Jobillico Québec | ✅ Terminé | [`README.md`](04-Scrapping Jobillico/README.md) |
| **05** | [`05-Scrapping Jobboom/`](05-Scrapping Jobboom/README.md) | Collecteur dédié Jobboom (JSON-LD Schema.org) | ✅ Terminé | [`README.md`](05-Scrapping Jobboom/README.md) |
| **06** | [`06-Scrapping Remotive/`](06-Scrapping Remotive/README.md) | Collecteur API REST Remotive (Télétravail & Canada) | ✅ Terminé | [`README.md`](06-Scrapping Remotive/README.md) |
| **07** | [`07-Scrapping Talent/`](07-Scrapping Talent/README.md) | Collecteur dédié Talent.com | ✅ Terminé | [`README.md`](07-Scrapping Talent/README.md) |
| **08** | [`ProjetFinal_V.0.0.0/`](ProjetFinal_V.0.0.0/README.md) | **Cœur actuel** : Pipeline multi-sources TOP 3 (Guichet, Jobboom, Remotive) | 🟡 **Actif** | [`README.md`](ProjetFinal_V.0.0.0/README.md) |
| **09** | *Module Visualisation (À venir)* | Interface web / Dashboard de recherche et filtrage dynamique | ⏳ À venir | À créer |
| **10** | *Module Aide Candidature (À venir)* | Analyseur et bonification de CV / matching d'offres | ⏳ À venir | À créer |

---

## 📦 3. Description détaillée des modules

### [Module 01] Inventaire des sources (`01-inventaire-des-sites/`)
* **Objectif** : Identifier les sources d'emplois et de stages en TI au Québec/Canada et à l'international.
* **Fichiers clés** : [`sites.md`](01-inventaire-des-sites/sites.md).
* **Statut** : ✅ Validé dans le cadre du Livrable 1 de la classe.

### [Module 02] POC Scraping initial (`02-preuve-de-concept-scraping/`)
* **Objectif** : Première expérimentation de collecte avec extraction de 100 offres.
* **Fichiers clés** : `collecte.py`, `parsers.py`, `models.py`, `test_scraper.py`.
* **Statut** : ✅ Livrable 2 complété.

### [Modules 03 à 07] Laboratoire des connecteurs individuels
Chaque dossier contient son propre environnement autonome (`models.py`, `parsers.py`, `collecte.py`, `main.py`, `test_*.py`, `README.md`) :
* **03 — Guichet-Emploi** : Collecte en cascade (Atom $\rightarrow$ Recherche 16 métiers $\rightarrow$ RDFa). 23 assertions unitaires.
* **04 — Jobillico** : Parsing HTML des offres québécoises.
* **05 — Jobboom** : Extraction des métadonnées sémantiques `application/ld+json`.
* **06 — Remotive** : Connecteur API REST officiel filtré Canada/Remote.
* **07 — Talent.com** : Extraction et normalisation des flux d'offres.

### [Module 08] Pipeline d'unification TOP 3 (`ProjetFinal_V.0.0.0/`) — MODULE CENTRAL
* **Objectif** : Unifier le Top 3 des sources les plus fiables (Guichet-Emplois, Jobboom, Remotive) dans un modèle Pydantic unique, avec déduplication inter-sources par empreinte (`titre`, `entreprise`, `lieu`).
* **Fichiers clés** :
  * [`collecte_top3.py`](ProjetFinal_V.0.0.0/collecte_top3.py) : Moteur d'orchestration multi-sources.
  * [`models.py`](ProjetFinal_V.0.0.0/models.py) : Schéma normalisé `JobOffer`.
  * [`scrapers/`](ProjetFinal_V.0.0.0/scrapers/) : Modules spécialisés `guichet.py`, `jobboom.py`, `remotive.py`.
  * [`test_top3.py`](ProjetFinal_V.0.0.0/test_top3.py) : Tests unitaires hors ligne validant l'intégration.
  * [`data/`](ProjetFinal_V.0.0.0/data/) : Exports consolidés `offres_top3.json`, `offres_top3.csv` et rapport de collecte.
* **Statut** : 🟡 **En production (Version Beta 1)**.

### [Module 09] Interface de présentation & filtrage (Piste 3 du cours)
* **Objectif** : Fournir une interface utilisateur simple (page HTML autonome ou dashboard) pour rechercher, trier (stages, régions, salaires) et consulter les offres unifiées issues du Module 08.
* **Statut** : ⏳ Prochain jalon à planifier.

### [Module 10] Aide à la candidature & Bonification de CV (Piste 4 du cours)
* **Objectif** : Comparer un CV étudiant (format `.txt`, `.pdf`, `.docx`) avec les compétences détectées dans les offres (`competences_cles`), calculer un taux de correspondance (*matching*) et recommander des adaptations ciblées.
* **Statut** : ⏳ Jalon ultérieur.

---

## 🛡️ 4. Protocole d'alignement avec le coordinateur (Grégory)

Pour garantir que le travail d'Hugo reste parfaitement synchronisé avec les attentes du cours, Antigravity appliquera le protocole suivant :

1. **Vérification périodique du dossier de référence** :
   * Consulter régulièrement [`equipe/gregory/livrable3/`](../gregory/livrable3/README.md) et [`livrables/`](../../livrables/).
   * Vérifier que notre modèle de données (`JobOffer`) reste compatible avec le schéma commun du groupe.
2. **Règles éthiques et pédagogiques strictes** :
   * 100 % de tests unitaires hors ligne (fixtures locales, zéro requête réseau pendant les tests `unittest`).
   * Respect strict des `robots.txt` et temporisation respectueuse (`crawl-delay` de 5 s sur Guichet-Emplois).
   * Aucune tentative de contournement anti-bot/Cloudflare.
   * Encodage strict en `utf-8` (ou `utf-8-sig` pour les exports CSV Excel).
3. **Signalement d'écart** :
   * Si une nouvelle consigne de Grégory ou un nouveau livrable officiel apparaît, Antigravity le signalera immédiatement à Hugo avant de poursuivre.

---

## 🔄 5. Règles de maintien documentaire

* **Chaque modification de code** dans un module entraîne la mise à jour immédiate :
  1. Du `README.md` propre au module concerné (instructions, état, tests).
  2. Du présent fichier [`PlanReadMe.MD`](PlanReadMe.MD) (statut, indicateur de localisation, date).
  3. Du [`README.md`](README.md) racine de l'espace Hugo.
