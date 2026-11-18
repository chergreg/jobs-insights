"""
generate_dataset.py - Génération du jeu d'essai data/offres_guichet_emplois.json.
Normalise et fusionne les données réelles collectées par Hugo et Kandet
dans le modèle unifié JobOffer (Pydantic v2).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Assure l'accès aux modules locaux
CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from models import JobOffer
from scrapers.guichet_emplois import (
    classify_stage,
    clean_posting_url,
    extract_tech_skills,
    parse_display_date,
)

# Table de normalisation des technologies brutes vers la nomenclature canonique
TECH_CANONICAL = {
    ".net": ".NET",
    "api": "API",
    "aws": "AWS",
    "agile": "Agile",
    "angular": "Angular",
    "azure": "Azure",
    "c#": "C#",
    "c++": "C++",
    "css": "CSS",
    "ci/cd": "CI/CD",
    "cloud": "Cloud",
    "devops": "DevOps",
    "docker": "Docker",
    "fastapi": "FastAPI",
    "gcp": "GCP",
    "git": "Git",
    "html": "HTML",
    "ia": "IA",
    "java": "Java",
    "javascript": "JavaScript",
    "jira": "Jira",
    "kubernetes": "Kubernetes",
    "linux": "Linux",
    "mysql": "MySQL",
    "node": "Node.js",
    "node.js": "Node.js",
    "php": "PHP",
    "postgresql": "PostgreSQL",
    "python": "Python",
    "qa": "QA",
    "react": "React",
    "rest": "REST",
    "sql": "SQL",
    "scrum": "Scrum",
    "spring": "Spring",
    "typescript": "TypeScript",
    "unreal": "Unreal Engine",
    "unreal engine": "Unreal Engine",
    "vue.js": "Vue.js",
}


def normalize_skills(raw_skills: list[str], title_text: str = "") -> list[str]:
    """Nettoie, normalise et déduplique la liste des compétences en éliminant les faux positifs."""
    result: set[str] = set()

    for item in raw_skills:
        clean_item = item.strip().lower()
        if clean_item in {"vue", "c"}:
            # Élimination des faux positifs récurrents
            continue
        if clean_item in TECH_CANONICAL:
            result.add(TECH_CANONICAL[clean_item])

    # Extraction directe depuis le titre avec nos regex strictes
    for tech in extract_tech_skills(title_text):
        result.add(tech)

    return sorted(list(result))


def main() -> None:
    data_dir = CUR_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_file = data_dir / "offres_guichet_emplois.json"

    hugo_file = CUR_DIR.parent.parent / "hugo" / "02-preuve-de-concept-scraping" / "data" / "offres_emploi_canada.json"
    kandet_file = CUR_DIR.parent.parent / "kandet" / "02-preuve-de-concept-scraping" / "echantillon.json"

    offers: list[JobOffer] = []
    seen_ids: set[str] = set()

    # 1. Traitement des offres de Hugo (87 offres)
    if hugo_file.is_file():
        hugo_raw = json.loads(hugo_file.read_text(encoding="utf-8"))
        for item in hugo_raw:
            raw_id = item.get("id", "").replace("gc-", "").replace("ge-", "").strip()
            job_id = f"ge-{raw_id}"
            if not raw_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            titre = item.get("titre", "Titre non spécifié")
            desc = item.get("description") or None
            est_stage, statut_stage, _ = classify_stage(titre, item.get("type_poste", ""), desc or "")

            url = clean_posting_url(item.get("url_source", ""))
            date_pub = parse_display_date(item.get("date_publication", ""))
            part = item.get("partenaire")
            if part and any(k in part for k in ["Guichet", "Job Bank", "Direct"]):
                part = None
            elif part:
                part = part.replace(".ca", "").replace(".com", "").strip()

            competences = normalize_skills(item.get("competences_cles", []), title_text=titre)

            offer = JobOffer(
                id=job_id,
                titre=titre,
                entreprise=item.get("entreprise", "Non spécifié"),
                lieu=item.get("lieu", "Québec (QC)"),
                province=item.get("province", "QC"),
                pays="Canada",
                url=url,
                source="guichet-emplois",
                source_partenaire=part,
                date_publication=date_pub,
                type_poste="Stage" if est_stage else item.get("type_poste", "Temps plein"),
                modalite=item.get("modalite") if item.get("modalite") not in {"Non spécifié", None} else None,
                est_stage=est_stage,
                statut_stage=statut_stage,
                description=desc,
                competences_cles=competences,
                salaire=item.get("salaire"),
            )
            offers.append(offer)

    # 2. Traitement des offres de Kandet (échantillon Guichet-Emplois)
    if kandet_file.is_file():
        kandet_raw = json.loads(kandet_file.read_text(encoding="utf-8")).get("offers", [])
        for item in kandet_raw:
            records = item.get("source_records", [])
            for rec in records:
                if rec.get("source") != "Guichet-Emplois":
                    continue
                raw_id = rec.get("source_id", "").replace("article-", "").replace("ge-", "").strip()
                job_id = f"ge-{raw_id}"
                if not raw_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                titre = rec.get("title", "Titre non spécifié")
                desc = rec.get("description") or None
                est_stage, statut_stage, _ = classify_stage(titre, rec.get("job_type", ""), desc or "")

                part = rec.get("origin_site")
                if part and any(k in part for k in ["Guichet", "Job Bank"]):
                    part = None
                elif part:
                    part = part.replace(".ca", "").replace(".com", "").strip()

                competences = normalize_skills(rec.get("tags", []), title_text=titre)

                offer = JobOffer(
                    id=job_id,
                    titre=titre,
                    entreprise=rec.get("employer", "Non spécifié"),
                    lieu=rec.get("location", "Québec (QC)"),
                    province="QC",
                    pays="Canada",
                    url=clean_posting_url(rec.get("url", "")),
                    source="guichet-emplois",
                    source_partenaire=part,
                    date_publication=rec.get("published_at") or None,
                    type_poste="Stage" if est_stage else "Temps plein",
                    modalite=rec.get("work_mode") or None,
                    est_stage=est_stage,
                    statut_stage=statut_stage,
                    description=desc,
                    competences_cles=competences,
                    salaire=rec.get("salary") or None,
                )
                offers.append(offer)

    # 3. Traitement des offres issues du cache local Guichet-Emplois (recherche et fiches détaillées)
    search_dir = CUR_DIR / "cache" / "guichet_emplois" / "search"
    details_dir = CUR_DIR / "cache" / "guichet_emplois" / "details"
    if search_dir.is_dir():
        from scrapers.guichet_emplois import parse_search_page_html, enrich_job_offer_from_detail
        cached_count = 0
        for sf in search_dir.glob("*.html"):
            try:
                page_offers, _ = parse_search_page_html(sf.read_text(encoding="utf-8"))
                for po in page_offers:
                    if po.id in seen_ids:
                        continue
                    clean_id = po.id.replace("ge-", "").replace("gc-", "")
                    det_file = details_dir / f"detail_{clean_id}.html"
                    if det_file.is_file():
                        po = enrich_job_offer_from_detail(po, det_file.read_text(encoding="utf-8"))
                    seen_ids.add(po.id)
                    offers.append(po)
                    cached_count += 1
            except Exception as err:
                pass
        if cached_count > 0:
            print(f" • {cached_count} nouvelle(s) offre(s) intégrée(s) depuis le cache de recherche Guichet-Emplois.")

    # Tri par date décroissante puis par ID
    offers.sort(key=lambda o: (o.date_publication or "", o.id), reverse=True)

    # Export JSON avec encodage UTF-8 et indentation lisible
    data = [o.model_dump() for o in offers]
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {len(offers)} offres exportees avec succes dans {output_file}")


if __name__ == "__main__":
    main()
