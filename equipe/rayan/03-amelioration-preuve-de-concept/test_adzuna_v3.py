"""Tests unitaires 100 % hors ligne pour le Livrable 3 — Amélioration du POC Adzuna Canada.

Vérifie :
1. Les deux offres SODEC avec le salaire suspect à 1 $ remplacé par la fourchette extraite
   du texte (sans écraser `api_salary_min = 1.0`, avec provenance et anomalie documentées).
2. Les fourchettes annuelles en français (`92 000$ à 115 000$`) et en anglais
   (`CAD 108,100 - CAD 222,800 - yearly`, `CA$110,600.00–CA$166,000.00 yearly`).
3. Les taux horaires (`28,40 à 40,88 $/heure`, `$70- $110 per hour`, `$45.00hr - $50.00hr`)
   et l'équivalence probable 2 080 h/an entre l'API (`93600 - 104000`) et le texte (`45 - 50 $/h`).
4. Les nombres avec espaces, virgules et décimales (`Base (min.): 31.51 Base (max.): 57.81`
   sans capturer `Réf n°: 4955` ni `80` heures).
5. Les salaires sans période explicite (`salary$100000 - $120000statusPermanent`, `Up to $210,000`)
   où `periode_salaire` doit rester `None`.
6. Les grilles salariales à plusieurs niveaux (BCG X : 4 échelons) avec anomalie explicite.
7. L'absence de faux positifs sur « permanente » (`vision de détention permanente`),
   « mandat » (`2 mandats ... au cours des 6 dernières années`) et « intern » (`international`, `internes`).
8. La détection des stages (`stage de 3 mois`, `Stage en développement Web`), remplacements
   (`Remplacement congé de maternité`), contrats à durée déterminée (`12 mois`, `6-12 mois`, `2 ans`),
   pigistes et cas mixtes (`Type: Permanent or Long Term Contract`).
9. La distinction stricte entre temps partiel (`2 à 3 jours par semaine`) et modalité hybride
   (`Hybrid work: 2 days in the office per week`, `2 jours/semaine au bureau de Québec`).
10. Les heures par période de paie (`80`) conservées avec l'unité `"période de paie"` sans conversion
    injustifiée en `40 h/semaine`.
11. La normalisation géographique de `location.area` (distinction entre `["Canada", "Québec"]` = province
    et `["Canada", "Québec", "Québec City"]` = ville de Québec / Capitale-Nationale).
12. La résilience HTTP (retry sur 503/429) et le masquage systématique des clés API (`app_id=***`).
13. La déduplication des 321 annonces des 10 fichiers du Livrable 2 vers les 229 offres uniques.

Exécution :
    python -m unittest discover -s equipe/rayan/03-amelioration-preuve-de-concept -p "test_*.py" -v
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from collecteur import (
    ClientAdzuna,
    DOSSIER_SORTIE_L2,
    ErreurCollecteAdzuna,
    charger_reponses_locales,
    masquer_secrets,
)
from extraction_texte import (
    convertir_montant,
    extraire_conditions_texte,
    extraire_salaire_texte,
)
from models import CHAMPS_FORMAT_COMMUN
from normalisation import (
    construire_offre_adzuna,
    extraire_competences_ti,
    normaliser_lieu_adzuna,
    verifier_pertinence_ti,
)
from pipeline import (
    exporter_csv_enrichi,
    exporter_format_commun_json,
    exporter_json_enrichi,
    executer_pipeline_documents,
)


class _FausseReponseHTTP:
    """Simule un objet `requests.Response` pour tester `ClientAdzuna` 100 % hors ligne."""

    def __init__(self, status_code: int, payload: dict | None = None, url: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.url = url

    def json(self) -> dict:
        return self._payload


class _FausseSessionHTTP:
    """Simule une séquence de réponses ou d'exceptions HTTP sans aucun accès réseau."""

    def __init__(self, reponses: list[object]) -> None:
        self.reponses = list(reponses)
        self.appels = 0

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 20):
        self.appels += 1
        item = self.reponses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestExtractionSalairesAdzuna(unittest.TestCase):
    """Vérifie l'extraction salariale déterministe, la provenance et la détection des anomalies."""

    def test_offres_sodec_salaire_api_1_dollar_suspect(self) -> None:
        """Les 2 offres SODEC ont `salary_min=1` dans l'API et `56 647 $ à 103 015 $` dans le texte."""
        raw_sodec = {
            "id": "5965086256",
            "title": "Programmeuse, programmeur - analyste",
            "company": {"display_name": "SODEC"},
            "location": {"display_name": "Montréal, Québec", "area": ["Canada", "Québec", "Montréal"]},
            "salary_min": 1,
            "salary_max": None,
            "contract_type": "contract",
            "contract_time": None,
            "description": (
                "TITRE : Programmeuse, programmeur - analyste LIEU DE TRAVAIL : Montréal "
                "DURÉE DU CONTRAT : 12 mois SALAIRE : Minimum : 56 647 $ Maximum : 103 015 $ "
                "La SODEC conjugue les mondes de la culture et de l’économie..."
            ),
            "redirect_url": "https://www.adzuna.ca/details/5965086256",
        }
        offre = construire_offre_adzuna(raw_sodec, mot_cle_recherche="programmeur", ville_recherche="Montréal, Québec")

        # 1. La valeur API brute 1.0 n'est pas effacée silencieusement
        self.assertEqual(offre.api_salary_min, 1.0)
        self.assertIsNone(offre.api_salary_max)

        # 2. Le texte extrait la vraie fourchette (et ne capture pas "12" de "12 mois" !)
        self.assertEqual(offre.texte_salaire_min, 56647.0)
        self.assertEqual(offre.texte_salaire_max, 103015.0)
        self.assertEqual(offre.texte_devise, "$")
        self.assertIsNone(offre.texte_periode_salaire)  # Période non écrite, donc non devinée

        # 3. Les valeurs consolidées prennent la description avec provenance et anomalie explicites
        self.assertEqual(offre.salaire_min, 56647.0)
        self.assertEqual(offre.salaire_max, 103015.0)
        self.assertEqual(offre.provenance_salaire, "description_remplace_api_suspect")
        self.assertTrue(any("salaire_api_suspect" in a for a in offre.anomalies))
        self.assertTrue(any("arbitrage_salaire" in a for a in offre.anomalies))

        # 4. La durée du contrat "12 mois" est bien extraite dans le champ contrat
        self.assertEqual(offre.duree_contrat, "12 mois")
        self.assertEqual(offre.type_contrat, "Contrat")
        self.assertEqual(offre.provenance_contrat, "api+description")

    def test_fourchettes_annuelles_francais_et_anglais(self) -> None:
        """Vérifie les fourchettes annuelles en français (`92 000$ à 115 000$`) et en anglais (`CAD`, `CA$`, `.00`)."""
        # Français (Eaton 5961958806)
        s_fr = extraire_salaire_texte(
            "Développeur(euse) Full Stack Sénior",
            "La fourchette salariale annuelle prévue pour ce poste est de 92 000$ à 115 000$.",
        )
        self.assertEqual(s_fr.salaire_min, 92000.0)
        self.assertEqual(s_fr.salaire_max, 115000.0)
        self.assertEqual(s_fr.devise, "$")
        self.assertEqual(s_fr.periode, "année")

        # Anglais SAP (5967041166)
        s_en1 = extraire_salaire_texte(
            "Senior Developer",
            "Compensation: CAD 108,100 - CAD 222,800 - yearly Company Description...",
        )
        self.assertEqual(s_en1.salaire_min, 108100.0)
        self.assertEqual(s_en1.salaire_max, 222800.0)
        self.assertEqual(s_en1.devise, "CAD")
        self.assertEqual(s_en1.periode, "année")

        # Anglais avec CA$, décimales .00 et tiret demi-cadratin (5967040238)
        s_en2 = extraire_salaire_texte(
            "Senior Solution Architect - Data & AI",
            "Full-time Remote Salary: CA$110,600.00–CA$166,000.00 yearly Core responsibilities...",
        )
        self.assertEqual(s_en2.salaire_min, 110600.0)
        self.assertEqual(s_en2.salaire_max, 166000.0)
        self.assertEqual(s_en2.devise, "CAD")
        self.assertEqual(s_en2.periode, "année")

    def test_taux_horaires_et_echelle_publique(self) -> None:
        """Vérifie l'extraction des taux horaires sans capturer les numéros d'échelle ou de référence."""
        # Secteur public (5902583221) : ne doit pas capturer 4278 ni 35 h/semaine
        s_pub = extraire_salaire_texte(
            "Technicienne ou technicien en informatique",
            "T-4278-070-2627-91689 STATUT : Remplacement congé de maternité - 35 h/semaine "
            "CORPS D'EMPLOI – ÉCHELLE : 4278 - 28,40 à 40,88 $/heure",
        )
        self.assertEqual(s_pub.salaire_min, 28.40)
        self.assertEqual(s_pub.salaire_max, 40.88)
        self.assertEqual(s_pub.devise, "$")
        self.assertEqual(s_pub.periode, "heure")

        # Anglais avec "Duration: 12 months" avant "$70- $110 per hour" (5967039563)
        s_sf = extraire_salaire_texte(
            "Salesforce Consultant",
            "Employment Type: Contract Duration: 12 months Compensation Range: $70- $110 per hour",
        )
        self.assertEqual(s_sf.salaire_min, 70.0)
        self.assertEqual(s_sf.salaire_max, 110.0)
        self.assertEqual(s_sf.devise, "$")
        self.assertEqual(s_sf.periode, "heure")

    def test_equivalence_probable_annuel_api_et_horaire_texte_2080h(self) -> None:
        """Sur l'offre 5966889227, API=(93600, 104000) équivaut à Texte=($45.00hr - $50.00hr) * 2080 h/an."""
        raw_cynet = {
            "id": "5966889227",
            "title": "Senior Capital Markets Support Engineer",
            "company": {"display_name": "CYNET SYSTEMS"},
            "location": {"display_name": "Montréal, Québec", "area": ["Canada", "Québec", "Montréal"]},
            "salary_min": 93600,
            "salary_max": 104000,
            "description": "Job Description \\n Pay Range: $45.00hr - $50.00hr \\n\\n Job Overview...",
            "redirect_url": "https://www.adzuna.ca/details/5966889227",
        }
        offre = construire_offre_adzuna(raw_cynet)

        # Les deux valeurs (API et texte) sont conservées intactes
        self.assertEqual(offre.api_salary_min, 93600.0)
        self.assertEqual(offre.api_salary_max, 104000.0)
        self.assertEqual(offre.texte_salaire_min, 45.0)
        self.assertEqual(offre.texte_salaire_max, 50.0)
        self.assertEqual(offre.texte_periode_salaire, "heure")

        # La provenance signale l'équivalence probable sous l'hypothèse explicite de 2080 h/an
        self.assertEqual(offre.provenance_salaire, "equivalence_probable_annuel_horaire_2080h")
        self.assertTrue(any("equivalence_probable_annuel_horaire_2080h" in a for a in offre.anomalies))

    def test_nombres_base_min_max_sans_devise_ni_periode(self) -> None:
        """Vérifie l'extraction de `Base (min.): 31.51 Base (max.): 57.81` (CIUSSS 5809893189)."""
        s_ciusss = extraire_salaire_texte(
            "Analyste spécialisé.e en informatique - Réseautique",
            "Réf n°: 4955 Statut de l'emploi: Permanent à temps plein Quart de travail: Jour "
            "Nombre d’heures par période de paie: 80 Base (min.): 31.51 Base (max.): 57.81",
        )
        self.assertEqual(s_ciusss.salaire_min, 31.51)
        self.assertEqual(s_ciusss.salaire_max, 57.81)
        self.assertIsNone(s_ciusss.devise)
        self.assertIsNone(s_ciusss.periode)  # Période non écrite -> None

    def test_salaires_sans_periode_explicite_ni_espaces(self) -> None:
        """Vérifie que `salary$100000 - $120000statusPermanent` et `Up to $210,000` gardent `periode=None`."""
        s_colle = extraire_salaire_texte(
            "Senior Software Developer",
            "ref. no.1001355-1typeHybridlocationMontréal, QCsalary$100000 - $120000statusPermanent",
        )
        self.assertEqual(s_colle.salaire_min, 100000.0)
        self.assertEqual(s_colle.salaire_max, 120000.0)
        self.assertEqual(s_colle.devise, "$")
        self.assertIsNone(s_colle.periode)

        s_plafond = extraire_salaire_texte(
            "Platform Engineer - $210,000 bonus! (Fintech)",
            "Salary – Up to $210,000 an exceptional bonus and package",
        )
        self.assertIsNone(s_plafond.salaire_min)
        self.assertEqual(s_plafond.salaire_max, 210000.0)
        self.assertEqual(s_plafond.type_mention, "plafond")
        self.assertIsNone(s_plafond.periode)

    def test_grille_salariale_multi_niveaux_bcg(self) -> None:
        """Vérifie que la grille BCG X à 4 échelons conserve les 4 paliers et signale l'ambiguïté."""
        raw_bcg = {
            "id": "5964819008",
            "title": "Forward Deployed AI Engineer, Canada - BCG X",
            "company": {"display_name": "BCG"},
            "location": {"display_name": "Montréal, Québec", "area": ["Canada", "Québec", "Montréal"]},
            "description": (
                "The First-year Base Compensation For This Role Is "
                "Forward Deployed AI Engineer I: $110,000 CAD "
                "Forward Deployed AI Engineer II: $150,000 CAD "
                "Forward Deployed AI Engineer III: $157,000 CAD "
                "Senior Forward Deployed AI Engineer : $210,000 CAD"
            ),
            "redirect_url": "https://www.adzuna.ca/details/5964819008",
        }
        offre = construire_offre_adzuna(raw_bcg)
        self.assertEqual(offre.texte_type_mention_salaire, "grille_multi_niveaux")
        self.assertEqual(offre.texte_paliers_salariaux, [110000.0, 150000.0, 157000.0, 210000.0])
        self.assertEqual(offre.provenance_salaire, "description_grille_multi_niveaux")
        self.assertTrue(any("grille_salariale_multi_niveaux" in a for a in offre.anomalies))


