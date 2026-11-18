"""
pipeline.py — Pipeline d'agrégation, de déduplication inter-sources, de filtrage et d'export.
Auteure : Elvira (Projet jobs-insights — Livrable 3 Multi-Sources)

Ce module :
1. Agrège les offres issues des 4 sources (Jobboom, Guichet-Emplois, Jobillico, Remotive).
2. Applique le filtre strict de fraîcheur (`date_publication >= 2026-01-01`) et de validité (`date_expiration >= aujourd'hui`),
   ainsi que le filtre métier TI (`is_it_job`).
3. Déduplique les offres en double entre sites via l'empreinte normalisée `(titre, entreprise, ville)`
   et fusionne leurs informations (salaire, GPS, compétences, description la plus complète, URLs cumulées).
4. Exporte en JSON, en CSV compatible Excel (`utf-8-sig`) et génère automatiquement `visualiseur.html`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from collecteurs import JobboomCollector, JobillicoCollector
from models import (
    JobOffer,
    clean_html_text,
    dedup_key,
    detect_is_internship,
    detect_work_mode,
    extract_skills,
    is_it_job,
    is_recent_and_valid_offer,
    normalize_city_name,
    normalize_iso_date,
)

SOURCE_LABELS = {
    "jobboom": "Jobboom",
    "guichet-emplois": "Guichet-Emplois",
    "guichet_emplois": "Guichet-Emplois",
    "guichet emplois": "Guichet-Emplois",
    "jobillico": "Jobillico",
    "jobillico québec": "Jobillico",
    "remotive": "Remotive",
}


class MultiSourcePipeline:
    """Pipeline d'unification, de déduplication inter-sources et d'export."""

    @staticmethod
    def normalize_source_name(raw_source: str | None) -> str:
        if not raw_source:
            return "Jobboom"
        low = raw_source.strip().lower()
        for key, canonical in SOURCE_LABELS.items():
            if key in low:
                return canonical
        return raw_source.strip()

    @staticmethod
    def merge_two_offers(primary: JobOffer, secondary: JobOffer) -> JobOffer:
        """
        Fusionne deux offres correspondant au même poste (trouvé sur deux canaux ou deux sites différents)
        sans aucune perte d'information : conserve le salaire, le GPS, le code postal,
        la description la plus riche et cumule les compétences, origines et URLs.
        """
        for orig in secondary.origines_decouverte:
            if orig not in primary.origines_decouverte:
                primary.origines_decouverte.append(orig)
        if secondary.source not in primary.origines_decouverte and secondary.source != primary.source:
            primary.origines_decouverte.append(secondary.source)

        for u in secondary.urls_sources:
            if u and u not in primary.urls_sources:
                primary.urls_sources.append(u)

        if not primary.salaire and secondary.salaire:
            primary.salaire = secondary.salaire
        if not primary.coordonnees_gps and secondary.coordonnees_gps:
            primary.coordonnees_gps = secondary.coordonnees_gps
        if not primary.code_postal and secondary.code_postal:
            primary.code_postal = secondary.code_postal
        if not primary.logo_entreprise and secondary.logo_entreprise:
            primary.logo_entreprise = secondary.logo_entreprise
        if not primary.partenaire_origine and secondary.partenaire_origine:
            primary.partenaire_origine = secondary.partenaire_origine
        if not primary.date_expiration and secondary.date_expiration:
            primary.date_expiration = secondary.date_expiration

        if len(secondary.description_texte or "") > len(primary.description_texte or ""):
            primary.description_texte = secondary.description_texte

        for skill in secondary.competences_cles:
            if skill not in primary.competences_cles:
                primary.competences_cles.append(skill)

        primary.est_stage = primary.est_stage or secondary.est_stage
        if primary.modalite == "Sur place" and secondary.modalite in ("Hybride", "Télétravail"):
            primary.modalite = secondary.modalite

        return primary

    @classmethod
    def deduplicate_and_merge(cls, offers: list[JobOffer]) -> list[JobOffer]:
        """
        Déduplique une liste d'offres :
        1. Par identifiant exact (`id`).
        2. Par empreinte inter-sources `(titre, entreprise, ville)` normalisée.
        """
        by_id: dict[str, JobOffer] = {}
        by_fingerprint: dict[tuple[str, str, str], JobOffer] = {}
        ordered_result: list[JobOffer] = []

        for offer in offers:
            if offer.id in by_id:
                cls.merge_two_offers(by_id[offer.id], offer)
                continue

            fp = dedup_key(offer)
            if fp[0] and fp[1] and fp in by_fingerprint:
                cls.merge_two_offers(by_fingerprint[fp], offer)
                by_id[offer.id] = by_fingerprint[fp]
                continue

            by_id[offer.id] = offer
            if fp[0] and fp[1]:
                by_fingerprint[fp] = offer
            ordered_result.append(offer)

        return ordered_result

    @staticmethod
    def filter_valid_recent_it_offers(
        offers: list[JobOffer],
        min_year: int = 2026,
        today_iso: str = "2026-11-18",
    ) -> list[JobOffer]:
        """
        Filtre strict garantissant que :
        - 100 % des offres appartiennent au domaine TI (`is_it_job`) ;
        - 100 % des offres sont publiées en `min_year` (2026) ou après (aucune offre des années passées) ;
        - 100 % des offres sont toujours valides (`date_expiration` absente ou >= `today_iso`).
        """
        valid_offers: list[JobOffer] = []
        for offer in offers:
            if not is_it_job(offer.titre, offer.url):
                continue
            if not is_recent_and_valid_offer(
                offer.date_publication,
                offer.date_expiration,
                min_year=min_year,
                today_iso=today_iso,
            ):
                continue
            valid_offers.append(offer)
        return valid_offers

    @staticmethod
    def filter_offers(
        offers: list[JobOffer],
        source: str | None = None,
        ville: str | None = None,
        modalite: str | None = None,
        competence: str | None = None,
        stages_only: bool = False,
        query: str | None = None,
    ) -> list[JobOffer]:
        """Filtre multicritère sur la liste d'offres unifiées."""
        filtered: list[JobOffer] = []
        for o in offers:
            if source and o.source.lower() != source.strip().lower():
                continue
            if ville and ville.strip().lower() not in o.ville.lower():
                continue
            if modalite and o.modalite.lower() != modalite.strip().lower():
                continue
            if competence:
                target_skill = competence.strip().lower()
                if not any(s.lower() == target_skill for s in o.competences_cles):
                    continue
            if stages_only and not o.est_stage:
                continue
            if query:
                q = query.strip().lower()
                haystack = f"{o.id} {o.titre} {o.entreprise} {o.ville} {o.description_texte} {' '.join(o.competences_cles)}".lower()
                if q not in haystack:
                    continue
            filtered.append(o)
        return filtered

    @classmethod
    def dict_to_job_offer(cls, item: dict[str, Any], default_origin: str = "") -> JobOffer | None:
        """Convertit un dictionnaire d'offre (issu des jeux de données du dépôt) en `JobOffer` normalisé."""
        url = str(item.get("url") or item.get("url_source") or "").strip()
        if not url:
            return None

        raw_source = str(item.get("source") or "Jobboom")
        # On ne garde que les 4 sources cibles (Jobboom, Guichet-Emplois, Jobillico, Remotive)
        low_src = raw_source.lower()
        if not any(k in low_src for k in ("jobboom", "guichet", "jobillico", "remotive")):
            return None

        source = cls.normalize_source_name(raw_source)
        title = clean_html_text(item.get("titre_employeur") or item.get("titre") or item.get("title") or "")
        if not title:
            return None

        desc = clean_html_text(
            item.get("description_texte")
            or item.get("description")
            or item.get("description_preview")
            or ""
        )
        company = clean_html_text(item.get("entreprise") or item.get("company") or "Non spécifié")
        raw_city = item.get("ville") or item.get("lieu") or item.get("city") or "Québec"
        city = normalize_city_name(raw_city) if source != "Remotive" else str(raw_city)

        pub_date = normalize_iso_date(
            item.get("date_publication") or item.get("date_posted") or item.get("published_at")
        )
        exp_date = normalize_iso_date(
            item.get("date_expiration") or item.get("valid_through") or item.get("date_fin")
        )

        coords = item.get("coordonnees_gps")
        if not isinstance(coords, dict):
            lat = item.get("latitude") or (item.get("gps", {}) or {}).get("lat")
            lon = item.get("longitude") or (item.get("gps", {}) or {}).get("lon")
            try:
                coords = (
                    {"latitude": float(lat), "longitude": float(lon)}
                    if lat is not None and lon is not None
                    else None
                )
            except (TypeError, ValueError):
                coords = None

        raw_id = str(item.get("id") or "").strip()
        if not raw_id:
            if source == "Jobboom":
                raw_id = JobboomCollector.extract_job_id(url)
            elif source == "Jobillico":
                raw_id = JobillicoCollector.extract_job_id(url)
            else:
                raw_id = f"{source[:2].lower()}-{abs(hash(url)) % 10_000_000}"

        emp_raw = item.get("type_contrat") or item.get("type_poste") or item.get("employment_type")
        if isinstance(emp_raw, list):
            emp_types = [str(x) for x in emp_raw if x]
        elif isinstance(emp_raw, str) and emp_raw:
            emp_types = [emp_raw]
        else:
            emp_types = ["FULL_TIME"]

        modalite_raw = str(item.get("modalite") or "")
        if modalite_raw in ("Sur place", "Hybride", "Télétravail"):
            modalite = modalite_raw
        else:
            modalite = detect_work_mode(title, desc, modalite_raw)

        est_stage = bool(item.get("est_stage")) or detect_is_internship(title, desc, emp_types)
        skills = extract_skills(title, desc)
        for existing_skill in item.get("competences_cles") or []:
            s_clean = str(existing_skill).strip()
            if s_clean and s_clean not in ("C", "VUE") and s_clean not in skills:
                skills.append(s_clean)

        origins = list(item.get("origines_decouverte") or ([default_origin] if default_origin else [source]))

        return JobOffer(
            id=raw_id,
            source=source,
            partenaire_origine=item.get("partenaire_origine") or item.get("source_partenaire"),
            origines_decouverte=origins,
            titre=title,
            entreprise=company,
            logo_entreprise=item.get("logo_entreprise"),
            ville=city,
            province=str(item.get("province") or item.get("region") or "QC"),
            pays="CA",
            code_postal=item.get("code_postal"),
            coordonnees_gps=coords,
            salaire=item.get("salaire"),
            type_contrat=emp_types,
            modalite=modalite,
            est_stage=est_stage,
            competences_cles=skills,
            date_publication=pub_date,
            date_expiration=exp_date,
            url=url,
            description_texte=desc,
        )

    @classmethod
    def consolidate_workspace_datasets(cls, repo_root: Path) -> list[JobOffer]:
        """
        Rassemble, filtre (uniquement 2026 et valides) et déduplique les offres TI réelles
        des 4 sources (Jobboom, Guichet-Emplois, Jobillico, Remotive) présentes dans le dépôt.
        """
        candidate_files: list[tuple[Path, str]] = [
            (
                repo_root / "equipe" / "elvira" / "03-amelioration-preuve-de-concept" / "offres_multi_sources.json",
                " cumul_existant",
            ),
            (
                repo_root / "equipe" / "elvira" / "03-amelioration-preuve-de-concept" / "offres_jobboom_v2.json",
                "Jobboom:v2_existant",
            ),
            (repo_root / "equipe" / "elvira" / "02-preuve-de-concept-scraping" / "offres_jobboom.json", "Jobboom:mots_cles_elvira"),
            (repo_root / "equipe" / "gregory" / "livrable3" / "data" / "offres_jobboom.json", "Jobboom:secteur_ti"),
            (repo_root / "equipe" / "mamadou" / "03-amelioration-preuve-de-concept" / "echantillon_v2.json", "Multi:mamadou_v2"),
            (repo_root / "equipe" / "mamadou" / "02-preuve-de-concept-scraping" / "sample_scraped_jobs.json", "Multi:mamadou_v1"),
            (repo_root / "equipe" / "gregory" / "livrable3" / "data" / "offres_guichet_emplois.json", "Guichet-Emplois:cnp_ti"),
            (repo_root / "equipe" / "gregory" / "livrable3" / "data" / "offres_remotive.json", "Remotive:api_rest"),
        ]

        raw_offers: list[JobOffer] = []
        for file_path, origin_tag in candidate_files:
            if not file_path.exists():
                continue
            try:
                items = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                offer = cls.dict_to_job_offer(item, default_origin=origin_tag)
                if offer is not None:
                    raw_offers.append(offer)

        valid_recent_it = cls.filter_valid_recent_it_offers(raw_offers)
        deduplicated = cls.deduplicate_and_merge(valid_recent_it)
        # Tri par date de publication décroissante (offres les plus récentes en premier)
        deduplicated.sort(key=lambda o: (o.date_publication or "", o.id), reverse=True)
        return deduplicated

    @staticmethod
    def export_json(offers: list[JobOffer], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [o.to_dict() for o in offers]
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def export_csv(offers: list[JobOffer], output_path: Path) -> None:
        """Exporte les offres en CSV (`utf-8-sig` avec séparateur `;`) directement ouvrable dans Excel."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "id",
            "source",
            "partenaire_origine",
            "titre",
            "entreprise",
            "ville",
            "province",
            "modalite",
            "est_stage",
            "salaire",
            "date_publication",
            "date_expiration",
            "competences_cles",
            "url",
        ]
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for o in offers:
                writer.writerow(
                    {
                        "id": o.id,
                        "source": o.source,
                        "partenaire_origine": o.partenaire_origine or "",
                        "titre": o.titre,
                        "entreprise": o.entreprise,
                        "ville": o.ville,
                        "province": o.province,
                        "modalite": o.modalite,
                        "est_stage": "Oui" if o.est_stage else "Non",
                        "salaire": o.salaire or "",
                        "date_publication": o.date_publication or "",
                        "date_expiration": o.date_expiration or "",
                        "competences_cles": ", ".join(o.competences_cles),
                        "url": o.url,
                    }
                )
