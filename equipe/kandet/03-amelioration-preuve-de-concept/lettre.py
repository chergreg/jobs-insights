"""Vérifier une lettre de motivation par rapport à une offre précise.

Comme pour le CV, tout se fait sur l'ordinateur avec des règles simples.
Le programme ne note pas la lettre : il repère ce qui peut être amélioré.

- La lettre cite-t-elle l'employeur et le poste ?
- Quelles technologies et compétences de l'offre y sont citées, lesquelles manquent ?
- Quels mots importants des tâches de l'offre n'y apparaissent pas ?
- Longueur, et zones à remplir oubliées (« [nom du poste] », « XXX »).

Pour comparer des mots malgré les conjugaisons, on compare leurs 5 premières
lettres sans accents : « développer » et « développeur » donnent « devel ».
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from competences import find_skills, find_technologies
from modele import AggregatedOffer
from texte import normalize


MIN_WORDS = 200
MAX_WORDS = 450
STEM_LENGTH = 5
MAX_KEYWORDS = 8
PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\n]{2,40}\]|<[^>\n]{2,40}>|\bX{3,}\b|_{4,}|\.{5,}")
# Mots trop courants pour dire quelque chose sur l'offre.
STOP_WORDS = set("""
avec dans pour les des une sur par aux leur leurs vous nous votre notre cette ainsi plus etre avoir faire
autres autre selon entre comme tous toutes toute tout sont elle elles ils mais donc afin aussi lors chez
dont celle celui ceux cela cette ces son ses sous vers pendant depuis tres bien peut doit faut quelle quel
travail poste emploi offre taches tache equipe entreprise client clients
mettre effectuer assurer realiser permettre utiliser prendre participer contribuer
""".split())
# Mots du nom de l'employeur qui ne le distinguent pas.
EMPLOYER_COMMON = set("""
les des the and inc ltee ltd ltée cie enr corp corporation groupe group technologies technologie solutions
services service conseils consultants canada quebec montreal international systemes systems informatique
""".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def _stem(word: str) -> str:
    return word[:STEM_LENGTH]


def _significant(text: str, min_length: int = 4) -> list[str]:
    """Mots importants, une seule fois par racine, écrits comme dans le texte (avec les accents)."""
    seen: dict[str, str] = {}
    for word in re.findall(r"[^\W\d_]+", text.lower()):
        plain = normalize(word)
        if len(plain) >= min_length and plain not in STOP_WORDS:
            seen.setdefault(_stem(plain), word)
    return list(seen.values())


@dataclass
class LetterCheck:
    word_count: int
    employer_mentioned: bool | None  # None : employeur inconnu dans l'offre
    title_mentioned: bool
    technologies_cited: list[str] = field(default_factory=list)
    technologies_missing: list[str] = field(default_factory=list)
    skills_cited: list[str] = field(default_factory=list)
    skills_missing: list[str] = field(default_factory=list)
    keywords_missing: list[str] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)


def employer_mentioned(letter: str, employer: str) -> bool | None:
    """Vrai si un mot distinctif du nom de l'employeur est dans la lettre."""
    distinctive = [word for word in _words(employer) if len(word) >= 3 and word not in EMPLOYER_COMMON]
    if not distinctive:
        distinctive = [word for word in _words(employer) if len(word) >= 3]
    if not distinctive:
        return None
    letter_words = set(_words(letter))
    return any(word in letter_words for word in distinctive)


def title_mentioned(letter: str, offer: AggregatedOffer) -> bool:
    """Vrai si au moins 2 mots importants sur 3 du titre (de l'employeur ou CNP) sont dans la lettre."""
    letter_stems = {_stem(word) for word in _words(letter)}
    # Titre CNP « développeur/développeuse Web full-stack » : on retire la forme féminine.
    cnp_title = re.sub(r"/[^\s/]+", "", offer.title)
    for title in (offer.original_title, cnp_title):
        words = _significant(title)
        if words and sum(_stem(normalize(word)) in letter_stems for word in words) * 3 >= len(words) * 2:
            return True
    return False


def missing_keywords(letter: str, offer: AggregatedOffer) -> list[str]:
    """Mots importants des tâches (ou du résumé) de l'offre absents de la lettre."""
    source = " ".join(offer.tasks) or offer.summary
    letter_stems = {_stem(word) for word in _words(letter)}
    return [
        word for word in _significant(source, min_length=5) if _stem(normalize(word)) not in letter_stems
    ][:MAX_KEYWORDS]


def check_letter(letter: str, offer: AggregatedOffer) -> LetterCheck:
    cited_tech = find_technologies(letter)
    cited_skills = find_skills(letter)
    return LetterCheck(
        word_count=len(re.findall(r"\w+(?:['’]\w+)?", letter)),
        employer_mentioned=employer_mentioned(letter, offer.employer),
        title_mentioned=title_mentioned(letter, offer),
        technologies_cited=[name for name in offer.technologies if name in cited_tech],
        technologies_missing=[name for name in offer.technologies if name not in cited_tech],
        skills_cited=[name for name in offer.skills if name in cited_skills],
        skills_missing=[name for name in offer.skills if name not in cited_skills],
        keywords_missing=missing_keywords(letter, offer),
        placeholders=list(dict.fromkeys(PLACEHOLDER_PATTERN.findall(letter))),
    )