class TestExtractionContratsHorairesModalites(unittest.TestCase):
    """Vérifie la séparation contrat / horaire / modalité et le rejet des faux positifs."""

    def test_exclusion_faux_positifs_permanente_mandat_intern(self) -> None:
        """Les mentions 'détention permanente', '2 mandats au cours des 6 dernières années' et 'international'/'internes' ne sont pas des contrats."""
        # 1. "vision de détention permanente" (Valsoft 5963224399)
        c_valsoft = extraire_conditions_texte(
            "Développeur(se) logiciel IA",
            "Valsoft acquiert et exploite des sociétés de logiciels avec une vision de détention permanente.",
        )
        self.assertIsNone(c_valsoft.type_contrat)

        # 2. "2 mandats ... au cours des 6 dernières années" (5636065186)
        c_mandats_passes = extraire_conditions_texte(
            "Technicien en soutien aux utilisateurs",
            "Avoir réalisé, à titre de technicien en soutien aux utilisateurs, 2 mandats d’une envergure "
            "de plus de 220 jours/personnes au cours des 6 dernières années.",
        )
        self.assertIsNone(c_mandats_passes.type_contrat)
        self.assertIsNone(c_mandats_passes.duree_contrat)

        # 3. "internationaux" / "équipes internes" (5963511212, 5967041356)
        c_intern = extraire_conditions_texte(
            "Senior Software Engineer",
            "Elle fournit les fonctionnalités de base à toutes les équipes internes et studios internationaux.",
        )
        self.assertIsNone(c_intern.type_contrat)

    def test_detection_stages_remplacements_contrats_et_cas_mixtes(self) -> None:
        """Vérifie l'extraction précise des stages, remplacements, durées de contrat et cas hybrides."""
        # Stage avec durée (5909547315)
        c_stage = extraire_conditions_texte(
            "DÉVELOPPEUR WEB BACK-END — STAGE (2026-2027)",
            "Workland offre un stage de 3 mois à titre de développeur web back-end.",
        )
        self.assertEqual(c_stage.type_contrat, "Stage")
        self.assertEqual(c_stage.duree_contrat, "3 mois")

        # Remplacement congé de maternité + 35 h/semaine (5902583221)
        c_remp = extraire_conditions_texte(
            "Technicien en informatique",
            "STATUT : Remplacement congé de maternité - 35 h/semaine",
        )
        self.assertEqual(c_remp.type_contrat, "Remplacement")
        self.assertEqual(c_remp.heures_valeur, 35.0)
        self.assertEqual(c_remp.heures_unite, "semaine")

        # Contrat de 2 ans à temps plein (5961247397)
        c_2ans = extraire_conditions_texte(
            "Analyste spécialisé en informatique",
            "pour combler un contrat à temps plein (35 heures par semaine) d'une durée de 2 ans.",
        )
        self.assertEqual(c_2ans.type_contrat, "Contrat")
        self.assertEqual(c_2ans.duree_contrat, "2 ans")
        self.assertEqual(c_2ans.horaire, "Temps plein")
        self.assertEqual(c_2ans.heures_valeur, 35.0)
        self.assertEqual(c_2ans.heures_unite, "semaine")

        # Cas mixte "Permanent or Long Term Contract" (5966870717)
        c_mixte = extraire_conditions_texte(
            "AI Application Modernization Architect/Lead",
            "Role: AI Application Modernization Architect/Lead \\n Type: Permanent or Long Term Contract",
        )
        self.assertEqual(c_mixte.type_contrat, "Permanent ou Contrat")

    def test_distinction_temps_partiel_vs_modalite_hybride(self) -> None:
        """Une modalité hybride ('2 jours/semaine au bureau') ne doit jamais être prise pour un temps partiel."""
        # Modalité hybride 2 jours/semaine au bureau (5961958830)
        c_hyb = extraire_conditions_texte(
            "ADMINISTRATEUR SYSTÈMES (SYSADMIN) MIDDLEWARE IIS Québec (hybride)",
            "dans le cadre d'un poste permanent. Ce poste est en mode hybride. 2 jours/semaine au bureau de Québec.",
        )
        self.assertEqual(c_hyb.type_contrat, "Permanent")
        self.assertEqual(c_hyb.modalite, "Hybride")
        self.assertIn("2 jours/semaine au bureau", c_hyb.details_modalite or "")
        self.assertIsNone(c_hyb.horaire)  # Aucun temps partiel inventé !

        # Vrai temps partiel + pigiste (5961954850)
        c_partiel = extraire_conditions_texte(
            "Expert en cybersécurité",
            "recherche d’un(e) Spécialiste en cybersécurité pour un temps partiel (2 à 3 jours par semaine). "
            "Pigiste/consultant(e) sont bienvenu(e)s. Télétravail et présentiel.",
        )
        self.assertEqual(c_partiel.horaire, "Temps partiel")
        self.assertIn("2 à 3 jours par semaine", c_partiel.details_horaire or "")
        self.assertEqual(c_partiel.type_contrat, "Pigiste / Consultant")
        self.assertEqual(c_partiel.modalite, "Hybride")

    def test_heures_periode_de_paie_sans_conversion_injustifiee(self) -> None:
        """80 heures par période de paie reste à `80.0` avec l'unité `'période de paie'` (jamais converti en 40 h/semaine)."""
        c_paie = extraire_conditions_texte(
            "Analyste spécialisé.e en informatique",
            "Statut de l'emploi: Permanent à temps plein Quart de travail: Jour "
            "Nombre d’heures par période de paie: 80",
        )
        self.assertEqual(c_paie.type_contrat, "Permanent")
        self.assertEqual(c_paie.horaire, "Temps plein")
        self.assertEqual(c_paie.heures_valeur, 80.0)
        self.assertEqual(c_paie.heures_unite, "période de paie")


