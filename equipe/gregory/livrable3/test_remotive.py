"""
test_remotive.py - Tests unitaires 100 % hors ligne pour le connecteur Remotive bonifié.

Vérifie l'ensemble des fonctionnalités sans aucun appel réseau réel :
1. Modèle commun Pydantic JobOffer et intégrité des données Remotive.
2. Fonctions pures de nettoyage, normalisation, conversion de dates et tags techniques.
3. Moteur de classification géographique multi-niveaux (Québec, Canada, Amérique du Nord, Worldwide, Hors cible).
4. Détection native des stages via job_type == 'internship' et détection contextuelle.
5. Extraction et consolidation des compétences techniques TI.
6. Parsing d'offres individuelles et de payloads JSON complets avec filtrage.
7. Gestionnaire de cache local 24 h (fraîcheur, persistance, enveloppe de métadonnées).
8. Mode hors ligne strict (offline_mode) interdisant tout accès réseau non désiré.
9. Validation du jeu d'essai exporté dans data/offres_remotive.json.

Exécution :
    python -m unittest test_remotive.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from scrapers.remotive import (
    REMOTIVE_API_BASE_URL,
    REMOTIVE_CACHE_HOURS,
    REMOTIVE_JOBS_ENDPOINT,
    OfflineModeError,
    RemotiveError,
    RemotiveScraper,
    _normalize,
    classify_remotive_location,
    clean_text,
    extract_tech_skills,
    normalize_remotive_tags,
    parse_remotive_date,
    parse_remotive_employment_and_stage,
    parse_remotive_job,
    parse_remotive_payload,
)


# ==============================================================================
# FIXTURES LOCALES HORS LIGNE
# ==============================================================================

FIXTURE_REMOTIVE_RAW_JOB_INTERN = {
    "id": 9901,
    "url": "https://remotive.com/remote-jobs/software-development/software-intern-9901",
    "title": "Software Engineer Intern - Python / Cloud",
    "company_name": "CloudNorth Technologies",
    "category": "Software Development",
    "tags": ["python", "docker", "aws", "git"],
    "job_type": "internship",
    "publication_date": "2026-11-15T14:30:00",
    "candidate_required_location": "Canada",
    "salary": "$25/hour",
    "description": (
        "<p>We are seeking a <strong>Software Engineer Intern</strong> to join our cloud platform team. "
        "The intern will participate in developing microservices with Python, FastAPI, and Docker. "
        "Must be currently enrolled in a Computer Science or related degree.</p>"
    ),
}

FIXTURE_REMOTIVE_RAW_JOB_QUEBEC = {
    "id": 9902,
    "url": "https://remotive.com/remote-jobs/devops/devops-specialist-9902",
    "title": "Spécialiste DevOps / Kubernetes",
    "company_name": "Solutions Nuage Québec Inc.",
    "category": "Devops",
    "tags": ["kubernetes", "linux", "ci/cd", "azure"],
    "job_type": "full_time",
    "publication_date": "2026-11-14T09:15:00",
    "candidate_required_location": "Montreal, QC, Canada",
    "salary": "90 000 $ - 110 000 $ par an",
    "description": (
        "<p>Entreprise basée à Montréal recherchant un spécialiste DevOps en télétravail complet. "
        "Environnement Linux, Terraform, Kubernetes, pipelines CI/CD Azure DevOps.</p>"
    ),
}

FIXTURE_REMOTIVE_RAW_JOB_NORTH_AMERICA = {
    "id": 9903,
    "url": "https://remotive.com/remote-jobs/data/senior-data-engineer-9903",
    "title": "Senior Data Engineer",
    "company_name": "DataScale Analytics",
    "category": "Data and Analytics",
    "tags": ["postgresql", "sql", "python", "gcp"],
    "job_type": "full_time",
    "publication_date": "2026-11-13T18:00:00",
    "candidate_required_location": "USA, Canada, USA timezones",
    "salary": "$130k - $160k",
    "description": (
        "<p>Design large scale data pipelines with SQL, PostgreSQL and Google Cloud (GCP).</p>"
    ),
}

FIXTURE_REMOTIVE_RAW_JOB_WORLDWIDE = {
    "id": 9904,
    "url": "https://remotive.com/remote-jobs/software-development/fullstack-developer-9904",
    "title": "Full-Stack Web Developer",
    "company_name": "Global OpenSource Lab",
    "category": "Software Development",
    "tags": ["react", "typescript", "node", "mongodb"],
    "job_type": "contract",
    "publication_date": "2026-11-12T11:00:00",
    "candidate_required_location": "Worldwide",
    "salary": "",  # Salaire non spécifié volontairement
    "description": (
        "<p>Worldwide remote contract for a Full-Stack developer proficient in React, TypeScript and Node.js.</p>"
    ),
}

FIXTURE_REMOTIVE_RAW_JOB_USA_ONLY = {
    "id": 9905,
    "url": "https://remotive.com/remote-jobs/software-development/us-only-dev-9905",
    "title": "Backend Java Developer",
    "company_name": "US Healthcare Systems",
    "category": "Software Development",
    "tags": ["java", "spring"],
    "job_type": "full_time",
    "publication_date": "2026-11-11T10:00:00",
    "candidate_required_location": "USA only",
    "salary": "$120,000",
    "description": "<p>Must reside in the United States. US citizenship required.</p>",
}

FIXTURE_REMOTIVE_RAW_JOB_NON_TI = {
    "id": 9906,
    "url": "https://remotive.com/remote-jobs/marketing/content-writer-9906",
    "title": "Content Writer & SEO Specialist",
    "company_name": "Marketing Trends",
    "category": "Marketing",
    "tags": ["copywriting", "seo"],
    "job_type": "full_time",
    "publication_date": "2026-11-10T15:00:00",
    "candidate_required_location": "Canada",
    "salary": "$50,000",
    "description": "<p>Write marketing blog posts and improve search engine rankings.</p>",
}

FIXTURE_REMOTIVE_PAYLOAD = {
    "00-warning": "Remotive test warning",
    "0-legal-notice": "Educational testing notice",
    "job-count": 6,
    "total-job-count": 6,
    "jobs": [
        FIXTURE_REMOTIVE_RAW_JOB_INTERN,
        FIXTURE_REMOTIVE_RAW_JOB_QUEBEC,
        FIXTURE_REMOTIVE_RAW_JOB_NORTH_AMERICA,
        FIXTURE_REMOTIVE_RAW_JOB_WORLDWIDE,
        FIXTURE_REMOTIVE_RAW_JOB_USA_ONLY,
        FIXTURE_REMOTIVE_RAW_JOB_NON_TI,
    ],
}


# ==============================================================================
# TESTS UNITAIRES
# ==============================================================================

class TestJobOfferRemotiveModel(unittest.TestCase):
    """Vérifie la conformité au modèle Pydantic pivot JobOffer."""

    def test_creation_minimale_et_valeurs_remotive(self) -> None:
        offer = JobOffer(
            id="rem-9901",
            titre="Software Engineer Intern",
            url="https://remotive.com/job/9901",
            source="remotive",
        )
        self.assertEqual(offer.id, "rem-9901")
        self.assertEqual(offer.titre, "Software Engineer Intern")
        self.assertEqual(offer.source, "remotive")
        self.assertIsNone(offer.source_partenaire)
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.pays, "Canada")
        self.assertFalse(offer.est_stage)
        self.assertEqual(offer.statut_stage, "not_indicated")
        self.assertIsNone(offer.salaire)

    def test_serialisation_pydantic(self) -> None:
        offer = parse_remotive_job(FIXTURE_REMOTIVE_RAW_JOB_INTERN)
        self.assertIsNotNone(offer)
        data = offer.model_dump()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["id"], "rem-9901")
        self.assertTrue(data["est_stage"])
        self.assertEqual(data["statut_stage"], "confirmed_stage")
        self.assertEqual(data["type_poste"], "Stage")
        self.assertEqual(data["modalite"], "Télétravail")
        self.assertEqual(data["salaire"], "$25/hour")
        self.assertIn("Python", data["competences_cles"])
        self.assertIn("FastAPI", data["competences_cles"])


class TestRemotiveHelpersAndNormalizers(unittest.TestCase):
    """Vérifie les fonctions de nettoyage, normalisation et compétences."""

    def test_clean_text(self) -> None:
        html_input = "<p>Recherche <strong>développeur</strong> &amp; architecte &nbsp; Cloud.</p>"
        result = clean_text(html_input)
        self.assertEqual(result, "Recherche développeur & architecte Cloud.")
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(None), "")

    def test_normalize(self) -> None:
        self.assertEqual(_normalize("Montréal (QC)"), "montreal (qc)")
        self.assertEqual(_normalize("Développeur Émérite"), "developpeur emerite")

    def test_parse_remotive_date(self) -> None:
        self.assertEqual(parse_remotive_date("2026-11-15T14:30:00"), "2026-11-15")
        self.assertEqual(parse_remotive_date("2026-11-09"), "2026-11-09")
        self.assertIsNone(parse_remotive_date(""))
        self.assertIsNone(parse_remotive_date(None))
        self.assertIsNone(parse_remotive_date("invalid-date"))

    def test_normalize_remotive_tags(self) -> None:
        raw_tags = ["python", "k8s", "docker", "reactjs", "unknown_tag_xyz", "aws"]
        norm = normalize_remotive_tags(raw_tags)
        self.assertIn("Python", norm)
        self.assertIn("Kubernetes", norm)
        self.assertIn("Docker", norm)
        self.assertIn("React", norm)
        self.assertIn("AWS", norm)
        self.assertNotIn("unknown_tag_xyz", norm)

    def test_extract_tech_skills(self) -> None:
        text = "Poste fullstack avec Python, React, PostgreSQL et conteneurs Docker sous Linux."
        skills = extract_tech_skills(text)
        self.assertIn("Python", skills)
        self.assertIn("React", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertIn("Docker", skills)
        self.assertIn("Linux", skills)


class TestRemotiveLocationClassification(unittest.TestCase):
    """Vérifie le moteur de classification géographique multi-niveaux."""

    def test_quebec_targeted_location(self) -> None:
        locs = ["Montreal, QC, Canada", "Quebec, Canada", "Laval, QC", "Remote - Montréal"]
        for loc in locs:
            res = classify_remotive_location(loc)
            self.assertTrue(res["is_canada_eligible"], f"Échec pour {loc}")
            self.assertEqual(res["geo_level"], "quebec")
            self.assertEqual(res["province"], "QC")
            self.assertEqual(res["pays"], "Canada")
            self.assertIn("Québec", res["lieu"])

    def test_canada_specific_provinces(self) -> None:
        res_on = classify_remotive_location("Toronto, Ontario, Canada")
        self.assertTrue(res_on["is_canada_eligible"])
        self.assertEqual(res_on["geo_level"], "canada")
        self.assertEqual(res_on["province"], "ON")

        res_bc = classify_remotive_location("Vancouver, British Columbia")
        self.assertTrue(res_bc["is_canada_eligible"])
        self.assertEqual(res_bc["geo_level"], "canada")
        self.assertEqual(res_bc["province"], "BC")

    def test_canada_general_location(self) -> None:
        res = classify_remotive_location("Canada")
        self.assertTrue(res["is_canada_eligible"])
        self.assertEqual(res["geo_level"], "canada")
        self.assertEqual(res["province"], "QC")
        self.assertEqual(res["lieu"], "Canada (Télétravail)")

    def test_north_america_location(self) -> None:
        locs = ["USA, Canada, USA timezones", "North America", "Americas", "USA or Canada"]
        for loc in locs:
            res = classify_remotive_location(loc)
            self.assertTrue(res["is_canada_eligible"], f"Échec pour {loc}")
            self.assertEqual(res["geo_level"], "north_america")
            self.assertEqual(res["province"], "QC")
            self.assertIn("Amérique du Nord", res["lieu"])

    def test_worldwide_location(self) -> None:
        locs = ["Worldwide", "Anywhere", "Remote worldwide", "", None]
        for loc in locs:
            res = classify_remotive_location(loc)
            self.assertTrue(res["is_canada_eligible"], f"Échec pour {loc}")
            self.assertEqual(res["geo_level"], "worldwide")
            self.assertEqual(res["province"], "QC")
            self.assertEqual(res["lieu"], "Télétravail mondial")

    def test_excluded_third_party_countries(self) -> None:
        locs = ["USA only", "United States", "UK only", "Germany", "LATAM, Europe"]
        for loc in locs:
            res = classify_remotive_location(loc)
            self.assertFalse(res["is_canada_eligible"], f"Ne devrait pas être éligible Canada : {loc}")
            self.assertEqual(res["geo_level"], "other")
            self.assertEqual(res["province"], "Hors Canada")


class TestRemotiveStageAndEmploymentParsing(unittest.TestCase):
    """Vérifie la détection native et contextuelle des stages et types de contrat."""

    def test_stage_confirme_via_job_type_internship(self) -> None:
        raw_job = {"job_type": "internship", "title": "Software Developer"}
        type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(raw_job, "")
        self.assertTrue(est_stage)
        self.assertEqual(statut_stage, "confirmed_stage")
        self.assertEqual(type_poste, "Stage")

    def test_stage_confirme_via_job_type_intern(self) -> None:
        raw_job = {"job_type": "intern", "title": "QA Engineer"}
        type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(raw_job, "")
        self.assertTrue(est_stage)
        self.assertEqual(statut_stage, "confirmed_stage")
        self.assertEqual(type_poste, "Stage")

    def test_stage_confirme_via_titre(self) -> None:
        raw_job = {"job_type": "full_time", "title": "Stagiaire Développeur Python"}
        type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(raw_job, "")
        self.assertTrue(est_stage)
        self.assertEqual(statut_stage, "confirmed_stage")
        self.assertEqual(type_poste, "Stage")

    def test_stage_possible_dans_description(self) -> None:
        raw_job = {"job_type": "full_time", "title": "Junior Developer"}
        desc = "Opportunity for students currently enrolled in computer science. Student intern placement."
        type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(raw_job, desc)
        self.assertTrue(est_stage)
        self.assertEqual(statut_stage, "possible_stage")

    def test_contrats_standards_non_stages(self) -> None:
        cas = [
            ("full_time", "Temps plein"),
            ("part_time", "Temps partiel"),
            ("contract", "Contrat"),
            ("freelance", "Pigiste / Freelance"),
        ]
        for code, attendu in cas:
            type_poste, est_stage, statut_stage = parse_remotive_employment_and_stage(
                {"job_type": code, "title": "Regular Developer"},
                "Normal software engineer job description."
            )
            self.assertEqual(type_poste, attendu)
            self.assertFalse(est_stage)
            self.assertEqual(statut_stage, "not_indicated")


class TestRemotiveJobAndPayloadParsing(unittest.TestCase):
    """Vérifie la transformation de jobs bruts et de payloads complets."""

    def test_parse_remotive_job_complet(self) -> None:
        offer = parse_remotive_job(FIXTURE_REMOTIVE_RAW_JOB_INTERN)
        self.assertIsNotNone(offer)
        self.assertEqual(offer.id, "rem-9901")
        self.assertEqual(offer.titre, "Software Engineer Intern - Python / Cloud")
        self.assertEqual(offer.entreprise, "CloudNorth Technologies")
        self.assertEqual(offer.lieu, "Canada (Télétravail)")
        self.assertEqual(offer.province, "QC")
        self.assertEqual(offer.pays, "Canada")
        self.assertEqual(offer.modalite, "Télétravail")
        self.assertEqual(offer.type_poste, "Stage")
        self.assertTrue(offer.est_stage)
        self.assertEqual(offer.statut_stage, "confirmed_stage")
        self.assertEqual(offer.salaire, "$25/hour")
        self.assertEqual(offer.date_publication, "2026-11-15")
        self.assertIn("Python", offer.competences_cles)
        self.assertIn("FastAPI", offer.competences_cles)
        self.assertIn("Docker", offer.competences_cles)
        self.assertIn("AWS", offer.competences_cles)
        self.assertIn("Git", offer.competences_cles)

    def test_parse_remotive_job_sans_salaire(self) -> None:
        offer = parse_remotive_job(FIXTURE_REMOTIVE_RAW_JOB_WORLDWIDE)
        self.assertIsNotNone(offer)
        self.assertIsNone(offer.salaire, "Le salaire doit rester None quand non mentionné")
        self.assertEqual(offer.type_poste, "Contrat")
        self.assertEqual(offer.lieu, "Télétravail mondial")

    def test_parse_remotive_job_invalide(self) -> None:
        self.assertIsNone(parse_remotive_job({}))
        self.assertIsNone(parse_remotive_job({"id": 123}))  # Titre manquant
        self.assertIsNone(parse_remotive_job("pas un dict"))

    def test_parse_payload_filtrage_canada_eligible(self) -> None:
        # Doit conserver Intern (Canada), Québec (Montréal), North America (USA, Canada), Worldwide
        # Doit exclure USA only (inaccessible aux Canadiens) et Content Writer (non-TI)
        offers = parse_remotive_payload(
            FIXTURE_REMOTIVE_PAYLOAD,
            geo_filter="canada_eligible",
            category_filter=True,
            stage_only=False,
        )
        offer_ids = [o.id for o in offers]
        self.assertIn("rem-9901", offer_ids)  # Intern (Canada)
        self.assertIn("rem-9902", offer_ids)  # Québec (Montréal)
        self.assertIn("rem-9903", offer_ids)  # North America
        self.assertIn("rem-9904", offer_ids)  # Worldwide
        self.assertNotIn("rem-9905", offer_ids)  # USA only
        self.assertNotIn("rem-9906", offer_ids)  # Marketing / non-TI

    def test_parse_payload_filtrage_canada_only(self) -> None:
        offers = parse_remotive_payload(
            FIXTURE_REMOTIVE_PAYLOAD,
            geo_filter="canada_only",
            category_filter=True,
        )
        offer_ids = [o.id for o in offers]
        self.assertIn("rem-9901", offer_ids)  # Canada strict
        self.assertIn("rem-9902", offer_ids)  # Montréal strict
        self.assertNotIn("rem-9903", offer_ids)  # North America exclu
        self.assertNotIn("rem-9904", offer_ids)  # Worldwide exclu

    def test_parse_payload_filtrage_quebec_only(self) -> None:
        offers = parse_remotive_payload(
            FIXTURE_REMOTIVE_PAYLOAD,
            geo_filter="quebec_only",
            category_filter=True,
        )
        offer_ids = [o.id for o in offers]
        self.assertEqual(offer_ids, ["rem-9902"])  # Uniquement Montréal

    def test_parse_payload_stage_only(self) -> None:
        offers = parse_remotive_payload(
            FIXTURE_REMOTIVE_PAYLOAD,
            geo_filter="canada_eligible",
            stage_only=True,
        )
        offer_ids = [o.id for o in offers]
        self.assertEqual(offer_ids, ["rem-9901"])
        self.assertTrue(offers[0].est_stage)

    def test_parse_payload_avec_limite(self) -> None:
        offers = parse_remotive_payload(
            FIXTURE_REMOTIVE_PAYLOAD,
            geo_filter="canada_eligible",
            limit=2,
        )
        self.assertEqual(len(offers), 2)

    def test_parse_payload_erreurs_structurelles(self) -> None:
        with self.assertRaises(ValueError):
            parse_remotive_payload("non un dictionnaire")
        with self.assertRaises(ValueError):
            parse_remotive_payload({"sans_liste_jobs": True})


class TestRemotiveCacheAndOfflineScraper(unittest.TestCase):
    """Vérifie le gestionnaire de cache local 24 h et le mode hors ligne."""

    def test_lecture_et_ecriture_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, cache_hours=24)
            cache_file = scraper.get_cache_file()
            self.assertFalse(cache_file.exists())

            # Sauvegarde d'un payload test
            test_payload = {"jobs": [FIXTURE_REMOTIVE_RAW_JOB_INTERN]}
            scraper.save_to_cache(cache_file, test_payload, REMOTIVE_JOBS_ENDPOINT)

            self.assertTrue(cache_file.exists())
            self.assertTrue(scraper.is_cache_fresh(cache_file))

            # Relecture
            loaded = scraper.load_from_cache(cache_file)
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded["jobs"]), 1)
            self.assertEqual(loaded["jobs"][0]["id"], 9901)

    def test_expiration_du_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, cache_hours=24)
            cache_file = scraper.get_cache_file()

            # Écriture d'un cache vieux de 25 heures
            old_time = datetime.now(timezone.utc) - timedelta(hours=25)
            envelope = {
                "fetched_at": old_time.isoformat(),
                "request_url": REMOTIVE_JOBS_ENDPOINT,
                "payload": {"jobs": []},
            }
            cache_file.write_text(json.dumps(envelope), encoding="utf-8")

            # Le cache doit être détecté comme expiré
            self.assertFalse(scraper.is_cache_fresh(cache_file))

    def test_offline_mode_bloque_appels_reseau_si_cache_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, offline_mode=True)
            with self.assertRaises(OfflineModeError):
                scraper.fetch_payload(refresh=False)

    def test_offline_mode_utilise_cache_frais_sans_reseau(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, offline_mode=True)
            cache_file = scraper.get_cache_file()

            # On pré-remplit le cache avec la fixture
            scraper.save_to_cache(cache_file, FIXTURE_REMOTIVE_PAYLOAD, REMOTIVE_JOBS_ENDPOINT)

            # En mode offline, fetch_payload doit fonctionner et retourner les données
            payload = scraper.fetch_payload()
            self.assertEqual(len(payload["jobs"]), 6)

            # Et scrape_offers doit retourner les offres sans aucune requête réseau
            offers = scraper.scrape_offers(geo_filter="canada_eligible")
            self.assertEqual(len(offers), 4)

    @patch("scrapers.remotive.requests.get")
    def test_fetch_payload_reseau_avec_mock(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = FIXTURE_REMOTIVE_PAYLOAD
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, offline_mode=False)
            payload = scraper.fetch_payload(refresh=True)

            self.assertEqual(payload, FIXTURE_REMOTIVE_PAYLOAD)
            mock_get.assert_called_once()
            # Vérification de l'enregistrement automatique du cache
            cache_file = scraper.get_cache_file()
            self.assertTrue(scraper.is_cache_fresh(cache_file))

    @patch("scrapers.remotive.requests.get")
    def test_gestion_erreur_http_429(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            scraper = RemotiveScraper(cache_dir=tmp_dir, offline_mode=False)
            with self.assertRaises(RemotiveError) as ctx:
                scraper.fetch_payload(refresh=True)
            self.assertIn("HTTP 429", str(ctx.exception))


class TestRemotiveDatasetValidation(unittest.TestCase):
    """Vérifie l'intégrité et la validité du jeu d'essai data/offres_remotive.json."""

    def test_jeu_dessai_exporte(self) -> None:
        dataset_path = Path(__file__).resolve().parent / "data" / "offres_remotive.json"
        if not dataset_path.exists():
            self.skipTest("Le fichier data/offres_remotive.json n'est pas encore généré.")

        content = dataset_path.read_text(encoding="utf-8")
        raw_list = json.loads(content)
        self.assertIsInstance(raw_list, list)
        self.assertGreater(len(raw_list), 0, "Le jeu d'essai Remotive ne doit pas être vide.")

        for item in raw_list:
            offer = JobOffer.model_validate(item)
            self.assertEqual(offer.source, "remotive")
            self.assertEqual(offer.modalite, "Télétravail")
            self.assertTrue(offer.id.startswith("rem-"))
            self.assertTrue(offer.url.startswith("http"))
            self.assertIsNotNone(offer.titre)
            self.assertGreater(len(offer.titre), 0)
            self.assertIn(offer.statut_stage, ["confirmed_stage", "possible_stage", "not_indicated"])


if __name__ == "__main__":
    unittest.main()
