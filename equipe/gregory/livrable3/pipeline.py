"""
pipeline.py - Pipeline d'unification multi-sources et moteur de déduplication.

Ce module constitue le cœur du Lot 5 de la démonstration du Livrable 3.
Il assure :
1. La déduplication intra-source (par identifiant unique normalisé et URL propre).
2. La déduplication inter-sources (par empreinte normalisée : titre + employeur + lieu).
3. La fusion intelligente préservant la richesse maximale :
   - Sélection de la description la plus complète et la plus longue.
   - Cumul sans doublon des compétences techniques clés.
   - Conservation des partenaires d'origine (ex. Jobillico sur Guichet-Emplois).
   - Priorisation stricte du signal de stage (confirmed_stage > possible_stage > not_indicated).
   - Rétention des modalités de travail, salaires et métadonnées complémentaires.
4. L'export final consolidé sous formats JSON (complet indenté) et CSV (compatibilité Excel Windows).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit, urlunsplit
from typing import Dict, List, Optional, Set, Tuple

try:
    from models import JobOffer
except ImportError:
    from .models import JobOffer


logger = logging.getLogger("PipelineUnification")

# --- Constantes et Priorités ------------------------------------------------

# Hiérarchie stricte des statuts de stage (du signal le plus fort au plus faible)
STAGE_PRIORITY = {
    "confirmed_stage": 2,
    "possible_stage": 1,
    "not_indicated": 0,
}

# Expressions régulières pour le nettoyage des entités corporatives
LEGAL_SUFFIXES_REGEX = re.compile(
    r"\b(inc|ltee|ltée|ltd|corp|corporation|llc|gmbh|co|cie|solutions|technologies|groupe|group)\b",
    re.IGNORECASE,
)

# Termes génériques ou inconnus à ne jamais utiliser pour matcher des employeurs
GENERIC_EMPLOYERS = {
    "",
    "non specifie",
    "non precise",
    "inconnu",
    "unknown",
    "n a",
    "na",
    "confidentiel",
    "confidential",
    "anonymous",
    "employeur",
    "recruteur",
}

# Villes et régions clés au Québec pour normalisation géographique
QUEBEC_LOCATIONS = {
    "montreal": "Montréal",
    "quebec": "Québec",
    "levis": "Lévis",
    "laval": "Laval",
    "gatineau": "Gatineau",
    "sherbrooke": "Sherbrooke",
    "trois rivieres": "Trois-Rivières",
    "saguenay": "Saguenay",
    "longueuil": "Longueuil",
    "terrebonne": "Terrebonne",
    "brossard": "Brossard",
    "saint jean sur richelieu": "Saint-Jean-sur-Richelieu",
    "rimouski": "Rimouski",
    "drummondville": "Drummondville",
    "saint jerome": "Saint-Jérôme",
    "granby": "Granby",
    "victoriaville": "Victoriaville",
    "shawinigan": "Shawinigan",
    "saint hyacinthe": "Saint-Hyacinthe",
    "joliette": "Joliette",
}


# --- Normaliseurs et Empreintes ----------------------------------------------

def clean_url(url: Optional[str]) -> str:
    """
    Nettoie une URL en supprimant les paramètres de requête de tracking,
    les ancres et les barres obliques finales.
    """
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        # Reconstruit l'URL sans query string ni fragment
        cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        return cleaned.lower()
    except Exception:
        return url.strip().split("?")[0].rstrip("/").lower()


def normalize_text(text: Optional[str]) -> str:
    """
    Supprime les accents, met en minuscules, remplace la ponctuation par des
    espaces et condense les espaces consécutifs.
    """
    if not text:
        return ""
    # Décomposition Unicode (suppression des diacritiques)
    normalized = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    # Remplacement des caractères non alphanumériques par des espaces
    cleaned = re.sub(r"[^\w\s]", " ", without_accents.lower())
    # Condensation des espaces
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_employer(employer: Optional[str]) -> str:
    """
    Normalise le nom d'un employeur en retirant les formes juridiques courantes
    (Inc, Ltée, Ltd, etc.) pour permettre le rapprochement inter-sources.
    """
    norm = normalize_text(employer)
    if not norm:
        return ""
    # Suppression des suffixes corporatifs
    norm = LEGAL_SUFFIXES_REGEX.sub(" ", norm)
    # Suppression des mentions géographiques en fin de nom (ex: "CGI Canada" -> "CGI")
    norm = re.sub(r"\b(canada|quebec|qc)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def normalize_title(title: Optional[str]) -> str:
    """
    Normalise l'intitulé d'un poste en lissant les variantes de genre
    (développeur/développeuse), les permutations fréquentes (programmeur-analyste)
    et les indications de contrat ou de langue.
    """
    norm = normalize_text(title)
    if not norm:
        return ""
    # Harmonisation des variantes fréquentes de genre et de permutations
    norm = re.sub(r"\b(developpeur\s+developpeuse|developpeuse\s+developpeur)\b", "developpeur", norm)
    norm = re.sub(r"\b(programmeur\s+programmeuse|programmeuse\s+programmeur)\b", "programmeur", norm)
    norm = re.sub(
        r"\b(analyste\s+programmeur|analyste\s+programmeuse|programmeur\s+analyste|programmeuse\s+analyste)\b",
        "analyste programmeur",
        norm,
    )
    norm = re.sub(
        r"\b(analyste\s+fonctionnel\s+analyste\s+fonctionnelle|analyste\s+fonctionnelle\s+analyste\s+fonctionnel)\b",
        "analyste fonctionnel",
        norm,
    )
    norm = re.sub(
        r"\b(administrateur\s+administratrice|administratrice\s+administrateur)\b",
        "administrateur",
        norm,
    )
    norm = re.sub(r"\b(ingenieur\s+ingenieure|ingenieure\s+ingenieur)\b", "ingenieur", norm)
    norm = re.sub(r"\b(technicien\s+technicienne|technicienne\s+technicien)\b", "technicien", norm)
    norm = re.sub(r"\b(stagiaire\s+stagiaire)\b", "stagiaire", norm)
    # Suppression des mentions entre parenthèses courantes
    norm = re.sub(r"\b(h\s*f|f\s*h|h\s*f\s*x|m\s*f|m\s*w\s*d)\b", " ", norm)
    norm = re.sub(r"\b(permanent|temporaire|temps\s+plein|temps\s+partiel|full\s+time|part\s+time)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def normalize_location(location: Optional[str]) -> str:
    """
    Normalise la localisation d'une offre pour faciliter le regroupement géographique.
    Traite d'abord les villes spécifiques pour éviter que la mention de la province 'Québec'
    ne masque la ville réelle (ex: 'Lévis, Québec' -> 'levis').
    """
    norm = normalize_text(location)
    if not norm:
        return ""
    # Détection de télétravail pur / remote
    if any(k in norm for k in ("teletravail", "remote", "virtuel", "anywhere", "partout")):
        return "teletravail"

    # Vérification des villes spécifiques en priorité (sauf 'quebec' qui est aussi la province)
    for key in QUEBEC_LOCATIONS:
        if key != "quebec" and key in norm:
            return key

    # Si aucune autre ville n'a matché et que 'quebec' est présent
    if "quebec" in norm:
        return "quebec"

    # Suppression de la province si mentionnée isolément
    norm = re.sub(r"\b(qc|canada)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def is_valid_identity(title: str, employer: str, location: str) -> bool:
    """
    Vérifie qu'une empreinte d'offre est suffisamment précise pour autoriser
    une fusion inter-sources sans risque de faux positifs.
    """
    if len(title) < 3:
        return False
    if not employer or employer in GENERIC_EMPLOYERS or len(employer) < 2:
        return False
    if not location:
        return False
    return True


def compute_identity(offer: JobOffer) -> Tuple[str, str, str]:
    """Calcule le triplet d'empreinte normalisée (titre, employeur, lieu)."""
    return (
        normalize_title(offer.titre),
        normalize_employer(offer.entreprise),
        normalize_location(offer.lieu),
    )


