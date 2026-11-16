"""
Livrable 3 — Amélioration du POC de scraping sur Guichet-Emplois Canada
Auteur : Mamadou

Combinaison des approches de Kandet (recherche par codes CNP TI + partenaire d'origine),
Hugo (repli DOM sur les fiches) et Mamadou v1 (extraction RDFa des fiches individuelles) :
- Utilisation de `requests` et `BeautifulSoup` (remplace les regex HTML de la v1 et allège le code).
- Recherche par les 14 codes CNP 2021 du secteur informatique au Québec (`fprov=QC`) + filtre étudiant/stage (`fsrc=16`).
- Enrichissement sur chaque fiche détaillée (`/rechercheemplois/offredemploi/{id}`) pour obtenir la description
  complète (sans troncature au premier `</div>`), les exigences et détecter les stages.
- Respect de `robots.txt` (`RobotFileParser`), `User-Agent` honnête et `Crawl-delay: 5`.
"""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://www.guichetemplois.gc.ca"
SEARCH_PATH = "/jobsearch/rechercheemplois"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "jobs-insights-osullivan/1.0 (atelier-livrable-3; mamadou)"
DEFAULT_CRAWL_DELAY = 5.0

# 14 codes CNP 2021 du domaine informatique (repris de l'approche de Kandet)
CNP_CODES_TI: tuple[str, ...] = (
    "20012",  # Gestionnaires des systèmes informatiques
    "21211",  # Spécialistes des données (Data Scientists)
    "21220",  # Spécialistes en cybersécurité
    "21221",  # Spécialistes des systèmes d'affaires
    "21222",  # Spécialistes en informatique
    "21223",  # Analystes de bases de données et administrateurs de données
    "21230",  # Développeurs de systèmes informatiques et programmeurs
    "21231",  # Ingénieurs et concepteurs en logiciel
    "21232",  # Développeurs et programmeurs de logiciels
    "21233",  # Concepteurs Web
    "21234",  # Développeurs et programmeurs Web
    "22220",  # Techniciens de réseaux informatiques
    "22221",  # Agents de soutien aux utilisateurs
    "22222",  # Évaluateurs de systèmes informatiques (QA)
)


@dataclass
class JobBankOffer:
    """Modèle uniforme d'une offre Guichet-Emplois (aucune valeur inventée : None si absent)."""

    source_id: str
    url: str
    cnp_title: Optional[str] = None
    title: Optional[str] = None
    employer: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    published_at: Optional[str] = None
    valid_through: Optional[str] = None
    workplace_mode: Optional[str] = None
    employment_type: Optional[str] = None
    education_level: Optional[str] = None
    origin_partner: Optional[str] = None
    stage_status: str = "not_indicated"
    description: Optional[str] = None


def build_cnp_search_url(
    province: str = "QC",
    cnp_codes: tuple[str, ...] = CNP_CODES_TI,
    student_only: bool = False,
    keyword: Optional[str] = None,
    page: int = 1,
) -> str:
    """Construit l'URL de recherche Guichet-Emplois avec les codes CNP TI et filtres."""
    params: list[tuple[str, str]] = []
    if keyword:
        params.append(("searchstring", keyword.strip()))
    for code in cnp_codes:
        params.append(("fn21", code))
    if province:
        params.append(("fprov", province))
    if student_only:
        params.append(("fsrc", "16"))  # Filtre officiel emplois étudiants / stages
    params.append(("sort", "D"))
    if page > 1:
        params.append(("page", str(page)))
    return f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"


def check_robots_permission(session: requests.Session, target_url: str) -> tuple[bool, float]:
    """Vérifie robots.txt et retourne (autorisé, crawl_delay)."""
    rp = RobotFileParser()
    try:
        resp = session.get(ROBOTS_URL, timeout=10)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            allowed = rp.can_fetch(USER_AGENT, target_url)
            delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*") or DEFAULT_CRAWL_DELAY
            return allowed, float(delay)
    except requests.RequestException:
        pass
    return True, DEFAULT_CRAWL_DELAY


