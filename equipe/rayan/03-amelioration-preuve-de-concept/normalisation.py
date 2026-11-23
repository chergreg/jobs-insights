"""Normalisation géographique, filtrage de pertinence TI, compétences et stages pour Adzuna.

Contributions de l'équipe réutilisées et adaptées :
- `equipe/kandet/03-amelioration-preuve-de-concept/regions.py` et `regions_quebec.csv` :
  indexation officielle MAMH des municipalités et arrondissements du Québec (CC-BY 4.0),
  adaptée aux 31 structures hiérarchiques `location.area` d'Adzuna (sans confondre
  `["Canada", "Québec"]` qui désigne la province entière avec la ville de Québec `"Québec City"`).
- `equipe/hugo/02-preuve-de-concept-scraping/parsers.py` et
  `equipe/elvira/03-amelioration-preuve-de-concept/models.py` :
  filtrage de pertinence des métiers TI (adapté aux titres bilingues, aux pluriels `systèmes`
  et à l'écriture inclusive `Administrateur·trice` / `Administrateur.trice` d'Adzuna) et
  catalogue de compétences `TECH_PATTERNS` sans faux positifs sur `"C"` isolé ou `"vue d'ensemble"`.
- `equipe/kandet/02-preuve-de-concept-scraping/poc_multi_source.py` :
  classification des stages (`confirmed_stage`, `possible_stage`, `not_indicated`).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import re
import unicodedata
from typing import Any

from extraction_texte import enrichir_et_consolider_offre
from models import NON_SPECIFIE, OffreAdzuna


# Chemin vers le fichier officiel des municipalités/régions préparé par Kandet (lecture seule)
CHEMIN_REGIONS_KANDET = (
    Path(__file__).resolve().parent.parent.parent
    / "kandet"
    / "03-amelioration-preuve-de-concept"
    / "regions_quebec.csv"
)

CODE_REGION_REGEX = re.compile(r"\s*\(\d+\)\s*$")


def normaliser_cle(texte: str | None) -> str:
    """Minuscules sans accents, tirets et apostrophes harmonisés pour l'index géographique."""
    decomposed = unicodedata.normalize("NFKD", (texte or "").casefold())
    sans_acc = "".join(c for c in decomposed if not unicodedata.combining(c))
    sans_acc = sans_acc.replace("’", "'")
    return " ".join(sans_acc.split())


def nettoyer_nom_region(valeur: str) -> str:
    """« Montérégie (16) » -> « Montérégie » (repris de `clean_region` de Kandet)."""
    return CODE_REGION_REGEX.sub("", valeur).strip()


@lru_cache(maxsize=1)
def charger_index_regions_quebec() -> dict[str, str]:
    """Charge l'index `ville/arrondissement -> région administrative` depuis `regions_quebec.csv` de Kandet.

    Inclut un index de repli intégré pour les villes présentes dans nos données Adzuna au cas où le
    fichier externe ne serait pas accessible.
    """
    index: dict[str, str] = {
        "montreal": "Montréal",
        "quebec": "Capitale-Nationale",
        "laval": "Laval",
        "levis": "Chaudière-Appalaches",
        "brossard": "Montérégie",
        "longueuil": "Montérégie",
        "saint-hyacinthe": "Montérégie",
        "saint-bruno-de-montarville": "Montérégie",
        "l'ile-perrot": "Montérégie",
        "boisbriand": "Laurentides",
        "saint-andre-d'argenteuil": "Laurentides",
        "mascouche": "Lanaudière",
        "terrebonne": "Lanaudière",
        "trois-rivieres": "Mauricie",
        "shawinigan": "Mauricie",
        "sherbrooke": "Estrie",
        "wolinak": "Centre-du-Québec",
        "saint-germain-de-grantham": "Centre-du-Québec",
        "petit-saguenay": "Saguenay–Lac-Saint-Jean",
        "gatineau": "Outaouais",
        "rimouski": "Bas-Saint-Laurent",
    }

    if not CHEMIN_REGIONS_KANDET.is_file():
        return index

    try:
        with CHEMIN_REGIONS_KANDET.open(encoding="utf-8-sig", newline="") as fichier:
            lignes = list(csv.DictReader(fichier, delimiter=";"))
    except OSError:
        return index

    ambigus: set[str] = set()
    index_csv: dict[str, str] = {}
    for categorie in ("municipalité", "arrondissement"):
        vus: dict[str, set[str]] = {}
        for ligne in lignes:
            if ligne.get("type") != categorie or not ligne.get("nom") or not ligne.get("region"):
                continue
            vus.setdefault(normaliser_cle(ligne["nom"]), set()).add(nettoyer_nom_region(ligne["region"]))
        for nom, regions in vus.items():
            if nom in index_csv or nom in ambigus:
                continue
            if len(regions) == 1:
                index_csv[nom] = next(iter(regions))
            else:
                ambigus.add(nom)

    index_csv.update(index)
    return index_csv