def get_publisher_key(offer: JobOffer) -> Tuple[str, str]:
    """
    Identifie l'émetteur d'origine de l'annonce :
    combine la source de collecte et le partenaire d'origine si présent.
    """
    source_clean = normalize_text(offer.source)
    partner_clean = normalize_text(offer.source_partenaire) if offer.source_partenaire else ""
    return (source_clean, partner_clean)


# --- Règles de Détection des Doublons ----------------------------------------

def is_intra_source_duplicate(a: JobOffer, b: JobOffer) -> bool:
    """
    Détermine si deux annonces correspondent au même enregistrement sur la même source.
    Critères :
    - Même source technique.
    - Même identifiant unique non vide OU même URL propre non vide.
    """
    if a.source.strip().lower() != b.source.strip().lower():
        return False

    # Comparaison des identifiants
    id_a = a.id.strip().lower()
    id_b = b.id.strip().lower()
    if id_a and id_b and id_a == id_b:
        return True

    # Comparaison des URLs nettoyées
    url_a = clean_url(a.url)
    url_b = clean_url(b.url)
    if url_a and url_b and url_a == url_b:
        return True

    return False


def is_cross_source_match(a: JobOffer, b: JobOffer) -> bool:
    """
    Détermine si deux annonces provenant de diffuseurs distincts
    décrivent le même poste (rediffusion multi-plateformes).
    Critères :
    - Émetteurs d'origine distincts (pour ne pas fusionner deux postes
      distincts mais similaires d'un même employeur sur le même site).
    - Empreinte normalisée identique et valide.
    """
    pub_a = get_publisher_key(a)
    pub_b = get_publisher_key(b)

    # Si c'est exactement le même diffuseur sans identifiant identique,
    # on ne fusionne pas (l'employeur peut avoir deux postes ouverts).
    if pub_a == pub_b:
        return False

    ident_a = compute_identity(a)
    ident_b = compute_identity(b)

    if not is_valid_identity(*ident_a) or not is_valid_identity(*ident_b):
        return False

    # 1. Correspondance exacte du triplet normalisé (titre, employeur, lieu)
    if ident_a == ident_b:
        return True

    # 2. Correspondance du titre et de l'employeur avec compatibilité de lieu
    # (ex: 'Montréal' et 'Télétravail' ou sous-chaîne géographique)
    if ident_a[0] == ident_b[0] and ident_a[1] == ident_b[1]:
        loc_a, loc_b = ident_a[2], ident_b[2]
        if loc_a == loc_b or loc_a in loc_b or loc_b in loc_a:
            return True
        if loc_a == "teletravail" or loc_b == "teletravail":
            return True

    return False


