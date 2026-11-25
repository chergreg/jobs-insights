"""Tests unitaires 100 % hors ligne pour le collecteur multi-sources enrichi (Livrable 3 - Lot 4 Final)."""

import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from assistant_et_interface import (
    audit_cover_letter,
    convert_to_common_format_dict,
    export_common_format_json,
    filter_offers,
    format_filtered_offers_summary,
    generate_interactive_html_portal,
    is_recent_and_valid_offer,
    match_cv_against_offers,
    read_cv_document,
    validate_common_format_records,
)
from poc_guichet_cnp_v2 import (
    CNP_2021_TI_DICT,
    CNP_CODES_TI,
    JobBankOffer,
    _cache_file_for_url,
    build_cnp_search_url,
    build_collection_report,
    build_jobboom_listing_url,
    classify_cnp_2021,
    clean_cache,
    collect_guichet_paginated_offers,
    collect_jobboom_paginated_urls,
    compute_content_hash,
    compute_dec_relevance_score,
    consolidate_data_directory,
    detect_stage_status,
    detect_ti_domain,
    enrich_offer_metadata,
    export_offers_to_csv,
    extract_education_level,
    extract_experience_and_seniority,
    extract_key_missions,
    extract_tech_skills,
    format_changes_report,
    get_cached_or_fetch,
    normalize_job_url,
    parse_iso_date,
    parse_job_detail_html,
    parse_jobboom_listing_html,
    parse_json_ld_job_posting,
    parse_remotive_job_item,
    parse_salary_details,
    parse_search_results_html,
    parse_talent_job_detail_html,
    purge_generated_outputs,
    resolve_quebec_location,
    split_recent_offers,
    unify_and_deduplicate_offers,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPocGuichetCnpV2(unittest.TestCase):
    def setUp(self) -> None:
        self.list_html = (FIXTURES_DIR / "liste_resultats_exemple.html").read_text(encoding="utf-8")
        self.detail_html = (FIXTURES_DIR / "fiche_offre_imbriquee.html").read_text(encoding="utf-8")

    def test_build_cnp_search_url_includes_14_cnp_and_corrects_fsrc_16(self) -> None:
        # En Lot 4, student_only=True n'ajoute plus fsrc=16 (qui filtre la source Guichet-Emplois directe et non les stages)
        url = build_cnp_search_url(province="QC", student_only=True, page=2)
        self.assertIn("fprov=QC", url)
        self.assertNotIn("fsrc=16", url)
        self.assertIn("page=2", url)
        self.assertEqual(len(CNP_CODES_TI), 14)
        for code in CNP_CODES_TI:
            self.assertIn(f"fn21={code}", url)

        # fsrc=16 n'est ajouté que si guichet_direct_only=True est demandé explicitement
        direct_url = build_cnp_search_url(province="QC", guichet_direct_only=True)
        self.assertIn("fsrc=16", direct_url)

    def test_parse_search_results_extracts_iso_date_clean_salary_and_partner(self) -> None:
        offers = parse_search_results_html(self.list_html)
        self.assertEqual(len(offers), 2)

        first = offers[0]
        self.assertEqual(first.id, "ge-50711091")
        self.assertEqual(first.source_id, "50711091")
        self.assertEqual(first.cnp_title, "agent/agente de soutien aux utilisateurs")
        self.assertEqual(first.code_cnp, "22221")
        self.assertEqual(first.domaine_ti, "tech_support")
        self.assertEqual(first.entreprise, "GolfIn - Saint-Georges")
        self.assertEqual(first.modalite, "Hybride")
        self.assertEqual(first.salaire, "22,50 $ de l'heure")
        self.assertEqual(first.salaire_min, 22.5)
        self.assertEqual(first.unite_salaire, "heure")
        self.assertEqual(first.date_publication, "2026-11-12")
        self.assertEqual(first.source_partenaire, "Jobillico")
        self.assertEqual(first.ville, "Saint-Georges")
        self.assertEqual(first.region_administrative, "Chaudière-Appalaches")

        second = offers[1]
        self.assertIsNone(second.salaire)
        self.assertEqual(second.date_publication, "2026-11-10")
        self.assertEqual(second.source_partenaire, "Guichet-Emplois")

    def test_parse_job_detail_handles_nested_divs_and_extracts_skills(self) -> None:
        offer = JobBankOffer(
            id="ge-50711091",
            source_id="50711091",
            url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091",
            cnp_title="agent/agente de soutien aux utilisateurs",
            titre="agent/agente de soutien aux utilisateurs",
        )
        enriched = parse_job_detail_html(self.detail_html, offer)

        self.assertEqual(enriched.titre, "Stagiaire en soutien informatique et réseaux")
        self.assertEqual(enriched.code_cnp, "22221")
        self.assertEqual(enriched.domaine_ti, "tech_support")
        self.assertEqual(enriched.niveau_seniorite, "Étudiant / Stage")
        self.assertEqual(enriched.date_fin, "2026-12-15")
        self.assertEqual(enriched.type_poste, "Temporaire, Temps plein")
        self.assertEqual(enriched.niveau_etudes, "Études collégiales (DEC)")
        self.assertIsNotNone(enriched.description)
        self.assertIn("Responsabilités principales après le premier div imbriqué", enriched.description or "")
        self.assertIn("Linux", enriched.competences_cles)
        self.assertTrue(enriched.est_stage)
        self.assertEqual(enriched.statut_stage, "confirmed_stage")
        self.assertGreaterEqual(enriched.score_pertinence_dec, 75)

    def test_parse_job_detail_cleans_double_escaped_partner_html_and_brief_fallback(self) -> None:
        partner_html = """
        <main>
          <span property="title">architecte d'applications</span>
          <div class="source-title-inner">
            <span class="orig-title-label">Appellation affichée :</span> Stagiaire Python &amp; Docker
          </div>
          <a id="externalJobLink" href="https://www.jobillico.com/fr/offre-d-emploi/test/123456?utm_source=jobbank">Voir</a>
          <span class="hidden" property="description">
            &lt;p&gt;&lt;strong&gt;Poste offert :&lt;/strong&gt; Développement backend FastAPI et PostgreSQL&lt;/p&gt;
          </span>
        </main>
        """
        offer = JobBankOffer(id="ge-50726141", source_id="50726141", url="https://example.com")
        enriched = parse_job_detail_html(partner_html, offer)
        self.assertEqual(enriched.titre_employeur, "Stagiaire Python & Docker")
        self.assertEqual(enriched.url_partenaire, "https://www.jobillico.com/fr/offre-d-emploi/test/123456")
        self.assertEqual(enriched.description, "Poste offert : Développement backend FastAPI et PostgreSQL")
        self.assertEqual(enriched.statut_stage, "confirmed_stage")
        self.assertEqual(enriched.competences_cles, ["Docker", "FastAPI", "PostgreSQL", "Python"])
        self.assertEqual(enriched.code_cnp, "21232")
        self.assertEqual(enriched.domaine_ti, "tech_backend")

    def test_extract_tech_skills_ignores_french_false_positives(self) -> None:
        skills = extract_tech_skills("C'est une vue d'ensemble du projet en Python, C# et Vue.js.")
        self.assertEqual(skills, ["C#", "Python", "Vue.js"])
        self.assertNotIn("C", skills)

    def test_detect_stage_excludes_supervision_false_positive(self) -> None:
        status = detect_stage_status(
            "Développeur senior Python",
            "Vous serez amené à superviser des stagiaires et accompagner les juniors.",
        )
        self.assertEqual(status, "not_indicated")

    def test_parse_talent_and_jobboom_json_ld(self) -> None:
        talent_html = """
        <html><head><script type="application/ld+json">
        {"@context":"https://schema.org","@graph":[{
          "@type":"JobPosting",
          "title":"Stagiaire Développeur Python",
          "datePosted":"2026-11-15",
          "employmentType":"INTERN",
          "description":"<p>Maîtrise de Python, Docker et SQL.</p>",
          "hiringOrganization":{"name":"Tech Québec"},
          "jobLocation":{
            "address":{"addressLocality":"Québec","addressRegion":"QC","postalCode":"G1R 2J6"},
            "geo":{"latitude":46.8139,"longitude":-71.2080}
          }
        }]}
        </script></head></html>
        """
        tc_offer = parse_talent_job_detail_html(talent_html, "https://ca.talent.com/fr/view?id=999&utm_source=test")
        self.assertIsNotNone(tc_offer)
        assert tc_offer is not None
        self.assertEqual(tc_offer.id, "tc-999")
        self.assertEqual(tc_offer.url, "https://ca.talent.com/fr/view?id=999")
        self.assertEqual(tc_offer.code_cnp, "21232")
        self.assertEqual(tc_offer.cnp_title, CNP_2021_TI_DICT["21232"])
        self.assertEqual(tc_offer.ville, "Québec")
        self.assertEqual(tc_offer.region_administrative, "Capitale-Nationale")
        self.assertEqual(tc_offer.code_postal, "G1R 2J6")
        self.assertEqual(tc_offer.latitude, 46.8139)
        self.assertEqual(tc_offer.competences_cles, ["Docker", "Python", "SQL"])
        self.assertTrue(tc_offer.est_stage)

        jb_list_html = """
        <div class="job_item job_item_sponsorship" data-url="/fr/offre-emploi/sponsor_p111"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-python_p222222"></div>
        """
        jb_urls = parse_jobboom_listing_html(jb_list_html)
        self.assertEqual(jb_urls, ["https://www.jobboom.com/fr/offre-emploi/dev-python_p222222"])

    def test_disk_cache_hit_skips_network_and_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            target_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091"

            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "<html>Fiche mise en cache</html>"
            mock_session.get.return_value = mock_resp

            content_1, from_cache_1 = get_cached_or_fetch(
                mock_session,
                target_url,
                cache_dir=cache_dir,
                ttl_seconds=86400,
                delay=0.0,
                use_cache=True,
            )
            self.assertFalse(from_cache_1)
            self.assertEqual(content_1, "<html>Fiche mise en cache</html>")
            self.assertEqual(mock_session.get.call_count, 1)

            with patch("poc_guichet_cnp_v2.time.sleep") as mock_sleep:
                content_2, from_cache_2 = get_cached_or_fetch(
                    mock_session,
                    target_url,
                    cache_dir=cache_dir,
                    ttl_seconds=86400,
                    delay=5.0,
                    use_cache=True,
                )
                self.assertTrue(from_cache_2)
                self.assertEqual(content_2, "<html>Fiche mise en cache</html>")
                self.assertEqual(mock_session.get.call_count, 1)
                mock_sleep.assert_not_called()

    def test_disk_cache_expired_refetches_from_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            target_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/99999999"
            cache_file = _cache_file_for_url(target_url, cache_dir=cache_dir)

            expired_payload = {
                "url": target_url,
                "fetched_at": time.time() - (25 * 3600),
                "content": "<html>Ancienne version expirée</html>",
            }
            cache_file.write_text(json.dumps(expired_payload), encoding="utf-8")

            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "<html>Nouvelle version fraîche</html>"
            mock_session.get.return_value = mock_resp

            content, from_cache = get_cached_or_fetch(
                mock_session,
                target_url,
                cache_dir=cache_dir,
                ttl_seconds=86400,
                delay=0.0,
                use_cache=True,
            )
            self.assertFalse(from_cache)
            self.assertEqual(content, "<html>Nouvelle version fraîche</html>")
            self.assertEqual(mock_session.get.call_count, 1)

    def test_pagination_guichet_and_jobboom_multi_pages_deduplicates(self) -> None:
        self.assertIn("page=2", build_jobboom_listing_url(page=2))

        page2_html = """
        <article id="article-50711091">
          <span class="noctitle">agent/agente de soutien aux utilisateurs</span>
          <li class="business">GolfIn - Saint-Georges</li>
        </article>
        <article id="article-50999999">
          <span class="noctitle">développeur/développeuse Python</span>
          <li class="business">Québec Numérique</li>
        </article>
        """
        mock_ge_session = MagicMock()
        resp_p1 = MagicMock(text=self.list_html)
        resp_p2 = MagicMock(text=page2_html)
        mock_ge_session.get.side_effect = [resp_p1, resp_p2]

        ge_offers = collect_guichet_paginated_offers(mock_ge_session, pages=2, delay=0.0)
        self.assertEqual(mock_ge_session.get.call_count, 2)
        self.assertEqual([o.id for o in ge_offers], ["ge-50711091", "ge-50684844", "ge-50999999"])

        jb_p1 = """
        <div class="job_item job_item_sponsorship" data-url="/fr/offre-emploi/pub_p100"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-a_p111111"></div>
        """
        jb_p2 = """
        <div class="job_item" data-url="/fr/offre-emploi/dev-a_p111111"></div>
        <div class="job_item" data-url="/fr/offre-emploi/dev-b_p222222"></div>
        """
        mock_jb_session = MagicMock()
        mock_jb_session.get.side_effect = [MagicMock(text=jb_p1), MagicMock(text=jb_p2)]

        jb_urls = collect_jobboom_paginated_urls(mock_jb_session, pages=2, delay=0.0)
        self.assertEqual(mock_jb_session.get.call_count, 2)
        self.assertEqual(
            jb_urls,
            [
                "https://www.jobboom.com/fr/offre-emploi/dev-a_p111111",
                "https://www.jobboom.com/fr/offre-emploi/dev-b_p222222",
            ],
        )

    # ==========================================================================
    # Nouveaux tests unitaires hors ligne du Lot 4
    # ==========================================================================
    def test_classify_cnp_2021_assigns_14_codes_and_rejects_non_ti_noise(self) -> None:
        # Vérification des classifications TI positives
        self.assertEqual(classify_cnp_2021("Développeur Full Stack React & Node.js"), ("21234", CNP_2021_TI_DICT["21234"]))
        self.assertEqual(classify_cnp_2021("Développeur logiciel Python Backend"), ("21232", CNP_2021_TI_DICT["21232"]))
        self.assertEqual(classify_cnp_2021("Analyste junior en cybersécurité"), ("21220", CNP_2021_TI_DICT["21220"]))
        self.assertEqual(classify_cnp_2021("Data Scientist / Spécialiste IA"), ("21211", CNP_2021_TI_DICT["21211"]))
        self.assertEqual(classify_cnp_2021("Administrateur de base de données PostgreSQL"), ("21223", CNP_2021_TI_DICT["21223"]))
        self.assertEqual(classify_cnp_2021("Technicien(ne) informatique - Soutien aux utilisateurs"), ("22221", CNP_2021_TI_DICT["22221"]))
        self.assertEqual(classify_cnp_2021("Administrateur(trice) systèmes et réseaux Linux"), ("22220", CNP_2021_TI_DICT["22220"]))
        self.assertEqual(classify_cnp_2021("Analyste en assurance qualité logicielle (QA)"), ("22222", CNP_2021_TI_DICT["22222"]))
        self.assertEqual(classify_cnp_2021("Chef.fe d'équipe TI"), ("20012", CNP_2021_TI_DICT["20012"]))
        self.assertEqual(classify_cnp_2021("Ingénieur DevOps et infonuagique"), ("21231", CNP_2021_TI_DICT["21231"]))
        self.assertEqual(classify_cnp_2021("Concepteur Web UI/UX"), ("21233", CNP_2021_TI_DICT["21233"]))
        self.assertEqual(classify_cnp_2021("Analyste fonctionnel SAP"), ("21221", CNP_2021_TI_DICT["21221"]))

        # Vérification du rejet strict des postes hors TI (0 faux positif)
        non_ti_titles = [
            "YouTube Creator",
            "Office Assistant",
            "Opérateur.trice à l'enneigement",
            "Programmeur CNC",
            "Audio Specialist",
            "Chef des ventes",
            "Charpentier-menuisier",
            "Commis d'épicerie",
            "Journalier au désassemblage de matériel informatique",
            "AI Trainer - Video Annotation",
            "Conseiller·ère en Recrutement TI et Développement Commercial",
        ]
        for noisy_title in non_ti_titles:
            self.assertIsNone(
                classify_cnp_2021(noisy_title, "Poste temps plein au Québec."),
                msg=f"Le poste hors TI '{noisy_title}' aurait dû être rejeté.",
            )

    def test_parsers_filter_out_non_ti_offers_on_jobboom_talent_and_remotive(self) -> None:
        non_ti_json_ld = """
        <html><head><script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting",
         "title":"Chef des ventes / Office Assistant",
         "description":"Gestion des ventes et accueil des clients.",
         "hiringOrganization":{"name":"Commerce Inc"},
         "jobLocation":{"address":{"addressLocality":"Montréal","addressRegion":"QC"}}}
        </script></head></html>
        """
        self.assertIsNone(parse_json_ld_job_posting(non_ti_json_ld, "https://www.jobboom.com/fr/offre-emploi/x_p12345", "jobboom", "jb"))
        self.assertIsNone(parse_talent_job_detail_html(non_ti_json_ld, "https://ca.talent.com/fr/view?id=12345"))

        noisy_remotive_item = {
            "id": 999999,
            "url": "https://remotive.com/remote-jobs/other/youtube-creator-999999",
            "title": "YouTube Creator & Video Annotation",
            "company_name": "MediaCorp",
            "candidate_required_location": "Canada",
            "description": "<p>Create videos for social media channels.</p>",
            "tags": ["video", "youtube"],
        }
        self.assertIsNone(parse_remotive_job_item(noisy_remotive_item))

    def test_jobtailor_domain_missions_seniority_salary_and_17_quebec_regions(self) -> None:
        self.assertEqual(detect_ti_domain("Analyste en cybersécurité SOC", code_cnp="21220"), "cybersecurite")
        self.assertEqual(detect_ti_domain("Ingénieur DevOps Cloud Azure", code_cnp="21231"), "devops_cloud")
        self.assertEqual(detect_ti_domain("Data Scientist Python", code_cnp="21211"), "data_ia")
        self.assertEqual(detect_ti_domain("Développeur Frontend React", code_cnp="21234"), "tech_frontend")
        self.assertEqual(detect_ti_domain("Technicien informatique niveau 2", code_cnp="22221"), "tech_support")
        self.assertEqual(detect_ti_domain("Développeur Backend Python FastAPI", code_cnp="21232"), "tech_backend")

        desc = (
            "Études: Collégial (DEC) en informatique. "
            "Principales responsabilités : • Concevoir des APIs REST avec FastAPI et PostgreSQL; "
            "• Automatiser les tests unitaires et le déploiement Docker. "
            "Exigences : 1 à 2 ans d'expérience. Salaire : Entre 28,50 $ et 35,00 $/heure."
        )
        missions = extract_key_missions(desc)
        self.assertGreaterEqual(len(missions), 2)
        self.assertIn("FastAPI", missions[0])

        edu = extract_education_level(None, desc)
        self.assertIsNotNone(edu)
        exp_req, seniority = extract_experience_and_seniority("Développeur junior Python", desc, est_stage=False)
        self.assertEqual(exp_req, "1 à 2 ans")
        self.assertEqual(seniority, "Junior / DEC")

        sal_txt, sal_min, sal_max, sal_unit = parse_salary_details(None, description=desc)
        self.assertIsNotNone(sal_txt)
        self.assertEqual(sal_min, 28.5)
        self.assertEqual(sal_max, 35.0)
        self.assertEqual(sal_unit, "heure")

        ville, prov, region, postal = resolve_quebec_location("Lévis (QC)", "QC", "Bureau situé au G6V 0A1.")
        self.assertEqual(ville, "Lévis")
        self.assertEqual(prov, "QC")
        self.assertEqual(region, "Chaudière-Appalaches")
        self.assertEqual(postal, "G6V 0A1")

    def test_url_normalization_content_hash_and_dec_relevance_score(self) -> None:
        dirty_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091;jsessionid=ABC123XYZ?utm_source=google&fbclid=999"
        clean_u = normalize_job_url(dirty_url)
        self.assertEqual(clean_u, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50711091")

        h1 = compute_content_hash(dirty_url, "Stagiaire Python", "Tech QC", "Développement FastAPI")
        h2 = compute_content_hash(clean_u, "stagiaire python", "Tech QC", "Développement FastAPI")
        self.assertEqual(len(h1), 16)
        self.assertEqual(h1, h2)

        stage_dec = enrich_offer_metadata(
            JobBankOffer(
                id="ge-1",
                source_id="1",
                url=clean_u,
                titre="Stagiaire développeur Python",
                entreprise="Tech Québec",
                lieu="Québec (QC)",
                modalite="Hybride",
                niveau_etudes="Collégial (DEC)",
                salaire="24,00 $ de l'heure",
                competences_cles=["Docker", "FastAPI", "Git", "PostgreSQL", "Python", "SQL"],
                description="Principales responsabilités : • Développer des services backend Python et SQL.",
            )
        )
        senior_phd = enrich_offer_metadata(
            JobBankOffer(
                id="ge-2",
                source_id="2",
                url="https://example.com/2",
                titre="Architecte quantique principal",
                entreprise="Quantum Corp",
                lieu="Toronto, ON",
                province="ON",
                niveau_etudes="Universitaire (Doctorat)",
                description="Doctorat et 10 ans d'expérience requis.",
            )
        )
        self.assertGreater(stage_dec.score_pertinence_dec, senior_phd.score_pertinence_dec)
        self.assertGreaterEqual(stage_dec.score_pertinence_dec, 85)

    def test_deduplication_cross_source_merge_and_csv_utf8_sig_export(self) -> None:
        # Même offre vue sur Guichet-Emplois (avec salaire) et sur Talent.com (avec GPS et description longue)
        off_ge = enrich_offer_metadata(
            JobBankOffer(
                id="ge-50700001",
                source_id="50700001",
                url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/50700001",
                titre="développeur/développeuse de logiciels",
                titre_employeur="Développeur Full Stack Python",
                entreprise="Solutions Nordiques Inc.",
                lieu="Québec (QC)",
                source="guichet-emplois",
                source_partenaire="Talent.com",
                salaire="38,00 $ de l'heure",
                competences_cles=["Python"],
                description="Offre #987654321 courte.",
            )
        )
        off_tc = enrich_offer_metadata(
            JobBankOffer(
                id="tc-987654321",
                source_id="987654321",
                url="https://ca.talent.com/fr/view?id=987654321",
                titre="Développeur Full Stack Python",
                titre_employeur="Développeur Full Stack Python",
                entreprise="Solutions Nordiques",
                lieu="Québec City (QC)",
                source="talent-canada",
                latitude=46.8139,
                longitude=-71.2080,
                competences_cles=["Docker", "Python", "React", "SQL"],
                description="Description complète sur Talent.com : Principales responsabilités : • Développer avec Python, React, Docker et SQL.",
            )
        )

        unified, stats = unify_and_deduplicate_offers([off_ge, off_tc])
        self.assertEqual(len(unified), 1)
        self.assertEqual(stats["doublons_inter_fusionnes"], 1)
        merged = unified[0]
        self.assertEqual(merged.latitude, 46.8139)
        self.assertEqual(merged.salaire_min, 38.0)
        self.assertEqual(merged.competences_cles, ["Docker", "Python", "React", "SQL"])
        self.assertEqual(merged.url_partenaire, "https://ca.talent.com/fr/view?id=987654321")

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "offres_unifiees.csv"
            export_offers_to_csv(unified, csv_path)
            raw_bytes = csv_path.read_bytes()
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"), "Le CSV doit commencer par le BOM UTF-8 (utf-8-sig) pour Excel.")
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f, delimiter=";"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["code_cnp"], "21234")
            self.assertEqual(rows[0]["region_administrative"], "Capitale-Nationale")

            report = build_collection_report(
                {"guichet-emplois": {"brutes_lues": 1, "retenues_ti_cnp": 1, "rejetees_hors_ti": 0}},
                stats,
                unified,
            )
            self.assertEqual(report["total_offres_unifiees_ti"], 1)
            self.assertEqual(report["offres_avec_coordonnees_gps"], 1)

    def test_consolidate_data_directory_filters_noise_and_writes_unified_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            d_dir = Path(tmp_dir)
            (d_dir / "offres_guichet_emplois.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "ge-100",
                            "source_id": "100",
                            "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/100;jsessionid=999",
                            "titre": "développeur/développeuse Python",
                            "entreprise": "Alpha TI Inc.",
                            "lieu": "Québec (QC)",
                            "salaire": "35,00 $ de l'heure",
                            "description": "Développement Python et SQL.",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d_dir / "offres_jobboom.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "jb-200",
                            "source_id": "200",
                            "url": "https://www.jobboom.com/fr/offre-emploi/dev_p200",
                            "titre": "Chef des ventes",
                            "entreprise": "Ventes Inc.",
                            "lieu": "Montréal (QC)",
                            "description": "Prospection commerciale.",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = consolidate_data_directory(d_dir)
            self.assertEqual(report["total_offres_unifiees_ti"], 1)
            self.assertEqual(report["collecte_par_source"]["jobboom"]["rejetees_hors_ti"], 1)
            self.assertTrue((d_dir / "offres_unifiees.json").is_file())
            self.assertTrue((d_dir / "offres_unifiees.csv").is_file())
            self.assertTrue((d_dir / "rapport_collecte.json").is_file())

    def test_is_recent_and_valid_offer_rejects_old_2023_offers_and_expired_dates(self) -> None:
        old_offer = JobBankOffer(
            id="jb-2023",
            source_id="2023",
            url="https://www.jobboom.com/fr/offre-emploi/dev_p2023",
            titre="Développeur Python",
            date_publication="2023-06-29",
        )
        valid_offer = JobBankOffer(
            id="ge-2026",
            source_id="2026",
            url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/2026",
            titre="Développeur Python",
            date_publication="2026-11-12",
            date_fin="2026-12-15",
        )
        self.assertFalse(is_recent_and_valid_offer(old_offer, min_year=2026))
        self.assertTrue(is_recent_and_valid_offer(valid_offer, min_year=2026, reference_date="2026-11-22"))
        self.assertFalse(is_recent_and_valid_offer(valid_offer, min_year=2026, reference_date="2026-12-20"))

        kept, nb_old = split_recent_offers([old_offer, valid_offer])
        self.assertEqual([o.id for o in kept], ["ge-2026"])
        self.assertEqual(nb_old, 1)

    def test_filter_offers_multicriteria_offline(self) -> None:
        o1 = enrich_offer_metadata(
            JobBankOffer(
                id="ge-1",
                source_id="1",
                url="https://example.com/1",
                titre="Stagiaire Développeur Python",
                entreprise="Tech Québec",
                lieu="Québec (QC)",
                source="guichet-emplois",
                date_publication="2026-11-12",
                salaire="26,00 $ de l'heure",
                est_stage=True,
                statut_stage="confirmed_stage",
                competences_cles=["Docker", "FastAPI", "Python", "SQL"],
            )
        )
        o2 = enrich_offer_metadata(
            JobBankOffer(
                id="jb-2",
                source_id="2",
                url="https://example.com/2",
                titre="Architecte Cloud Senior",
                entreprise="Cloud Montréal",
                lieu="Montréal (QC)",
                source="jobboom",
                date_publication="2026-11-10",
                salaire="120 000 $ par année",
                est_stage=False,
                statut_stage="not_indicated",
                competences_cles=["AWS", "Kubernetes", "Terraform"],
            )
        )
        self.assertEqual(len(filter_offers([o1, o2], region="Capitale-Nationale")), 1)
        self.assertEqual(len(filter_offers([o1, o2], techno="Python", stages_only=True)), 1)
        self.assertEqual(len(filter_offers([o1, o2], domaine="devops_cloud")), 1)
        self.assertEqual(len(filter_offers([o1, o2], salaire_min=25.0, unite_salaire="heure")), 1)
        self.assertEqual(len(filter_offers([o1, o2], salaire_min=30.0, unite_salaire="heure")), 0)

    def test_read_cv_document_docx_and_match_cv_against_offers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = Path(tmp_dir) / "cv_test.docx"
            xml_content = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Étudiant DEC en informatique à Québec — recherche de stage</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Compétences : Python, FastAPI, PostgreSQL, Docker, Git, Linux, SQL.</w:t></w:r></w:p>"
                "</w:body></w:document>"
            )
            with zipfile.ZipFile(docx_path, "w") as zf:
                zf.writestr("word/document.xml", xml_content)

            cv_text = read_cv_document(docx_path)
            self.assertIn("FastAPI", cv_text)

            target_offer = enrich_offer_metadata(
                JobBankOffer(
                    id="ge-101",
                    source_id="101",
                    url="https://example.com/101",
                    titre="Stagiaire Développeur Python Backend",
                    entreprise="Québec Numérique",
                    lieu="Québec (QC)",
                    date_publication="2026-11-15",
                    est_stage=True,
                    statut_stage="confirmed_stage",
                    competences_cles=["Docker", "FastAPI", "Git", "PostgreSQL", "Python", "SQL"],
                    description="Stage DEC en développement backend Python FastAPI et PostgreSQL.",
                )
            )
            unrelated_offer = enrich_offer_metadata(
                JobBankOffer(
                    id="jb-202",
                    source_id="202",
                    url="https://example.com/202",
                    titre="Architecte SAP Senior",
                    entreprise="ERP Corp",
                    lieu="Montréal (QC)",
                    date_publication="2026-11-15",
                    competences_cles=["Oracle", "SAP"],
                    description="10 ans d'expérience SAP requis.",
                )
            )

            profile, matches = match_cv_against_offers(cv_text, [unrelated_offer, target_offer], top_n=2)
            self.assertTrue(profile.cherche_stage)
            self.assertIn("Python", profile.competences)
            self.assertEqual(matches[0].offer.id, "ge-101")
            self.assertGreater(matches[0].score_ats, matches[1].score_ats)
            self.assertGreaterEqual(matches[0].score_ats, 80)

    def test_audit_cover_letter_detects_placeholders_and_missing_keywords(self) -> None:
        offer = enrich_offer_metadata(
            JobBankOffer(
                id="ge-500",
                source_id="500",
                url="https://example.com/500",
                titre="Stagiaire Développeur Python",
                entreprise="GolfIn Québec",
                lieu="Québec (QC)",
                competences_cles=["Docker", "FastAPI", "PostgreSQL", "Python"],
                missions_cles=["Concevoir des APIs REST performantes", "Automatiser les tests unitaires"],
            )
        )
        draft_letter = (
            "Madame, Monsieur, Je postule pour le poste de [nom du poste] au sein de votre équipe. "
            "Grâce à ma formation DEC, j'utilise Python et Git dans mes projets. "
            "Je serais ravi d'échanger en entrevue afin de contribuer ensemble."
        )
        audit = audit_cover_letter(draft_letter, offer, cv_text="Compétences : Python, Docker, FastAPI, Git")
        self.assertFalse(audit.mentionne_employeur)
        self.assertIn("[nom du poste]", audit.zones_a_remplir_oubliees)
        self.assertIn("Python", audit.technologies_citees)
        self.assertIn("Docker", audit.technologies_manquantes)
        self.assertTrue(any("GolfIn" in c for c in audit.conseils))
        self.assertTrue(any("Docker" in c for c in audit.conseils))

    def test_convert_to_common_format_and_generate_xss_safe_html_portal(self) -> None:
        xss_offer = enrich_offer_metadata(
            JobBankOffer(
                id="ge-777",
                source_id="777",
                url="https://example.com/777",
                titre="Développeur Python </script><script>alert(1)</script>",
                entreprise="SecuCorp",
                lieu="Québec (QC)",
                date_publication="2026-11-15",
                competences_cles=["Python", "SQL"],
            )
        )
        common_dict = convert_to_common_format_dict(xss_offer)
        self.assertEqual(common_dict["id"], "ge-777")
        self.assertIn("statut_stage", common_dict)
        self.assertIn("competences_cles", common_dict)

        with tempfile.TemporaryDirectory() as tmp_dir:
            common_path = Path(tmp_dir) / "offres_format_commun.json"
            html_path = Path(tmp_dir) / "portail_ti_jobtailor.html"
            export_common_format_json([xss_offer], common_path)
            generate_interactive_html_portal([xss_offer], html_path)

            self.assertTrue(common_path.is_file())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertNotIn("</script><script>alert(1)", html_text)
            self.assertIn("<\\/script>", html_text)

    def test_nouveautes_disparues_historique_et_purge_garder_historique(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            d_dir = Path(tmp_dir) / "data"
            c_dir = Path(tmp_dir) / "cache"
            d_dir.mkdir(parents=True, exist_ok=True)
            c_dir.mkdir(parents=True, exist_ok=True)

            # Collecte 1 : offres ge-100 et jb-200
            (d_dir / "offres_guichet_emplois.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "ge-100",
                            "source_id": "100",
                            "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/100",
                            "titre": "Développeur Python",
                            "entreprise": "Alpha TI",
                            "lieu": "Québec (QC)",
                            "date_publication": "2026-11-10",
                            "description": "Développement Python et SQL.",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d_dir / "offres_jobboom.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "jb-200",
                            "source_id": "200",
                            "url": "https://www.jobboom.com/fr/offre-emploi/dev_p200",
                            "titre": "Analyste programmeur Java",
                            "entreprise": "Beta TI",
                            "lieu": "Montréal (QC)",
                            "date_publication": "2026-11-11",
                            "description": "Développement Java et Spring.",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            consolidate_data_directory(d_dir)

            # Collecte 2 : jb-200 disparaît, ge-100 reste, ge-300 apparaît
            (d_dir / "offres_jobboom.json").write_text("[]", encoding="utf-8")
            (d_dir / "offres_guichet_emplois.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "ge-100",
                            "source_id": "100",
                            "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/100",
                            "titre": "Développeur Python",
                            "entreprise": "Alpha TI",
                            "lieu": "Québec (QC)",
                            "date_publication": "2026-11-10",
                            "description": "Développement Python et SQL.",
                        },
                        {
                            "id": "ge-300",
                            "source_id": "300",
                            "url": "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/300",
                            "titre": "Administrateur système Linux",
                            "entreprise": "Gamma TI",
                            "lieu": "Lévis (QC)",
                            "date_publication": "2026-11-20",
                            "description": "Administration Linux et Docker.",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rep2 = consolidate_data_directory(d_dir)

            unified = json.loads((d_dir / "offres_unifiees.json").read_text(encoding="utf-8"))
            by_id = {o["id"]: o for o in unified}
            self.assertFalse(by_id["ge-100"]["nouvelle"])
            self.assertTrue(by_id["ge-300"]["nouvelle"])
            self.assertEqual(rep2["changements_depuis_precedente"]["nb_nouvelles"], 1)
            self.assertEqual(rep2["changements_depuis_precedente"]["nb_disparues"], 1)
            self.assertEqual(rep2["changements_depuis_precedente"]["disparues"][0]["titre"], "Analyste programmeur Java")

            hist_path = d_dir / "historique-collectes.csv"
            self.assertTrue(hist_path.is_file())
            self.assertTrue(hist_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with hist_path.open(encoding="utf-8-sig", newline="") as f:
                hist_rows = list(csv.DictReader(f, delimiter=";"))
            self.assertEqual(len(hist_rows), 2)
            self.assertEqual(hist_rows[1]["nouvelles"], "1")
            self.assertEqual(hist_rows[1]["disparues"], "1")

            changes_txt = format_changes_report(d_dir)
            self.assertIn("ge-300", changes_txt)
            self.assertIn("Analyste programmeur Java", changes_txt)

            # --purger --garder-historique conserve historique-collectes.csv
            purge_generated_outputs(d_dir, c_dir, purge_cache=True, keep_history=True)
            self.assertTrue(hist_path.is_file())
            self.assertFalse((d_dir / "offres_unifiees.json").is_file())

            # --purger sans --garder-historique supprime tout
            purge_generated_outputs(d_dir, c_dir, purge_cache=True, keep_history=False)
            self.assertFalse(hist_path.is_file())

    def test_regle_fusion_offre_la_plus_complete_doublons_et_meme_site_distincts(self) -> None:
        # 1. Même poste sur deux sites différents : la 2e offre est plus complète -> elle devient principale
        courte_ge = enrich_offer_metadata(
            JobBankOffer(
                id="ge-111",
                source_id="111",
                url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/111",
                titre="Développeur React",
                entreprise="Studio Web Inc.",
                lieu="Québec (QC)",
                source="guichet-emplois",
                source_partenaire="Talent.com",
                description="Courte annonce.",
            )
        )
        riche_tc = enrich_offer_metadata(
            JobBankOffer(
                id="tc-222",
                source_id="222",
                url="https://ca.talent.com/fr/view?id=222",
                titre="Développeur React",
                entreprise="Studio Web",
                lieu="Québec City (QC)",
                source="talent-canada",
                salaire="40 $ / heure",
                modalite="Hybride",
                niveau_etudes="DEC en informatique",
                latitude=46.81,
                longitude=-71.21,
                competences_cles=["React", "TypeScript", "Docker"],
                description="Description détaillée du poste Développeur React avec TypeScript et Docker.",
            )
        )
        # 2. Deux annonces du MÊME site (jobboom) avec des numéros différents -> on garde les deux
        jb_1 = enrich_offer_metadata(
            JobBankOffer(
                id="jb-301",
                source_id="301",
                url="https://www.jobboom.com/fr/offre-emploi/dev_p301",
                titre="Technicien informatique",
                entreprise="Collège ABC",
                lieu="Montréal (QC)",
                source="jobboom",
                description="Poste 1 support technique.",
            )
        )
        jb_2 = enrich_offer_metadata(
            JobBankOffer(
                id="jb-302",
                source_id="302",
                url="https://www.jobboom.com/fr/offre-emploi/dev_p302",
                titre="Technicien informatique",
                entreprise="Collège ABC",
                lieu="Montréal (QC)",
                source="jobboom",
                description="Poste 2 support technique.",
            )
        )

        unified, stats = unify_and_deduplicate_offers([courte_ge, riche_tc, jb_1, jb_2])
        self.assertEqual(stats["doublons_inter_fusionnes"], 1)
        self.assertEqual(len(unified), 3)

        merged_react = next(o for o in unified if o.id == "tc-222")
        self.assertEqual(merged_react.doublons, ["ge-111"])
        self.assertEqual(merged_react.url_partenaire, "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/111")
        self.assertIn("Aussi publié sur : guichet-emplois, ge-111", format_filtered_offers_summary([merged_react]))

        jb_ids = {o.id for o in unified if o.source == "jobboom"}
        self.assertEqual(jb_ids, {"jb-301", "jb-302"})

    def test_compatibilite_format_commun_avec_modele_joboffer_gregory(self) -> None:
        offre = enrich_offer_metadata(
            JobBankOffer(
                id="ge-888",
                source_id="888",
                url="https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/888",
                titre="Stagiaire développeur Python",
                entreprise="Tech Québec",
                lieu="Québec (QC)",
                source="guichet-emplois",
                source_partenaire="",
                date_publication="2026-11-18T12:00:00Z",
                type_poste="",
                modalite="",
                salaire="",
                description="Stage Python et SQL.",
                competences_cles=["Python", "SQL"],
            )
        )
        common = convert_to_common_format_dict(offre)
        self.assertEqual(len(common), 18)
        self.assertIsNone(common["source_partenaire"])
        self.assertEqual(common["type_poste"], "Stage")
        self.assertIsNone(common["modalite"])
        self.assertIsNone(common["salaire"])
        self.assertEqual(common["date_publication"], "2026-11-18")
        self.assertTrue(common["est_stage"])
        self.assertEqual(common["statut_stage"], "confirmed_stage")

        offre_sans_type = JobBankOffer(
            id="jb-889",
            source_id="889",
            url="https://www.jobboom.com/fr/offre-emploi/dev_p889",
            titre="Développeur Python",
            entreprise="Tech Québec",
            lieu="Québec (QC)",
            source="jobboom",
            type_poste="",
            description="Poste Python.",
        )
        common_sans_type = convert_to_common_format_dict(offre_sans_type)
        self.assertIsNone(common_sans_type["type_poste"])

        ok, msg = validate_common_format_records([common, common_sans_type])
        self.assertTrue(ok, msg)

    def test_nettoyer_cache_supprime_disparues_et_expirees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            d_dir = Path(tmp_dir) / "data"
            c_dir = Path(tmp_dir) / "cache"
            d_dir.mkdir(parents=True, exist_ok=True)
            c_dir.mkdir(parents=True, exist_ok=True)
            now = 1_700_000_000.0

            active_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/100"
            gone_url = "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/200"
            expired_url = "https://www.jobboom.com/fr/offre-emploi/dev_p300"
            search_url = "https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fn21=21232&page=1"

            (d_dir / "offres_unifiees.json").write_text(
                json.dumps([{"id": "ge-100", "source": "guichet-emplois", "source_id": "100", "url": active_url}]),
                encoding="utf-8",
            )
            (d_dir / "rapport_collecte.json").write_text(
                json.dumps({"changements_depuis_precedente": {"disparues": [{"url": gone_url}]}}),
                encoding="utf-8",
            )

            _cache_file_for_url(active_url, c_dir).write_text(
                json.dumps({"url": active_url, "fetched_at": now - 60, "content": "ok"}),
                encoding="utf-8",
            )
            _cache_file_for_url(gone_url, c_dir).write_text(
                json.dumps({"url": gone_url, "fetched_at": now - 60, "content": "gone"}),
                encoding="utf-8",
            )
            _cache_file_for_url(expired_url, c_dir).write_text(
                json.dumps({"url": expired_url, "fetched_at": now - 90000, "content": "old"}),
                encoding="utf-8",
            )
            _cache_file_for_url(search_url, c_dir).write_text(
                json.dumps({"url": search_url, "fetched_at": now - 60, "content": "search"}),
                encoding="utf-8",
            )

            stats = clean_cache(cache_dir=c_dir, data_dir=d_dir, ttl_seconds=86400, now=now)
            self.assertEqual(stats["pages_supprimees"], 2)
            self.assertEqual(stats["disparues"], 1)
            self.assertEqual(stats["expirees"], 1)
            self.assertGreater(stats["octets_liberes"], 0)
            self.assertTrue(_cache_file_for_url(active_url, c_dir).exists())
            self.assertTrue(_cache_file_for_url(search_url, c_dir).exists())
            self.assertFalse(_cache_file_for_url(gone_url, c_dir).exists())
            self.assertFalse(_cache_file_for_url(expired_url, c_dir).exists())


if __name__ == "__main__":
    unittest.main()