class TestNormalisationGeographiqueEtPertinenceTI(unittest.TestCase):
    """Vérifie la normalisation géographique (`location.area` + régions QC) et le filtrage TI."""

    def test_distinction_quebec_province_vs_quebec_ville(self) -> None:
        """`['Canada', 'Québec']` est la province entière, tandis que `['Canada', 'Québec', 'Québec City']` est la ville."""
        lieu_prov = normaliser_lieu_adzuna(
            {"display_name": "Québec, Canada", "area": ["Canada", "Québec"]},
            latitude=None,
            longitude=None,
        )
        self.assertIsNone(lieu_prov["ville"])
        self.assertIsNone(lieu_prov["region_administrative"])
        self.assertEqual(lieu_prov["province"], "QC")
        self.assertEqual(lieu_prov["precision_lieu"], "province")

        lieu_ville = normaliser_lieu_adzuna(
            {"display_name": "Beauport, Québec City", "area": ["Canada", "Québec", "Québec City", "Beauport"]},
            latitude=46.86,
            longitude=-71.19,
        )
        self.assertEqual(lieu_ville["ville"], "Québec")
        self.assertEqual(lieu_ville["arrondissement_ou_mrc"], "Beauport")
        self.assertEqual(lieu_ville["region_administrative"], "Capitale-Nationale")
        self.assertEqual(lieu_ville["precision_lieu"], "ville")

        lieu_5_niv = normaliser_lieu_adzuna(
            {"display_name": "Brossard, Champlain", "area": ["Canada", "Québec", "Montérégie", "Champlain", "Brossard"]},
        )
        self.assertEqual(lieu_5_niv["ville"], "Brossard")
        self.assertEqual(lieu_5_niv["region_administrative"], "Montérégie")
        self.assertEqual(lieu_5_niv["precision_lieu"], "ville")

    def test_pertinence_ti_et_competences_sans_faux_positifs(self) -> None:
        """Vérifie l'exclusion d'Actuarial Analyst / Chauffeur et l'inclusion d'Administrateur.trice systèmes."""
        ok_act, _ = verifier_pertinence_ti(
            "Actuarial Analyst",
            "Notre client cherche actuellement un analyste-programmeur pour un poste permanent.",
        )
        self.assertFalse(ok_act)

        ok_chauf, _ = verifier_pertinence_ti("Chauffeur classe 1 -Plancher mobile", "")
        self.assertFalse(ok_chauf)

        ok_sys, _ = verifier_pertinence_ti("Administrateur.trice systèmes sénior", "")
        self.assertTrue(ok_sys)

        # Compétences sans faux positifs sur "C" ni "Vue"
        comps = extraire_competences_ti(
            "Développeur Python et Vue.js",
            "C'est un poste avec une belle vue d'ensemble sur l'architecture JavaScript et SQL.",
        )
        self.assertIn("Python", comps)
        self.assertIn("Vue.js", comps)
        self.assertIn("JavaScript", comps)
        self.assertIn("SQL", comps)
        self.assertNotIn("C", comps)
        self.assertNotIn("Java", comps)