# --- Moteur de Fusion Intelligente -------------------------------------------

def merge_job_offers(base: JobOffer, other: JobOffer) -> JobOffer:
    """
    Fusionne deux offres représentant le même poste en maximisant la richesse
    informationnelle selon les directives de AGENTS.md :
    - Description la plus longue et détaillée.
    - Cumul des compétences clés uniques normalisées.
    - Conservation de la provenance partenaire (ex. Jobillico).
    - Priorisation du signal de stage le plus fort.
    - Préservation des informations de salaire, modalité et date.
    """
    # 1. Arbitrage sur le statut de stage
    base_rank = STAGE_PRIORITY.get(base.statut_stage, 0)
    other_rank = STAGE_PRIORITY.get(other.statut_stage, 0)
    if other_rank > base_rank:
        merged_statut_stage = other.statut_stage
    else:
        merged_statut_stage = base.statut_stage

    merged_est_stage = (
        (merged_statut_stage == "confirmed_stage")
        or base.est_stage
        or other.est_stage
    )

    # 2. Description la plus longue et informative
    desc_base = base.description or ""
    desc_other = other.description or ""
    merged_description = desc_base if len(desc_base) >= len(desc_other) else desc_other
    if not merged_description.strip():
        merged_description = None

    # 3. Cumul des compétences techniques sans doublon
    skills_map: Dict[str, str] = {}
    for skill in (base.competences_cles or []) + (other.competences_cles or []):
        if not skill:
            continue
        cleaned = skill.strip()
        canon_key = cleaned.lower()
        if canon_key not in skills_map:
            skills_map[canon_key] = cleaned
    merged_competences = sorted(list(skills_map.values()), key=lambda s: s.lower())

    # 4. Conservation du partenaire d'origine
    merged_partenaire = base.source_partenaire
    if not merged_partenaire and other.source_partenaire:
        merged_partenaire = other.source_partenaire
    elif merged_partenaire and other.source_partenaire and merged_partenaire != other.source_partenaire:
        # Si deux partenaires différents sont mentionnés, on conserve le principal
        merged_partenaire = base.source_partenaire

    # 5. Salaire : privilégier une mention explicite
    merged_salaire = base.salaire
    if (not merged_salaire or merged_salaire in ("Non spécifié", "")) and other.salaire:
        merged_salaire = other.salaire

    # 6. Modalité de travail
    merged_modalite = base.modalite
    if (not merged_modalite or merged_modalite in ("Non spécifié", "")) and other.modalite:
        merged_modalite = other.modalite

    # 7. Type de poste
    merged_type_poste = base.type_poste
    if merged_est_stage and merged_type_poste != "Stage":
        # Si le stage est confirmé, on enrichit le type de poste
        if not merged_type_poste or merged_type_poste == "Non spécifié":
            merged_type_poste = "Stage"
        elif "stage" not in merged_type_poste.lower():
            merged_type_poste = f"{merged_type_poste} / Stage"
    elif (not merged_type_poste or merged_type_poste == "Non spécifié") and other.type_poste:
        merged_type_poste = other.type_poste

    # 8. Date de publication (conserver la plus ancienne / première parution)
    merged_date_pub = base.date_publication
    if not merged_date_pub and other.date_publication:
        merged_date_pub = other.date_publication
    elif merged_date_pub and other.date_publication:
        # Prendre la date la plus ancienne (premier signalement de l'offre)
        merged_date_pub = min(merged_date_pub, other.date_publication)

    # 9. Localisation la plus précise
    lieu_base = base.lieu or ""
    lieu_other = other.lieu or ""
    merged_lieu = base.lieu
    if lieu_base in ("Non spécifié", "", "Canada", "QC") and lieu_other not in ("Non spécifié", "", "Canada", "QC"):
        merged_lieu = other.lieu
    elif len(lieu_other) > len(lieu_base) and "non specifie" not in normalize_text(lieu_other):
        merged_lieu = other.lieu

    # 10. Entreprise
    merged_entreprise = base.entreprise
    if merged_entreprise in ("Non spécifié", "") and other.entreprise not in ("Non spécifié", ""):
        merged_entreprise = other.entreprise

    return JobOffer(
        id=base.id,
        titre=base.titre,
        entreprise=merged_entreprise,
        lieu=merged_lieu,
        province=base.province or other.province or "QC",
        pays=base.pays or other.pays or "Canada",
        url=base.url,
        source=base.source,
        source_partenaire=merged_partenaire,
        date_publication=merged_date_pub,
        type_poste=merged_type_poste,
        modalite=merged_modalite,
        est_stage=merged_est_stage,
        statut_stage=merged_statut_stage,
        description=merged_description,
        competences_cles=merged_competences,
        salaire=merged_salaire,
        date_extraction=base.date_extraction,
    )


