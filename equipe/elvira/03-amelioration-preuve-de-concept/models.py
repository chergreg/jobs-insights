"""
models.py — Modèle de données unifié `JobOffer` et fonctions de validation/normalisation.
Auteure : Elvira (Projet jobs-insights — Livrable 3 Multi-Sources)

Ce module définit :
1. La classe `JobOffer` (@dataclass) commune aux 4 sources (Jobboom, Guichet-Emplois, Jobillico, Remotive).
2. Le filtre strict de fraîcheur et de validité (`is_recent_and_valid_offer`) :
   aucune offre des années passées (< 2026) et aucune offre expirée.
3. Le filtre de pertinence TI (`is_it_job`) et l'extraction sans faux positifs des compétences,
   modalités, stages et salaires.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from bs4 import BeautifulSoup

MIN_PUBLICATION_YEAR = 2026
REFERENCE_TODAY_ISO = "2026-11-18"

FRENCH_MONTHS = {
    "janvier": "01",
    "fevrier": "02",
    "février": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "aout": "08",
    "août": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "decembre": "12",
    "décembre": "12",
}

# Mots-clés confirmant qu'un titre d'offre appartient bien au domaine TI / Informatique
IT_TITLE_POSITIVE_PATTERNS = re.compile(
    r"\b(?:"
    r"informatique|informaticien(?:ne)?|ti\b|it\b|"
    r"developpeur(?:euse)?|developer|programmeur(?:euse)?|programmer|software\s+engineer|"
    r"logiciel(?:s)?|software|web|fullstack|full[\s-]?stack|frontend|front[\s-]?end|backend|back[\s-]?end|"
    r"devops|sre\b|cloud|cybersecurite|cybersecurity|securite\s+informatique|infosec|"
    r"data|donnees|base(?:s)?\s+de\s+donnees|dba|bi\b|intelligence\s+d['’]affaires|"
    r"reseau(?:x)?|network|systeme(?:s)?|administrateur(?:trice)?\s+systeme|sysadmin|"
    r"support\s+technique|soutien\s+technique|soutien\s+informatique|soutien\s+aux\s+utilisateurs|"
    r"helpdesk|help\s+desk|technicien(?:ne)?\s+informatique|technicien(?:ne)?\s+ti|technicien(?:ne)?\s+reseau|"
    r"end\s+user\s+computing|euc\b|configuration\s+informatique|infrastructure|"
    r"analyste\s+fonctionnel|analyste\s+ti|analyste[\s-]programmeur|analyste\s+en\s+informatique|"
    r"architecte\s+ti|architecte\s+logiciel|architecte\s+de\s+solutions|architecte\s+entreprise|"
    r"specialiste\s+d['’]?application|gestionnaire\s+du\s+web|concepteur(?:trice)?\s+web|"
    r"qa\b|assurance\s+qualite|testeur(?:euse)?\s+logiciel|testeur(?:euse)?\s+ de\s+systemes|"
    r"scrum\s+master|product\s+owner|integrateur(?:trice)?\s+web|intelligence\s+artificielle|\bia\b|\bai\b"
    r")\b",
    flags=re.IGNORECASE,
)

# Mots-clés dans le titre qui indiquent clairement un poste HORS informatique
IT_TITLE_EXCLUSION_PATTERNS = re.compile(
    r"\b(?:"
    r"cvc|cvac|hvac|batiment(?:s)?|construction|mecanicien|electromecanicien|usinage|cnc|"
    r"comptable|comptabilite|accounting|accounts\s+receivable|accounts\s+payable|controleur|"
    r"succursale|sqdc|vendeur|vente(?:s)?|sales\s+representative|service\s+a\s+la\s+clientele|"
    r"deductions|claims|reclamations|soumissions|inspecteur|travaux|loans|journalier|desassemblage|"
    r"cuisinier|nettoyage|entretien\s+menager|chauffeur|camionneur|infirmier"
    r")\b",
    flags=re.IGNORECASE,
)

TECH_SKILLS_PATTERNS: list[tuple[str, str]] = [
    ("Python", r"\bpython\b"),
    ("Java", r"\bjava\b"),
    ("C#", r"\bc#|\bc\s*sharp\b"),
    (".NET", r"(?:^|[\s,;(/])\.net\b|\basp\.net\b"),
    ("C++", r"\bc\+\+"),
    ("JavaScript", r"\bjavascript\b|\bjs\b"),
    ("TypeScript", r"\btypescript\b"),
    ("React", r"\breact(?:\.js|js)?\b"),
    ("Angular", r"\bangular(?:\.js|js)?\b"),
    ("Vue.js", r"\bvue\.js\b|\bvuejs\b"),
    ("Node.js", r"\bnode\.js\b|\bnodejs\b"),
    ("jQuery", r"\bjquery\b"),
    ("HTML", r"\bhtml5?\b"),
    ("CSS", r"\bcss3?\b|\bsass\b|\bscss\b"),
    ("PHP", r"\bphp\b|\blaravel\b|\bsymfony\b"),
    ("SQL", r"\bsql\b"),
    ("T-SQL", r"\bt-sql\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("MongoDB", r"\bmongodb\b"),
    ("SSIS", r"\bssis\b"),
    ("SSRS", r"\bssrs\b"),
    ("Power BI", r"\bpower\s*bi\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("AWS", r"\baws\b|\bamazon\s+web\s+services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle\s+cloud\b"),
    ("Git", r"\bgit\b|\bgithub\b|\bgitlab\b"),
    ("Jira", r"\bjira\b"),
    ("Confluence", r"\bconfluence\b"),
    ("CI/CD", r"\bci\s*/\s*cd\b"),
    ("DevOps", r"\bdevops\b"),
    ("Linux", r"\blinux\b"),
    ("Windows", r"\bwindows\b"),
    ("Active Directory", r"\bactive\s+directory\b"),
    ("VMware", r"\bvmware\b"),
    ("ITIL", r"\bitil\b"),
    ("Agile", r"\bagile\b|\bscrum\b"),
    ("REST API", r"\brest\s*api\b|\bapi\s*rest\b|\brestful\b|\bapi\b"),
    ("AJAX", r"\bajax\b"),
    ("XML", r"\bxml\b"),
    ("JSON", r"\bjson\b"),
    ("VBA", r"\bvba\b"),
]

STAGE_REGEX = re.compile(
    r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|student|etudiant(?:e)?)\b",
    flags=re.IGNORECASE,
)

UNIT_LABELS = {
    "HOUR": "heure",
    "DAY": "jour",
    "WEEK": "semaine",
    "MONTH": "mois",
    "YEAR": "an",
}


@dataclass
class JobOffer:
    """
    Modèle de données unifié représentant une offre d'emploi ou de stage TI
    issue de n'importe quelle source (Jobboom, Guichet-Emplois, Jobillico, Remotive).
    """

    id: str
    source: str
    titre: str
    entreprise: str
    ville: str
    province: str = "QC"
    pays: str = "CA"
    code_postal: str | None = None
    coordonnees_gps: dict[str, float] | None = None
    salaire: str | None = None
    type_contrat: list[str] = field(default_factory=list)
    modalite: str = "Sur place"
    est_stage: bool = False
    competences_cles: list[str] = field(default_factory=list)
    date_publication: str | None = None
    date_expiration: str | None = None
    url: str = ""
    description_texte: str = ""
    logo_entreprise: str | None = None
    partenaire_origine: str | None = None
    origines_decouverte: list[str] = field(default_factory=list)
    urls_sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.url and self.url not in self.urls_sources:
            self.urls_sources.insert(0, self.url)
        if not self.origines_decouverte:
            self.origines_decouverte = [self.source]

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'offre en dictionnaire JSON-sérialisable propre (1 seule description nettoyée)."""
        return asdict(self)


