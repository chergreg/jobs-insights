"""
Module d'exploration, de filtrage multicritère, d'aide à la candidature (Piste 3 & Piste 4 :
Matching CV .txt/.md/.docx/.json + Audit de lettre de motivation), de conversion au format
commun de la classe (modèle JobOffer de Grégory) et de génération du portail Web interactif
autonome (`portail_ti_jobtailor.html`).

Auteur : Mamadou (Livrable 3 — Bonification inspirée des travaux de Grégory, Kandet, Elvira et Hugo
         et de notre moteur personnel JobTailor_V3).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import html
import json
from pathlib import Path
import re
from typing import Any, Optional
import zipfile
from xml.etree import ElementTree

from poc_guichet_cnp_v2 import (
    CNP_2021_TI_DICT,
    JobBankOffer,
    _normalize_for_match,
    _strip_accents,
    detect_ti_domain,
    extract_experience_and_seniority,
    extract_tech_skills,
)

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PLACEHOLDER_RE = re.compile(r"\[[^\]\n]{2,50}\]|<[^>\n]{2,50}>|\bX{3,}\b|_{4,}|\.{5,}")

SENIORITY_RANK: dict[str, int] = {
    "Étudiant / Stage": 0,
    "Junior / DEC": 1,
    "Intermédiaire": 2,
    "Senior": 3,
}

STOPWORDS_MISSIONS: set[str] = {
    "avec", "dans", "pour", "les", "des", "une", "sur", "par", "aux", "leur", "leurs",
    "vous", "nous", "votre", "notre", "cette", "ainsi", "plus", "etre", "avoir", "faire",
    "autres", "autre", "selon", "entre", "comme", "tous", "toutes", "toute", "tout",
    "sont", "elle", "elles", "ils", "mais", "donc", "afin", "aussi", "lors", "chez",
    "travail", "poste", "emploi", "offre", "taches", "equipe", "entreprise", "client",
    "clients", "mettre", "effectuer", "assurer", "realiser", "permettre", "utiliser",
    "participer", "contribuer", "collaborer",
}

EMPLOYER_GENERIC_WORDS: set[str] = {
    "les", "des", "the", "and", "inc", "ltee", "ltd", "cie", "enr", "corp", "corporation",
    "groupe", "group", "technologies", "technologie", "solutions", "services", "service",
    "conseils", "consultants", "canada", "quebec", "montreal", "international", "systemes",
    "systems", "informatique",
}


# ==============================================================================
# 1. Filtre de fraîcheur et validité 2026 (inspiré d'Elvira)
# ==============================================================================
def is_recent_and_valid_offer(
    offer: JobBankOffer,
    min_year: int = 2026,
    reference_date: Optional[str] = None,
) -> bool:
    """
    Vérifie qu'une offre n'est ni une ancienne annonce d'une année passée (ex. offres Jobboom
    de 2023), ni une offre dont la date de fin d'affichage (`date_fin`) est dépassée.
    """
    if offer.date_publication and len(offer.date_publication) >= 4:
        try:
            pub_year = int(offer.date_publication[:4])
            if pub_year < min_year:
                return False
        except ValueError:
            pass

    if reference_date and offer.date_fin and re.match(r"^\d{4}-\d{2}-\d{2}$", offer.date_fin):
        if offer.date_fin < reference_date:
            return False

    return True


# ==============================================================================
# 2. Filtrage multicritère hors ligne (inspiré de Kandet & Elvira)
# ==============================================================================
def filter_offers(
    offers: list[JobBankOffer],
    ville: Optional[str] = None,
    region: Optional[str] = None,
    domaine: Optional[str] = None,
    code_cnp: Optional[str] = None,
    techno: Optional[str] = None,
    seniorite: Optional[str] = None,
    source: Optional[str] = None,
    stages_only: bool = False,
    salaire_min: Optional[float] = None,
    unite_salaire: Optional[str] = None,
    recent_only: bool = True,
) -> list[JobBankOffer]:
    """Filtre une liste d'offres TI hors ligne selon les critères fournis (insensible aux accents/casse)."""
    result: list[JobBankOffer] = []

    v_norm = _normalize_for_match(ville) if ville else ""
    r_norm = _normalize_for_match(region) if region else ""
    d_norm = _normalize_for_match(domaine) if domaine else ""
    cnp_norm = (code_cnp or "").strip()
    t_norm = _strip_accents(techno.lower().strip()) if techno else ""
    s_norm = _normalize_for_match(seniorite) if seniorite else ""
    src_norm = _normalize_for_match(source) if source else ""
    u_norm = _strip_accents(unite_salaire.lower().strip()) if unite_salaire else ""

    for off in offers:
        if recent_only and not is_recent_and_valid_offer(off):
            continue
        if stages_only and not off.est_stage:
            continue
        if v_norm and v_norm not in _normalize_for_match(f"{off.ville or ''} {off.lieu or ''}"):
            continue
        if r_norm and r_norm not in _normalize_for_match(off.region_administrative or ""):
            continue
        if d_norm and d_norm not in _normalize_for_match(off.domaine_ti or ""):
            continue
        if cnp_norm and (off.code_cnp or "") != cnp_norm:
            continue
        if src_norm and src_norm not in _normalize_for_match(off.source):
            continue
        if s_norm and s_norm not in _normalize_for_match(off.niveau_seniorite or ""):
            continue
        if t_norm:
            skills_joined = _strip_accents(" ".join(off.competences_cles or []).lower())
            if t_norm not in skills_joined:
                continue
        if salaire_min is not None:
            if off.salaire_min is None:
                continue
            if u_norm and u_norm not in _strip_accents((off.unite_salaire or "").lower()):
                continue
            if (off.salaire_max or off.salaire_min) < salaire_min:
                continue

        result.append(off)

    return result


# ==============================================================================
# 3. Aide à la candidature : Lecture CV (.txt, .md, .docx, .json) & Matching ATS
# ==============================================================================
@dataclass
class CandidateCVProfile:
    """Profil candidat extrait d'un fichier CV (.txt, .md, .docx ou .json JobTailor_V3)."""

    raw_text: str
    competences: list[str]
    domaine_principal: str
    niveau_seniorite: str
    experience_mentionnee: Optional[str]
    cherche_stage: bool
    langues: list[str] = field(default_factory=list)
    niveau_etudes: str = "Collégial (DEC / AEC)"


