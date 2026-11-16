"""
parsers.py - Logique pure de parsing, filtrage DEC et normalisation pour Guichet-Emplois.
Ce module est totalement découplé du réseau et peut être testé 100 % hors ligne.

Fonctionnalités :
1. Extraction depuis le flux Atom XML officiel (/jobsearch/feed/jobSearchRSSfeed).
2. Extraction depuis les résultats de recherche HTML (/jobsearch/jobsearch).
3. Extraction détaillée par cascade :
   - Étape 1 : Métadonnées sémantiques RDFa / Schema.org (JobPosting)
   - Étape 2 : Repli DOM HTML (sections description, modalité et compétences)
4. Filtrage strict du périmètre DEC en informatique :
   - Couvre : Programmation, Web, Logiciel, Réseaux, Support TI, QA, DevOps, Cybersécurité et Stages.
   - Élimine : Métiers non-TI (cleaning man/woman, concierge, entretien, restauration, etc.).
5. Détection stricte et sans faux positifs des compétences techniques (exclut 'C' isolé et 'Vue').
6. Priorisation des URLs et contenus en langue française (?lang=fra).
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from models import JobOffer

# ==============================================================================
# 1. MOTIFS D'EXCLUSION NON-TI & INCLUSION DEC EN INFORMATIQUE
# ==============================================================================

# Métiers hors TI à rejeter systématiquement (pour éliminer 'cleaning man/woman', etc.)
MOTIFS_NON_TI = [
    re.compile(r"\bclean(?:ing|er|ers)?\b", re.IGNORECASE),
    re.compile(r"\bnettoy(?:age|eur|euse|eurs|euses)\b", re.IGNORECASE),
    re.compile(r"\bentretien\s+m[eé]nag(?:er|ère)\b", re.IGNORECASE),
    re.compile(r"\bconcierge\b", re.IGNORECASE),
    re.compile(r"\bcuisin(?:e|ier|ière|iers|ières)\b", re.IGNORECASE),
    re.compile(r"\bserveu(?:r|se|rs|ses)\b", re.IGNORECASE),
    re.compile(r"\bplongeu(?:r|se|rs|ses)\b", re.IGNORECASE),
    re.compile(r"\bcommis\b(?!\s+(?:ti|informatique|donn[eé]es))", re.IGNORECASE),
    re.compile(r"\bchauffeu(?:r|se|rs|ses)\b", re.IGNORECASE),
    re.compile(r"\bmanutentionn?aire\b", re.IGNORECASE),
    re.compile(r"\bcaissi(?:er|ère|ers|ères)\b", re.IGNORECASE),
    re.compile(r"\bpr[eé]pos[eé](?:e)?\s+aux\s+b[eé]n[eé]ficiaires\b", re.IGNORECASE),
    re.compile(r"\bpr[eé]pos[eé](?:e)?\s+[aà]\s+l['’]entretien\b", re.IGNORECASE),
    re.compile(r"\bgardien(?:ne)?\b", re.IGNORECASE),
    re.compile(r"\bvendeu(?:r|se|rs|ses)\b(?!\s+(?:informatique|logiciel))", re.IGNORECASE),
    re.compile(r"\bcharpentier|menuisier|m[eé]canicien|soudeur\b", re.IGNORECASE),
]

# Motifs positifs ciblés sur l'ensemble des branches du DEC en informatique :
# 1. Développement d'applications (Web, Logiciel, Mobile, Jeux vidéo, DevOps)
# 2. Infrastructure, Réseaux et Sécurité (Technicien, Sysadmin, Support TI, Cybersécurité)
# 3. Données et Assurance Qualité (Bases de données, QA/Test)
# 4. Stages en informatique
MOTIFS_DEC_INFORMATIQUE = [
    # Programmation & Développement logiciel / Web
    re.compile(r"\bprogrammeu(?:r|se|rs|ses)?\b", re.IGNORECASE),
    re.compile(r"\bprogrammation\b", re.IGNORECASE),
    re.compile(r"\bd[eé]veloppeu(?:r|se|rs|ses)?\b", re.IGNORECASE),
    re.compile(r"\bd[eé]veloppement\b", re.IGNORECASE),
    re.compile(r"\bprogrammer(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bdeveloper(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsoftware\b", re.IGNORECASE),
    re.compile(r"\blogiciel(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bweb\b", re.IGNORECASE),
    re.compile(r"\bfull[\s-]?stack\b", re.IGNORECASE),
    re.compile(r"\bfront[\s-]?end\b", re.IGNORECASE),
    re.compile(r"\bback[\s-]?end\b", re.IGNORECASE),
    re.compile(r"\bmobile\b", re.IGNORECASE),
    re.compile(r"\bjeux?\s+vid[eé]o\b|\bvideo\s+games?\b", re.IGNORECASE),
    re.compile(r"\bgame(?:play)?\b", re.IGNORECASE),
    re.compile(r"\bdevops\b", re.IGNORECASE),
    re.compile(r"\bcloud\b|\binfonuagique\b", re.IGNORECASE),
    re.compile(r"\barchitecte\s+(?:logiciel|syst[eè]me|cloud|solutions?|ti)\b", re.IGNORECASE),
    re.compile(r"\bing[eé]nieu?r(?:e)?\s+(?:logiciel|informati(?:que|cien)|syst[eè]me|devops)\b", re.IGNORECASE),
    
    # Infrastructure, Réseaux, Systèmes, Support TI et Cybersécurité
    re.compile(r"\br[eé]seau(?:x)?\b|\bnetwork(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsyst[eè]me(?:s)?\s+informatique(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsysadmin\b|\badministrat(?:eur|rice)\s+syst[eè]me\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+informatique\b|\bit\s+support\b", re.IGNORECASE),
    re.compile(r"\bsoutien\s+technique\b|\btech\s+support\b", re.IGNORECASE),
    re.compile(r"\bhelpdesk\b|\bhelp\s+desk\b", re.IGNORECASE),
    re.compile(r"\btechnicien(?:ne)?\s+(?:en\s+)?(?:informatique|r[eé]seau|ti|syst[eè]me|soutien)\b", re.IGNORECASE),
    re.compile(r"\bagent(?:e)?\s+de\s+soutien\b", re.IGNORECASE),
    re.compile(r"\bcybers[eé]curit[eé]\b|\bcybersecurity\b|\bs[eé]curit[eé]\s+informatique\b", re.IGNORECASE),
    re.compile(r"\bbases?\s+de\s+donn[eé]es\b|\bdatabase\b|\bdba\b", re.IGNORECASE),
    re.compile(r"\banalyste\s+(?:ti|informatique|programmeur|syst[eè]me|donn[eé]es|affaires\s+ti|fonctionnel\s+ti)\b", re.IGNORECASE),
    
    # Données, IA et Big Data
    re.compile(r"\bdata\s+(?:engineer|analyst|scientist)\b|\bing[eé]nieur\s+donn[eé]es\b", re.IGNORECASE),
    re.compile(r"\bintelligence\s+artificielle\b|\bia\b|\bai\b", re.IGNORECASE),
    
    # Assurance Qualité (QA) et Test logiciel
    re.compile(r"\bassurance\s+qualit[eé]\b|\bqa\b|\btesteu(?:r|se)\s+logiciel\b|\bqa\s+tester\b", re.IGNORECASE),
    re.compile(r"\b[eé]valuateu(?:r|se)\s+de\s+syst[eè]mes\b", re.IGNORECASE),
    
    # Stages en informatique
    re.compile(r"\b(?:stage|stagiaire|intern|internship|co[\s-]?op)\s+(?:en\s+|de\s+|d['’]\s*)?(?:informatique|d[eé]veloppement|prog(?:rammation)?|web|ti|logiciel|qa|r[eé]seau)\b", re.IGNORECASE),
    
    # Termes généraux TI
    re.compile(r"\binformatique\b|\btechnologies?\s+de\s+l['’]information\b|\bit\b", re.IGNORECASE),
]

# Dictionnaire de motifs stricts pour compétences TI (sans faux positifs français)
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


def est_metier_dec_informatique(titre: str, texte_complementaire: str = "") -> bool:
    """
    Vérifie si une offre d'emploi correspond au domaine du DEC en informatique :
    - Programmation / Développement (Web, Logiciel, Mobile, Jeux vidéo, DevOps)
    - Infrastructure, Réseaux et Sécurité (Technicien, Sysadmin, Support TI, Cyber)
    - Données et Assurance Qualité (Bases de données, QA)
    - Stages informatiques

    Rejette formellement les offres hors TI (ex: cleaning man/woman, concierge, etc.).
    """
    titre_propre = (titre or "").strip()
    if not titre_propre:
        return False

    texte_global = f"{titre_propre} {texte_complementaire}".lower()

    # 1. Vérification des exclusions prioritaires
    for pattern in MOTIFS_NON_TI:
        if pattern.search(titre_propre):
            # Exception : si le titre contient explicitement un terme logiciel/informatique fort
            mots_sauvegarde = ["informatique", "logiciel", "software", "programmeur", "développeur", "developer"]
            if not any(w in titre_propre.lower() for w in mots_sauvegarde):
                return False

    # 2. Vérification de correspondance avec le domaine TI
    for pattern in MOTIFS_DEC_INFORMATIQUE:
        if pattern.search(titre_propre):
            return True

    # 3. Si le titre est un stage générique (ex: "Stagiaire"), vérifier le texte complémentaire
    if any(k in titre_propre.lower() for k in ["stage", "stagiaire", "intern", "étudiant"]):
        for pattern in MOTIFS_DEC_INFORMATIQUE:
            if pattern.search(texte_global):
                return True

    # 4. Vérifier si des compétences TI majeures sont mentionnées dans le titre
    for tech_name, pat in TECH_PATTERNS:
        if pat.search(titre_propre):
            return True

    return False


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


def normaliser_url_francaise(url: str, base_url: str = "https://www.guichetemplois.gc.ca") -> str:
    """Normalise l'URL pour pointer vers le domaine français avec le paramètre lang=fra."""
    if not url:
        return ""
    full_url = urljoin(base_url, url)
    full_url = full_url.replace("jobbank.gc.ca", "guichetemplois.gc.ca")
    if "lang=fra" not in full_url:
        separateur = "&" if "?" in full_url else "?"
        full_url = f"{full_url}{separateur}lang=fra"
    return full_url


