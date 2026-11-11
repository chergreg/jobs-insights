"""
models.py - Modèles de données pour le projet Jobs Insights.
Définit la structure standard des offres d'emploi pour assurer
la cohérence et la compatibilité entre les différentes sources.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class JobOffer(BaseModel):
    """
    Modèle représentant une offre d'emploi / stage standardisée.
    """
    id: str = Field(..., description="Identifiant unique de l'offre (ex: gc-50701948)")
    titre: str = Field(..., description="Titre du poste")
    entreprise: str = Field(default="Non spécifié", description="Nom de l'entreprise ou employeur")
    lieu: str = Field(default="Québec", description="Ville ou région")
    province: str = Field(default="QC", description="Code de province (ex: QC, ON, BC)")
    pays: str = Field(default="Canada", description="Pays")
    salaire: Optional[str] = Field(default=None, description="Information brute sur le salaire / taux horaire")
    date_publication: Optional[str] = Field(default=None, description="Date d'affichage de l'offre")
    modalite: Optional[str] = Field(default=None, description="Modalité : Sur place, Hybride, Télétravail")
    type_poste: Optional[str] = Field(default=None, description="Type de contrat : Temps plein, Temps partiel, Stage")
    competences_cles: List[str] = Field(default_factory=list, description="Mots-clés / compétences informatiques détectées")
    description: Optional[str] = Field(default=None, description="Description ou résumé du poste")
    url_source: str = Field(..., description="URL complète vers l'offre d'emploi")
    source: str = Field(default="Guichet-Emplois", description="Plateforme source d'extraction")
    partenaire: Optional[str] = Field(default=None, description="Partenaire d'origine (ex: Jobillico, Guichet-Emplois direct)")
    date_extraction: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Horodatage ISO de l'extraction"
    )