def letter_tips(check: LetterCheck, offer: AggregatedOffer, cv_technologies: list[str] | None = None) -> list[str]:
    """Suggestions concrètes. Avec le CV, on distingue ce qu'on sait faire de ce qu'il faudrait apprendre."""
    tips: list[str] = []
    title = offer.original_title or offer.title
    if check.placeholders:
        tips.append("Zones à remplir oubliées : " + ", ".join(check.placeholders) + ".")
    if check.employer_mentioned is False:
        tips.append(f"Nommez l'employeur ({offer.employer}) et dites pourquoi il vous intéresse.")
    if not check.title_mentioned:
        tips.append(f"Indiquez clairement le poste visé : « {title} ».")
    if check.technologies_cited:
        tips.append("Bien : la lettre cite " + ", ".join(check.technologies_cited) + ", demandés par l'offre.")
    if check.technologies_missing:
        if cv_technologies is not None:
            known = [name for name in check.technologies_missing if name in cv_technologies]
            unknown = [name for name in check.technologies_missing if name not in cv_technologies]
            if known:
                tips.append("Ces technologies sont dans votre CV mais pas dans la lettre : " + ", ".join(known)
                            + ". Donnez un exemple concret où vous les avez utilisées.")
            if unknown:
                tips.append("Demandées par l'offre, absentes de la lettre et du CV : " + ", ".join(unknown)
                            + ". N'en parlez que si vous les connaissez; sinon, montrez que vous apprenez vite.")
        else:
            tips.append("Technologies de l'offre absentes de la lettre : " + ", ".join(check.technologies_missing)
                        + ". Citez celles que vous connaissez vraiment, avec un exemple.")
    if check.skills_missing:
        tips.append("Compétences recherchées absentes de la lettre : " + ", ".join(check.skills_missing) + ".")
    if check.keywords_missing:
        tips.append("Mots importants des tâches de l'offre absents de la lettre : " + ", ".join(check.keywords_missing)
                    + ". Reprenez une ou deux tâches qui correspondent à votre expérience.")
    if check.word_count < MIN_WORDS:
        tips.append(f"La lettre est courte ({check.word_count} mots). Visez environ {MIN_WORDS} à {MAX_WORDS} mots, "
                    "avec un exemple de projet ou d'expérience.")
    elif check.word_count > MAX_WORDS:
        tips.append(f"La lettre est longue ({check.word_count} mots). Visez une page, environ {MIN_WORDS} à {MAX_WORDS} mots.")
    if not offer.description and offer.original_url:
        tips.append(f"Lisez l'annonce complète avant d'envoyer la lettre : {offer.original_url}")
    return tips


def find_offer(offers: list[AggregatedOffer], reference: str) -> AggregatedOffer | None:
    """Trouve une offre par son numéro du Guichet-Emplois, son identifiant Remotive ou son lien."""
    reference = reference.strip()
    number = re.search(r"(\d+)\s*/?$", reference)
    for offer in offers:
        for record in offer.source_records:
            if reference and (reference == record.url or reference == offer.original_url):
                return offer
            if number and record.source_id == number.group(1):
                return offer
    return None


def build_letter_report(check: LetterCheck, offer: AggregatedOffer, tips: list[str]) -> str:
    link = offer.source_records[0].url if offer.source_records else ""
    lines = [
        "# Vérification de ma lettre de motivation",
        "",
        f"Offre : [{offer.original_title or offer.title}]({link}) — {offer.employer or 'employeur non précisé'}",
        "",
        "| Vérification | Résultat |",
        "|---|---|",
        f"| Longueur | {check.word_count} mots |",
        f"| Employeur cité | {'oui' if check.employer_mentioned else 'non' if check.employer_mentioned is False else 'inconnu'} |",
        f"| Poste cité | {'oui' if check.title_mentioned else 'non'} |",
        f"| Technologies de l'offre citées | {', '.join(check.technologies_cited) or 'aucune'} |",
        f"| Technologies de l'offre absentes | {', '.join(check.technologies_missing) or 'aucune'} |",
        f"| Zones à remplir oubliées | {', '.join(check.placeholders) or 'aucune'} |",
        "",
        "## Suggestions",
        "",
    ]
    lines += [f"- {tip}" for tip in tips] or ["- Rien à signaler avec ces règles. Relisez quand même l'offre complète."]
    lines += ["", "---", "Ces vérifications viennent de règles simples : elles ne jugent ni le style ni l'orthographe."]
    return "\n".join(lines) + "\n"