@dataclass
class OfferCVMatchResult:
    """Résultat de correspondance ATS (0-100) entre un CV et une offre TI."""

    offer: JobBankOffer
    score_ats: int
    competences_communes: list[str] = field(default_factory=list)
    competences_manquantes: list[str] = field(default_factory=list)
    raisons_score: list[str] = field(default_factory=list)
    suggestions_adaptation_cv: list[str] = field(default_factory=list)


@dataclass
class CoverLetterAuditResult:
    """Diagnostic déterministe d'une lettre de motivation face à une offre TI."""

    offer_id: str
    offer_title: str
    employer: str
    word_count: int
    mentionne_employeur: bool
    mentionne_titre: bool
    structure_vous_moi_nous: bool
    technologies_citees: list[str] = field(default_factory=list)
    technologies_manquantes: list[str] = field(default_factory=list)
    mots_cles_missions_manquants: list[str] = field(default_factory=list)
    zones_a_remplir_oubliees: list[str] = field(default_factory=list)
    conseils: list[str] = field(default_factory=list)


def read_cv_document(path: Path) -> str:
    """
    Lit le texte d'un CV aux formats `.txt`, `.md`, `.docx` (Word natif via zipfile) ou `.json` (`master_profile.json`).
    Refuse les formats binaires non supportés (ex. `.pdf`) avec un message explicite.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        raw_bytes = path.read_bytes()
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw_bytes.decode("cp1252", errors="replace")

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as zf:
                xml_bytes = zf.read("word/document.xml")
                root = ElementTree.fromstring(xml_bytes)
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ValueError(f"Le fichier {path.name} n'est pas un document Word (.docx) valide.") from exc

        paragraphs: list[str] = []
        for p_node in root.iter(WORD_NS + "p"):
            chunks: list[str] = []
            for node in p_node.iter():
                if node.tag == WORD_NS + "t" and node.text:
                    chunks.append(node.text)
                elif node.tag == WORD_NS + "tab":
                    chunks.append(" ")
                elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
                    chunks.append("\n")
            if chunks:
                paragraphs.append("".join(chunks))
        return "\n".join(paragraphs)

    raise ValueError(
        f"Format '{suffix}' non pris en charge hors ligne. "
        "Veuillez fournir votre CV en .txt, .md, .docx (Word) ou .json."
    )


def build_candidate_profile_from_text(cv_text: str) -> CandidateCVProfile:
    """Construit le profil candidat (`CandidateCVProfile`) à partir du texte brut d'un CV."""
    norm = _strip_accents(cv_text.lower())
    skills = extract_tech_skills(cv_text)

    wants_stage = bool(
        re.search(
            r"\b(?:recherche|cherche|disponible\s+pour|objectif|cible)\b[^.\n]{0,45}\b(?:stage|stagiaire|internship|intern)\b"
            r"|\b(?:stagiaire\s+en\s+informatique|etudiant\w*\s+au\s+dec)\b",
            norm,
        )
    )
    exp_str, seniority = extract_experience_and_seniority(
        title="Stagiaire" if wants_stage else cv_text[:120],
        description=cv_text,
        est_stage=wants_stage,
    )
    dom = detect_ti_domain(cv_text[:200], description=cv_text, competences=skills)

    langs: list[str] = []
    if re.search(r"\b(?:francais|french|bilingue|bilingual)\b", norm):
        langs.append("Français")
    if re.search(r"\b(?:anglais|english|bilingue|bilingual)\b", norm):
        langs.append("Anglais")

    edu = "Collégial (DEC / AEC)"
    if re.search(r"\b(?:baccalaureat|bachelor|universit\w+)\b", norm):
        edu = "Universitaire (Baccalauréat)"

    return CandidateCVProfile(
        raw_text=cv_text,
        competences=skills,
        domaine_principal=dom,
        niveau_seniorite=seniority,
        experience_mentionnee=exp_str,
        cherche_stage=wants_stage,
        langues=langs,
        niveau_etudes=edu,
    )


def match_cv_with_offer(profile: CandidateCVProfile, offer: JobBankOffer) -> OfferCVMatchResult:
    """
    Calcule le score d'adéquation ATS (0 à 100) entre un CV et une offre TI
    en combinant la logique `JobTailor_V3` (filtrage de domaine + couverture ATS)
    et la pondération de Kandet (couverture relative + volume de compétences communes + séniorité).
    """
    off_skills = list(offer.competences_cles or [])
    cand_set = {s.lower(): s for s in profile.competences}

    shared = [s for s in off_skills if s.lower() in cand_set]
    missing = [s for s in off_skills if s.lower() not in cand_set]
    reasons: list[str] = []

    # 1. Score Technologies & Compétences (sur 60 points)
    if off_skills:
        coverage_ratio = len(shared) / len(off_skills)
        volume_bonus = min(len(shared), 4) / 4.0
        tech_points = 60.0 * (0.60 * coverage_ratio + 0.40 * volume_bonus)
        # Pénalité légère si l'offre ne liste qu'une seule compétence générique
        if len(off_skills) == 1:
            tech_points *= 0.80
        elif len(off_skills) == 2:
            tech_points *= 0.90
        reasons.append(f"Technologies en commun : {len(shared)}/{len(off_skills)}")
    else:
        tech_points = 25.0

    # 2. Score Domaine TI (sur 15 points — logique JobTailor_V3)
    if offer.domaine_ti == profile.domaine_principal:
        domain_points = 15.0
        reasons.append(f"Domaine TI aligné ({offer.domaine_ti})")
    elif {offer.domaine_ti, profile.domaine_principal} <= {"tech_backend", "tech_frontend", "devops_cloud", "data_ia"}:
        domain_points = 9.0
    else:
        domain_points = 4.0

    # 3. Score Niveau de séniorité & Études (sur 25 points)
    cand_rank = SENIORITY_RANK.get(profile.niveau_seniorite, 1)
    off_rank = SENIORITY_RANK.get(offer.niveau_seniorite or "Intermédiaire", 2)
    diff = off_rank - cand_rank
    if diff <= 0:
        level_points = 25.0
        reasons.append(f"Niveau accessible ({offer.niveau_seniorite})")
    elif diff == 1:
        level_points = 14.0
        reasons.append(f"Niveau un cran au-dessus ({offer.niveau_seniorite})")
    else:
        level_points = 3.0
        reasons.append(f"Niveau exigeant ({offer.niveau_seniorite})")

    total_score = int(round(tech_points + domain_points + level_points))

    # Bonus Stage si l'étudiant cherche un stage
    if profile.cherche_stage and offer.est_stage:
        total_score = min(100, total_score + 12)
        reasons.append("Bonus Stage confirmé (+12 pts)")

    total_score = max(0, min(100, total_score))

    # Suggestions concrètes d'adaptation du CV (0 invention / 0 hallucination)
    suggestions: list[str] = []
    target_title = offer.titre_employeur or offer.titre or "ce poste"
    if shared:
        suggestions.append(
            f"Mettez en évidence en haut de votre CV vos compétences vérifiées demandées par l'offre : {', '.join(shared[:6])}."
        )
    if missing:
        suggestions.append(
            f"Compétences demandées absentes de votre CV (Gap Analysis) : {', '.join(missing[:5])}. "
            "Si vous les avez pratiquées en projet académique ou personnel, ajoutez-les avec une preuve concrète ; sinon, ne les inventez jamais."
        )
    if offer.missions_cles:
        suggestions.append(
            f"Orientez vos puces d'expérience (méthode STAR) vers la mission clé de l'offre : « {offer.missions_cles[0]} »."
        )
    else:
        suggestions.append(
            f"Adaptez votre titre de profil CV en mentionnant l'intitulé « {target_title} » ({offer.code_cnp} - {offer.domaine_ti})."
        )

    return OfferCVMatchResult(
        offer=offer,
        score_ats=total_score,
        competences_communes=shared,
        competences_manquantes=missing,
        raisons_score=reasons,
        suggestions_adaptation_cv=suggestions,
    )


