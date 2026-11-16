"""
models.py - Modèle de données unifié pour le projet jobs-insights (Livrable 3).
Définit le schéma pivot Pydantic JobOffer partagé par l'ensemble des collecteurs
(Guichet-Emplois, Jobboom, Remotive) et le pipeline d'unification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobOffer(BaseModel):
    """
    Modèle de données unifié représentant une offre d'emploi ou de stage.
    Conforme aux spécifications de la section 4 du plan directeur Livrable 3
    et aux règles d'intégrité de AGENTS.md (zéro invention de données absentes).
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(..., description="Identifiant unique normalisé (ex: 'ge-50701948', 'jb-12345', 'rem-987')")
    titre: str = Field(..., description="Intitulé du poste")
    entreprise: str = Field(default="Non spécifié", description="Nom de l'employeur / entreprise")
    lieu: str = Field(default="Non spécifié", description="Ville ou région (ex: 'Québec, QC', 'Montréal, QC')")
    province: str = Field(default="QC", description="Code normalisé de province (ex: 'QC', 'ON', 'BC')")
    pays: str = Field(default="Canada", description="Pays de l'offre")
    url: str = Field(..., description="Lien direct propre vers l'offre (sans identifiant de session)")
    source: str = Field(default="guichet-emplois", description="Portail d'origine ('guichet-emplois', 'jobboom', 'remotive')")
    source_partenaire: Optional[str] = Field(default=None, description="Partenaire d'origine si agrégé (ex: 'Jobillico', 'Québec emploi')")
    date_publication: Optional[str] = Field(default=None, description="Date de publication au format ISO AAAA-MM-JJ")
    type_poste: Optional[str] = Field(default="Temps plein", description="Type de contrat : 'Temps plein', 'Temps partiel', 'Stage', etc.")
    modalite: Optional[str] = Field(default=None, description="Modalité de travail : 'Sur place', 'Hybride', 'Télétravail'")
    est_stage: bool = Field(default=False, description="True si l'offre correspond à un stage ou emploi étudiant, False sinon")
    statut_stage: str = Field(default="not_indicated", description="Classification du stage : 'confirmed_stage', 'possible_stage', 'not_indicated'")
    description: Optional[str] = Field(default=None, description="Texte descriptif complet nettoyé de tout balisage HTML")
    competences_cles: List[str] = Field(default_factory=list, description="Liste ordonnée de compétences / technologies clés détectées")
    salaire: Optional[str] = Field(default=None, description="Rémunération textuelle brute si mentionnée, None sinon")
    date_extraction: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Horodatage ISO de l'extraction"
    )

    @property
    def url_source(self) -> str:
        """Alias de rétrocompatibilité pour le champ url."""
        return self.url
