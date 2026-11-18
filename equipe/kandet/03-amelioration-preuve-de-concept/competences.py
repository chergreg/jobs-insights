"""Technologies, compétences, expérience, niveau et description courte.

La liste des technologies reprend l'idée de TECH_PATTERNS de Hugo
(equipe/hugo/02-preuve-de-concept-scraping/parsers.py) : des expressions
précises pour éviter les faux positifs en français (« C » seul, « vue
d'ensemble », « Java » dans « JavaScript »). J'ai ajouté des technologies
vues dans nos offres (.NET, SharePoint, Power BI, Active Directory...).
"""

from __future__ import annotations

import re

from analyse import classify_stage
from modele import AggregatedOffer
from texte import clean, normalize


TECHNOLOGY_PATTERNS = [
    ("Python", r"\bpython\b"),
    ("Java", r"\bjava\b(?!\s*script)"),
    ("JavaScript", r"\bjavascript\b|(?<![.\w])js\b"),
    ("TypeScript", r"\btypescript\b"),
    ("C#", r"(?<![\w#])c#(?![\w#])"),
    ("C++", r"(?<![\w+])c\+\+(?!\+)"),
    ("C", r"\blangage\s+c\b|\bprogrammation\s+c\b|\bc\s*/\s*c\+\+|\bansi\s+c\b"),
    (".NET", r"(?<![\w.])\.net\b|\basp\.net\b|\bdotnet\b"),
    ("PHP", r"\bphp\b"),
    ("Ruby", r"\bruby\b"),
    ("Go", r"\bgolang\b"),
    ("Kotlin", r"\bkotlin\b"),
    ("Swift", r"\bswift\b"),
    ("Rust", r"\brust\b"),
    ("HTML/CSS", r"\bhtml5?\b|\bcss3?\b"),
    ("React", r"\breact(?:\.js|js)?\b"),
    ("Angular", r"\bangular(?:\.js|js)?\b"),
    ("Vue.js", r"\bvue\.?js\b|\bvuejs\b"),
    ("Node.js", r"\bnode\.?js\b"),
    ("Django", r"\bdjango\b"),
    ("Spring", r"\bspring\s*boot\b|\bspring\s+framework\b"),
    ("SQL", r"\bsql\b"),
    ("SQL Server", r"\bsql\s+server\b|\bmssql\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("Oracle", r"\boracle\b"),
    ("MongoDB", r"\bmongo(?:db)?\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("AWS", r"\baws\b|\bamazon\s+web\s+services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle\s+cloud\b"),
    ("Terraform", r"\bterraform\b"),
    ("Git", r"\bgit\b(?![-\w])|\bgithub\b|\bgitlab\b"),
    ("CI/CD", r"\bci\s*/\s*cd\b"),
    ("Linux", r"\blinux\b"),
    ("Windows", r"\bwindows\b"),
    ("Active Directory", r"\bactive\s+directory\b"),
    ("Microsoft 365", r"\b(?:microsoft|office)\s*365\b"),
    ("SharePoint", r"\bsharepoint\b"),
    ("Power BI", r"\bpower\s*bi\b"),
    ("Power Platform", r"\bpower\s*(?:apps|automate|platform)\b"),
    ("Tableau", r"\btableau\s+(?:software|desktop|server)\b"),
    ("SAP", r"\bsap\b"),
    ("Salesforce", r"\bsalesforce\b"),
    ("VMware", r"\bvmware\b"),
    ("Cisco", r"\bcisco\b"),
    ("ServiceNow", r"\bservicenow\b"),
    ("Jira", r"\bjira\b"),
    ("API REST", r"\brest(?:ful)?\s*api|\bapi\s+rest"),
    ("Machine learning", r"\bmachine\s+learning\b|\bapprentissage\s+(?:automatique|machine)\b"),
]
TECHNOLOGY_REGEXES = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in TECHNOLOGY_PATTERNS]

# Compétences générales, cherchées dans le texte sans accents.
SKILL_PATTERNS = [
    ("Soutien aux utilisateurs", r"\bsoutien\s+(?:technique|aux\s+utilisateurs)|\bsupport\s+(?:technique|informatique|aux\s+utilisateurs)|\bhelp\s*desk|\bcentre\s+de\s+services|\bservice\s+desk"),
    ("Réseaux", r"\breseaux?\s+(?:informatiques?|locaux)|\bnetwork(?:ing)?\b|\blan\b|\bwan\b|\bvpn\b|\bpare-feu|\bfirewall"),
    ("Cybersécurité", r"\bcybersecurite|\bsecurite\s+(?:informatique|de\s+l.information|des\s+ti)|\bcybersecurity|\binformation\s+security"),
    ("Bases de données", r"\bbases?\s+de\s+donnees|\bdatabases?\b"),
    ("Développement Web", r"\b(?:developpement|application)s?\s+web|\bweb\s+development|\bsites?\s+web"),
    ("Développement mobile", r"\b(?:application|developpement)s?\s+mobiles?|\bmobile\s+(?:app|development)|\bandroid\b|\bios\b"),
    ("Infonuagique", r"\binfonuagique|\bcloud\b"),
    ("Analyse de données", r"\banalyse\s+de\s+(?:donnees|donnees)|\bdata\s+analy|\bintelligence\s+d.affaires|\bbusiness\s+intelligence"),
    ("Intelligence artificielle", r"\bintelligence\s+artificielle|\bartificial\s+intelligence|\bia\s+generative|\bllm\b"),
    ("Assurance qualité", r"\bassurance\s+(?:de\s+la\s+)?qualite|\bquality\s+assurance|\btests?\s+(?:logiciels?|automatises?|unitaires)|\bsoftware\s+testing"),
    ("DevOps", r"\bdevops\b"),
    ("Agile / Scrum", r"\bagile\b|\bagilite\b|\bscrum\b"),
    ("Gestion de projet", r"\bgestion\s+de\s+projets?|\bproject\s+management|\bcoordonner\s+(?:les\s+)?projets"),
    ("Architecture", r"\barchitecture\s+(?:logicielle|des\s+systemes|de\s+solutions|ti|technologique)|\bsolution\s+architecture"),
]
SKILL_REGEXES = [(name, re.compile(pattern)) for name, pattern in SKILL_PATTERNS]

# Mots du titre qui donnent le niveau directement.
SENIOR_TITLE = re.compile(r"\b(?:senior|sr|principal|lead|chef|head|directeur|directrice|director|architecte|architect)\b")
JUNIOR_TITLE = re.compile(r"\b(?:junior|jr|debutant|debutante|entry\s+level|stagiaire|stage|intern|internship)\b")
MIDDLE_TITLE = re.compile(r"\b(?:intermediaire|intermediate)\b")

# Expérience du Guichet-Emplois : « 5 ans ou plus », « 1 an à moins de 2 ans », « 7 mois à moins d'un an ».
EXPERIENCE_YEARS = re.compile(r"(\d{1,2})\s*(?:an|ans|annees?)\b")
EXPERIENCE_MONTHS = re.compile(r"(\d{1,2})\s*mois\b")
# Dans une description : « 3 ans d'expérience », « minimum de 5 ans », « 5+ years of experience ».
DESCRIPTION_EXPERIENCE = re.compile(
    r"(?:minimum|au\s+moins|at\s+least)\s+(?:de\s+)?(\d{1,2})\s*(?:\+\s*)?(?:an|ans|annees?|years?)\b"
    r"|(\d{1,2})\s*(?:\+\s*)?(?:an|ans|annees?|years?)\s+(?:ou\s+plus\s+|et\s+plus\s+|or\s+more\s+)?"
    r"(?:d['’ ]\s*|of\s+)(?:experience|exp)\b"
    r"|(\d{1,2})\s*(?:a|-|–|to)\s*\d{1,2}\s*(?:ans|annees|years)\s+(?:d['’ ]\s*|of\s+)experience"
)
# Champ « Stage » écrit par le Guichet-Emplois dans la description d'une fiche.
GUICHET_STAGE_FIELD = re.compile(r"\bstage\s*:\s*ce\s+poste\s+est\s+un\s+stage\b")

SUMMARY_MAX_LENGTH = 300


def find_technologies(text: str) -> list[str]:
    return [name for name, regex in TECHNOLOGY_REGEXES if regex.search(text)]


def find_skills(text: str) -> list[str]:
    normalized = normalize(text)
    return [name for name, regex in SKILL_REGEXES if regex.search(normalized)]


def experience_years(experience: str, description: str = "") -> float | None:
    """Nombre minimum d'années d'expérience demandé, ou None si rien n'est écrit."""
    field = normalize(experience)
    if field:
        if "aucune" in field or "atout" in field:
            return 0.0
        years = EXPERIENCE_YEARS.search(field)
        months = EXPERIENCE_MONTHS.search(field)
        if months and (not years or months.start() < years.start()):
            return round(int(months.group(1)) / 12, 1)
        if years:
            return float(years.group(1))
    match = DESCRIPTION_EXPERIENCE.search(normalize(description))
    if match:
        return float(next(group for group in match.groups() if group))
    return None


def experience_level(title: str, years: float | None) -> str:
    """Débutant, intermédiaire ou avancé. Un mot du titre l'emporte sur les années."""
    normalized = normalize(title)
    if JUNIOR_TITLE.search(normalized):
        return "débutant"
    if SENIOR_TITLE.search(normalized):
        return "avancé"
    if MIDDLE_TITLE.search(normalized):
        return "intermédiaire"
    if years is None:
        return ""
    if years < 2:
        return "débutant"
    if years < 5:
        return "intermédiaire"
    return "avancé"


def short_summary(tasks: list[str], description: str, title: str = "") -> str:
    """Les 2 premières tâches, ou les 2 premières phrases de la description.

    Le texte est seulement coupé, jamais réécrit.
    """
    if tasks:
        text = "; ".join(tasks[:2])
    else:
        # Sur le Guichet-Emplois, la description commence par « Études: ... ».
        tasks_part = re.search(r"T[âa]ches\s*:\s*(.+)", description)
        text = tasks_part.group(1) if tasks_part else description
        # Beaucoup de partenaires répètent le titre au début de la description.
        if title and normalize(text).startswith(normalize(title)):
            text = text[len(title):].lstrip(" -:|")
        sentences = re.split(r"(?<=[.!?])\s+", clean(text))
        text = " ".join(sentences[:2])
    text = clean(text)
    if len(text) <= SUMMARY_MAX_LENGTH:
        return text
    cut = text[:SUMMARY_MAX_LENGTH]
    end = max(cut.rfind(". "), cut.rfind("; "))
    if end > SUMMARY_MAX_LENGTH // 2:
        return cut[: end + 1].rstrip(";").rstrip()
    return cut[: cut.rfind(" ")].rstrip(" ,;") + " …"


def enrich_offer(offer: AggregatedOffer) -> None:
    """Ajoute technologies, compétences, expérience, niveau, stage et résumé."""
    tags = [tag for record in offer.source_records for tag in record.tags]
    full_text = " ".join(
        [offer.original_title, offer.title, offer.description, " ".join(offer.tasks), " ".join(tags)]
    )
    offer.technologies = find_technologies(full_text)
    offer.skills = find_skills(full_text)
    offer.experience_years_min = experience_years(offer.experience, offer.description)
    title = offer.original_title or offer.title
    offer.level = experience_level(title, offer.experience_years_min)
    offer.summary = short_summary(offer.tasks, offer.description, title)

    # Les stages sont recherchés aussi dans le vrai titre et la description.
    priority = {"not_indicated": 0, "possible_stage": 1, "confirmed_stage": 2}
    if GUICHET_STAGE_FIELD.search(normalize(offer.description)):
        status, signals = "confirmed_stage", ["guichet_stage_field"]
    else:
        status, signals = classify_stage(
            f"{offer.original_title} {offer.title}", offer.job_type, offer.description
        )
    if priority[status] > priority.get(offer.stage_status, 0):
        offer.stage_status = status
        offer.stage_signals = list(dict.fromkeys(offer.stage_signals + signals))