def match_cv_against_offers(
    cv_text: str,
    offers: list[JobBankOffer],
    top_n: int = 10,
) -> tuple[CandidateCVProfile, list[OfferCVMatchResult]]:
    """Compare un CV à l'ensemble des offres TI et retourne le profil + les meilleures offres triées."""
    profile = build_candidate_profile_from_text(cv_text)
    matches = [match_cv_with_offer(profile, off) for off in offers if is_recent_and_valid_offer(off)]
    matches.sort(
        key=lambda m: (
            m.score_ats,
            1 if (profile.cherche_stage and m.offer.est_stage) else 0,
            len(m.competences_communes),
            m.offer.score_pertinence_dec,
        ),
        reverse=True,
    )
    return profile, matches[: max(1, top_n)]


# ==============================================================================
# 4. Audit de Lettre de Motivation (Méthode Vous / Moi / Nous + Mots-clés offre)
# ==============================================================================
def audit_cover_letter(
    letter_text: str,
    offer: JobBankOffer,
    cv_text: Optional[str] = None,
) -> CoverLetterAuditResult:
    """
    Vérifie une lettre de motivation par rapport à une offre TI précise :
    - Mention de l'employeur et du titre du poste
    - Présence des technologies de l'offre (en distinguant celles présentes dans le CV)
    - Mots-clés des missions clés (`missions_cles`)
    - Structure Vous / Moi / Nous (`JobTailor_V3`) et absence de crochets oubliés (`[nom du poste]`, `XXX`).
    """
    words = re.findall(r"\w+(?:['’]\w+)?", letter_text)
    word_count = len(words)
    letter_norm = _normalize_for_match(letter_text)
    letter_tokens = set(letter_norm.split())
    letter_stems = {w[:5] for w in letter_tokens if len(w) >= 4}

    # 1. Mention de l'employeur (mots distinctifs hors Inc, Ltée, Solutions, Technologies...)
    emp_name = offer.entreprise or ""
    emp_tokens = [
        w for w in _normalize_for_match(emp_name).split()
        if len(w) >= 3 and w not in EMPLOYER_GENERIC_WORDS
    ]
    if not emp_tokens:
        emp_tokens = [w for w in _normalize_for_match(emp_name).split() if len(w) >= 3]
    mentionne_employeur = any(w in letter_tokens for w in emp_tokens) if emp_tokens else True

    # 2. Mention du titre du poste (au moins la moitié des racines significatives du titre)
    raw_title = offer.titre_employeur or offer.titre or ""
    clean_title = re.sub(r"/[^\s/]+", "", raw_title)
    title_words = [
        w for w in _normalize_for_match(clean_title).split()
        if len(w) >= 4 and w not in STOPWORDS_MISSIONS
    ]
    if title_words:
        matched_t = sum(1 for w in title_words if w[:5] in letter_stems)
        mentionne_titre = (matched_t * 2) >= len(title_words)
    else:
        mentionne_titre = True

    # 3. Technologies citées vs manquantes
    cited_skills = {s.lower() for s in extract_tech_skills(letter_text)}
    off_skills = list(offer.competences_cles or [])
    tech_cited = [s for s in off_skills if s.lower() in cited_skills]
    tech_missing = [s for s in off_skills if s.lower() not in cited_skills]

    # 4. Mots-clés des missions clés absents de la lettre
    missions_corpus = " ".join(offer.missions_cles or []) or (offer.description or "")[:400]
    mission_keywords: list[str] = []
    seen_stems: set[str] = set()
    for w in re.findall(r"[^\W\d_]{5,}", missions_corpus.lower()):
        nw = _strip_accents(w)
        if nw not in STOPWORDS_MISSIONS and nw[:5] not in seen_stems:
            seen_stems.add(nw[:5])
            if nw[:5] not in letter_stems:
                mission_keywords.append(w)
            if len(mission_keywords) >= 6:
                break

    # 5. Structure Vous / Moi / Nous et placeholders oubliés
    placeholders = list(dict.fromkeys(PLACEHOLDER_RE.findall(letter_text)))
    has_vous = any(w in letter_tokens for w in ("votre", "vos", "equipe", "entreprise")) or mentionne_employeur
    has_moi = any(w in letter_tokens for w in ("mon", "mes", "j", "ai", "experience", "formation", "parcours"))
    has_nous = any(w in letter_tokens for w in ("ensemble", "contribuer", "apporter", "entrevue", "entretien", "echanger"))
    structure_ok = has_vous and has_moi and has_nous

    # 6. Conseils actionnables
    conseils: list[str] = []
    display_title = offer.titre_employeur or offer.titre or "le poste"
    if placeholders:
        conseils.append(f"Attention : remplacez les zones à remplir oubliées : {', '.join(placeholders)}.")
    if not mentionne_employeur and offer.entreprise:
        conseils.append(f"Bloc VOUS (Accroche) : citez explicitement l'employeur « {offer.entreprise} ».")
    if not mentionne_titre:
        conseils.append(f"Objet & Accroche : mentionnez clairement l'intitulé du poste « {display_title} ».")
    if tech_cited:
        conseils.append(f"Points forts : votre lettre valorise déjà {', '.join(tech_cited)}.")
    if tech_missing:
        if cv_text:
            cv_skills_low = {s.lower() for s in extract_tech_skills(cv_text)}
            in_cv = [s for s in tech_missing if s.lower() in cv_skills_low]
            not_in_cv = [s for s in tech_missing if s.lower() not in cv_skills_low]
            if in_cv:
                conseils.append(
                    f"Bloc MOI (Preuves) : vous maîtrisez {', '.join(in_cv)} dans votre CV mais ne les citez pas dans la lettre. Ajoutez un exemple concret !"
                )
            if not_in_cv:
                conseils.append(
                    f"Compétences de l'offre absentes du CV et de la lettre : {', '.join(not_in_cv[:4])} (ne les mentionnez que si vous les connaissez réellement)."
                )
        else:
            conseils.append(
                f"Technologies de l'offre non mentionnées dans la lettre : {', '.join(tech_missing[:5])}. Citez celles que vous maîtrisez."
            )
    if mission_keywords:
        conseils.append(
            f"Vocabulaire ATS des missions à intégrer si pertinent : {', '.join(mission_keywords[:5])}."
        )
    if word_count < 160:
        conseils.append(f"Longueur ({word_count} mots) : lettre un peu courte (visez 200 à 380 mots selon la méthode Vous / Moi / Nous).")
    elif word_count > 450:
        conseils.append(f"Longueur ({word_count} mots) : lettre un peu longue (allégez pour tenir sur une page, ~250-380 mots).")
    if not structure_ok:
        conseils.append("Structure recommandée (JobTailor) : 1. Accroche (VOUS), 2. Adéquation & Preuves (MOI), 3. Synergie (NOUS), 4. Appel à l'action (Entrevue).")

    return CoverLetterAuditResult(
        offer_id=offer.id,
        offer_title=display_title,
        employer=offer.entreprise or "Non spécifié",
        word_count=word_count,
        mentionne_employeur=mentionne_employeur,
        mentionne_titre=mentionne_titre,
        structure_vous_moi_nous=structure_ok,
        technologies_citees=tech_cited,
        technologies_manquantes=tech_missing,
        mots_cles_missions_manquants=mission_keywords,
        zones_a_remplir_oubliees=placeholders,
        conseils=conseils,
    )