# --- Rapport Statistique du Pipeline -----------------------------------------

@dataclass
class PipelineStats:
    """Statistiques consolidées de l'exécution du pipeline d'unification."""
    total_input: int = 0
    intra_duplicates_merged: int = 0
    cross_duplicates_merged: int = 0
    total_unified: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_stage_status: Dict[str, int] = field(default_factory=dict)
    by_work_mode: Dict[str, int] = field(default_factory=dict)
    top_skills: List[Tuple[str, int]] = field(default_factory=list)

    def format_summary(self) -> str:
        """Génère un rapport texte synthétique et structuré."""
        lines = [
            "==================================================================",
            "        RAPPORT DU PIPELINE D'UNIFICATION & DÉDUPLICATION         ",
            "==================================================================",
            f" Total d'annonces en entrée       : {self.total_input}",
            f" Doublons intra-source fusionnés  : {self.intra_duplicates_merged}",
            f" Doublons inter-sources fusionnés : {self.cross_duplicates_merged}",
            f" Offres uniques consolidées       : {self.total_unified}",
            "------------------------------------------------------------------",
            " Répartition par source principale :",
        ]
        for src, count in sorted(self.by_source.items(), key=lambda x: x[1], reverse=True):
            pct = (count / self.total_unified * 100) if self.total_unified else 0
            lines.append(f"   - {src:<18} : {count:>4} ({pct:>5.1f} %)")

        lines.append("------------------------------------------------------------------")
        lines.append(" Répartition des détections de stages :")
        for st, count in sorted(self.by_stage_status.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"   - {st:<18} : {count:>4}")

        lines.append("------------------------------------------------------------------")
        lines.append(" Top 10 des technologies détectées :")
        for skill, count in self.top_skills[:10]:
            lines.append(f"   - {skill:<18} : {count:>4} mentions")
        lines.append("==================================================================")
        return "\n".join(lines)


# --- Moteur Principal d'Unification ------------------------------------------

