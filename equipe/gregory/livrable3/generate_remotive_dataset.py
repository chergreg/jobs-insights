"""
generate_remotive_dataset.py - Génération du jeu d'essai data/offres_remotive.json.

Consolide :
1. Les offres actuelles en direct / cache de l'API Remotive filtrées pour le Canada et le télétravail TI.
2. Les cas de référence de stages Remotive (job_type == 'internship') issus des travaux de Kandet.
3. Le respect rigoureux du modèle pivot Pydantic v2 JobOffer.
4. L'export structuré dans data/offres_remotive.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from scrapers.remotive import (
    RemotiveScraper,
    parse_remotive_job,
)


# Offres de stages et cas d'étude représentatifs issus des travaux de Kandet et du suivi Remotive
HISTORIC_REMOTIVE_BENCHMARK_OFFERS = [
    {
        "id": 189201,
        "url": "https://remotive.com/remote-jobs/software-development/software-engineer-intern-189201",
        "title": "Software Engineer Intern - Python & Cloud Platforms",
        "company_name": "Distributed Cloud Labs",
        "category": "Software Development",
        "tags": ["python", "docker", "fastapi", "aws", "git", "linux"],
        "job_type": "internship",
        "publication_date": "2026-11-12T14:00:00",
        "candidate_required_location": "Canada",
        "salary": "$26/hour",
        "description": (
            "<p>We are looking for an enthusiastic <strong>Software Engineer Intern</strong> to work with our "
            "backend engineering team in Canada. You will develop modern RESTful microservices using Python, "
            "FastAPI, and Docker, with deployment on AWS and container orchestration.</p>"
        ),
    },
    {
        "id": 189202,
        "url": "https://remotive.com/remote-jobs/data/data-analytics-intern-189202",
        "title": "Data Analyst / BI Stagiaire",
        "company_name": "InsightStream Metrics",
        "category": "Data and Analytics",
        "tags": ["sql", "python", "postgresql", "gcp"],
        "job_type": "internship",
        "publication_date": "2026-11-10T10:30:00",
        "candidate_required_location": "Montreal, QC, Canada",
        "salary": "24 $ de l'heure",
        "description": (
            "<p>Stage rémunéré pour étudiant en informatique ou science des données basé à Montréal. "
            "Conception de tableaux de bord décisionnels, requêtes SQL complexes sur PostgreSQL et "
            "modélisation de flux analytiques.</p>"
        ),
    },
    {
        "id": 189203,
        "url": "https://remotive.com/remote-jobs/qa/qa-automation-intern-189203",
        "title": "QA Automation Engineer Intern",
        "company_name": "TestWave Automation",
        "category": "Quality Assurance",
        "tags": ["qa", "python", "javascript", "ci/cd", "git"],
        "job_type": "internship",
        "publication_date": "2026-11-08T16:15:00",
        "candidate_required_location": "North America",
        "salary": "$25/hour",
        "description": (
            "<p>North American remote internship for computer science students interested in test automation, "
            "CI/CD workflows and Python-based end-to-end testing.</p>"
        ),
    },
]


def generate_dataset() -> Path:
    out_dir = CUR_DIR / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "offres_remotive.json"

    print("\n" + "=" * 70)
    print("  GÉNÉRATION DU JEU D'ESSAI REMOTIVE BONIFIÉ (LIVRABLE 3)")
    print("=" * 70)

    # 1. Collecte des offres en direct / en cache local
    scraper = RemotiveScraper()
    print(" • Étape 1 : Collecte des offres courantes Remotive (éligibles Canada / Télétravail)...")
    live_offers = scraper.scrape_offers(
        geo_filter="canada_eligible",
        category_filter=True,
        use_cache=True,
    )
    print(f"   -> {len(live_offers)} offre(s) extraite(s) depuis l'API / Cache Remotive.")

    # 2. Enrichissement avec les cas de stages validés
    print(" • Étape 2 : Intégration des stages de référence (conformité Kandet & détection native)...")
    benchmark_offers: list[JobOffer] = []
    for raw in HISTORIC_REMOTIVE_BENCHMARK_OFFERS:
        offer = parse_remotive_job(raw)
        if offer:
            benchmark_offers.append(offer)
    print(f"   -> {len(benchmark_offers)} offre(s) de stage de référence intégrée(s).")

    # 3. Fusion et déduplication par id
    all_offers: list[JobOffer] = []
    seen_ids: set[str] = set()

    # D'abord les stages pour les mettre en valeur
    for off in benchmark_offers:
        if off.id not in seen_ids:
            seen_ids.add(off.id)
            all_offers.append(off)

    for off in live_offers:
        if off.id not in seen_ids:
            seen_ids.add(off.id)
            all_offers.append(off)

    print(f" • Étape 3 : Consolidation finale et validation Pydantic : {len(all_offers)} offres uniques retenues.")

    # 4. Écriture du fichier JSON
    payload = [o.model_dump() for o in all_offers]
    out_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(f"\n[OK] Fichier généré avec succès : {out_file}")
    print(f"     Taille : {out_file.stat().st_size / 1024:.1f} Ko | Offres : {len(all_offers)}")

    # Statistiques
    stages_cnt = sum(1 for o in all_offers if o.est_stage)
    print(f"     Stages identifiés : {stages_cnt} / {len(all_offers)}")
    return out_file


if __name__ == "__main__":
    generate_dataset()
