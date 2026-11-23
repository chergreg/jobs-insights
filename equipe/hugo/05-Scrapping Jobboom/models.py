"""
models.py - Modèle de données standardisé pour le scraper Jobboom.
Compatible avec le modèle JobOffer du projet Jobs Insights (Espace Hugo).
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class JobOffer(BaseModel):
    """
    Modèle représentant une offre d'emploi / stage standardisée.
    """
    id: str = Field(..., description="Identifiant unique de l'offre (ex: jb-3661921)")
    titre: str = Field(..., description="Titre du poste")
    entreprise: str = Field(default="Non spécifié", description="Nom de l'entreprise ou employeur")
    lieu: str = Field(default="Québec", description="Ville ou région")
    province: str = Field(default="QC", description="Code de province (ex: QC, ON, BC)")
    pays: str = Field(default="Canada", description="Pays")
    salaire: Optional[str] = Field(default="Non spécifié", description="Rémunération ou taux horaire")
    date_publication: Optional[str] = Field(default=None, description="Date de publication normalisée ISO")
    modalite: str = Field(default="Non spécifié", description="Sur place, Hybride ou Télétravail")
    type_poste: str = Field(default="Non spécifié", description="Temps plein, Temps partiel, Stage, etc.")
    competences_cles: List[str] = Field(default_factory=list, description="Liste des compétences techniques")
    description: str = Field(default="", description="Description textuelle nettoyée de l'offre")
    url_source: str = Field(..., description="URL directe de l'offre")
    source: str = Field(default="Jobboom", description="Nom de la plateforme source")
    partenaire: Optional[str] = Field(default="Jobboom Québec", description="Indication de la source ou partenaire")
    methode_extraction: str = Field(default="HTML+JSON-LD", description="Méthode employée pour collecter l'offre")
    date_extraction: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Horodatage de la collecte"
    )