class TestResilienceCollecteurEtPipelineL2(unittest.TestCase):
    """Vérifie la sécurité des clés API, le retry sur 503 et la déduplication des 321 annonces du L2."""

    def test_masquage_cles_api_et_retry_503(self) -> None:
        """Une erreur 503 persistante ou temporaire ne doit jamais exposer `app_id` ni `app_key`."""
        creds = {"app_id": "ID_SECRET_999", "app_key": "CLE_SECRETE_888"}
        url_fuite = "https://api.adzuna.com/v1/api/jobs/ca/search/1?app_id=ID_SECRET_999&app_key=CLE_SECRETE_888"
        texte_masque = masquer_secrets(url_fuite, creds)
        self.assertNotIn("ID_SECRET_999", texte_masque)
        self.assertNotIn("CLE_SECRETE_888", texte_masque)
        self.assertIn("app_id=***", texte_masque)
        self.assertIn("app_key=***", texte_masque)

        # Simulation : deux erreurs 503 suivies d'un 200 OK
        attentes: list[float] = []
        session_ok = _FausseSessionHTTP(
            [
                _FausseReponseHTTP(503, url=url_fuite),
                _FausseReponseHTTP(503, url=url_fuite),
                _FausseReponseHTTP(200, payload={"count": 1, "results": [{"id": "1", "title": "Dev"}]}),
            ]
        )
        client = ClientAdzuna(
            credentials=creds,
            max_tentatives=3,
            delai_initial_retry=1.0,
            session=session_ok,
            attendre=attentes.append,
        )
        data = client.appeler_api("search/1", what="devops")
        self.assertEqual(data["count"], 1)
        self.assertEqual(attentes, [1.0, 2.0])

        # Simulation : 3 erreurs 503 consécutives -> exception propre sans secret
        session_ko = _FausseSessionHTTP(
            [
                 RuntimeError(f"503 Server Error for url: {url_fuite}"),
                RuntimeError(f"503 Server Error for url: {url_fuite}"),
                RuntimeError(f"503 Server Error for url: {url_fuite}"),
            ]
        )
        client_ko = ClientAdzuna(
            credentials=creds,
            max_tentatives=3,
            delai_initial_retry=0.5,
            session=session_ko,
            attendre= lambda _: None,
        )
        with self.assertRaises(ErreurCollecteAdzuna) as ctx:
            client_ko.appeler_api("search/1", what="devops")
        self.assertNotIn("ID_SECRET_999", str(ctx.exception))
        self.assertNotIn("CLE_SECRETE_888", str(ctx.exception))

    def test_pipeline_complet_sur_donnees_livrable_2(self) -> None:
        """Vérifie la déduplication 321 -> 229 offres uniques et les statistiques exactes sur les 10 fichiers du L2."""
        documents = charger_reponses_locales(DOSSIER_SORTIE_L2)
        self.assertEqual(len(documents), 10)

        offres, stats = executer_pipeline_documents(documents, date_extraction="2026-11-23T12:00:00+00:00")
        self.assertEqual(stats.annonces_brutes_recues, 321)
        self.assertEqual(stats.offres_uniques_par_id, 229)
        self.assertEqual(stats.doublons_meme_id_fusionnes, 92)
        self.assertEqual(len(offres), 229)

        # Vérification des métriques d'enrichissement salarial, contractuel, horaire et modalité
        self.assertEqual(stats.api_salaires_presents, 22)
        self.assertEqual(stats.api_salaires_suspects, 2)
        self.assertEqual(stats.api_salaires_valides, 20)
        self.assertEqual(stats.texte_salaires_extraits, 13)
        self.assertEqual(stats.consolide_salaires_valides, 32)
        self.assertEqual(stats.consolide_periodes_salariales, 7)

        self.assertEqual(stats.api_contrats_presents, 51)
        self.assertEqual(stats.consolide_contrats_presents, 60)
        self.assertEqual(stats.api_horaires_presents, 58)
        self.assertEqual(stats.consolide_horaires_presents, 66)
        self.assertEqual(stats.texte_modalites_extraites, 34)

        # Vérification des exports JSON, CSV (utf-8-sig) et Format commun (18 champs)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            p_json = exporter_json_enrichi(offres, stats, tmp / "test_v3.json")
            p_csv = exporter_csv_enrichi(offres, tmp / "test_v3.csv")
            p_com = exporter_format_commun_json(offres, tmp / "test_commun.json")

            self.assertTrue(p_json.is_file())
            self.assertTrue(p_csv.read_bytes().startswith(b"\xef\xbb\xbf"))  # BOM utf-8-sig pour Excel
            exemple_commun = offres[0].to_format_commun()
            self.assertEqual(list(exemple_commun.keys()), CHAMPS_FORMAT_COMMUN)


if __name__ == "__main__":
    unittest.main()