def strip_accents(text: str) -> str:
    """Supprime les accents d'une chaîne pour faciliter les comparaisons regex et la déduplication."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def clean_html_text(raw_html: str | None) -> str:
    """
    Nettoie une chaîne HTML (même doublement échappée comme sur certaines offres partenaires)
    pour obtenir une seule description en texte brut lisible.
    """
    if not raw_html:
        return ""
    unescaped_once = html.unescape(str(raw_html))
    soup = BeautifulSoup(unescaped_once, "html.parser")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    if "<p>" in text or "<strong>" in text or "<li" in text:
        soup2 = BeautifulSoup(text, "html.parser")
        text = html.unescape(soup2.get_text(separator=" "))
    return re.sub(r"\s+", " ", text).strip()


def normalize_iso_date(raw_date: str | None) -> str | None:
    """
    Normalise une date (ISO `2026-11-12T...`, ou français `12 novembre 2026`)
    au format `YYYY-MM-DD`. Retourne `None` si la date est invalide.
    """
    if not raw_date:
        return None
    s = str(raw_date).strip()
    iso_m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if iso_m:
        return iso_m.group(1)

    fr_m = re.search(r"(\d{1,2})\s+([a-zéûô]+)\s+(\d{4})", s.lower())
    if fr_m:
        day = int(fr_m.group(1))
        month_name = strip_accents(fr_m.group(2))
        year = fr_m.group(3)
        month = FRENCH_MONTHS.get(month_name) or FRENCH_MONTHS.get(fr_m.group(2))
        if month:
            return f"{year}-{month}-{day:02d}"
    return None


def is_recent_and_valid_offer(
    date_publication: str | None,
    date_expiration: str | None = None,
    min_year: int = MIN_PUBLICATION_YEAR,
    today_iso: str = REFERENCE_TODAY_ISO,
) -> bool:
    """
    Vérifie que l'offre est récente (publiée en `min_year` ou après : aucune offre de l'année passée)
    et qu'elle est toujours valide (`date_expiration` absente ou >= `today_iso`).
    """
    pub_iso = normalize_iso_date(date_publication)
    if not pub_iso:
        return False
    try:
        pub_year = int(pub_iso[:4])
    except ValueError:
        return False
    if pub_year < min_year:
        return False

    if date_expiration:
        exp_iso = normalize_iso_date(date_expiration)
        if exp_iso and exp_iso < today_iso:
            return False

    return True


def is_it_job(title: str, url: str = "") -> bool:
    """
    Vérifie que l'offre est réellement un poste en Informatique / TI
    d'après son titre (et son slug d'URL), en excluant les postes hors-sujet.
    """
    normalized_title = strip_accents(title or "").lower()
    normalized_url = strip_accents(url or "").lower()
    target = f"{normalized_title} {normalized_url}"

    if IT_TITLE_EXCLUSION_PATTERNS.search(target):
        return False

    return bool(IT_TITLE_POSITIVE_PATTERNS.search(target))


def detect_work_mode(title: str, description_text: str, location_hint: str | None = None) -> str:
    """Détecte la modalité de travail (Télétravail, Hybride, Sur place)."""
    combined = f"{title} {description_text} {location_hint or ''}".lower()
    if any(term in combined for term in ("hybride", "hybrid", "mode hybride", "télétravail partiel")):
        return "Hybride"
    if any(
        term in combined
        for term in ("télétravail", "teletravail", "100% à distance", "remote", "travail à distance", "telecommute")
    ):
        return "Télétravail"
    return "Sur place"


def detect_is_internship(title: str, description_text: str, employment_types: list[str] | None = None) -> bool:
    """Détecte si l'offre correspond à un stage."""
    emp_upper = {str(t).upper() for t in (employment_types or [])}
    if any(tag in emp_upper for tag in ("INTERN", "INTERNSHIP", "STAGE", "CO-OP")):
        return True
    if STAGE_REGEX.search(title or ""):
        return True
    if re.search(
        r"\b(?:offre de stage|stage rémunéré|stagiaire en|stage offert|internship opportunity)\b",
        description_text or "",
        re.IGNORECASE,
    ):
        return True
    return False