def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def detect_stage_status(title: Optional[str], description: Optional[str], student_filter: bool = False) -> str:
    """
    Classifie si l'offre est un stage à partir du titre et de la description complète.
    Exclut les mentions négatives ou d'encadrement (ex: 'superviser les stagiaires').
    """
    combined = f"{title or ''} {description or ''}".lower()
    # Exclure les contextes où le poste encadre un stagiaire ou refuse les stages
    cleaned = re.sub(
        r"\b(superviser|encadrer|former|accompagner)\s+(des|les|un|une)?\s*(stagiaires?|étudiants?)\b",
        "",
        combined,
    )
    if re.search(r"\b(stage|stagiaire|intern|internship|co-op|coop|alternance|ate)\b", cleaned):
        return "confirmed_stage"
    if student_filter or re.search(r"\b(emploi\s+étudiant|étudiant\(e\)|student\s+job)\b", cleaned):
        return "possible_stage"
    return "not_indicated"


def parse_search_results_html(html_text: str) -> list[JobBankOffer]:
    """
    Extrait les offres de la page de résultats Guichet-Emplois avec BeautifulSoup.
    Conserve le titre CNP, l'employeur, le lieu, le salaire, la modalité et le site partenaire.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    offers: list[JobBankOffer] = []
    seen_ids: set[str] = set()

    for article in soup.select("article[id^='article-']"):
        art_id = str(article.get("id", "")).replace("article-", "").strip()
        if not art_id or art_id in seen_ids:
            continue
        seen_ids.add(art_id)

        # Titre CNP affiché dans la liste
        title_node = article.select_one("span.noctitle")
        cnp_title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else None

        # Employeur
        biz_node = article.select_one("li.business")
        employer = _clean_text(biz_node.get_text(" ", strip=True)) if biz_node else None

        # Lieu (en retirant le texte lecteur d'écran 'Emplacement')
        loc_node = article.select_one("li.location")
        location = None
        if loc_node:
            loc_copy = BeautifulSoup(str(loc_node), "html.parser")
            for hidden in loc_copy.select(".wb-inv"):
                hidden.decompose()
            location = _clean_text(loc_copy.get_text(" ", strip=True))

        # Salaire (en retirant le libellé 'Salaire :')
        sal_node = article.select_one("li.salary")
        salary = None
        if sal_node:
            sal_copy = BeautifulSoup(str(sal_node), "html.parser")
            for hidden in sal_copy.select(".wb-inv"):
                hidden.decompose()
            raw_sal = _clean_text(sal_copy.get_text(" ", strip=True))
            if raw_sal:
                raw_sal = re.sub(r"^Salaire\s*:\s*", "", raw_sal, flags=re.I).strip()
            if raw_sal and not any(k in raw_sal.lower() for k in ("non disponible", "not available")):
                salary = raw_sal

        # Date affichée
        date_node = article.select_one("li.date")
        published_at = _clean_text(date_node.get_text(" ", strip=True)) if date_node else None

        # Modalité (Sur place, Hybride, Télétravail)
        tele_node = article.select_one("span.telework")
        workplace_mode = _clean_text(tele_node.get_text(" ", strip=True)) if tele_node else None

        # Site partenaire d'origine (ex: Jobillico, Québec emploi, Talent.com)
        partner_node = article.select_one("li.source span.wb-inv")
        origin_partner = _clean_text(partner_node.get_text(" ", strip=True)) if partner_node else "Guichet-Emplois"

        clean_url = f"{BASE_URL}/rechercheemplois/offredemploi/{art_id}"

        offers.append(
            JobBankOffer(
                source_id=art_id,
                url=clean_url,
                cnp_title=cnp_title,
                title=cnp_title,
                employer=employer,
                location=location,
                salary=salary,
                published_at=published_at,
                workplace_mode=workplace_mode,
                origin_partner=origin_partner,
            )
        )

    return offers


def parse_job_detail_html(html_text: str, offer: JobBankOffer, student_filter: bool = False) -> JobBankOffer:
    """
    Enrichit une offre à partir du HTML de sa fiche détaillée via BeautifulSoup :
    - Récupère la description complète (RDFa `property="description"` ou `#job-posting-detail`)
      sans jamais tronquer aux `<div>` imbriqués (correction du bug regex de la v1).
    - Récupère le titre de la fiche, la date de fin (`validThrough`), le type d'emploi et le niveau d'études.
    - Met à jour `stage_status` grâce au texte complet de la fiche.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Titre RDFa sur la fiche
    title_prop = soup.find(attrs={"property": "title"})
    if title_prop:
        detail_title = _clean_text(title_prop.get_text(" ", strip=True))
        if detail_title:
            offer.title = detail_title

    # 2. Employeur RDFa (si absent de la liste)
    if not offer.employer:
        org_prop = soup.find(attrs={"property": "hiringOrganization"})
        if org_prop:
            name_prop = org_prop.find(attrs={"property": "name"}) or org_prop
            offer.employer = _clean_text(name_prop.get_text(" ", strip=True))

    # 3. Description complète (RDFa property="description" puis repli DOM)
    # Note : les offres partenaires (ex: Jobillico) contiennent du HTML doublement échappé (&lt;p&gt;)
    desc_node = soup.find(attrs={"property": "description"}) or soup.select_one("#job-posting-detail")
    if desc_node:
        raw_desc = desc_node.get_text(" ", strip=True)
        if "<" in raw_desc and ">" in raw_desc:
            raw_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)
        offer.description = _clean_text(raw_desc)

    # 4. Date limite de candidature (validThrough)
    valid_node = soup.find(attrs={"property": "validThrough"})
    if valid_node:
        offer.valid_through = _clean_text(valid_node.get_text(" ", strip=True))

    # 5. Type d'emploi et horaire (employmentType / workHours)
    emp_parts: list[str] = []
    for prop_name in ("employmentType", "workHours"):
        node = soup.find(attrs={"property": prop_name})
        if node:
            val = _clean_text(node.get_text(" ", strip=True))
            if val and val not in emp_parts:
                emp_parts.append(val)
    if emp_parts:
        offer.employment_type = ", ".join(emp_parts)

    # 6. Niveau d'études requis (educationRequirements)
    edu_node = soup.find(attrs={"property": "educationRequirements"})
    if edu_node:
        offer.education_level = _clean_text(edu_node.get_text(" ", strip=True))

    # 7. Détection de stage sur le titre + description complète
    offer.stage_status = detect_stage_status(offer.title, offer.description, student_filter=student_filter)
    return offer


