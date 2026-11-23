"""Regroupement des offres des 3 sources : détection et fusion des doublons (aucun appel réseau).

Deux offres sont le **même poste** si :
1. elles ont le même ``id`` ; ou
2. elles ont la même **empreinte** (titre + entreprise + ville, comparés sans accents ni majuscules)
   ET ne viennent pas du même diffuseur.

Le « diffuseur » est le couple (source, site partenaire). Exemples :
- ``ge-1`` (Guichet-Emplois, partenaire Talent.com) et ``tc-9`` (Talent.com) : diffuseurs différents
  → fusion possible, c'est le cas typique d'une offre reprise par le Guichet-Emplois ;
- ``jb-1`` et ``jb-2`` (Jobboom, mêmes titre, entreprise et ville) : même diffuseur, numéros différents
  → **pas** de fusion, l'employeur peut vraiment avoir publié deux postes (règle reprise de la démo de Gregory).

Fusion : on garde l'offre la plus complète et on comble **seulement ses champs vides** avec l'autre.
Rien n'est inventé ; les ``id`` fusionnés sont gardés dans ``doublons``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields

from modele import Offre
from scrapers.commun import sans_accents

# Formes juridiques retirées du nom d'entreprise : « Mewlogic Inc. » = « Mewlogic ».
FORMES_JURIDIQUES = re.compile(r"\b(inc|incorporee|ltee|ltd|limitee|corp|corporation|senc|llc)\b")
# Champs jamais recopiés d'une offre à l'autre : ils décrivent l'annonce gardée elle-même.
CHAMPS_PROPRES = ("id", "source", "url", "source_partenaire", "doublons")


# --- Empreinte -------------------------------------------------------------------------

def _simplifier(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, espaces réduites."""
    if not texte:
        return ""
    texte = re.sub(r"[^a-z0-9]+", " ", sans_accents(texte))
    return " ".join(texte.split())


def titre_normalise(titre: str | None) -> str:
    """« développeur Web/développeuse Web » → « developpeur web » (forme masculine/féminine du Guichet)."""
    if titre and "/" in titre:
        titre = titre.split("/", 1)[0]
    return _simplifier(titre)


def entreprise_normalisee(entreprise: str | None) -> str:
    return " ".join(FORMES_JURIDIQUES.sub(" ", _simplifier(entreprise)).split())


def ville_normalisee(lieu: str | None) -> str:
    """« Québec City (QC) », « Québec (QC) », « Québec, QC » → « quebec »."""
    if not lieu:
        return ""
    ville = re.split(r"[(,]", lieu, maxsplit=1)[0]
    ville = _simplifier(ville)
    ville = re.sub(r"\b(city|ville de|ville)\b", " ", ville)
    return " ".join(ville.split())


def empreinte(offre: Offre) -> tuple[str, str, str] | None:
    """(titre, entreprise, ville) normalisés, ou ``None`` s'il manque une des trois parties :
    sans entreprise ou sans ville, on ne fusionne pas (trop de risque de confondre deux postes)."""
    cle = (titre_normalise(offre.titre), entreprise_normalisee(offre.entreprise), ville_normalisee(offre.lieu))
    return cle if all(cle) else None


def diffuseur(offre: Offre) -> tuple[str, str]:
    """(source, partenaire) : qui a réellement publié l'annonce.

    Une offre Talent.com reprise par le Guichet-Emplois donne (« guichet-emplois », « talent com ») :
    ce n'est pas le même diffuseur que l'offre lue sur Talent.com (« talent », « »), la fusion est permise.
    """
    return (offre.source, _simplifier(offre.source_partenaire))


# --- Fusion ------------------------------------------------------------------------------

def nb_champs_remplis(offre: Offre) -> int:
    """Nombre de champs renseignés (``None`` et listes vides ne comptent pas)."""
    return sum(1 for f in fields(offre) if f.name != "doublons" and getattr(offre, f.name) not in (None, [], ""))


def fusionner(a: Offre, b: Offre) -> Offre:
    """Garde l'offre la plus complète et comble ses champs vides avec l'autre. ``a`` gagne à égalité."""
    base, autre = (a, b) if nb_champs_remplis(a) >= nb_champs_remplis(b) else (b, a)
    for f in fields(base):
        if f.name in CHAMPS_PROPRES:
            continue
        if getattr(base, f.name) in (None, [], "") and getattr(autre, f.name) not in (None, [], ""):
            setattr(base, f.name, getattr(autre, f.name))
    base.competences = list(dict.fromkeys(base.competences + autre.competences))
    for identifiant in [autre.id, *autre.doublons]:
        if identifiant != base.id and identifiant not in base.doublons:
            base.doublons.append(identifiant)
    return base


# --- Regroupement ------------------------------------------------------------------------

@dataclass
class Bilan:
    offres_recues: int = 0
    doublons_meme_id: int = 0
    doublons_empreinte: int = 0
    exemples: list[str] = field(default_factory=list)          # « tc-9 = ge-1 », pour vérifier à la main

    @property
    def doublons(self) -> int:
        return self.doublons_meme_id + self.doublons_empreinte


def regrouper(offres: list[Offre]) -> tuple[list[Offre], Bilan]:
    """Retire les doublons en gardant l'ordre de première apparition."""
    bilan = Bilan(offres_recues=len(offres))
    uniques: list[Offre] = []
    par_id: dict[str, int] = {}
    par_empreinte: dict[tuple[str, str, str], list[int]] = {}

    for offre in offres:
        position = par_id.get(offre.id)
        if position is not None:
            bilan.doublons_meme_id += 1
        else:
            cle = empreinte(offre)
            for candidat in par_empreinte.get(cle, []) if cle else []:
                if diffuseur(uniques[candidat]) != diffuseur(offre):
                    position = candidat
                    bilan.doublons_empreinte += 1
                    if len(bilan.exemples) < 10:
                        bilan.exemples.append(f"{offre.id} = {uniques[candidat].id}")
                    break

        if position is None:
            position = len(uniques)
            uniques.append(offre)
        else:
            uniques[position] = fusionner(uniques[position], offre)

        fusion = uniques[position]
        for identifiant in [fusion.id, offre.id, *fusion.doublons]:
            par_id[identifiant] = position
        for cle in {empreinte(offre), empreinte(fusion)} - {None}:
            if position not in par_empreinte.setdefault(cle, []):
                par_empreinte[cle].append(position)
    return uniques, bilan
