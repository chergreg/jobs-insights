"""
models.py - Modèle de données unifié pour le pipeline TOP 3 (Espace Hugo).
Définit la structure standardisée JobOffer pour Guichet-Emplois, Jobboom et Remotive.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class JobOffer(BaseModel):
    """
    Modèle unifié représentant une offre d'emploi / stage standardisée.
    """
    id: str = Field(..., description="Identifiant unique (ex: gc-50701948, jb-3661921, rem-1928374)")
    titre: str = Field(..., description="Titre normalisé du poste")
    entreprise: str = Field(default="Non spécifié", description="Nom de l'employeur")
    lieu: str = Field(default="Québec", description="Ville ou région")
    province: str = Field(default="QC", description="Code de province (QC, ON, Télétravail, etc.)")
    pays: str = Field(default="Canada", description="Pays")
    salaire: Optional[str] = Field(default="Non spécifié", description="Rémunération")
    date_publication: Optional[str] = Field(default=None, description="Date de publication ISO")
    modalite: str = Field(default="Non spécifié", description="Sur place, Hybride ou Télétravail")
    type_poste: str = Field(default="Non spécifié", description="Temps plein, Temps partiel, Stage, etc.")
    competences_cles: List[str] = Field(default_factory=list, description="Compétences techniques détectées")
    description: str = Field(default="", description="Description textuelle nettoyée de l'offre")
    url_source: str = Field(..., description="URL directe de l'offre")
    source: str = Field(..., description="Source principale (Guichet-Emplois, Jobboom, Remotive)")
    partenaire: Optional[str] = Field(default=None, description="Source d'origine ou flux")
    methode_extraction: str = Field(default="Standard", description="Méthode de collecte")
    date_extraction: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Horodatage de la collecte"
    )

    def cle_deduplication(self) -> str:
        """
        Génère une clé normalisée pour identifier et fusionner les doublons multi-sources.
        Combine le titre nettoyé et l'entreprise simplifiée.
        """
        import unicodedata
        import re

        def normaliser_chaine(s: str) -> str:
            if not s:
                return ""
            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8').lower()
            s = re.sub(r"\b(inc|ltee|ltd|corp|corporation|canada|quebec)\b", "", s)
            return re.sub(r"[^a-z0-9]", "", s)

        t = normaliser_chaine(self.titre)
        e = normaliser_chaine(self.entreprise)
        return f"{t}_{e}"
