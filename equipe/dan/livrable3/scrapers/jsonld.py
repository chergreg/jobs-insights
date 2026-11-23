"""Lecture des données structurées JSON-LD (schema.org) : partagée par Jobboom et Talent.com.

Les blocs ``<script type="application/ld+json">`` sont lus avec ``json.loads`` (jamais par regex).
Un bloc peut contenir un objet, une liste ou un ``@graph`` ; un bloc invalide est ignoré.
Règle d'intégrité : ``champs_jobposting`` ne renvoie que les champs vraiment présents.
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from scrapers.commun import UNITES_SALAIRE, date_iso, espaces, est_un_stage, html_vers_texte, montant, sans_accents

TYPES_POSTE = {
    "FULL_TIME": "Temps plein", "PART_TIME": "Temps partiel", "PERMANENT": "Permanent",
    "TEMPORARY": "Temporaire", "CONTRACTOR": "Contrat", "CONTRACT": "Contrat",
    "INTERN": "Stage", "INTERNSHIP": "Stage", "SEASONAL": "Saisonnier", "PER_DIEM": "À la journée",
}
TYPES_STAGE = {"INTERN", "INTERNSHIP"}

# Provinces et territoires du Canada, en français et en anglais (sans accents, minuscules) → code.
PROVINCES = {
    "quebec": "QC", "ontario": "ON", "alberta": "AB", "manitoba": "MB", "saskatchewan": "SK",
    "nova scotia": "NS", "nouvelle-ecosse": "NS", "new brunswick": "NB", "nouveau-brunswick": "NB",
    "british columbia": "BC", "colombie-britannique": "BC",
    "prince edward island": "PE", "ile-du-prince-edouard": "PE",
    "newfoundland and labrador": "NL", "terre-neuve-et-labrador": "NL",
    "yukon": "YT", "northwest territories": "NT", "territoires du nord-ouest": "NT", "nunavut": "NU",
}
CODES_PROVINCES = set(PROVINCES.values())


def objets_jsonld(html: str) -> list[dict]:
    """Tous les objets JSON-LD de la page, à plat (les ``@graph`` sont dépliés)."""
    soupe = BeautifulSoup(html, "html.parser")
    objets: list[dict] = []
    for script in soupe.find_all("script", type="application/ld+json"):
        try:
            donnees = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        for objet in donnees if isinstance(donnees, list) else [donnees]:
            if isinstance(objet, dict) and isinstance(objet.get("@graph"), list):
                objets += [o for o in objet["@graph"] if isinstance(o, dict)]
            elif isinstance(objet, dict):
                objets.append(objet)
    return objets


def est_du_type(objet: dict, type_: str) -> bool:
    valeur = objet.get("@type")
    return valeur == type_ or (isinstance(valeur, list) and type_ in valeur)


def jobposting(html: str) -> dict | None:
    """Premier objet ``JobPosting`` de la page, ou ``None``."""
    return next((o for o in objets_jsonld(html) if est_du_type(o, "JobPosting")), None)


# --- Champs d'un JobPosting ---------------------------------------------------------------

def _premier(valeur):
    """Un champ JSON-LD peut être un objet ou une liste d'objets : on prend le premier."""
    if isinstance(valeur, list):
        return valeur[0] if valeur else None
    return valeur


def _texte(valeur) -> str | None:
    if valeur is None:
        return None
    texte = espaces(str(valeur))
    return texte or None


def province(valeur) -> str | None:
    """« QC », « Quebec », « Québec », « Ontario » → code. Texte inconnu : ``None``."""
    texte = _texte(valeur)
    if not texte:
        return None
    if texte.upper() in CODES_PROVINCES:
        return texte.upper()
    return PROVINCES.get(sans_accents(texte))


def coordonnee(valeur) -> float | None:
    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return None


def salaire(job: dict) -> str | None:
    """``baseSalary`` → « 22 $ à 26 $ de l'heure ». ``None`` s'il est absent."""
    base = job.get("baseSalary")
    if isinstance(base, (str, int, float)):
        return _texte(base)
    if not isinstance(base, dict):
        return None
    valeur = base.get("value")
    unite = base.get("unitText")
    if isinstance(valeur, dict):
        unite = valeur.get("unitText") or unite
        mini, maxi, exact = valeur.get("minValue"), valeur.get("maxValue"), valeur.get("value")
    else:
        mini, maxi, exact = None, None, valeur
    if mini is not None and maxi is not None and mini != maxi:
        texte = f"{montant(mini)} $ à {montant(maxi)} $"
    elif exact is not None or mini is not None:
        texte = f"{montant(exact if exact is not None else mini)} $"
    else:
        return None
    suffixe = UNITES_SALAIRE.get(str(unite).upper()) if unite else None
    return f"{texte} {suffixe}" if suffixe else texte


def champs_jobposting(job: dict) -> dict:
    """Champs d'``Offre`` tirés d'un ``JobPosting``. Une clé n'est présente que si la valeur existe."""
    organisation = job.get("hiringOrganization")
    entreprise = organisation.get("name") if isinstance(organisation, dict) else organisation
    lieu_json = _premier(job.get("jobLocation"))
    adresse = lieu_json.get("address") if isinstance(lieu_json, dict) else None
    geo = lieu_json.get("geo") if isinstance(lieu_json, dict) else None
    ville = _texte(adresse.get("addressLocality")) if isinstance(adresse, dict) else None
    region = province(adresse.get("addressRegion")) if isinstance(adresse, dict) else None

    types = job.get("employmentType") or []
    types = [str(t).upper() for t in (types if isinstance(types, list) else [types])]
    titre = _texte(job.get("title"))
    teletravail = str(job.get("jobLocationType", "")).upper() == "TELECOMMUTE"

    valeurs = {
        "titre": titre,
        "entreprise": _texte(entreprise),
        "lieu": f"{ville} ({region})" if ville and region else ville,
        "province": region,
        "latitude": coordonnee(geo.get("latitude")) if isinstance(geo, dict) else None,
        "longitude": coordonnee(geo.get("longitude")) if isinstance(geo, dict) else None,
        "date_publication": date_iso(_texte(job.get("datePosted"))),
        "type_poste": ", ".join(TYPES_POSTE.get(t, t.capitalize()) for t in types) or None,
        "modalite": "Télétravail" if teletravail else None,
        "est_stage": True if TYPES_STAGE & set(types) else est_un_stage(titre),
        "salaire": salaire(job),
        "description": html_vers_texte(job.get("description")),
    }
    return {cle: v for cle, v in valeurs.items() if v is not None}
