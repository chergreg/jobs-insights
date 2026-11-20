"""Aide à la candidature (piste 4 du projet) : comparer un CV avec les offres.

Tout se fait sur l'ordinateur, avec des règles simples et expliquées :
le CV n'est envoyé à aucun service extérieur.

1. read_cv() lit un CV en .txt, .md ou .docx (Word).
2. build_profile() en tire les technologies, compétences, années d'expérience,
   niveau et langues, avec les mêmes règles que pour les offres (competences.py).
3. match_offer() donne à chaque offre une note sur 100 et les raisons de cette note.
4. suggestions() propose des pistes pour adapter son CV à une offre précise.

Note sur 100 (les parties absentes d'une offre ne comptent pas) :
- technologies : 55 points, selon la part des technologies de l'offre présentes
  dans le CV (60 %) et le nombre de technologies en commun, jusqu'à 4 (40 %) ;
- compétences générales : 25 points, selon la part des compétences de l'offre
  présentes dans le CV ;
- niveau : 20 points si l'offre est du niveau du CV ou plus bas, 5 points
  si elle est un niveau au-dessus, 0 si elle est deux niveaux au-dessus.
- une offre qui liste peu d'éléments donne peu d'information : 1 élément garde
  70 % de la note, 2 éléments 80 %, 3 éléments 90 %, 4 et plus 100 % ;
- +10 points pour un stage, si le CV cherche un stage (note plafonnée à 100).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

from competences import experience_years, find_skills, find_technologies
from modele import AggregatedOffer
from texte import clean, normalize


LEVEL_RANK = {"débutant": 0, "intermédiaire": 1, "avancé": 2}
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
STUDENT_PATTERN = re.compile(r"\b(?:etudiant|etudiante|finissant|finissante|stage|stagiaire|intern|internship)\b")
STAGE_WANTED_PATTERN = re.compile(r"\b(?:recherche|cherche|disponible pour|looking for)\b[^.\n]{0,40}\b(?:stage|internship)\b")
LANGUAGE_WORDS = {"Français": r"\bfrancais\b|\bfrench\b", "Anglais": r"\banglais\b|\benglish\b"}
POINTS_TECHNOLOGIES = 55
POINTS_SKILLS = 25
POINTS_LEVEL = 20
STAGE_BONUS = 10
INFORMATION_FLOOR = 0.6
FULL_INFORMATION = 4


# --- Lecture du CV -------------------------------------------------------------

def read_cv(path: Path) -> str:
    """Texte d'un CV en .txt, .md ou .docx. Les autres formats sont refusés avec un message clair."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        raw = path.read_bytes()
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("cp1252")  # fichier enregistré par le Bloc-notes en ANSI
    if suffix == ".docx":
        return _read_docx(path)
    raise ValueError(
        f"Format {suffix or 'inconnu'} non pris en charge. "
        "Enregistrez le CV en .docx (Word) ou en .txt, puis relancez."
    )


