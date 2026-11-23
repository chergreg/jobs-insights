"""Modèle commun ``Offre`` et exports JSON / CSV.

Les trois scrapers (Guichet-Emplois, Jobboom, Talent.com) produisent tous des ``Offre``.
Règle d'intégrité (AGENTS.md) : une information absente reste ``None``, jamais devinée.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Offre:
    """Une offre d'emploi ou de stage, quelle que soit sa source."""

    # Obligatoires : sans eux, l'offre n'est pas exploitable.
    id: str                                   # préfixe de source + numéro, ex. "ge-50738681"
    source: str                               # "guichet-emplois", "jobboom", "talent"
    titre: str
    url: str

    # Facultatifs : None si la source ne les donne pas.
    source_partenaire: str | None = None      # site d'origine si l'offre est reprise (ex. "Jobillico")
    entreprise: str | None = None
    lieu: str | None = None                   # texte affiché, ex. "Québec (QC)"
    province: str | None = None               # code, ex. "QC"
    latitude: float | None = None
    longitude: float | None = None
    date_publication: str | None = None       # ISO AAAA-MM-JJ
    type_poste: str | None = None             # ex. "Temps plein"
    modalite: str | None = None               # "Sur place", "Hybride", "Télétravail"
    est_stage: bool | None = None             # None = la source ne permet pas de le savoir
    salaire: str | None = None                # texte tel qu'affiché
    description: str | None = None            # texte sans balises HTML
    competences: list[str] = field(default_factory=list)
    doublons: list[str] = field(default_factory=list)  # id des offres fusionnées dans celle-ci (lot 6)


CHAMPS = [f.name for f in fields(Offre)]


def exporter_json(offres: list[Offre], chemin: str | Path) -> Path:
    """Écrit les offres en JSON UTF-8 lisible, avec la date d'export et le nombre d'offres."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = {
        "date_export": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nombre": len(offres),
        "offres": [asdict(o) for o in offres],
    }
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    return chemin


def lire_json(chemin: str | Path) -> list[Offre]:
    """Relit un fichier produit par ``exporter_json`` (utile pour regrouper les sources)."""
    contenu = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return [Offre(**o) for o in contenu["offres"]]


def _cellule(valeur: object) -> str:
    """Valeur d'une cellule CSV : vide si None, liste jointe par des virgules, booléen en oui/non."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, list):
        return ", ".join(str(v) for v in valeur)
    return str(valeur)


def exporter_csv(offres: list[Offre], chemin: str | Path) -> Path:
    """Écrit les offres en CSV pour Excel sous Windows : ``utf-8-sig`` et séparateur ``;``."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(CHAMPS)
        for offre in offres:
            ecrivain.writerow(_cellule(getattr(offre, nom)) for nom in CHAMPS)
    return chemin
