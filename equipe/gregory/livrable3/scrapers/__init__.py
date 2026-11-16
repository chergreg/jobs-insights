"""
Module des scrapers pour le Livrable 3 (jobs-insights).
Connecteurs spécialisés :
- guichet_emplois : Guichet-Emplois Canada (recherche CNP + enrichissement RDFa / DOM) [Lot 2]
- jobboom : Jobboom Québec (HTML SSR + JSON-LD Schema.org) [Lot 3]
- remotive : Remotive API REST + télétravail / stages [Lot 4]
"""

from .guichet_emplois import GuichetEmploisScraper
from .jobboom import JobboomScraper

__all__ = ["GuichetEmploisScraper", "JobboomScraper"]
