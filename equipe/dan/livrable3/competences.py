"""Détection des compétences TI et du statut de stage dans le titre et la description d'une offre.

Repris de l'équipe :
- Hugo (``03-Scrapping Guichet-Emploi/parsers.py``) et Gregory (démo L3) : motifs de compétences
  « sans faux positifs » (« vue d'ensemble » ≠ Vue.js, « C » seul ignoré, Java ≠ JavaScript) ;
- Gregory (démo L3) : statut de stage à trois valeurs (``confirmed_stage``, ``possible_stage``,
  ``not_indicated``) et motifs « stage en… », « être inscrit… », « internship position ».

Bonifications :
- quelques compétences fréquentes dans les postes de support TI au Québec (Windows, Active Directory,
  Microsoft 365, réseau TCP/IP, HTML, CSS, .NET, Power BI) ;
- « Node.js » ne compte plus aussi pour JavaScript, et « node » seul n'est plus pris pour Node.js ;
- « Agile » seulement avec son contexte (« méthode agile », « Agile/Scrum »), car « agile » est aussi
  un adjectif français courant ;
- une offre sans description donne une liste vide : cela veut dire « inconnu », pas « aucune compétence ».

Sans réseau. Usage :
    from competences import detecter_competences, statut_stage
    detecter_competences("Développeur Python", "Vous utiliserez Docker et SQL.")  # ['Docker', 'Python', 'SQL']
"""

from __future__ import annotations

import re

from scrapers.commun import sans_accents

I = re.IGNORECASE

# (nom affiché, motif). Les motifs s'appliquent au texte d'origine (avec accents).
MOTIFS_COMPETENCES: list[tuple[str, re.Pattern[str]]] = [
    # Langages et cadriciels (Hugo / Gregory)
    ("Python", re.compile(r"\bpython\b", I)),
    ("Java", re.compile(r"\bjava\b(?!\s*script)", I)),
    ("JavaScript", re.compile(r"\bjavascript\b|(?<![\w.])js\b", I)),      # « Node.js » ne compte pas
    ("TypeScript", re.compile(r"\btypescript\b", I)),
    ("C#", re.compile(r"\bc#(?=[^\w#]|$)", I)),
    ("C++", re.compile(r"\bc\+\+(?=[^\w+]|$)", I)),
    ("C", re.compile(r"\blangage\s+c\b|\bprog(?:rammation)?\s+c\b|\bc\s*/\s*c\+\+|\bansi\s+c\b", I)),
    ("PHP", re.compile(r"\bphp\b", I)),
    ("React", re.compile(r"\breact(?:\.js)?\b", I)),
    ("Angular", re.compile(r"\bangular(?:\.?js)?\b", I)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|framework\s+vue)\b", I)),
    ("Node.js", re.compile(r"\bnode\.?js\b", I)),                         # « node » seul : trop vague
    ("Django", re.compile(r"\bdjango\b", I)),
    ("FastAPI", re.compile(r"\bfastapi\b", I)),
    ("Spring Boot", re.compile(r"\bspring\s*boot\b", I)),
    (".NET", re.compile(r"(?<![\w.])\.net\b|\bdotnet\b|\basp\.net\b", I)),
    ("HTML", re.compile(r"\bhtml5?\b", I)),
    ("CSS", re.compile(r"\bcss3?\b", I)),
    # Données
    ("SQL", re.compile(r"\bsql\b", I)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", I)),
    ("MySQL", re.compile(r"\bmysql\b", I)),
    ("MongoDB", re.compile(r"\bmongo(?:db)?\b", I)),
    ("Power BI", re.compile(r"\bpower\s*bi\b", I)),
    # Infonuagique et DevOps
    ("Docker", re.compile(r"\bdocker\b", I)),
    ("Kubernetes", re.compile(r"\b(?:kubernetes|k8s)\b", I)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", I)),
    ("Azure", re.compile(r"\bazure\b", I)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", I)),
    ("Git", re.compile(r"\bgit\b(?!e)|\bgithub\b|\bgitlab\b", I)),
    ("CI/CD", re.compile(r"\bci\s*[/-]\s*cd\b", I)),
    ("Linux", re.compile(r"\blinux\b", I)),
    # Support TI et réseaux
    ("Windows", re.compile(r"\bwindows\b", I)),
    ("Active Directory", re.compile(r"\bactive\s+directory\b", I)),
    ("Microsoft 365", re.compile(r"\b(?:microsoft|office)\s*365\b|\bm365\b|\bo365\b", I)),
    ("TCP/IP", re.compile(r"\btcp\s*/\s*ip\b", I)),
    # Méthodes
    ("Scrum", re.compile(r"\bscrum\b", I)),
    ("Agile", re.compile(r"\b(?:m[ée]thodes?|m[ée]thodologies?|approche|environnement|cadre)\s+agiles?\b"
                         r"|\bagile\s*/\s*scrum\b|\bagile\s+(?:methodolog|development|team)", I)),
    ("Assurance qualité", re.compile(r"\bassurance\s+(?:de\s+la\s+)?qualit[ée]\b|\bqa\b", I)),
]

# Statut de stage (Gregory, démo L3). Les motifs s'appliquent au texte sans accents.
STAGE_DANS_TITRE = re.compile(r"\b(?:stages?|stagiaires?|interns?|internships?|co[\s-]?op|work[\s-]?terms?)\b")
STAGE_DANS_DESCRIPTION = re.compile(
    r"\b(?:internship|intern|co[\s-]?op|work[\s-]?term)\s+(?:position|role|program|opportunity|placement)\b"
    r"|\bstudents?\s+(?:intern|position|role|placement)\b"
    r"|\b(?:stage|stagiaire)\s+(?:en|de|du|d'|remunere)\b"
)
ETUDIANT_INSCRIT = re.compile(
    r"\b(?:currently\s+enrolled|enrolled\s+(?:in|at)|must\s+be\s+(?:a\s+)?student|student\s+status"
    r"|(?:doit\s+)?etre\s+(?:inscrit|inscrite|etudiant|etudiante))\b"
)

CONFIRME, POSSIBLE, NON_INDIQUE = "confirmed_stage", "possible_stage", "not_indicated"


def detecter_competences(*textes: str | None) -> list[str]:
    """Compétences trouvées dans les textes donnés (titre, description…), triées par nom."""
    texte = "\n".join(t for t in textes if t)
    if not texte:
        return []
    return sorted({nom for nom, motif in MOTIFS_COMPETENCES if motif.search(texte)}, key=str.casefold)


def statut_stage(titre: str | None, description: str | None = None, est_stage: bool | None = None) -> str:
    """``confirmed_stage`` (stage dans le titre ou déjà détecté), ``possible_stage`` (indice dans la
    description) ou ``not_indicated``. Jamais « pas un stage » : on dit seulement ce qu'on voit."""
    if est_stage or (titre and STAGE_DANS_TITRE.search(sans_accents(titre))):
        return CONFIRME
    texte = sans_accents(description or "").replace("’", "'")
    if STAGE_DANS_DESCRIPTION.search(texte) or ETUDIANT_INSCRIT.search(texte):
        return POSSIBLE
    return NON_INDIQUE