def unify_offers(offers: List[JobOffer]) -> Tuple[List[JobOffer], PipelineStats]:
    """
    Exécute l'unification et la déduplication complète d'une liste d'offres :
    1. Déduplication intra-source.
    2. Déduplication inter-sources avec fusion d'informations.
    3. Production des statistiques de pipeline.
    """
    stats = PipelineStats(total_input=len(offers))
    unified: List[JobOffer] = []

    for offer in offers:
        # A. Vérification des doublons intra-source
        intra_idx = -1
        for idx, existing in enumerate(unified):
            if is_intra_source_duplicate(existing, offer):
                intra_idx = idx
                break

        if intra_idx >= 0:
            unified[intra_idx] = merge_job_offers(unified[intra_idx], offer)
            stats.intra_duplicates_merged += 1
            continue

        # B. Vérification des doublons inter-sources
        cross_idx = -1
        for idx, existing in enumerate(unified):
            if is_cross_source_match(existing, offer):
                cross_idx = idx
                break

        if cross_idx >= 0:
            unified[cross_idx] = merge_job_offers(unified[cross_idx], offer)
            stats.cross_duplicates_merged += 1
            continue

        # C. Offre unique, ajout au catalogue consolidé
        unified.append(offer)

    # Calcul des statistiques finales
    stats.total_unified = len(unified)

    # Répartition par source
    for off in unified:
        stats.by_source[off.source] = stats.by_source.get(off.source, 0) + 1
        stats.by_stage_status[off.statut_stage] = stats.by_stage_status.get(off.statut_stage, 0) + 1
        if off.modalite:
            stats.by_work_mode[off.modalite] = stats.by_work_mode.get(off.modalite, 0) + 1

    # Comptage des compétences
    skill_counts: Dict[str, int] = {}
    for off in unified:
        for skill in off.competences_cles:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    stats.top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)

    return unified, stats


# --- Fonctions d'Export et de Chargement --------------------------------------

def export_to_json(offers: List[JobOffer], output_path: Path | str, indent: int = 2) -> Path:
    """
    Exporte la collection d'offres dans un fichier JSON structuré et indenté,
    avec encodage UTF-8 conforme à AGENTS.md.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [offer.model_dump() for offer in offers]
    content = json.dumps(serialized, ensure_ascii=False, indent=indent) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def export_to_csv(
    offers: List[JobOffer],
    output_path: Path | str,
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
) -> Path:
    """
    Exporte la collection d'offres dans un fichier CSV encodé en utf-8-sig avec séparateur ';'
    pour une compatibilité irréprochable avec Microsoft Excel sous Windows.
    Nettoie les sauts de ligne dans les descriptions pour préserver une lecture tabulaire propre.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "titre",
        "entreprise",
        "lieu",
        "province",
        "pays",
        "url",
        "source",
        "source_partenaire",
        "date_publication",
        "type_poste",
        "modalite",
        "est_stage",
        "statut_stage",
        "competences_cles",
        "salaire",
        "date_extraction",
        "description",
    ]

    with open(path, mode="w", newline="", encoding=encoding) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            delimiter=delimiter,
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()

        for offer in offers:
            desc_clean = re.sub(r"[\r\n]+", " ", offer.description or "").strip()
            skills_str = ", ".join(offer.competences_cles) if offer.competences_cles else ""

            row = {
                "id": offer.id,
                "titre": offer.titre,
                "entreprise": offer.entreprise or "Non spécifié",
                "lieu": offer.lieu or "Non spécifié",
                "province": offer.province or "QC",
                "pays": offer.pays or "Canada",
                "url": offer.url,
                "source": offer.source,
                "source_partenaire": offer.source_partenaire or "",
                "date_publication": offer.date_publication or "",
                "type_poste": offer.type_poste or "",
                "modalite": offer.modalite or "",
                "est_stage": "True" if offer.est_stage else "False",
                "statut_stage": offer.statut_stage,
                "competences_cles": skills_str,
                "salaire": offer.salaire or "",
                "date_extraction": offer.date_extraction,
                "description": desc_clean,
            }
            writer.writerow(row)

    return path


def load_offers_from_json(json_path: Path | str) -> List[JobOffer]:
    """Charge une liste d'offres JobOffer depuis un fichier JSON."""
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fichier de données introuvable : {path}")

    raw_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError(f"Le fichier JSON {path} doit contenir une liste d'offres.")

    return [JobOffer(**item) for item in raw_data]


def load_all_datasets(data_dir: Path | str) -> List[JobOffer]:
    """
    Charge et agrège les trois jeux d'essai sources
    (Guichet-Emplois, Jobboom, Remotive) situés dans le dossier data.
    """
    directory = Path(data_dir)
    target_files = [
        directory / "offres_guichet_emplois.json",
        directory / "offres_jobboom.json",
        directory / "offres_remotive.json",
    ]

    all_offers: List[JobOffer] = []
    for f in target_files:
        if f.is_file():
            loaded = load_offers_from_json(f)
            logger.info("Chargé %d offres depuis %s", len(loaded), f.name)
            all_offers.extend(loaded)
        else:
            logger.warning("Fichier source absent : %s", f)

    return all_offers