# ==============================================================================
# 5. Convertisseur vers le Format Commun de la Classe (`JobOffer` de Grégory)
# ==============================================================================
def convert_to_common_format_dict(offer: JobBankOffer) -> dict[str, Any]:
    """
    Convertit un `JobBankOffer` (36 champs) vers les 17 champs exacts du modèle pivot
    `JobOffer` de Grégory (`equipe/gregory/livrable3/models.py`), sans aucune donnée devinée.
    """
    return {
        "id": offer.id,
        "titre": offer.titre_employeur or offer.titre or "Non spécifié",
        "entreprise": offer.entreprise or "Non spécifié",
        "lieu": offer.lieu or "Non spécifié",
        "province": offer.province or "Non spécifié",
        "pays": offer.pays or "Canada",
        "url": offer.url,
        "source": offer.source,
        "source_partenaire": offer.source_partenaire,
        "date_publication": offer.date_publication,
        "type_poste": offer.type_poste,
        "modalite": offer.modalite,
        "est_stage": bool(offer.est_stage),
        "statut_stage": offer.statut_stage,
        "description": offer.description,
        "competences_cles": list(offer.competences_cles or []),
        "salaire": offer.salaire,
        "date_extraction": offer.date_extraction,
    }


def export_common_format_json(offers: list[JobBankOffer], output_path: Path) -> Path:
    """Exporte les offres au format commun `JobOffer` de la classe dans `output_path`."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    common_list = [convert_to_common_format_dict(o) for o in offers if is_recent_and_valid_offer(o)]
    output_path.write_text(json.dumps(common_list, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def load_offers_from_json(json_path: Path) -> list[JobBankOffer]:
    """Charge un fichier JSON d'offres (`offres_unifiees.json`, etc.) en liste de `JobBankOffer`."""
    if not json_path.is_file():
        raise FileNotFoundError(f"Fichier d'offres introuvable : {json_path}")
    raw_list = json.loads(json_path.read_text(encoding="utf-8"))
    valid_fields = set(JobBankOffer.__dataclass_fields__.keys())
    loaded: list[JobBankOffer] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        kwargs = {k: v for k, v in item.items() if k in valid_fields}
        if "id" not in kwargs or "source_id" not in kwargs or "url" not in kwargs:
            continue
        loaded.append(JobBankOffer(**kwargs))
    return loaded


def format_filtered_offers_summary(offers: list[JobBankOffer], limit: int = 15) -> str:
    """Formate un résumé lisible des offres filtrées hors ligne pour le terminal."""
    lines = [
        f"\n================================================================================",
        f" RÉSULTATS DU FILTRAGE HORS LIGNE : {len(offers)} offre(s) TI correspondante(s)",
        f"================================================================================",
    ]
    for idx, o in enumerate(offers[: max(1, limit)], start=1):
        title = o.titre_employeur or o.titre or "Sans titre"
        skills_str = ", ".join((o.competences_cles or [])[:6]) or "Aucune détectée"
        sal_str = f" | {o.salaire}" if o.salaire else ""
        stage_str = " | [STAGE]" if o.est_stage else ""
        lines.append(
            f" {idx:2d}. [{o.id} | CNP {o.code_cnp} | {o.domaine_ti}] {title}\n"
            f"     Employeur : {o.entreprise or 'Non spécifié'} — {o.ville or o.lieu or 'Québec'} ({o.region_administrative or 'QC'})"
            f"{sal_str}{stage_str} | Pertinence DEC : {o.score_pertinence_dec}/100\n"
            f"     Technos   : {skills_str}\n"
            f"     Lien      : {o.url}"
        )
    if len(offers) > limit:
        lines.append(f"\n ... et {len(offers) - limit} autre(s) offre(s) (utilisez --html pour tout explorer).")
    return "\n".join(lines)