def collect_offers(
    limit: int = 5,
    student_only: bool = False,
    keyword: Optional[str] = None,
    delay: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Exécute la collecte complète : vérification robots.txt -> liste CNP -> enrichissement fiches."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "fr-CA,fr;q=0.9",
        }
    )

    search_url = build_cnp_search_url(province="QC", student_only=student_only, keyword=keyword)
    allowed, robots_delay = check_robots_permission(session, search_url)
    effective_delay = delay if delay is not None else robots_delay

    if not allowed:
        raise PermissionError(f"Accès refusé par {ROBOTS_URL} pour {search_url}")

    print(f"[1/3] Recherche CNP TI au Québec : {search_url}")
    print(f"      -> robots.txt : autorisé | délai appliqué : {effective_delay:.1f}s")

    resp = session.get(search_url, timeout=15)
    resp.raise_for_status()

    offers = parse_search_results_html(resp.text)
    print(f"[2/3] {len(offers)} offres détectées sur la 1re page de résultats.")

    selected = offers[:limit]
    for idx, offer in enumerate(selected, start=1):
        time.sleep(effective_delay)
        print(f"[3/3] ({idx}/{len(selected)}) Lecture de la fiche : {offer.url} (origine : {offer.origin_partner})")
        try:
            detail_resp = session.get(offer.url, timeout=15)
            detail_resp.raise_for_status()
            parse_job_detail_html(detail_resp.text, offer, student_filter=student_only)
        except requests.RequestException as exc:
            print(f"      ! Erreur réseau sur {offer.url} : {exc}")

    return [asdict(o) for o in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecteur Guichet-Emplois par codes CNP TI + fiches RDFa (Livrable 3)")
    parser.add_argument("--limite", type=int, default=5, help="Nombre de fiches détaillées à enrichir (défaut: 5)")
    parser.add_argument("--stages", action="store_true", help="Activer le filtre emplois étudiants / stages (fsrc=16)")
    parser.add_argument("--mot-cle", type=str, default=None, help="Mot-clé additionnel optionnel")
    parser.add_argument("--delai", type=float, default=None, help="Délai en secondes entre requêtes (défaut: robots.txt = 5s)")
    parser.add_argument("--sortie", type=str, default="echantillon_v2.json", help="Fichier JSON de sortie")
    args = parser.parse_args()

    results = collect_offers(
        limit=args.limite,
        student_only=args.stages,
        keyword=args.mot_cle,
        delay=args.delai,
    )

    out_path = Path(__file__).parent / args.sortie
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTerminé : {len(results)} offres enrichies enregistrées dans {out_path.name}")


if __name__ == "__main__":
    main()