def _read_docx(path: Path) -> str:
    """Un .docx est un dossier compressé : le texte est dans word/document.xml."""
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError(f"{path.name} n'est pas un fichier Word (.docx) lisible.") from error

    paragraphs = []
    for paragraph in root.iter(WORD_NS + "p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == WORD_NS + "t" and node.text:
                parts.append(node.text)
            elif node.tag == WORD_NS + "tab":
                parts.append(" ")
            elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


# --- Profil tiré du CV --------------------------------------------------------------

@dataclass
class CandidateProfile:
    technologies: list[str]
    skills: list[str]
    years: float | None
    level: str
    languages: list[str]
    wants_stage: bool
    has_bachelor: bool = False


def build_profile(text: str) -> CandidateProfile:
    normalized = normalize(text)
    years = experience_years("", text)
    is_student = bool(STUDENT_PATTERN.search(normalized))
    if years is None and is_student:
        years = 0.0  # étudiant sans expérience chiffrée
    level = "" if years is None else ("débutant" if years < 2 else "intermédiaire" if years < 5 else "avancé")
    return CandidateProfile(
        technologies=find_technologies(text),
        skills=find_skills(text),
        years=years,
        level=level,
        languages=[name for name, pattern in LANGUAGE_WORDS.items() if re.search(pattern, normalized)],
        wants_stage=bool(STAGE_WANTED_PATTERN.search(normalized)),
        has_bachelor=bool(re.search(r"\bbaccalaureat\b|\bbachelor", normalized)),
    )


# --- Comparaison avec une offre -------------------------------------------------------

@dataclass
class Match:
    offer: AggregatedOffer
    score: int
    shared_technologies: list[str] = field(default_factory=list)
    missing_technologies: list[str] = field(default_factory=list)
    shared_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def match_offer(profile: CandidateProfile, offer: AggregatedOffer) -> Match | None:
    """Note sur 100 et raisons. None si l'offre ne liste ni technologie ni compétence."""
    offer_tech, offer_skills = list(offer.technologies), list(offer.skills)
    if not offer_tech and not offer_skills:
        return None

    shared_tech = [name for name in offer_tech if name in profile.technologies]
    shared_skills = [name for name in offer_skills if name in profile.skills]
    earned = possible = 0.0
    reasons: list[str] = []

    if offer_tech:
        coverage = len(shared_tech) / len(offer_tech)
        earned += POINTS_TECHNOLOGIES * (0.6 * coverage + 0.4 * min(len(shared_tech), 4) / 4)
        possible += POINTS_TECHNOLOGIES
        reasons.append(f"{len(shared_tech)} technologie(s) sur {len(offer_tech)} en commun")
    if offer_skills:
        earned += POINTS_SKILLS * len(shared_skills) / len(offer_skills)
        possible += POINTS_SKILLS
        reasons.append(f"{len(shared_skills)} compétence(s) sur {len(offer_skills)} en commun")

    possible += POINTS_LEVEL
    if offer.level in LEVEL_RANK and profile.level in LEVEL_RANK:
        gap = LEVEL_RANK[offer.level] - LEVEL_RANK[profile.level]
        if gap <= 0:
            earned += POINTS_LEVEL
            reasons.append(f"niveau {offer.level} : accessible")
        elif gap == 1:
            earned += 5
            reasons.append(f"niveau {offer.level} : un peu au-dessus du CV ({profile.level})")
        else:
            reasons.append(f"niveau {offer.level} : bien au-dessus du CV ({profile.level})")
    else:
        earned += POINTS_LEVEL / 2  # niveau inconnu : ni bonus ni pénalité complète
        reasons.append("niveau non précisé")

    score = 100 * earned / possible
    # Une offre qui liste très peu d'éléments donne peu d'information : sa note est réduite
    # (1 élément : 70 %, 2 : 80 %, 3 : 90 %, 4 et plus : 100 %).
    listed = len(offer_tech) + len(offer_skills)
    score *= INFORMATION_FLOOR + (1 - INFORMATION_FLOOR) * min(listed, FULL_INFORMATION) / FULL_INFORMATION
    if listed < FULL_INFORMATION:
        reasons.append(f"peu d'information dans l'offre ({listed} élément(s))")
    if profile.wants_stage and offer.stage_status != "not_indicated":
        score += STAGE_BONUS
        reasons.append("stage, comme demandé dans le CV")
    return Match(
        offer=offer,
        score=min(100, round(score)),
        shared_technologies=shared_tech,
        missing_technologies=[name for name in offer_tech if name not in profile.technologies],
        shared_skills=shared_skills,
        missing_skills=[name for name in offer_skills if name not in profile.skills],
        reasons=reasons,
    )


def stage_offers(matches: list[Match]) -> list[tuple[int, Match]]:
    """Rang (à partir de 1) et offre, pour chaque stage du classement."""
    return [(rank, match) for rank, match in enumerate(matches, start=1) if match.offer.stage_status != "not_indicated"]


def rank_offers(profile: CandidateProfile, offers: list[AggregatedOffer]) -> tuple[list[Match], int]:
    """Offres triées de la meilleure à la moins bonne, et nombre d'offres sans information à comparer."""
    matches, without_information = [], 0
    for offer in offers:
        match = match_offer(profile, offer)
        if match is None:
            without_information += 1
        else:
            matches.append(match)
    matches.sort(key=lambda item: (-item.score, -len(item.shared_technologies), item.offer.title))
    return matches, without_information


# --- Suggestions pour une offre ---------------------------------------------------------

def _required_languages(offer: AggregatedOffer) -> list[str]:
    required: list[str] = []
    for value in offer.languages:
        text = normalize(value)
        if "bilingue" in text:
            required += ["Français", "Anglais"]
        for name, pattern in LANGUAGE_WORDS.items():
            if re.search(pattern, text):
                required.append(name)
    return list(dict.fromkeys(required))


def suggestions(profile: CandidateProfile, match: Match, today: date | None = None) -> list[str]:
    """Pistes concrètes pour adapter son CV à cette offre. Rien n'est inventé sur le candidat."""
    offer, today = match.offer, today or date.today()
    tips: list[str] = []

    if match.shared_technologies:
        tips.append(
            "Mettez en avant " + ", ".join(match.shared_technologies)
            + " : l'offre les demande et ils sont déjà dans votre CV. Placez-les en haut de vos compétences "
            "et montrez-les dans un projet."
        )
    if match.missing_technologies:
        several = len(match.missing_technologies) > 1
        tips.append(
            "L'offre mentionne aussi " + ", ".join(match.missing_technologies)
            + (". Ajoutez-les seulement si vous les connaissez vraiment"
               if several else ". Ajoutez-la seulement si vous la connaissez vraiment")
            + "; sinon, c'est un sujet à apprendre ou à aborder en entrevue."
        )
    if match.missing_skills:
        tips.append(
            "Compétences recherchées absentes du CV : " + ", ".join(match.missing_skills)
            + ". Si vous en avez l'expérience (cours, projet, emploi), décrivez-la avec un exemple."
        )

    missing_languages = [name for name in _required_languages(offer) if name not in profile.languages]
    if missing_languages:
        tips.append("Langue(s) demandée(s) par l'offre et absente(s) du CV : " + ", ".join(missing_languages) + ".")

    needed = offer.experience_years_min
    if needed is not None and (profile.years or 0) < needed:
        tips.append(
            f"L'offre demande {offer.experience or f'{needed:g} an(s)'} d'expérience. Mettez en valeur vos stages, "
            "projets d'équipe et emplois étudiants en TI, avec leur durée."
        )
    if offer.education and "baccalaureat" in normalize(offer.education) and not profile.has_bachelor:
        tips.append(f"Études demandées : {offer.education}. Si vous n'avez pas ce diplôme, insistez sur l'« expérience équivalente » quand l'offre l'accepte.")

    if offer.tasks:
        tips.append("Reliez vos projets à ces tâches de l'offre : " + "; ".join(offer.tasks[:3]) + ".")
    elif offer.summary:
        tips.append(f"Relisez le début de l'offre et reprenez ses mots-clés : « {offer.summary[:200]} »")
    if not offer.description and offer.original_url:
        tips.append(f"La description complète est seulement sur le site d'origine : {offer.original_url}")

    if profile.wants_stage and offer.stage_status == "not_indicated":
        tips.append("Cette offre n'est pas présentée comme un stage : demandez à l'employeur s'il accepte les stagiaires.")
    try:
        days = (date.fromisoformat(offer.expires_at) - today).days
        if days == 0:
            tips.append(f"Postulez vite : l'offre expire aujourd'hui ({offer.expires_at}).")
        elif 0 < days <= 7:
            tips.append(f"Postulez vite : l'offre expire le {offer.expires_at} (dans {days} jour{'s' if days > 1 else ''}).")
    except ValueError:
        pass
    return tips


# --- Rapport Markdown ---------------------------------------------------------------------

def build_report(
    profile: CandidateProfile,
    matches: list[Match],
    without_information: int,
    filters_text: str,
    top: int = 10,
    detailed: int = 3,
    today: date | None = None,
) -> str:
    """Rapport lisible (Markdown) : profil, meilleures offres, suggestions pour les premières."""
    today = today or date.today()
    lines = [
        "# Offres les plus proches de mon CV",
        "",
        f"Rapport créé le {today.isoformat()}. Filtres : {filters_text}.",
        "",
        "## Ce que le programme a trouvé dans le CV",
        "",
        f"- Technologies : {', '.join(profile.technologies) or 'aucune reconnue'}",
        f"- Compétences : {', '.join(profile.skills) or 'aucune reconnue'}",
        f"- Expérience : {'non précisée' if profile.years is None else f'{profile.years:g} an(s)'}"
        + (f" (niveau {profile.level})" if profile.level else ""),
        f"- Langues : {', '.join(profile.languages) or 'non précisées'}",
        f"- Cherche un stage : {'oui' if profile.wants_stage else 'non'}",
        "",
        "Si une information manque, ajoutez-la clairement dans le CV (ex. « Langages : Python, SQL ») et relancez.",
        "",
        f"## Les {min(top, len(matches))} meilleures offres",
        "",
        f"{len(matches)} offres comparées. {without_information} offres ne listent ni technologie ni compétence : "
        "elles ne sont pas classées.",
        "",
        "| # | Note | Offre | Employeur | Ville | Technologies en commun |",
        "|---|---|---|---|---|---|",
    ]
    for rank, match in enumerate(matches[:top], start=1):
        offer = match.offer
        title = (offer.original_title or offer.title).replace("|", "/")
        link = offer.source_records[0].url if offer.source_records else ""
        title_cell = f"[{title}]({link})" if link else title
        lines.append(
            f"| {rank} | {match.score} | {title_cell} | {(offer.employer or '?').replace('|', '/')} "
            f"| {offer.city or offer.location or '?'} | {', '.join(match.shared_technologies) or '—'} |"
        )
    if profile.wants_stage:
        stages = stage_offers(matches)
        lines += ["", "### Stages dans le classement", ""]
        lines += [
            f"- n° {rank} : {m.offer.original_title or m.offer.title} — {m.offer.employer or '?'} ({m.score}/100)"
            for rank, m in stages
        ] or ["- Aucun stage parmi ces offres. Essayez sans filtre de région, ou revenez après une nouvelle collecte."]
    for rank, match in enumerate(matches[:detailed], start=1):
        offer = match.offer
        lines += [
            "",
            f"## {rank}. {offer.original_title or offer.title} — {offer.employer or 'employeur non précisé'}",
            "",
            f"Note : {match.score}/100 ({'; '.join(match.reasons)}).",
            "",
            "Pistes pour adapter le CV :",
            "",
        ]
        lines += [f"- {tip}" for tip in suggestions(profile, match, today)] or ["- Aucune suggestion particulière."]
    lines += [
        "",
        "---",
        "Ces notes viennent de règles simples (technologies, compétences, niveau). Elles aident à choisir "
        "par où commencer, mais elles ne remplacent pas la lecture de l'offre complète.",
    ]
    return "\n".join(lines) + "\n"