# Correspondance directe des régions administratives telles qu'écrites par Adzuna dans `area[2]`
REGIONS_ADZUNA_CANONIQUES: dict[str, str] = {
    "bas-saint-laurent": "Bas-Saint-Laurent",
    "saguenay - lac-saint-jean": "Saguenay–Lac-Saint-Jean",
    "saguenay-lac-saint-jean": "Saguenay–Lac-Saint-Jean",
    "quebec city": "Capitale-Nationale",
    "capitale-nationale": "Capitale-Nationale",
    "mauricie": "Mauricie",
    "estrie": "Estrie",
    "montreal": "Montréal",
    "outaouais": "Outaouais",
    "abitibi-temiscamingue": "Abitibi-Témiscamingue",
    "cote-nord": "Côte-Nord",
    "nord-du-quebec": "Nord-du-Québec",
    "gaspesie-iles-de-la-madeleine": "Gaspésie–Îles-de-la-Madeleine",
    "chaudiere - appalaches": "Chaudière-Appalaches",
    "chaudiere-appalaches": "Chaudière-Appalaches",
    "laval region": "Laval",
    "laval": "Laval",
    "lanaudiere": "Lanaudière",
    "laurentides": "Laurentides",
    "monteregie": "Montérégie",
    "centre-du-quebec": "Centre-du-Québec",
}

# Synonymes de municipalités utilisés par Adzuna en anglais ou abrégé
SYNONYMES_VILLES_ADZUNA: dict[str, str] = {
    "quebec city": "Québec",
    "montreal west": "Montréal-Ouest",
    "saint-bruno": "Saint-Bruno-de-Montarville",
    "saint-andre-d'argenteuil": "Saint-André-d'Argenteuil",
    "saint-francois-d'orleans": "Saint-François-de-l'Île-d'Orléans",
}

PROVINCES_CANADA: dict[str, str] = {
    "quebec": "QC",
    "ontario": "ON",
    "british columbia": "BC",
    "colombie-britannique": "BC",
    "alberta": "AB",
    "manitoba": "MB",
    "saskatchewan": "SK",
    "nova scotia": "NS",
    "nouvelle-ecosse": "NS",
    "new brunswick": "NB",
    "nouveau-brunswick": "NB",
}


