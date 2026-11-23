"""Modèles de données pour le Livrable 3 — Amélioration du POC Adzuna Canada.

Inspiré de :
- `equipe/dan/livrable3/modele.py` (@dataclass `Offre`, champ `doublons`, exports JSON/CSV) ;
- `equipe/kandet/03-amelioration-preuve-de-concept/modele.py` (`SourceRecord`, `search_terms`) ;
- `equipe/kandet/format-commun/convertir.py` et `equipe/ferdinand/format-commun/convertir.py`
  (conversion vers les 18 champs du format commun `JobOffer` de la classe sans inventer de valeurs).

Règle fondamentale :
Chaque offre distingue explicitement :
1. Les valeurs structurées brutes fournies par l'API Adzuna (`api_*`).
2. Les valeurs extraites de façon déterministe depuis l'extrait de description (`texte_*`).
3. Les valeurs consolidées, leur provenance (`provenance_*`) et les anomalies/divergences (`anomalies`).
Aucune valeur structurée de l'API n'est écrasée silencieusement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


NON_SPECIFIE = "Non spécifié"

# Les 18 champs du format commun de la classe (modèle JobOffer de Grégory / Kandet / Ferdinand).
CHAMPS_FORMAT_COMMUN = [
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
    "description",
    "competences_cles",
    "salaire",
    "date_extraction",
]


@dataclass
class ExtractionSalaireTexte:
    """Résultat de l'extraction salariale sur le titre et l'extrait de description."""

    salaire_min: float | None = None
    salaire_max: float | None = None
    devise: str | None = None
    periode: str | None = None  # "heure", "semaine", "mois", "année" ou None si non écrite
    type_mention: str | None = None  # "fourchette", "plafond", "montant_unique", "grille_multi_niveaux"
    paliers_detectes: list[float] = field(default_factory=list)
    segment_extrait: str | None = None


@dataclass
class ExtractionConditionsTexte:
    """Résultat de l'extraction du contrat, de l'horaire et de la modalité depuis le texte."""

    # 1. Type de contrat (distinct du temps de travail et de la modalité)
    type_contrat: str | None = None  # "Permanent", "Contrat", "Stage", "Remplacement", "Pigiste / Consultant", "Permanent ou Contrat"
    duree_contrat: str | None = None  # ex. "12 mois", "6-12 mois", "3 mois", "2 ans"
    segment_contrat: str | None = None

    # 2. Temps de travail / Horaire
    horaire: str | None = None  # "Temps plein", "Temps partiel" ou None
    heures_valeur: float | None = None  # ex. 35.0, 40.0, 80.0
    heures_unite: str | None = None  # "semaine", "période de paie" (jamais converti sans connaître la durée de la période)
    details_horaire: str | None = None  # ex. "2 à 3 jours par semaine", "Quart de travail: Jour"
    segment_horaire: str | None = None

    # 3. Modalité de travail
    modalite: str | None = None  # "Présentiel", "Hybride", "Télétravail" ou None
    details_modalite: str | None = None  # ex. "3 days in the office / 2 days remote", "2 jours/semaine au bureau"
    segment_modalite: str | None = None


@dataclass
class OffreAdzuna:
    """Représentation complète et traçable d'une offre Adzuna Canada."""

    # --- Identifiants et métadonnées de base ---
    id: str  # Identifiant préfixé, ex. "adz-5965086256"
    id_adzuna: str  # Identifiant brut Adzuna, ex. "5965086256"
    source: str = "adzuna"
    titre: str = ""
    entreprise: str = NON_SPECIFIE
    url: str = ""
    date_publication: str | None = None  # ISO AAAA-MM-JJ
    date_creation_brute: str | None = None  # Horodatage complet Adzuna
    categorie_tag: str | None = None
    categorie_label: str | None = None
    description: str = ""
    attribution: str = "Jobs by Adzuna"
    date_extraction: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # --- Localisation enrichie (Axe 3 : location.area + GPS + régions du Québec) ---
    lieu_brut: str = NON_SPECIFIE
    area_brute: list[str] = field(default_factory=list)
    ville: str | None = None
    arrondissement_ou_mrc: str | None = None
    region_administrative: str | None = None
    province: str | None = None
    pays: str = "Canada"
    precision_lieu: str = "inconnue"  # "ville", "region", "province", "inconnue"
    latitude: float | None = None
    longitude: float | None = None

    # --- 1. Valeurs structurées brutes de l'API Adzuna (jamais écrasées) ---
    api_salary_min: float | None = None
    api_salary_max: float | None = None
    api_salary_is_predicted: str | None = None
    api_contract_type: str | None = None  # "permanent", "contract" ou None
    api_contract_time: str | None = None  # "full_time", "part_time" ou None

    # --- 2. Valeurs extraites de la description et du titre ---
    texte_salaire_min: float | None = None
    texte_salaire_max: float | None = None
    texte_devise: str | None = None
    texte_periode_salaire: str | None = None
    texte_type_mention_salaire: str | None = None
    texte_paliers_salariaux: list[float] = field(default_factory=list)
    texte_segment_salaire: str | None = None

    texte_type_contrat: str | None = None
    texte_duree_contrat: str | None = None
    texte_segment_contrat: str | None = None

    texte_horaire: str | None = None
    texte_heures_valeur: float | None = None
    texte_heures_unite: str | None = None
    texte_details_horaire: str | None = None
    texte_segment_horaire: str | None = None

    texte_modalite: str | None = None
    texte_details_modalite: str | None = None
    texte_segment_modalite: str | None = None

    # --- 3. Valeurs consolidées et traçabilité de la provenance ---
    salaire_min: float | None = None
    salaire_max: float | None = None
    devise: str | None = None
    periode_salaire: str | None = None
    salaire_resume: str | None = None
    provenance_salaire: str = "aucune"

    type_contrat: str | None = None
    duree_contrat: str | None = None
    provenance_contrat: str = "aucune"

    horaire_travail: str | None = None
    provenance_horaire: str = "aucune"

    modalite: str | None = None
    provenance_modalite: str = "aucune"

    # --- Enrichissement métier TI (Axe 2) ---
    est_pertinent_ti: bool = True
    raison_filtrage_ti: str = ""
    est_stage: bool = False
    statut_stage: str = "not_indicated"  # "confirmed_stage", "possible_stage", "not_indicated"
    competences_cles: list[str] = field(default_factory=list)

    # --- Traçabilité des recherches, déduplication et anomalies ---
    mots_cles_recherche: list[str] = field(default_factory=list)
    villes_recherche: list[str] = field(default_factory=list)
    doublons_ids: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Retourne un dictionnaire JSON-sérialisable complet."""
        return asdict(self)

    def to_format_commun(self) -> dict[str, Any]:
        """Convertit l'offre vers les 18 champs du format commun de la classe.

        Respecte la règle de Kandet et Ferdinand : aucune valeur absente n'est devinée
        (pas de `"Temps plein"` ni de `"QC"` par défaut si l'information n'est pas établie).
        """
        # Construction du champ type_poste du format commun
        if self.est_stage or self.type_contrat == "Stage":
            type_poste_commun = "Stage"
        elif self.type_contrat and self.horaire_travail:
            type_poste_commun = f"{self.type_contrat} ({self.horaire_travail})"
        elif self.horaire_travail:
            type_poste_commun = self.horaire_travail
        elif self.type_contrat:
            type_poste_commun = self.type_contrat
        else:
            type_poste_commun = None

        # Construction du lieu normalisé lisible
        if self.ville and self.province:
            lieu_commun = f"{self.ville} ({self.province})"
        elif self.region_administrative and self.province:
            lieu_commun = f"{self.region_administrative} ({self.province})"
        elif self.lieu_brut:
            lieu_commun = self.lieu_brut
        else:
            lieu_commun = NON_SPECIFIE

        # Alignement du libellé de modalité sur le format commun ("Sur place", "Hybride", "Télétravail")
        if self.modalite == "Présentiel":
            modalite_commune: str | None = "Sur place"
        else:
            modalite_commune = self.modalite

        return {
            "id": self.id,
            "titre": self.titre or NON_SPECIFIE,
            "entreprise": self.entreprise or NON_SPECIFIE,
            "lieu": lieu_commun,
            "province": self.province or NON_SPECIFIE,
            "pays": self.pays or NON_SPECIFIE,
            "url": self.url,
            "source": self.source,
            "source_partenaire": None,
            "date_publication": self.date_publication,
            "type_poste": type_poste_commun,
            "modalite": modalite_commune,
            "est_stage": self.est_stage,
            "statut_stage": self.statut_stage,
            "description": self.description or None,
            "competences_cles": list(self.competences_cles),
            "salaire": self.salaire_resume,
            "date_extraction": self.date_extraction,
        }