def format_cv_matching_report(
    profile: CandidateCVProfile,
    matches: list[OfferCVMatchResult],
) -> str:
    """Formate le rapport complet d'appariement CV <-> Offres (Piste 4 + JobTailor_V3)."""
    lines = [
        "\n================================================================================",
        " ASSISTANT DE CANDIDATURE JOBTAILOR (PISTE 4) — PROFIL DÉTECTÉ DANS VOTRE CV",
        "================================================================================",
        f" • Domaine TI principal : {profile.domaine_principal}",
        f" • Niveau / Séniorité   : {profile.niveau_seniorite} | Études : {profile.niveau_etudes}",
        f" • Objectif & Langues   : {'Recherche de stage détectée' if profile.cherche_stage else 'Emploi / Stage'} | Langues : {', '.join(profile.langues) if profile.langues else 'Français'}",
        f" • Compétences TI ({len(profile.competences)}) : {', '.join(profile.competences) if profile.competences else 'Aucune détectée'}",
        "\n================================================================================",
        f" TOP {len(matches)} OFFRES TI LES PLUS COMPATIBLES AVEC VOTRE CV (SCORE ATS / 100)",
        "================================================================================",
    ]
    for rank, m in enumerate(matches, start=1):
        o = m.offer
        title = o.titre_employeur or o.titre or "Sans titre"
        shared_str = ", ".join(m.competences_communes) if m.competences_communes else "Aucune en commun"
        missing_str = ", ".join(m.competences_manquantes[:6]) if m.competences_manquantes else "Aucune compétence manquante (100 % couvert !)"
        lines.append(
            f"\n #{rank} — SCORE ATS : {m.score_ats}/100 | [{o.id}] {title}\n"
            f"    Employeur       : {o.entreprise or 'Non spécifié'} ({o.ville or o.lieu or 'QC'} — {o.region_administrative or 'QC'})\n"
            f"    CNP / Domaine   : CNP {o.code_cnp} ({o.cnp_title}) | {o.domaine_ti} | {o.niveau_seniorite}\n"
            f"    ✓ Maîtrisées    : {shared_str}\n"
            f"    ✗ À travailler  : {missing_str}\n"
            f"    Conseil CV      : {m.suggestions_adaptation_cv[0] if m.suggestions_adaptation_cv else ''}\n"
            f"    Lien            : {o.url}"
        )
    return "\n".join(lines)


def format_cover_letter_audit_report(audit: CoverLetterAuditResult) -> str:
    """Formate le rapport d'audit de lettre de motivation (Méthode Vous / Moi / Nous)."""
    lines = [
        "\n================================================================================",
        f" AUDIT DE LETTRE DE MOTIVATION (JOBTAILOR VOUS/MOI/NOUS) — Offre [{audit.offer_id}]",
        "================================================================================",
        f" • Poste ciblé             : {audit.offer_title} — {audit.employer}",
        f" • Longueur de la lettre   : {audit.word_count} mots (cible : 200 à 380 mots)",
        f" • Mention de l'employeur  : {'OUI ✓' if audit.mentionne_employeur else 'NON ✗ (à ajouter)'}",
        f" • Mention de l'intitulé   : {'OUI ✓' if audit.mentionne_titre else 'NON ✗ (à ajouter)'}",
        f" • Structure Vous/Moi/Nous : {'COMPLÈTE ✓' if audit.structure_vous_moi_nous else 'INCOMPLÈTE ✗'}",
        f" • Technos de l'offre citées ({len(audit.technologies_citees)}) : {', '.join(audit.technologies_citees) or 'Aucune'}",
        f" • Technos non citées ({len(audit.technologies_manquantes)})        : {', '.join(audit.technologies_manquantes) or 'Aucune'}",
    ]
    if audit.zones_a_remplir_oubliees:
        lines.append(f" • ⚠ Zones oubliées        : {', '.join(audit.zones_a_remplir_oubliees)}")
    lines.append("\n CONSEILS D'OPTIMISATION (ZÉRO HALLUCINATION) :")
    for tip in audit.conseils:
        lines.append(f"   -> {tip}")
    return "\n".join(lines)