def normaliser_lieu_adzuna(
    location_dict: dict[str, Any] | None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Analyse l'objet `location` (`display_name` + `area`) et les coordonnées GPS d'Adzuna.

    Distingue 4 niveaux de précision (`precision_lieu`) :
    - `"ville"` : municipalité ou arrondissement identifié (ex. Montréal, Québec, Lévis, Brossard) ;
    - `"region"` : seule la région administrative est connue (ex. `["Canada", "Québec", "Bas-Saint-Laurent"]`) ;
    - `"province"` : seule la province est connue (`["Canada", "Québec"]`, `display_name="Québec, Canada"`) ;
    - `"inconnue"` : information absente.
    """
    loc = location_dict or {}
    lieu_brut = str(loc.get("display_name") or NON_SPECIFIE).strip()
    area_brute = [str(x).strip() for x in (loc.get("area") or []) if str(x).strip()]

    pays = "Canada"
    province: str | None = None
    region: str | None = None
    ville: str | None = None
    arrondissement_ou_mrc: str | None = None
    precision = "inconnue"

    if area_brute:
        if normaliser_cle(area_brute[0]) == "canada":
            pays = "Canada"
        else:
            pays = area_brute[0]

    if len(area_brute) >= 2:
        prov_cle = normaliser_cle(area_brute[1])
        province = PROVINCES_CANADA.get(prov_cle, area_brute[1])

    # Cas 1 : Longueur 2 -> ["Canada", "Québec"] = Province seule (JAMAIS la ville de Québec !)
    if len(area_brute) == 2:
        precision = "province" if province else "inconnue"

    # Cas 2 : Longueur 3 -> ["Canada", "Québec", "Montréal" | "Québec City" | "Bas-Saint-Laurent"]
    elif len(area_brute) == 3:
        niv2 = area_brute[2]
        niv2_cle = normaliser_cle(niv2)
        region = REGIONS_ADZUNA_CANONIQUES.get(niv2_cle)

        if niv2_cle in {"montreal", "quebec city", "laval"}:
            ville = SYNONYMES_VILLES_ADZUNA.get(niv2_cle, niv2)
            precision = "ville"
        else:
            index_reg = charger_index_regions_quebec()
            if not region and niv2_cle in index_reg:
                ville = SYNONYMES_VILLES_ADZUNA.get(niv2_cle, niv2)
                region = index_reg[niv2_cle]
                precision = "ville"
            else:
                precision = "region" if region else "province"

    # Cas 3 : Longueur 4 -> ex. ["Canada", "Québec", "Laval region", "Laval"],
    # ["Canada", "Québec", "Montréal", "Outremont"], ["Canada", "Québec", "Québec City", "Beauport"]
    elif len(area_brute) == 4:
        niv2_cle = normaliser_cle(area_brute[2])
        niv3 = area_brute[3]
        niv3_cle = normaliser_cle(niv3)

        region = REGIONS_ADZUNA_CANONIQUES.get(niv2_cle)
        ville_canon = SYNONYMES_VILLES_ADZUNA.get(niv3_cle, niv3)

        if niv2_cle == "quebec city":
            ville = "Québec"
            arrondissement_ou_mrc = ville_canon
        elif niv2_cle == "laval region":
            ville = "Laval"
        else:
            ville = ville_canon
            if niv2_cle == "montreal" and normaliser_cle(ville_canon) != "montreal":
                arrondissement_ou_mrc = ville_canon

        if not region:
            index_reg = charger_index_regions_quebec()
            region = index_reg.get(normaliser_cle(ville)) or index_reg.get(niv3_cle)
        precision = "ville"

    # Cas 4 : Longueur >= 5 -> [Pays, Province, Région, MRC, Municipalité]
    # ex. ["Canada", "Québec", "Montérégie", "Champlain", "Brossard"]
    elif len(area_brute) >= 5:
        niv2_cle = normaliser_cle(area_brute[2])
        arrondissement_ou_mrc = area_brute[3]
        niv4 = area_brute[4]
        niv4_cle = normaliser_cle(niv4)

        region = REGIONS_ADZUNA_CANONIQUES.get(niv2_cle)
        ville = SYNONYMES_VILLES_ADZUNA.get(niv4_cle, niv4)
        if not region:
            index_reg = charger_index_regions_quebec()
            region = index_reg.get(normaliser_cle(ville)) or index_reg.get(niv4_cle)
        precision = "ville"

    return {
        "lieu_brut": lieu_brut,
        "area_brute": area_brute,
        "ville": ville,
        "arrondissement_ou_mrc": arrondissement_ou_mrc,
        "region_administrative": region,
        "province": province,
        "pays": pays,
        "precision_lieu": precision,
        "latitude": float(latitude) if latitude is not None else None,
        "longitude": float(longitude) if longitude is not None else None,
    }


# --- Filtrage de pertinence métier TI (adapté de Hugo et Elvira) --------------

# Motifs d'exclusion prioritaires sur le titre (métiers hors informatique)
MOTIFS_TITRE_HORS_TI = re.compile(
    r"\b(?:"
    r"actuari(?:al|el|at)|actuaire|"
    r"chauffeur|camionneur|livreur|plancher\s+mobile|"
    r"immobilier(?:s)?|real\s+estate|"
    r"cvc|cvac|hvac|batiment(?:s)?|construction|mecanicien|electromecanicien|usinage|cnc|"
    r"comptable|comptabilite|accounting|controleur\s+financier|"
    r"cuisinier|plongeur|serveur|nettoyage|entretien\s+menager|concierge|infirmier"
    r")\b",
    re.I,
)

# Motifs d'inclusion TI sur le titre (supporte les pluriels, le bilinguisme FR/EN et l'écriture inclusive)
MOTIFS_TITRE_TI = re.compile(
    r"\b(?:"
    r"informatique(?:s)?|informaticien(?:ne)?|ti\b|it\b|"
    r"developpeur(?:euse|se)?|developer(?:s)?|programmeur(?:euse|se)?|programmer(?:s)?|"
    r"logiciel(?:s)?|software|web|fullstack|full\s+stack|frontend|front\s+end|backend|back\s+end|"
    r"devops|devsecops|sre\b|cloud|infonuagique|cybersecurite|cybersecurity|securite|security|infosec|"
    r"data|donnees|dba\b|bi\b|intelligences?\s+d['’ ]affaires|scientifique\s+des\s+donnees|intelligence\s+artificielle|\bia\b|\bai\b|"
    r"reseau(?:x)?|reseautique|network(?:s)?|systeme(?:s)?|systems?|sysadmin|administrateur|administratrice|administrator|"
    r"support|soutien|helpdesk|help\s+desk|technicien(?:ne)?|technician|"
    r"analyste|analyst|anayst|architecte|architecture\s+organique|architect|ingenieur(?:e)?|engineer(?:s)?|"
    r"qa\b|qualite|quality\s+assurance|testeur(?:euse)?|"
    r"ui\b|ux\b|jouabilite|gameplay|game\s+designer|technical\s+designer|"
    r"pilote\s+des\s+applications|specialiste\s+technique|"
    r"oracle|salesforce|netsuite|sailpoint|cisco|voip|sap\b|python|java|javascript|angular|react|dotnet|net|sql|linux|windows|solaris|aws|azure"
    r")\b",
    re.I,
)


def _preparer_titre_pour_filtre(titre: str | None) -> str:
    """Retire les accents et remplace la ponctuation d'écriture inclusive (`·`, `.`, `/`, `-`) par des espaces."""
    t = normaliser_cle(titre)
    t = re.sub(r"[·./()\[\]\-–—,:;]+", " ", t)
    return " ".join(t.split())


def verifier_pertinence_ti(titre: str | None, description: str | None = None) -> tuple[bool, str]:
    """Vérifie si l'offre appartient au domaine de l'informatique / TI d'après son titre.

    Comme démontré lors de l'analyse sur Adzuna (`Actuarial Analyst`), on ne valide pas un titre
    hors-TI sous prétexte que sa description contient le mot-clé recherché, sauf si le titre est
    un intitulé générique de stage (`Stagiaire`, `Intern`).
    """
    titre_prep = _preparer_titre_pour_filtre(titre)
    if not titre_prep:
        return False, "titre_vide"

    m_excl = MOTIFS_TITRE_HORS_TI.search(titre_prep)
    if m_excl:
        return False, f"exclusion_hors_ti:{m_excl.group(0)}"

    m_incl = MOTIFS_TITRE_TI.search(titre_prep)
    if m_incl:
        return True, f"titre_ti:{m_incl.group(0)}"

    # Cas particulier d'un intitulé de stage générique ("Stagiaire", "Intern")
    if re.search(r"\b(?:stage|stagiaire|intern|internship)\b", titre_prep):
        desc_prep = _preparer_titre_pour_filtre(description)
        m_desc = MOTIFS_TITRE_TI.search(desc_prep)
        if m_desc:
            return True, f"stage_ti_description:{m_desc.group(0)}"

    return False, "aucun_marqueur_ti_dans_titre"


# --- Détection des compétences techniques (sans faux positifs C / Vue) --------

# Repris et combiné de Hugo (`parsers.py`), Kandet (`competences.py`) et Elvira (`models.py`)
CATALOGUE_COMPETENCES_TI: list[tuple[str, re.Pattern[str]]] = [
    ("Python", re.compile(r"\bpython\b", re.I)),
    ("Java", re.compile(r"\bjava\b(?!\s*script)", re.I)),
    ("JavaScript", re.compile(r"\bjavascript\b|(?<![.\w])js\b", re.I)),
    ("TypeScript", re.compile(r"\btypescript\b", re.I)),
    ("C#", re.compile(r"(?<![\w#])c#(?![\w#])|\bc\s*sharp\b", re.I)),
    ("C++", re.compile(r"(?<![\w+])c\+\+(?!\+)", re.I)),
    ("C", re.compile(r"\blangage\s+c\b|\bprogrammation\s+c\b|\bc\s*/\s*c\+\+|\bansi\s+c\b", re.I)),
    (".NET", re.compile(r"(?<![\w.])\.net\b|\basp\.net\b|\bdotnet\b", re.I)),
    ("PHP", re.compile(r"\bphp\b|\blaravel\b|\bsymfony\b", re.I)),
    ("Go", re.compile(r"\bgolang\b", re.I)),
    ("Rust", re.compile(r"\brust\b", re.I)),
    ("Kotlin", re.compile(r"\bkotlin\b", re.I)),
    ("Swift", re.compile(r"\bswift\b", re.I)),
    ("HTML", re.compile(r"\bhtml5?\b", re.I)),
    ("CSS", re.compile(r"\bcss3?\b|\bsass\b|\bscss\b", re.I)),
    ("React", re.compile(r"\breact(?:\.js|js)?\b", re.I)),
    ("Angular", re.compile(r"\bangular(?:\.js|js)?\b", re.I)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|vuejs|framework\s+vue)\b", re.I)),
    ("Node.js", re.compile(r"\bnode\.?js\b|\bnodejs\b", re.I)),
    ("Django", re.compile(r"\bdjango\b", re.I)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.I)),
    ("Spring", re.compile(r"\bspring(?:\s*boot|\s+framework)?\b", re.I)),
    ("SQL", re.compile(r"\bsql\b", re.I)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.I)),
    ("MySQL", re.compile(r"\bmysql\b", re.I)),
    ("MongoDB", re.compile(r"\bmongo(?:db)?\b", re.I)),
    ("Oracle", re.compile(r"\boracle\b", re.I)),
    ("SSIS", re.compile(r"\bssis\b", re.I)),
    ("Power BI", re.compile(r"\bpower\s*bi\b", re.I)),
    ("Docker", re.compile(r"\bdocker\b", re.I)),
    ("Kubernetes", re.compile(r"\bkubernetes\b|\bk8s\b", re.I)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", re.I)),
    ("Azure", re.compile(r"\bazure\b", re.I)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", re.I)),
    ("Git", re.compile(r"\bgit\b(?![-\w])|\bgithub\b|\bgitlab\b", re.I)),
    ("CI/CD", re.compile(r"\bci\s*[/\-]\s*cd\b", re.I)),
    ("DevOps", re.compile(r"\bdevops\b|\bdevsecops\b", re.I)),
    ("Linux", re.compile(r"\blinux\b|\bubuntu\b|\bred\s*hat\b|\bsolaris\b", re.I)),
    ("Windows", re.compile(r"\bwindows(?:\s+server)?\b", re.I)),
    ("Active Directory", re.compile(r"\bactive\s+directory\b|\bentra\s+id\b", re.I)),
    ("VMware", re.compile(r"\bvmware\b|\bhyper-v\b", re.I)),
    ("Cisco", re.compile(r"\bcisco\b|\bsd-wan\b|\bfortinet\b", re.I)),
    ("Salesforce", re.compile(r"\bsalesforce\b", re.I)),
    ("SAP", re.compile(r"\bsap\b", re.I)),
    ("SharePoint", re.compile(r"\bsharepoint\b", re.I)),
    ("Jira", re.compile(r"\bjira\b", re.I)),
    ("Agile", re.compile(r"\bagile\b|\bscrum\b", re.I)),
    ("API REST", re.compile(r"\brest(?:ful)?\s*api\b|\bapi\s+rest\b", re.I)),
]


def extraire_competences_ti(titre: str | None, description: str | None) -> list[str]:
    """Extrait les technologies TI mentionnées dans le titre et l'extrait de description."""
    texte = f"{titre or ''} \n {description or ''}"
    trouvees: list[str] = []
    for nom, patron in CATALOGUE_COMPETENCES_TI:
        if patron.search(texte):
            trouvees.append(nom)
    return trouvees


# --- Classification des stages (adaptée de Kandet) ----------------------------

PATRON_STAGE_CONFIRME_TITRE = re.compile(
    r"\b(?:stages?|stagiaires?|internships?|co[\s-]?op)\b",
    re.I,
)
PATRON_STAGE_POSSIBLE_DESC = re.compile(
    r"\b(?:offre\s+un\s+stage|stage\s+de\s+\d+\s*mois|recherche\s+des\s+stagiaires|"
    r"convention\s+de\s+stage|ouvert\s+aux\s+[ée]tudiants\s+actuellement\s+inscrits)\b",
    re.I,
)


def classifier_stage(titre: str | None, description: str | None, type_contrat_consolide: str | None) -> tuple[bool, str]:
    """Retourne `(est_stage, statut_stage)` avec `statut_stage` parmi
    `confirmed_stage`, `possible_stage`, `not_indicated`."""
    if type_contrat_consolide == "Stage" or PATRON_STAGE_CONFIRME_TITRE.search(titre or ""):
        return True, "confirmed_stage"
    if PATRON_STAGE_POSSIBLE_DESC.search(description or ""):
        return True, "confirmed_stage"
    return False, "not_indicated"


# --- Construction complète d'une OffreAdzuna à partir du JSON brut -----------

def construire_offre_adzuna(
    raw_job: dict[str, Any],
    mot_cle_recherche: str = "",
    ville_recherche: str = "",
    date_extraction: str | None = None,
) -> OffreAdzuna:
    """Transforme un objet d'annonce JSON Adzuna en `OffreAdzuna` normalisée et enrichie."""
    id_brut = str(raw_job.get("id") or "").strip()
    titre = " ".join(str(raw_job.get("title") or "").split())
    description = " ".join(str(raw_job.get("description") or "").split())

    comp = raw_job.get("company") or {}
    entreprise = str(comp.get("display_name") or NON_SPECIFIE).strip() or NON_SPECIFIE

    cat = raw_job.get("category") or {}
    cat_tag = cat.get("tag")
    cat_label = cat.get("label")

    created_raw = str(raw_job.get("created") or "").strip() or None
    date_pub = created_raw[:10] if created_raw and len(created_raw) >= 10 else None

    info_lieu = normaliser_lieu_adzuna(
        raw_job.get("location"),
        raw_job.get("latitude"),
        raw_job.get("longitude"),
    )

    # Valeurs brutes API (conservées telles quelles)
    api_smin_raw = raw_job.get("salary_min")
    api_smax_raw = raw_job.get("salary_max")
    api_smin = float(api_smin_raw) if api_smin_raw is not None else None
    api_smax = float(api_smax_raw) if api_smax_raw is not None else None
    api_spred = str(raw_job.get("salary_is_predicted")) if raw_job.get("salary_is_predicted") is not None else None
    api_ctype = raw_job.get("contract_type")
    api_ctime = raw_job.get("contract_time")

    offre = OffreAdzuna(
        id=f"adz-{id_brut}" if id_brut else "adz-inconnu",
        id_adzuna=id_brut,
        source="adzuna",
        titre=titre,
        entreprise=entreprise,
        url=str(raw_job.get("redirect_url") or "").strip(),
        date_publication=date_pub,
        date_creation_brute=created_raw,
        categorie_tag=cat_tag,
        categorie_label=cat_label,
        description=description,
        lieu_brut=info_lieu["lieu_brut"],
        area_brute=info_lieu["area_brute"],
        ville=info_lieu["ville"],
        arrondissement_ou_mrc=info_lieu["arrondissement_ou_mrc"],
        region_administrative=info_lieu["region_administrative"],
        province=info_lieu["province"],
        pays=info_lieu["pays"],
        precision_lieu=info_lieu["precision_lieu"],
        latitude=info_lieu["latitude"],
        longitude=info_lieu["longitude"],
        api_salary_min=api_smin,
        api_salary_max=api_smax,
        api_salary_is_predicted=api_spred,
        api_contract_type=api_ctype,
        api_contract_time=api_ctime,
        mots_cles_recherche=[mot_cle_recherche] if mot_cle_recherche else [],
        villes_recherche=[ville_recherche] if ville_recherche else [],
    )
    if date_extraction:
        offre.date_extraction = date_extraction

    # 1. Extraction textuelle et consolidation (salaires, contrats, horaires, modalité, provenance)
    enrichir_et_consolider_offre(offre)

    # 2. Pertinence TI, compétences techniques et classification des stages
    est_ti, raison_ti = verifier_pertinence_ti(offre.titre, offre.description)
    offre.est_pertinent_ti = est_ti
    offre.raison_filtrage_ti = raison_ti
    if not est_ti:
        offre.anomalies.append(f"offre_hors_ti_probable: {raison_ti}")

    offre.competences_cles = extraire_competences_ti(offre.titre, offre.description)
    est_st, statut_st = classifier_stage(offre.titre, offre.description, offre.type_contrat)
    offre.est_stage = est_st
    offre.statut_stage = statut_st

    return offre
