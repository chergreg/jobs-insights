"""
parsers.py - Logique pure de parsing et de normalisation pour Guichet-Emplois.
Ce module est totalement découplé du réseau et peut être testé 100 % hors ligne.

Fonctionnalités :
1. Extraction depuis le flux Atom XML officiel (/jobsearch/feed/jobSearchRSSfeed).
2. Extraction depuis les résultats de recherche HTML (/jobsearch/jobsearch).
3. Extraction détaillée par cascade :
   - Étape 1 : Métadonnées sémantiques RDFa / Schema.org (JobPosting)
   - Étape 2 : Repli DOM HTML (sections description, modalité et compétences)
4. Détection stricte et sans faux positifs des compétences techniques (exclut 'C' isolé et 'Vue').
5. Classification fine des stages et modalités.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from models import JobOffer

# Dictionnaire de motifs stricts pour compétences TI (sans faux positifs français)
# Note: Pour C++ et C#, le symbole '#' et '+' n'étant pas dans \w, on utilise (?=[^\w]|$).
TECH_PATTERNS = [
    ("Python", re.compile(r"\bpython\b", re.IGNORECASE)),
    ("Java", re.compile(r"\bjava\b(?!script)", re.IGNORECASE)),
    ("JavaScript", re.compile(r"\b(?:javascript|js)\b", re.IGNORECASE)),
    ("TypeScript", re.compile(r"\btypescript\b", re.IGNORECASE)),
    ("C#", re.compile(r"\bc#(?=[^\w#]|$)", re.IGNORECASE)),
    ("C++", re.compile(r"\bc\+\+(?=[^\w\+]|$)", re.IGNORECASE)),
    ("C", re.compile(r"(?:\blangage\s+c\b|\bprog(?:rammation)?\s+c\b|\bc\s*\/\s*c\+\+|\bansi\s+c\b)", re.IGNORECASE)),
    ("React", re.compile(r"\breact(?:\.js)?\b", re.IGNORECASE)),
    ("Angular", re.compile(r"\bangular(?:\.js)?\b", re.IGNORECASE)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|vuejs|framework\s+vue)\b", re.IGNORECASE)),
    ("Node.js", re.compile(r"\bnode(?:\.js)?\b", re.IGNORECASE)),
    ("PHP", re.compile(r"\bphp\b", re.IGNORECASE)),
    ("SQL", re.compile(r"\bsql\b", re.IGNORECASE)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.IGNORECASE)),
    ("MySQL", re.compile(r"\bmysql\b", re.IGNORECASE)),
    ("MongoDB", re.compile(r"\bmongodb\b", re.IGNORECASE)),
    ("Docker", re.compile(r"\bdocker\b", re.IGNORECASE)),
    ("Kubernetes", re.compile(r"\b(?:kubernetes|k8s)\b", re.IGNORECASE)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", re.IGNORECASE)),
    ("Azure", re.compile(r"\bazure\b", re.IGNORECASE)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", re.IGNORECASE)),
    ("Git", re.compile(r"\bgit\b(?!e)", re.IGNORECASE)),
    ("Linux", re.compile(r"\blinux\b", re.IGNORECASE)),
    ("Spring Boot", re.compile(r"\bspring\s*boot\b", re.IGNORECASE)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.IGNORECASE)),
    ("Django", re.compile(r"\bdjango\b", re.IGNORECASE)),
    ("CI/CD", re.compile(r"\bci[\/\-]cd\b", re.IGNORECASE)),
    ("Agile", re.compile(r"\bagile\b", re.IGNORECASE)),
    ("Scrum", re.compile(r"\bscrum\b", re.IGNORECASE)),
    ("QA", re.compile(r"\b(?:assurance\s+qualit[eé]|qa)\b", re.IGNORECASE)),
]

STAGE_PATTERNS = re.compile(
    r"\b(?:stage|stages|stagiaire|stagiaires|intern|interns|internship|co[\s-]?op)\b",
    re.IGNORECASE
)


def clean_text(raw_html: str) -> str:
    """Nettoie le balisage HTML et normalise les espaces."""
    if not raw_html:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw_html))
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def extract_tech_skills(text: str) -> List[str]:
    """
    Extrait les compétences techniques en éliminant les faux positifs
    courants en français (ex: 'vue d'ensemble' ne matche pas Vue.js, 'c.' ne matche pas C).
    """
    if not text:
        return []
    found: Set[str] = set()
    for tech_name, pattern in TECH_PATTERNS:
        if pattern.search(text):
            found.add(tech_name)
    return sorted(list(found))


def detect_stage(title: str, text: str = "") -> str:
    """Détecte si l'offre est un stage, un emploi étudiant ou un emploi standard."""
    comb = f"{title} {text}".lower()
    if STAGE_PATTERNS.search(comb):
        return "Stage"
    if "étudiant" in comb or "student" in comb:
        return "Étudiant"
    return "Temps plein"


# ==============================================================================
# 1. PARSEUR FLUX ATOM XML OFFICIEL (Rapide, structuré, résilient)
# ==============================================================================
def parse_atom_feed(xml_content: str | bytes, base_url: str = "https://www.guichetemplois.gc.ca") -> List[JobOffer]:
    """
    Parse les entrées d'un flux Atom XML officiel de Guichet-Emplois.
    Chaque <entry> contient le titre, l'url, la date et un bloc <summary type="html">
    avec l'employeur, le salaire, le numéro d'emploi et la localisation.
    """
    if isinstance(xml_content, str):
        xml_bytes = xml_content.encode("utf-8")
    else:
        xml_bytes = xml_content

    offers: List[JobOffer] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return offers

    atom_ns = "{http://www.w3.org/2005/Atom}"

    for entry in root.findall(f"{atom_ns}entry"):
        title_el = entry.find(f"{atom_ns}title")
        titre = title_el.text.strip() if title_el is not None and title_el.text else "Titre non spécifié"

        link_el = entry.find(f"{atom_ns}link")
        url_source = link_el.attrib.get("href", "") if link_el is not None else ""
        if url_source and not url_source.startswith("http"):
            url_source = urljoin(base_url, url_source)

        updated_el = entry.find(f"{atom_ns}updated")
        date_pub = updated_el.text.strip() if updated_el is not None and updated_el.text else None

        id_el = entry.find(f"{atom_ns}id")
        raw_id = id_el.text.strip() if id_el is not None and id_el.text else url_source.split("/")[-1].split("?")[0]
        clean_id = raw_id.replace("article-", "").replace("gc-", "")
        job_id = f"gc-{clean_id}"

        # Extraction des métadonnées contenues dans le HTML du résumé
        summary_el = entry.find(f"{atom_ns}summary")
        summary_html = summary_el.text if summary_el is not None and summary_el.text else ""

        lieu = "Québec (QC)"
        province = "QC"
        entreprise = "Non spécifié"
        salaire = None

        if summary_html:
            # Recherche de l'employeur
            emp_m = re.search(r"<strong>(?:Employer|Employeur)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if emp_m:
                entreprise = emp_m.group(1).strip()

            # Recherche du lieu
            loc_m = re.search(r"<strong>(?:Location|Emplacement)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if loc_m:
                lieu = loc_m.group(1).strip()
                for prov in ["QC", "ON", "BC", "AB", "MB", "NB", "NS"]:
                    if f"({prov})" in lieu or prov in lieu:
                        province = prov
                        break

            # Recherche du salaire
            sal_m = re.search(r"<strong>(?:Salary|Salaire)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if sal_m:
                salaire = sal_m.group(1).strip()

        type_poste = detect_stage(titre, summary_html)
        description_initiale = clean_text(summary_html) if summary_html else None

        offer = JobOffer(
            id=job_id,
            titre=titre,
            entreprise=entreprise,
            lieu=lieu,
            province=province,
            pays="Canada",
            salaire=salaire,
            date_publication=date_pub,
            type_poste=type_poste,
            modalite="Non spécifié",
            competences_cles=extract_tech_skills(titre),
            description=description_initiale,
            url_source=url_source,
            source="Guichet-Emplois",
            partenaire="Guichet-Emplois (Atom Feed)",
            methode_extraction="Atom-XML"
        )
        offers.append(offer)

    return offers


# ==============================================================================
# 2. PARSEUR DE RECHERCHE HTML (Résultats de recherche par mot-clé)
# ==============================================================================
def parse_search_page_html(html_str: str, base_url: str = "https://www.guichetemplois.gc.ca") -> List[JobOffer]:
    """Parse les cartes <article> sur les pages de résultats HTML de Guichet-Emplois."""
    soup = BeautifulSoup(html_str, "html.parser")
    articles = soup.find_all("article")
    offers: List[JobOffer] = []

    for article in articles:
        try:
            link_tag = article.find("a", class_="resultJobItem")
            if not link_tag or "href" not in link_tag.attrs:
                continue

            raw_href = link_tag["href"]
            clean_href = raw_href.split(";")[0]
            full_url = urljoin(base_url, clean_href)

            raw_id = article.get("id", "")
            base_ident = raw_id.replace("article-", "").replace("gc-", "") if raw_id else clean_href.split("/")[-1]
            job_id = f"gc-{base_ident}"

            title_tag = article.find("span", class_="noctitle")
            titre = title_tag.get_text(strip=True) if title_tag else "Titre non spécifié"

            business_tag = article.find("li", class_="business")
            entreprise = business_tag.get_text(strip=True) if business_tag else "Non spécifié"

            location_tag = article.find("li", class_="location")
            lieu_brut = location_tag.get_text(" ", strip=True) if location_tag else "Québec (QC)"
            lieu_propre = re.sub(r"^(emplacement|location)\s*", "", lieu_brut, flags=re.IGNORECASE).strip()

            province = "QC"
            for prov in ["QC", "ON", "BC", "AB", "MB", "NB", "NS"]:
                if f"({prov})" in lieu_propre:
                    province = prov
                    break

            salary_tag = article.find("li", class_="salary")
            salaire = None
            if salary_tag:
                sal_txt = salary_tag.get_text(" ", strip=True)
                salaire = re.sub(r"^(salaire\s*:?|salary\s*:?)\s*", "", sal_txt, flags=re.IGNORECASE).strip()

            date_tag = article.find("li", class_="date")
            date_pub = date_tag.get_text(strip=True) if date_tag else None

            source_tag = article.find("span", class_="job-source")
            partenaire = "Guichet-Emplois (Direct)"
            if source_tag:
                part_text = source_tag.get_text(strip=True)
                if part_text:
                    partenaire = part_text

            type_poste = detect_stage(titre)

            offer = JobOffer(
                id=job_id,
                titre=titre,
                entreprise=entreprise,
                lieu=lieu_propre,
                province=province,
                pays="Canada",
                salaire=salaire,
                date_publication=date_pub,
                type_poste=type_poste,
                modalite="Non spécifié",
                competences_cles=extract_tech_skills(titre),
                description=None,
                url_source=full_url,
                source="Guichet-Emplois",
                partenaire=partenaire,
                methode_extraction="HTML-Search"
            )
            offers.append(offer)
        except Exception:
            continue

    return offers


# ==============================================================================
# 3. ENRICHISSEMENT DÉTAILLÉ EN CASCADE (RDFa / Schema.org -> DOM Fallback)
# ==============================================================================
def enrich_offer_detail(offer: JobOffer, detail_html: str) -> JobOffer:
    """
    Enrichit l'offre à partir du HTML de sa fiche détaillée en utilisant
    une stratégie en cascade :
    1. Métadonnées sémantiques RDFa (property="description", etc.) ou JSON-LD.
    2. Repli vers le DOM (brief, responsabilités, exigences).
    3. Remplissage garanti du champ `description` et compétences sans faux positifs.
    """
    if not detail_html:
        return offer

    soup = BeautifulSoup(detail_html, "html.parser")
    description_trouvee: Optional[str] = None
    section_texte_exigences: List[str] = []

    # 1. Analyse du bandeau résumé (Modalité et Type de poste)
    brief = soup.find("ul", class_="job-posting-brief")
    if brief:
        brief_text = brief.get_text(" ", strip=True).lower()
        if "télétravail" in brief_text or "remote" in brief_text:
            offer.modalite = "Télétravail"
        elif "hybride" in brief_text or "hybrid" in brief_text:
            offer.modalite = "Hybride"
        elif "sur place" in brief_text or "on site" in brief_text:
            offer.modalite = "Sur place"

        if any(k in brief_text for k in ["stage", "stagiaire", "intern", "coop", "co-op"]):
            offer.type_poste = "Stage"
        elif "temps partiel" in brief_text:
            offer.type_poste = "Temps partiel"

    # 2. Stratégie Cascade pour la DESCRIPTION :
    # Niveau A : Balise sémantique Schema.org / RDFa property="description"
    rdfa_desc = soup.find(attrs={"property": "description"})
    if rdfa_desc:
        cleaned_desc = clean_text(rdfa_desc.get_text(separator="\n", strip=True))
        if len(cleaned_desc) > 30:
            description_trouvee = cleaned_desc
            section_texte_exigences.append(cleaned_desc)
            offer.methode_extraction += "+RDFa-Detail"

    # Niveau B (Repli) : Conteneurs de contenu spécifiques dans le DOM
    if not description_trouvee:
        conteneurs_candidats = [
            soup.find("div", id="job-posting-detail"),
            soup.find("section", class_="job-posting-detail-requirements"),
            soup.find("div", class_="job-posting-details-body"),
            soup.find("div", class_="cmp-content"),
        ]
        for conteneur in conteneurs_candidats:
            if conteneur:
                txt = clean_text(conteneur.get_text(separator="\n", strip=True))
                if len(txt) > 40:
                    description_trouvee = txt
                    section_texte_exigences.append(txt)
                    offer.methode_extraction += "+DOM-Detail"
                    break

    # Niveau C (Ultime secours) : Si description toujours introuvable, assembler le brief et les listes
    if not description_trouvee:
        job_details = soup.find_all("div", class_="job-posting-detail-requirements")
        if job_details:
            details_text = "\n".join(clean_text(d.get_text(separator=" ", strip=True)) for d in job_details)
            if details_text.strip():
                description_trouvee = details_text
                section_texte_exigences.append(details_text)

    # Attribution de la description (si aucune trouvée, conserver le résumé existant ou indiquer Non spécifié)
    if description_trouvee:
        offer.description = description_trouvee
    elif not offer.description:
        offer.description = f"Poste de {offer.titre} chez {offer.entreprise} ({offer.lieu}). Consultez l'offre complète sur {offer.url_source}."

    # 3. Extraction ciblée des compétences clés (Strict, sans faux positifs)
    texte_pour_competences = " ".join(section_texte_exigences) if section_texte_exigences else (offer.description or "")
    competences_enrichies = extract_tech_skills(texte_pour_competences)
    offer.competences_cles = sorted(list(set(offer.competences_cles + competences_enrichies)))

    return offer