# ==============================================================================
# 6. Générateur du Portail Web Interactif Autonome (`portail_ti_jobtailor.html`)
# ==============================================================================
def generate_interactive_html_portal(
    offers: list[JobBankOffer],
    output_path: Path,
) -> Path:
    """
    Génère une application Web monopage autonome (`portail_ti_jobtailor.html`)
    ouvrable d'un double-clic dans le navigateur (zéro serveur, zéro dépendance externe,
    rendu sécurisé via `textContent` contre toute injection XSS) permettant :
    - Recherche plein texte et filtrage par Source (5 sites), Code CNP 2021 (14 codes),
      Domaine TI (6 domaines JobTailor), Région administrative (17 régions QC),
      Technologie, Séniorité, Stages uniquement et Salaire.
    - Comparaison interactive avec le CV de l'étudiant (.txt/.md/.docx ou texte collé)
      et classement en direct par Score ATS (/100) avec compétences maîtrisées vs manquantes.
    - Vérificateur interactif de lettre de motivation par offre.
    - Export CSV Excel (`utf-8-sig`) en un clic.
    """
    valid_offers = [o for o in offers if is_recent_and_valid_offer(o)]
    serialized_offers = [asdict(o) for o in valid_offers]
    # Échapper `</` en `<\/` pour empêcher toute balise `</script>` de casser le bloc JSON embarqué
    safe_json = json.dumps(serialized_offers, ensure_ascii=False).replace("</", "<\\/")
    safe_cnp_dict = json.dumps(CNP_2021_TI_DICT, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portail TI Québec & JobTailor — Livrable 3 (Mamadou)</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #1e293b;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --green: #22c55e;
      --orange: #f59e0b;
      --purple: #a855f7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 1.5rem;
    }}
    .header-inner {{
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }}
    h1 {{ margin: 0; font-size: 1.4rem; color: #fff; }}
    .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-top: 0.2rem; }}
    .stats-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
    }}
    .stat-pill {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      padding: 0.35rem 0.75rem;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 600;
    }}
    .container {{
      max-width: 1400px;
      margin: 1.25rem auto;
      padding: 0 1.25rem;
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 1.25rem;
    }}
    @media (max-width: 960px) {{
      .container {{ grid-template-columns: 1fr; }}
    }}
    .sidebar {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.1rem;
      height: fit-content;
    }}
    .sidebar h2 {{
      margin: 0 0 0.8rem 0;
      font-size: 1.05rem;
      color: var(--accent);
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.45rem;
    }}
    .field {{ margin-bottom: 0.75rem; }}
    .field label {{
      display: block;
      font-size: 0.8rem;
      color: var(--muted);
      margin-bottom: 0.25rem;
      font-weight: 600;
    }}
    input[type="text"], input[type="number"], select, textarea {{
      width: 100%;
      background: #0f172a;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.5rem 0.65rem;
      font-size: 0.88rem;
    }}
    textarea {{ resize: vertical; min-height: 95px; font-family: inherit; }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.86rem;
      margin: 0.6rem 0;
      cursor: pointer;
    }}
    .btn {{
      display: inline-block;
      background: var(--accent);
      color: #0f172a;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      padding: 0.55rem 0.9rem;
      font-size: 0.85rem;
      cursor: pointer;
      text-decoration: none;
      text-align: center;
    }}
    .btn:hover {{ background: var(--accent-hover); color: #fff; }}
    .btn-secondary {{
      background: #334155;
      color: var(--text);
    }}
    .btn-row {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-top: 0.6rem;
    }}
    .offer-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.1rem 1.25rem;
      margin-bottom: 0.9rem;
      transition: border-color 0.15s;
    }}
    .offer-card:hover {{ border-color: var(--accent); }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .card-title {{
      margin: 0;
      font-size: 1.1rem;
      color: #fff;
    }}
    .card-company {{
      color: var(--accent);
      font-weight: 600;
      font-size: 0.92rem;
      margin-top: 0.15rem;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin: 0.55rem 0;
    }}
    .badge {{
      font-size: 0.75rem;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      background: #0f172a;
      border: 1px solid var(--border);
      color: var(--muted);
    }}
    .badge-cnp {{ border-color: #38bdf8; color: #38bdf8; }}
    .badge-stage {{ background: rgba(34,197,94,0.15); border-color: var(--green); color: #4ade80; font-weight: 700; }}
    .badge-score {{ background: rgba(168,85,247,0.15); border-color: var(--purple); color: #c084fc; font-weight: 700; }}
    .badge-cv {{ background: rgba(34,197,94,0.2); border-color: var(--green); color: #86efac; font-weight: 700; }}
    .skills-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      margin: 0.55rem 0;
    }}
    .skill-tag {{
      font-size: 0.74rem;
      padding: 0.18rem 0.5rem;
      border-radius: 999px;
      background: rgba(56,189,248,0.12);
      color: #7dd3fc;
      border: 1px solid rgba(56,189,248,0.3);
      cursor: pointer;
    }}
    .skill-match {{
      background: rgba(34,197,94,0.2);
      color: #86efac;
      border-color: var(--green);
    }}
    .skill-gap {{
      background: rgba(245,158,11,0.15);
      color: #fcd34d;
      border-color: var(--orange);
    }}
    .desc-preview {{
      font-size: 0.87rem;
      color: #cbd5e1;
      margin: 0.5rem 0;
    }}
    details {{
      margin-top: 0.55rem;
      font-size: 0.84rem;
      color: var(--muted);
    }}
    details summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 600;
    }}
    .letter-box {{
      margin-top: 0.65rem;
      padding: 0.75rem;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div>
        <h1>Portail TI Québec &amp; JobTailor — 5 Sources Unifiées (Mamadou)</h1>
        <div class="subtitle">Guichet-Emplois · Jobboom · Talent.com (GPS) · Jobillico · Remotive | 14 codes CNP 2021 TI | 17 régions QC</div>
      </div>
      <div class="stats-bar">
        <span class="stat-pill" id="stat-count">0 offres affichées</span>
        <span class="stat-pill" id="stat-sources">5 plateformes TI</span>
        <button class="btn" id="btn-export-csv" type="button">Exporter en CSV (Excel)</button>
      </div>
    </div>
  </header>

  <main class="container">
    <aside class="sidebar">
      <h2>1. Filtres &amp; Recherche TI</h2>
      <div class="field">
        <label for="f-q">Recherche par mots-clés (titre, entreprise, techno, ville)</label>
        <input type="text" id="f-q" placeholder="Ex. Python, FastAPI, Desjardins, Québec...">
      </div>
      <div class="field">
        <label for="f-source">Plateforme source (5 sites)</label>
        <select id="f-source">
          <option value="">Toutes les sources</option>
          <option value="guichet-emplois">Guichet-Emplois Canada</option>
          <option value="jobboom">Jobboom Québec</option>
          <option value="talent-canada">Talent.com Canada (GPS)</option>
          <option value="jobillico">Jobillico Québec</option>
          <option value="remotive">Remotive (Télétravail)</option>
        </select>
      </div>
      <div class="field">
        <label for="f-cnp">Code CNP 2021 TI (14 professions)</label>
        <select id="f-cnp">
          <option value="">Tous les 14 codes CNP TI</option>
        </select>
      </div>
      <div class="field">
        <label for="f-domaine">Sous-domaine TI (JobTailor)</label>
        <select id="f-domaine">
          <option value="">Tous les sous-domaines TI</option>
          <option value="tech_backend">Développement Backend &amp; Logiciel</option>
          <option value="tech_frontend">Développement Frontend &amp; Web</option>
          <option value="tech_support">Support TI, Systèmes &amp; Réseaux</option>
          <option value="devops_cloud">DevOps, SRE &amp; Infonuagique</option>
          <option value="data_ia">Science des données, BI &amp; IA</option>
          <option value="cybersecurite">Cybersécurité</option>
        </select>
      </div>
      <div class="field">
        <label for="f-region">Région administrative (17 régions QC)</label>
        <select id="f-region">
          <option value="">Toutes les régions</option>
        </select>
      </div>
      <div class="field">
        <label for="f-techno">Technologie / Compétence clé</label>
        <select id="f-techno">
          <option value="">Toutes les technologies</option>
        </select>
      </div>
      <div class="field">
        <label for="f-seniorite">Niveau de séniorité</label>
        <select id="f-seniorite">
          <option value="">Tous les niveaux</option>
          <option value="Étudiant / Stage">Étudiant / Stage</option>
          <option value="Junior / DEC">Junior / DEC</option>
          <option value="Intermédiaire">Intermédiaire</option>
          <option value="Senior">Senior</option>
        </select>
      </div>
      <div class="field">
        <label for="f-sort">Trier par</label>
        <select id="f-sort">
          <option value="dec">Score pertinence DEC (0-100)</option>
          <option value="cv">Compatibilité avec mon CV (/100)</option>
          <option value="date">Date de publication (récentes)</option>
          <option value="salary">Salaire chiffré</option>
        </select>
      </div>
      <label class="checkbox-row">
        <input type="checkbox" id="f-stage">
        <span>Afficher uniquement les stages TI</span>
      </label>
      <div class="btn-row">
        <button class="btn btn-secondary" id="btn-reset" type="button">Réinitialiser les filtres</button>
      </div>

      <h2 style="margin-top:1.4rem;">2. Matching CV (Piste 4 JobTailor)</h2>
      <div class="field">
        <label for="cv-input">Collez le texte de votre CV pour calculer votre score ATS (/100) sur chaque offre :</label>
        <textarea id="cv-input" placeholder="Ex. Étudiant au DEC en informatique (Collège O'Sullivan). Compétences : Python, SQL, PostgreSQL, Docker, Git, Linux, FastAPI, React, Soutien TI..."></textarea>
      </div>
      <div class="btn-row">
        <button class="btn" id="btn-apply-cv" type="button">Comparer mon CV</button>
        <button class="btn btn-secondary" id="btn-clear-cv" type="button">Effacer CV</button>
      </div>
      <div id="cv-summary" style="font-size:0.8rem;color:#86efac;margin-top:0.5rem;"></div>
    </aside>

    <section>
      <div id="offers-list"></div>
    </section>
  </main>

  <script id="offers-data" type="application/json">{safe_json}</script>
  <script id="cnp-data" type="application/json">{safe_cnp_dict}</script>
  <script>
    const OFFERS = JSON.parse(document.getElementById('offers-data').textContent);
    const CNP_DICT = JSON.parse(document.getElementById('cnp-data').textContent);
    let activeCvSkills = new Set();

    function norm(s) {{
      return (s || '').toString().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
    }}

    // Initialiser les listes déroulantes dynamiques
    const cnpSel = document.getElementById('f-cnp');
    Object.entries(CNP_DICT).forEach(([code, title]) => {{
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = code + ' — ' + title;
      cnpSel.appendChild(opt);
    }});

    const regions = Array.from(new Set(OFFERS.map(o => o.region_administrative).filter(Boolean))).sort();
    const regSel = document.getElementById('f-region');
    regions.forEach(r => {{
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r;
      regSel.appendChild(opt);
    }});

    const allTechs = new Map();
    OFFERS.forEach(o => (o.competences_cles || []).forEach(t => allTechs.set(t, (allTechs.get(t) || 0) + 1)));
    const techSel = document.getElementById('f-techno');
    Array.from(allTechs.entries()).sort((a, b) => b[1] - a[1]).forEach(([t, count]) => {{
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t + ' (' + count + ')';
      techSel.appendChild(opt);
    }});

    function extractCvSkillsFromText(text) {{
      const n = norm(text);
      const found = new Set();
      for (const tech of allTechs.keys()) {{
        const parts = norm(tech).split(/[\\/(),\\s]+/).filter(w => w.length >= 2);
        if (parts.some(p => n.includes(p))) {{
          found.add(tech);
        }}
      }}
      return found;
    }}

    function computeCvScore(offer) {{
      if (activeCvSkills.size === 0) return null;
      const skills = offer.competences_cles || [];
      if (skills.length === 0) return 40;
      const shared = skills.filter(s => activeCvSkills.has(s));
      const ratio = shared.length / skills.length;
      const vol = Math.min(shared.length, 4) / 4;
      let score = Math.round(70 * (0.6 * ratio + 0.4 * vol) + (offer.score_pertinence_dec * 0.3));
      return Math.max(5, Math.min(100, score));
    }}

    function renderOffers() {{
      const q = norm(document.getElementById('f-q').value);
      const src = document.getElementById('f-source').value;
      const cnp = document.getElementById('f-cnp').value;
      const dom = document.getElementById('f-domaine').value;
      const reg = document.getElementById('f-region').value;
      const tech = document.getElementById('f-techno').value;
      const sen = document.getElementById('f-seniorite').value;
      const sortBy = document.getElementById('f-sort').value;
      const stageOnly = document.getElementById('f-stage').checked;

      const filtered = OFFERS.filter(o => {{
        if (stageOnly && !o.est_stage) return false;
        if (src && o.source !== src) return false;
        if (cnp && o.code_cnp !== cnp) return false;
        if (dom && o.domaine_ti !== dom) return false;
        if (reg && o.region_administrative !== reg) return false;
        if (sen && o.niveau_seniorite !== sen) return false;
        if (tech && !(o.competences_cles || []).includes(tech)) return false;
        if (q) {{
          const hay = norm([o.titre, o.titre_employeur, o.entreprise, o.ville, o.region_administrative, (o.competences_cles || []).join(' '), o.description].join(' '));
          if (!hay.includes(q)) return false;
        }}
        return true;
      }});

      filtered.sort((a, b) => {{
        if (sortBy === 'cv' && activeCvSkills.size > 0) {{
          return (computeCvScore(b) || 0) - (computeCvScore(a) || 0);
        }}
        if (sortBy === 'date') {{
          return (b.date_publication || '').localeCompare(a.date_publication || '');
        }}
        if (sortBy === 'salary') {{
          return (b.salaire_min || 0) - (a.salaire_min || 0);
        }}
        return (b.score_pertinence_dec || 0) - (a.score_pertinence_dec || 0);
      }});

      document.getElementById('stat-count').textContent = filtered.length + ' / ' + OFFERS.length + ' offres TI';
      const listEl = document.getElementById('offers-list');
      listEl.textContent = '';

      filtered.slice(0, 120).forEach(o => {{
        const card = document.createElement('article');
        card.className = 'offer-card';

        const top = document.createElement('div');
        top.className = 'card-top';
        const left = document.createElement('div');
        const h3 = document.createElement('h3');
        h3.className = 'card-title';
        h3.textContent = o.titre_employeur || o.titre || 'Poste TI';
        const comp = document.createElement('div');
        comp.className = 'card-company';
        comp.textContent = (o.entreprise || 'Employeur') + ' — ' + (o.ville || o.lieu || 'Québec') + (o.region_administrative ? ' (' + o.region_administrative + ')' : '');
        left.appendChild(h3);
        left.appendChild(comp);

        const link = document.createElement('a');
        link.className = 'btn';
        link.href = o.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Voir l\\'offre (' + o.source + ')';
        top.appendChild(left);
        top.appendChild(link);
        card.appendChild(top);

        const badges = document.createElement('div');
        badges.className = 'badges';
        const addBadge = (txt, cls) => {{
          if (!txt) return;
          const b = document.createElement('span');
          b.className = 'badge ' + (cls || '');
          b.textContent = txt;
          badges.appendChild(b);
        }};
        if (o.est_stage) addBadge('STAGE TI', 'badge-stage');
        addBadge('CNP ' + (o.code_cnp || '') + ' : ' + (o.cnp_title || ''), 'badge-cnp');
        addBadge('Domaine : ' + (o.domaine_ti || ''), '');
        addBadge('Niveau : ' + (o.niveau_seniorite || ''), '');
        addBadge('Pertinence DEC : ' + o.score_pertinence_dec + '/100', 'badge-score');
        if (o.salaire) addBadge('Salaire : ' + o.salaire, '');
        if (o.modalite) addBadge(o.modalite, '');
        if (o.date_publication) addBadge('Publiée : ' + o.date_publication, '');

        const cvSc = computeCvScore(o);
        if (cvSc !== null) {{
          addBadge('Match CV : ' + cvSc + ' / 100', 'badge-cv');
        }}
        card.appendChild(badges);

        const skillsRow = document.createElement('div');
        skillsRow.className = 'skills-row';
        (o.competences_cles || []).forEach(sk => {{
          const st = document.createElement('span');
          let cls = 'skill-tag';
          if (activeCvSkills.size > 0) {{
            cls += activeCvSkills.has(sk) ? ' skill-match' : ' skill-gap';
          }}
          st.className = cls;
          st.textContent = sk;
          st.onclick = () => {{
            document.getElementById('f-techno').value = sk;
            renderOffers();
          }};
          skillsRow.appendChild(st);
        }});
        card.appendChild(skillsRow);

        const descP = document.createElement('p');
        descP.className = 'desc-preview';
        const dText = o.description || '';
        descP.textContent = dText.length > 260 ? dText.slice(0, 260) + '…' : dText;
        card.appendChild(descP);

        const det = document.createElement('details');
        const sum = document.createElement('summary');
        sum.textContent = 'Plus de détails, missions clés & vérificateur de lettre de motivation';
        det.appendChild(sum);

        const fullD = document.createElement('p');
        fullD.textContent = dText;
        det.appendChild(fullD);

        if (o.missions_cles && o.missions_cles.length > 0) {{
          const ul = document.createElement('ul');
          o.missions_cles.forEach(m => {{
            const li = document.createElement('li');
            li.textContent = m;
            ul.appendChild(li);
          }});
          det.appendChild(ul);
        }}

        const lBox = document.createElement('div');
        lBox.className = 'letter-box';
        const lArea = document.createElement('textarea');
        lArea.placeholder = 'Collez votre brouillon de lettre de motivation pour vérifier son alignement avec cette offre (' + (o.entreprise || '') + ')...';
        const lBtn = document.createElement('button');
        lBtn.className = 'btn';
        lBtn.style.marginTop = '0.4rem';
        lBtn.type = 'button';
        lBtn.textContent = 'Vérifier ma lettre pour cette offre';
        const lRes = document.createElement('ul');
        lBtn.onclick = () => {{
          lRes.textContent = '';
          const txt = lArea.value || '';
          const nTxt = norm(txt);
          const words = txt.trim() ? txt.trim().split(/\\s+/).length : 0;
          const tips = [];
          tips.push('Longueur : ' + words + ' mots (recommandé : 200 à 380 mots).');
          if (o.entreprise && !nTxt.includes(norm(o.entreprise).split(' ')[0])) {{
            tips.push('À corriger : citez explicitement l\\'employeur « ' + o.entreprise + ' ».');
          }} else {{
            tips.push('OK : l\\'employeur est bien mentionné.');
          }}
          const missingSk = (o.competences_cles || []).filter(s => !nTxt.includes(norm(s).split(' ')[0]));
          if (missingSk.length > 0) {{
            tips.push('Compétences de l\\'offre non citées dans la lettre : ' + missingSk.join(', '));
          }} else {{
            tips.push('Excellent : toutes les compétences clés de l\\'offre sont citées.');
          }}
          tips.forEach(t => {{
            const li = document.createElement('li');
            li.textContent = t;
            lRes.appendChild(li);
          }});
        }};
        lBox.appendChild(lArea);
        lBox.appendChild(lBtn);
        lBox.appendChild(lRes);
        det.appendChild(lBox);

        card.appendChild(det);
        listEl.appendChild(card);
      }});
    }}

    ['f-q', 'f-source', 'f-cnp', 'f-domaine', 'f-region', 'f-techno', 'f-seniorite', 'f-sort', 'f-stage'].forEach(id => {{
      document.getElementById(id).addEventListener('input', renderOffers);
      document.getElementById(id).addEventListener('change', renderOffers);
    }});

    document.getElementById('btn-reset').onclick = () => {{
      ['f-q', 'f-source', 'f-cnp', 'f-domaine', 'f-region', 'f-techno', 'f-seniorite'].forEach(id => document.getElementById(id).value = '');
      document.getElementById('f-sort').value = 'dec';
      document.getElementById('f-stage').checked = false;
      renderOffers();
    }};

    document.getElementById('btn-apply-cv').onclick = () => {{
      const txt = document.getElementById('cv-input').value || '';
      activeCvSkills = extractCvSkillsFromText(txt);
      document.getElementById('f-sort').value = 'cv';
      document.getElementById('cv-summary').textContent = 'Compétences détectées dans votre CV (' + activeCvSkills.size + ') : ' + Array.from(activeCvSkills).join(', ');
      renderOffers();
    }};

    document.getElementById('btn-clear-cv').onclick = () => {{
      document.getElementById('cv-input').value = '';
      activeCvSkills = new Set();
      document.getElementById('cv-summary').textContent = '';
      document.getElementById('f-sort').value = 'dec';
      renderOffers();
    }};

    document.getElementById('btn-export-csv').onclick = () => {{
      const headers = ['id','source','code_cnp','domaine_ti','titre','entreprise','ville','region_administrative','niveau_seniorite','salaire','score_pertinence_dec','competences_cles','url'];
      const rows = [headers.join(';')];
      OFFERS.forEach(o => {{
        const vals = headers.map(h => {{
          let v = o[h];
          if (Array.isArray(v)) v = v.join(', ');
          v = (v === null || v === undefined) ? '' : String(v).replace(/"/g, '""');
          return '"' + v + '"';
        }});
        rows.push(vals.join(';'));
      }});
      const blob = new Blob(['\\uFEFF' + rows.join('\\r\\n')], {{ type: 'text/csv;charset=utf-8;' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'offres_ti_selection.csv';
      a.click();
    }};

    renderOffers();
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path