# ==============================================================================
# 2. PARSEUR FLUX ATOM XML OFFICIEL (Rapide, structuré, résilient)
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
        raw_url = link_el.attrib.get("href", "") if link_el is not None else ""
        url_source = normaliser_url_francaise(raw_url, base_url=base_url)

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
            emp_m = re.search(r"<strong>(?:Employer|Employeur)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if emp_m:
                entreprise = emp_m.group(1).strip()

            loc_m = re.search(r"<strong>(?:Location|Emplacement)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if loc_m:
                lieu = loc_m.group(1).strip()
                for prov in ["QC", "ON", "BC", "AB", "MB", "NB", "NS"]:
                    if f"({prov})" in lieu or prov in lieu:
                        province = prov
                        break

            sal_m = re.search(r"<strong>(?:Salary|Salaire)\s*:?</strong>\s*([^<]+)", summary_html, re.I)
            if sal_m:
                salaire = sal_m.group(1).strip()

        # Filtrage strict DEC en informatique
        if not est_metier_dec_informatique(titre, summary_html):
            continue

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
# 3. PARSEUR DE RECHERCHE HTML (Résultats de recherche par mot-clé)
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
            full_url = normaliser_url_francaise(clean_href, base_url=base_url)

            raw_id = article.get("id", "")
            base_ident = raw_id.replace("article-", "").replace("gc-", "") if raw_id else clean_href.split("/")[-1].split("?")[0]
            job_id = f"gc-{base_ident}"

            title_tag = article.find("span", class_="noctitle")
            titre = title_tag.get_text(strip=True) if title_tag else "Titre non spécifié"

            # Filtrage strict DEC en informatique dès les cartes de recherche
            if not est_metier_dec_informatique(titre):
                continue

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
# 4. ENRICHISSEMENT DÉTAILLÉ EN CASCADE (RDFa / Schema.org -> DOM Fallback)
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