def extract_skills(title: str, description_text: str) -> list[str]:
    """Extrait la liste des compétences techniques TI mentionnées dans l'offre sans faux positifs."""
    combined = f"{title} {description_text}"
    found: list[str] = []
    for label, pattern in TECH_SKILLS_PATTERNS:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            found.append(label)
    return found


def extract_salary(job_data: dict[str, Any]) -> str | None:
    """
    Extrait le salaire depuis le champ `baseSalary` d'un JSON-LD JobPosting s'il existe.
    Retourne `None` si aucun salaire n'est renseigné (sans jamais inventer de valeur).
    """
    base_salary = job_data.get("baseSalary")
    if base_salary is None:
        return None
    if isinstance(base_salary, (int, float)):
        return f"{base_salary} $"
    if isinstance(base_salary, str):
        cleaned = base_salary.strip()
        return cleaned or None
    if isinstance(base_salary, dict):
        currency = base_salary.get("currency") or "CAD"
        val = base_salary.get("value")
        if isinstance(val, dict):
            min_v = val.get("minValue")
            max_v = val.get("maxValue")
            exact_v = val.get("value")
            unit_raw = str(val.get("unitText") or "").upper()
            unit = UNIT_LABELS.get(unit_raw, unit_raw.lower())
            suffix = f" / {unit}" if unit else ""
            if min_v is not None and max_v is not None:
                return f"{min_v} à {max_v} {currency}{suffix}"
            if exact_v is not None:
                return f"{exact_v} {currency}{suffix}"
        elif isinstance(val, (int, float, str)) and str(val).strip():
            return f"{val} {currency}"
    return None


def normalize_city_name(raw_location: str | None) -> str:
    """Nettoie le nom de ville (ex: 'Québec (QC)' -> 'Québec', 'Montréal, QC' -> 'Montréal')."""
    if not raw_location:
        return "Non spécifié"
    cleaned = re.sub(r"\s*\([A-Z]{2}\)\s*", "", str(raw_location))
    cleaned = re.sub(r",\s*(?:QC|Québec|Quebec|Canada).*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("Québec City", "Québec").replace("Montreal", "Montréal")
    return cleaned.strip() or "Non spécifié"


def dedup_key(offer: JobOffer) -> tuple[str, str, str]:
    """
    Calcule l'empreinte normalisée `(titre, entreprise, ville)` d'une offre
    pour détecter et fusionner les doublons entre plateformes (ex: Guichet-Emplois + Jobillico/Jobboom).
    """

    def norm(val: str) -> str:
        s = strip_accents(val or "").lower()
        s = re.sub(r"\b(?:inc|ltee|ltd|corp|senc|groupe)\b\.?", "", s)
        s = re.sub(r"[^a-z0-9]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    return (
        norm(offer.titre),
        norm(offer.entreprise),
        norm(normalize_city_name(offer.ville)),
    )
