"""
Livrable 3 (Lot 4 Final) — Collecteur Multi-Sources Enrichi, Classifieur CNP 2021 TI,
Intégration JobTailor_V3, Déduplication Inter-Sources & Export Consolidé (5 Sources Québec / Canada)
Auteur : Mamadou

Sources intégrées, filtrées TI (14 codes CNP 2021) et bonifiées :
1. Guichet-Emplois Canada : Recherche par les 14 codes CNP 2021 TI (fn21) + province QC
   (correction de fsrc=16 qui filtre la source Guichet-Emplois directe et non les stages)
   + cascade d'enrichissement des fiches (RDFa property="description", repli DOM #job-posting-detail,
   bandeau ul.job-posting-brief, .source-title-inner, a#externalJobLink, tâches RDFa).
2. Talent.com Canada : Double JSON-LD @graph (ItemList -> JobPosting) + coordonnées GPS (latitude / longitude)
   + classification CNP 2021 TI et filtrage anti-bruit hors TI.
3. Jobboom Québec : Catégorie Technologies (_i10lfr) ordonnée hors commandites + fiche JSON-LD JobPosting
   + classification CNP 2021 TI et rejet strict des offres hors TI (ex. vente, audio, CNC, enneigement).
4. Jobillico Québec : Recherche TI Québec/Montréal + fiche JSON-LD JobPosting + classification CNP 2021 TI.
5. Remotive API : API REST JSON officielle (postes TI télétravail ouverts au Canada) avec cache 24 h
   + classification CNP 2021 TI et rejet du bruit hors TI.

Enrichissement du schéma `JobBankOffer` (ADN JobTailor_V3 + meilleures briques de la classe) :
- `code_cnp` & `cnp_title` sur les 5 sources (14 codes CNP 2021 TI, 0 faux positif hors TI)
- `domaine_ti` (`tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`)
- `missions_cles` (`list[str]` — responsabilités et tâches extraites)
- `niveau_etudes`, `experience_requise` et `niveau_seniorite` (`Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`)
- `salaire`, `salaire_min`, `salaire_max`, `unite_salaire` (`heure`, `année`, `mois`, `semaine`, `jour`)
- `ville`, `region_administrative` (17 régions administratives du Québec), `code_postal`, `latitude`, `longitude`
- `url` nettoyée (sans `;jsessionid` ni traceurs `utm_*`), `url_partenaire`, `http_status` (`200`), `content_hash` (`SHA-256`)
- `score_pertinence_dec` (`0-100` : score d'adéquation pour un étudiant du DEC en Techniques de l'informatique)
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from typing import Any, Optional
from urllib.parse import parse_qsl, quote, quote_plus, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GUICHET_BASE_URL = "https://www.guichetemplois.gc.ca"
GUICHET_SEARCH_PATH = "/jobsearch/rechercheemplois"
USER_AGENT = "jobs-insights-osullivan/1.0 (atelier-livrable-3; mamadou)"
DEFAULT_CRAWL_DELAY = 5.0
CACHE_DIR = Path(__file__).parent / "cache"
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CACHE_TTL_SECONDS = 86400  # 24 heures

# Paramètres de pistage (tracking) retirés lors de la normalisation d'URL (repris de JobTailor_V3)
TRACKING_PARAMS: set[str] = {
    "lshs", "upg", "lijn", "lijp", "lirk", "lids", "lisp", "liet",
    "source", "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "fbclid", "gclid", "lang",
}

# 14 codes CNP 2021 officiels du domaine informatique (Classification nationale des professions)
CNP_2021_TI_DICT: dict[str, str] = {
    "20012": "Gestionnaires des systèmes informatiques",
    "21211": "Spécialistes des données",
    "21220": "Spécialistes en cybersécurité",
    "21221": "Spécialistes des systèmes d'affaires",
    "21222": "Spécialistes en informatique",
    "21223": "Analystes de bases de données et administrateurs de données",
    "21230": "Développeurs de systèmes informatiques et programmeurs",
    "21231": "Ingénieurs et concepteurs en logiciel",
    "21232": "Développeurs et programmeurs de logiciels",
    "21233": "Concepteurs Web",
    "21234": "Développeurs et programmeurs Web",
    "22220": "Techniciens de réseaux informatiques",
    "22221": "Agents de soutien aux utilisateurs",
    "22222": "Évaluateurs de systèmes informatiques",
}

CNP_CODES_TI: tuple[str, ...] = tuple(CNP_2021_TI_DICT.keys())

# Catalogue de détection de compétences TI (sans faux positifs français sur "C" ou "Vue")
TECH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Python", re.compile(r"\bpython\b", re.I)),
    ("Java", re.compile(r"\bjava\b(?!script)", re.I)),
    ("JavaScript", re.compile(r"(?<!\.)\b(?:javascript|js)\b", re.I)),
    ("TypeScript", re.compile(r"\btypescript\b", re.I)),
    ("C#", re.compile(r"\bc#(?=[^\w#]|$)", re.I)),
    ("C++", re.compile(r"\bc\+\+(?=[^\w\+]|$)", re.I)),
    ("C", re.compile(r"(?:\blangage\s+c\b|\bprogrammation\s+c\b|\bc\s*\/\s*c\+\+)", re.I)),
    ("React", re.compile(r"\breact(?:\.js)?\b", re.I)),
    ("Angular", re.compile(r"\bangular(?:\.js)?\b", re.I)),
    ("Vue.js", re.compile(r"\b(?:vue\.?js|vuejs|framework\s+vue)\b", re.I)),
    ("Node.js", re.compile(r"\bnode(?:\.js)?\b", re.I)),
    ("PHP", re.compile(r"\bphp\b", re.I)),
    ("Go", re.compile(r"\bgolang\b", re.I)),
    ("Rust", re.compile(r"\brust\b", re.I)),
    ("SQL", re.compile(r"\bsql\b", re.I)),
    ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.I)),
    ("MySQL", re.compile(r"\bmysql\b", re.I)),
    ("MongoDB", re.compile(r"\bmongodb\b", re.I)),
    ("Docker", re.compile(r"\bdocker\b", re.I)),
    ("Kubernetes", re.compile(r"\b(?:kubernetes|k8s)\b", re.I)),
    ("AWS", re.compile(r"\baws\b|\bamazon\s+web\s+services\b", re.I)),
    ("Azure", re.compile(r"\bazure\b|\bentra\s+id\b", re.I)),
    ("GCP", re.compile(r"\bgcp\b|\bgoogle\s+cloud\b", re.I)),
    ("Git", re.compile(r"\bgit(?:hub|lab)?\b(?!e)", re.I)),
    ("Linux", re.compile(r"\blinux\b|\bubuntu\b|\bred\s*hat\b", re.I)),
    ("Windows Server", re.compile(r"\bwindows\s+server\b|\bactive\s+directory\b|\bintune\b", re.I)),
    ("VMware", re.compile(r"\bvmware\b|\bhyper-v\b|\bveeam\b", re.I)),
    ("Réseaux (TCP/IP, VLAN, VPN)", re.compile(r"\b(?:tcp\/ip|vlan|dhcp|dns|fortinet|pare-feu|firewall)\b", re.I)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.I)),
    ("Django", re.compile(r"\bdjango\b", re.I)),
    ("Spring Boot", re.compile(r"\bspring\s*boot\b", re.I)),
    (".NET", re.compile(r"(?:(?<!\w)\.net\b|\basp\.net\b)", re.I)),
    ("CI/CD", re.compile(r"\bci[\/\-]cd\b|\bdevops\b|\bjenkins\b", re.I)),
    ("Agile / Scrum", re.compile(r"\b(?:agile|scrum)\b", re.I)),
    ("QA / Tests", re.compile(r"\b(?:assurance\s+qualit[eé]|selenium|cypress|pytest)\b", re.I)),
    ("IA / Machine Learning", re.compile(r"\b(?:intelligence\s+artificielle|machine\s+learning|llm|copilot|pytorch|tensorflow)\b", re.I)),
    ("HTML/CSS", re.compile(r"\b(?:html5?|css3?|tailwind|bootstrap|sass)\b", re.I)),
    ("Power BI / Tableau", re.compile(r"\b(?:power\s*bi|tableau\s+(?:software|desktop|server)|dax|ssrs|ssis)\b", re.I)),
    ("Microsoft 365 / SharePoint", re.compile(r"\b(?:(?:microsoft|office)\s*365|sharepoint|power\s*(?:apps|automate|platform)|exchange)\b", re.I)),
    ("SAP / ERP", re.compile(r"\b(?:sap|s\/4hana|abap|erp|netsuite)\b", re.I)),
    ("CRM (Salesforce / Dynamics)", re.compile(r"\b(?:salesforce|dynamics\s*365|d365|crm)\b", re.I)),
    ("ServiceNow / Jira / ITIL", re.compile(r"\b(?:servicenow|jira|confluence|glpi|itil)\b", re.I)),
    ("SQL Server / Oracle", re.compile(r"\b(?:sql\s+server|mssql|oracle|pl\/sql|t-sql)\b", re.I)),
    ("Terraform / Ansible", re.compile(r"\b(?:terraform|ansible|helm|openshift)\b", re.I)),
    ("PowerShell / Bash", re.compile(r"\b(?:powershell|bash)\b", re.I)),
    ("API REST / GraphQL", re.compile(r"\b(?:api\s+rest|rest(?:ful)?\s*api|graphql|microservices?)\b", re.I)),
    ("Mobile (iOS / Android)", re.compile(r"\b(?:android|ios|kotlin|swift|flutter|react\s+native)\b", re.I)),
    ("Cybersécurité (SIEM / SOC)", re.compile(r"\b(?:cybersecurit[eé]|cybersecurity|siem|iso\s*27001|soc|pentest\w*|zero\s+trust|edr|cisco)\b", re.I)),
    ("Soutien TI / Helpdesk", re.compile(r"\b(?:help\s*desk|service\s+desk|soutien\s+technique|soutien\s+aux\s+utilisateurs|bureau\s+de\s+d[eé]pannage|desktop\s+support)\b", re.I)),
]

# Compétences de base par code CNP 2021 TI lorsque l'annonce est un résumé partenaire sans liste d'outils
# (repris de la logique domain_hint de JobTailor_V3/src/pipeline/skills_catalog.py lignes 149-156)
CNP_DEFAULT_SKILLS: dict[str, list[str]] = {
    "20012": ["Agile / Scrum", "Gestion TI"],
    "21211": ["IA / Machine Learning", "SQL"],
    "21220": ["Cybersécurité (SIEM / SOC)", "Réseaux (TCP/IP, VLAN, VPN)"],
    "21221": ["SAP / ERP", "SQL"],
    "21222": ["SQL", "Windows Server"],
    "21223": ["SQL", "SQL Server / Oracle"],
    "21230": ["Linux", "SQL"],
    "21231": ["CI/CD", "Git"],
    "21232": ["Git", "SQL"],
    "21233": ["HTML/CSS", "JavaScript"],
    "21234": ["HTML/CSS", "JavaScript"],
    "22220": ["Réseaux (TCP/IP, VLAN, VPN)", "Windows Server"],
    "22221": ["Soutien TI / Helpdesk", "Windows Server"],
    "22222": ["QA / Tests", "Agile / Scrum"],
}

MONTHS_FR_EN: dict[str, int] = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# Table autonome des principales villes, municipalités et arrondissements du Québec -> 17 régions administratives
QUEBEC_CITY_TO_REGION_FALLBACK: dict[str, str] = {
    # 01 - Bas-Saint-Laurent
    "rimouski": "Bas-Saint-Laurent",
    "riviere du loup": "Bas-Saint-Laurent",
    "matane": "Bas-Saint-Laurent",
    "la pocatiere": "Bas-Saint-Laurent",
    # 02 - Saguenay--Lac-Saint-Jean
    "saguenay": "Saguenay--Lac-Saint-Jean",
    "chicoutimi": "Saguenay--Lac-Saint-Jean",
    "jonquiere": "Saguenay--Lac-Saint-Jean",
    "alma": "Saguenay--Lac-Saint-Jean",
    "roberval": "Saguenay--Lac-Saint-Jean",
    "dolbeau mistassini": "Saguenay--Lac-Saint-Jean",
    # 03 - Capitale-Nationale
    "quebec": "Capitale-Nationale",
    "ville de quebec": "Capitale-Nationale",
    "quebec city": "Capitale-Nationale",
    "sainte foy": "Capitale-Nationale",
    "charlesbourg": "Capitale-Nationale",
    "beauport": "Capitale-Nationale",
    "ancienne lorette": "Capitale-Nationale",
    "l ancienne lorette": "Capitale-Nationale",
    "saint augustin de desmaures": "Capitale-Nationale",
    "wendake": "Capitale-Nationale",
    "baie saint paul": "Capitale-Nationale",
    "la malbaie": "Capitale-Nationale",
    "pont rouge": "Capitale-Nationale",
    "donnacona": "Capitale-Nationale",
    # 04 - Mauricie
    "trois rivieres": "Mauricie",
    "shawinigan": "Mauricie",
    "la tuque": "Mauricie",
    "louiseville": "Mauricie",
    # 05 - Estrie
    "sherbrooke": "Estrie",
    "magog": "Estrie",
    "granby": "Estrie",
    "bromont": "Estrie",
    "cowansville": "Estrie",
    "coaticook": "Estrie",
    "valcourt": "Estrie",
    "windsor": "Estrie",
    "lac megantic": "Estrie",
    # 06 - Montréal (incluant arrondissements et villes liées)
    "montreal": "Montréal",
    "dorval": "Montréal",
    "pointe claire": "Montréal",
    "kirkland": "Montréal",
    "dollard des ormeaux": "Montréal",
    "beaconsfield": "Montréal",
    "baie d urfe": "Montréal",
    "sainte anne de bellevue": "Montréal",
    "westmount": "Montréal",
    "mont royal": "Montréal",
    "ville mont royal": "Montréal",
    "cote saint luc": "Montréal",
    "montreal est": "Montréal",
    "montreal ouest": "Montréal",
    "saint laurent": "Montréal",
    "ville saint laurent": "Montréal",
    "lachine": "Montréal",
    "lasalle": "Montréal",
    "verdun": "Montréal",
    "anjou": "Montréal",
    "outremont": "Montréal",
    "saint leonard": "Montréal",
    "pierrefonds": "Montréal",
    "rosemont": "Montréal",
    "hochelaga": "Montréal",
    # 07 - Outaouais
    "gatineau": "Outaouais",
    "hull": "Outaouais",
    "aylmer": "Outaouais",
    "buckingham": "Outaouais",
    "maniwaki": "Outaouais",
    # 08 - Abitibi-Témiscamingue
    "rouyn noranda": "Abitibi-Témiscamingue",
    "val d or": "Abitibi-Témiscamingue",
    "amos": "Abitibi-Témiscamingue",
    "la sarre": "Abitibi-Témiscamingue",
    # 09 - Côte-Nord
    "sept iles": "Côte-Nord",
    "baie comeau": "Côte-Nord",
    "fermont": "Côte-Nord",
    # 10 - Nord-du-Québec
    "chibougamau": "Nord-du-Québec",
    "matagami": "Nord-du-Québec",
    "lebel sur quevillon": "Nord-du-Québec",
    # 11 - Gaspésie--Îles-de-la-Madeleine
    "gaspe": "Gaspésie--Îles-de-la-Madeleine",
    "carleton sur mer": "Gaspésie--Îles-de-la-Madeleine",
    "chandler": "Gaspésie--Îles-de-la-Madeleine",
    "sainte anne des monts": "Gaspésie--Îles-de-la-Madeleine",
    # 12 - Chaudière-Appalaches
    "levis": "Chaudière-Appalaches",
    "saint georges": "Chaudière-Appalaches",
    "thetford mines": "Chaudière-Appalaches",
    "montmagny": "Chaudière-Appalaches",
    "sainte marie": "Chaudière-Appalaches",
    "beauceville": "Chaudière-Appalaches",
    "saint romuald": "Chaudière-Appalaches",
    "charny": "Chaudière-Appalaches",
    # 13 - Laval
    "laval": "Laval",
    # 14 - Lanaudière
    "terrebonne": "Lanaudière",
    "repentigny": "Lanaudière",
    "mascoudche": "Lanaudière",
    "mascouche": "Lanaudière",
    "joliette": "Lanaudière",
    "l assomption": "Lanaudière",
    "berthierville": "Lanaudière",
    "rawdon": "Lanaudière",
    # 15 - Laurentides
    "saint jerome": "Laurentides",
    "blainville": "Laurentides",
    "mirabel": "Laurentides",
    "saint eustache": "Laurentides",
    "boisbriand": "Laurentides",
    "sainte therese": "Laurentides",
    "rosemere": "Laurentides",
    "deux montagnes": "Laurentides",
    "saint sauveur": "Laurentides",
    "sainte agathe des monts": "Laurentides",
    "mont tremblant": "Laurentides",
    "lachute": "Laurentides",
    # 16 - Montérégie
    "longueuil": "Montérégie",
    "brossard": "Montérégie",
    "saint jean sur richelieu": "Montérégie",
    "saint hyacinthe": "Montérégie",
    "chateauguay": "Montérégie",
    "boucherville": "Montérégie",
    "salaberry de valleyfield": "Montérégie",
    "valleyfield": "Montérégie",
    "vaudreuil dorion": "Montérégie",
    "vaudreuil": "Montérégie",
    "sorel tracy": "Montérégie",
    "saint bruno de montarville": "Montérégie",
    "saint bruno": "Montérégie",
    "sainte julie": "Montérégie",
    "varennes": "Montérégie",
    "beloeil": "Montérégie",
    "chambly": "Montérégie",
    "candiac": "Montérégie",
    "la prairie": "Montérégie",
    "saint constant": "Montérégie",
    "sainte catherine": "Montérégie",
    "saint lambert": "Montérégie",
    "saint hubert": "Montérégie",
    "greenfield park": "Montérégie",
    "mont saint hilaire": "Montérégie",
    "marieville": "Montérégie",
    "saint antoine abbe": "Montérégie",
    "franklin": "Montérégie",
    "beauharnois": "Montérégie",
    "mercier": "Montérégie",
    "saint amable": "Montérégie",
    "contrecoeur": "Montérégie",
    "acton vale": "Montérégie",
    # 17 - Centre-du-Québec
    "drummondville": "Centre-du-Québec",
    "victoriaville": "Centre-du-Québec",
    "becancour": "Centre-du-Québec",
    "plessisville": "Centre-du-Québec",
    "nicolet": "Centre-du-Québec",
    "warwick": "Centre-du-Québec",
}

# Motifs d'exclusion stricte hors TI (0 faux positif : vente, RH, bâtiment, épicerie, audio, CNC, enneigement, etc.)
NON_TI_TITLE_EXCLUSIONS = re.compile(
    r"\b(?:"
    r"enneigement|menuisier|charpentier|ebeniste|soudeur|plombier|electricien|mecanicien|"
    r"programmeur\s+cnc|usinage|machiniste|journalier|manoeuvre|cariste|chauffeur|livreur|"
    r"commis|caissier|caissiere|epicerie|boulangerie|cuisinier|sous\s+chef|serveur|barista|"
    r"chef\s+des\s+ventes|representant\s+des\s+ventes|conseiller\s+aux\s+ventes|coordonnateur\s+ventes|"
    r"recrutement|recruteur|ressources\s+humaines|talent\s+acquisition|"
    r"audio\s+specialist|specialiste\s+audio|systemes\s+audiovisuels|audio\s+visual|"
    r"impression\s+3d|dessinateur\s+technique|"
    r"biens\s+de\s+consommation|consumer\s+goods|"
    r"youtube\s+creator|content\s+creator|office\s+assistant|adjoint\s+administratif|receptionniste|"
    r"video\s+annotation|data\s+annotator|"
    r"infirmier|infirmiere|prepose\s+aux\s+beneficiaires|comptable|paie|ventilation|"
    r"gerant\s+logistique|coordonnateur\s+logistique"
    r")\b",
    re.I,
)

UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
POSTAL_CODE_RE = re.compile(r"\b([A-CEGHJ-NPR-TVXY]\d[A-CEGHJ-NPR-TV-Z])\s?(\d[A-CEGHJ-NPR-TV-Z]\d)\b", re.I)


@dataclass
class JobBankOffer:
    """
    Modèle de données enrichi et unifié (Lot 4) pour l'ensemble des 5 sources
    (Guichet-Emplois, Talent.com, Jobboom, Jobillico, Remotive).
    Combine le socle Livrable 3, l'ADN de JobTailor_V3 et les meilleures briques de la classe.
    Zéro donnée inventée : None si absent.
    """

    id: str
    source_id: str
    url: str
    titre: Optional[str] = None
    titre_employeur: Optional[str] = None
    code_cnp: Optional[str] = None
    cnp_title: Optional[str] = None
    domaine_ti: Optional[str] = None
    entreprise: Optional[str] = None
    lieu: Optional[str] = None
    ville: Optional[str] = None
    region_administrative: Optional[str] = None
    code_postal: Optional[str] = None
    province: str = "QC"
    pays: str = "Canada"
    source: str = "guichet-emplois"
    source_partenaire: Optional[str] = None
    url_partenaire: Optional[str] = None
    date_publication: Optional[str] = None
    date_fin: Optional[str] = None
    type_poste: Optional[str] = None
    modalite: Optional[str] = None
    niveau_etudes: Optional[str] = None
    experience_requise: Optional[str] = None
    niveau_seniorite: Optional[str] = None
    salaire: Optional[str] = None
    salaire_min: Optional[float] = None
    salaire_max: Optional[float] = None
    unite_salaire: Optional[str] = None
    est_stage: bool = False
    statut_stage: str = "not_indicated"
    competences_cles: list[str] = field(default_factory=list)
    missions_cles: list[str] = field(default_factory=list)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    score_pertinence_dec: int = 0
    http_status: int = 200
    content_hash: Optional[str] = None
    description: Optional[str] = None
    date_extraction: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Alias de compatibilité avec les tests unitaires existants
    @property
    def title(self) -> Optional[str]:
        return self.titre

    @title.setter
    def title(self, value: Optional[str]) -> None:
        self.titre = value

    @property
    def employer(self) -> Optional[str]:
        return self.entreprise

    @employer.setter
    def employer(self, value: Optional[str]) -> None:
        self.entreprise = value

    @property
    def location(self) -> Optional[str]:
        return self.lieu

    @location.setter
    def location(self, value: Optional[str]) -> None:
        self.lieu = value

    @property
    def salary(self) -> Optional[str]:
        return self.salaire

    @salary.setter
    def salary(self, value: Optional[str]) -> None:
        self.salaire = value

    @property
    def published_at(self) -> Optional[str]:
        return self.date_publication

    @published_at.setter
    def published_at(self, value: Optional[str]) -> None:
        self.date_publication = value

    @property
    def valid_through(self) -> Optional[str]:
        return self.date_fin

    @valid_through.setter
    def valid_through(self, value: Optional[str]) -> None:
        self.date_fin = value

    @property
    def workplace_mode(self) -> Optional[str]:
        return self.modalite

    @workplace_mode.setter
    def workplace_mode(self, value: Optional[str]) -> None:
        self.modalite = value

    @property
    def employment_type(self) -> Optional[str]:
        return self.type_poste

    @employment_type.setter
    def employment_type(self, value: Optional[str]) -> None:
        self.type_poste = value

    @property
    def education_level(self) -> Optional[str]:
        return self.niveau_etudes

    @education_level.setter
    def education_level(self, value: Optional[str]) -> None:
        self.niveau_etudes = value

    @property
    def origin_partner(self) -> Optional[str]:
        return self.source_partenaire

    @origin_partner.setter
    def origin_partner(self, value: Optional[str]) -> None:
        self.source_partenaire = value

    @property
    def stage_status(self) -> str:
        return self.statut_stage

    @stage_status.setter
    def stage_status(self, value: str) -> None:
        self.statut_stage = value
        self.est_stage = value in ("confirmed_stage", "possible_stage")


# ==============================================================================
# Fonctions utilitaires : Nettoyage, URL, Hash SHA-256 (JobTailor_V3), Dates ISO
# ==============================================================================
def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    raw_str = UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), str(text))
    unescaped = html.unescape(html.unescape(raw_str))
    cleaned = re.sub(r"\s+", " ", unescaped).strip()
    return cleaned if cleaned else None


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _normalize_for_match(text: Optional[str]) -> str:
    """Normalise un texte en minuscules sans accents et retire les suffixes inclusifs (ne), (trice), .fe."""
    if not text:
        return ""
    no_acc = _strip_accents(str(text))
    # Retirer les marques de genre inclusives collées aux mots : Technicien(ne), Administrateur(trice), Chef.fe
    no_gender = re.sub(r"\((?:ne|e|trice|euse|ere|s)\)|[·.](?:fe|ne|e|trice|euse)\b", "", no_acc)
    cleaned = re.sub(r"[^\w#+]+", " ", no_gender)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_job_url(raw_url: Optional[str]) -> str:
    """
    Nettoie une URL d'offre sans jamais la reconstruire (repris de JobTailor_V3/src/watchers/http_client.py) :
    retire ;jsessionid=... et les paramètres de tracking (utm_*, fbclid, gclid, lshs, etc.).
    """
    if not raw_url:
        return ""
    cleaned = html.unescape(raw_url.strip())
    cleaned = re.sub(r";jsessionid=[^?&#/]+", "", cleaned, flags=re.I)

    parsed = urlsplit(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return cleaned

    netloc = parsed.netloc.lower()
    path = parsed.path
    query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_pairs = [(k, v) for (k, v) in query_pairs if k.lower() not in TRACKING_PARAMS]
    new_query = urlencode(filtered_pairs)
    return urlunsplit((parsed.scheme.lower(), netloc, path, new_query, ""))


def compute_content_hash(
    url: Optional[str],
    title: Optional[str],
    company: Optional[str],
    summary: Optional[str],
) -> str:
    """
    Calcule l'empreinte SHA-256 unique (16 caractères hex) d'une offre
    (repris de JobTailor_V3/src/watchers/http_client.py).
    """
    norm_u = normalize_job_url(url)
    t_str = (title or "").strip().lower()
    c_str = (company or "").strip().lower()
    s_str = (summary or "").strip()[:300].lower()
    payload = f"{norm_u}|{t_str}|{c_str}|{s_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_iso_date(raw_date: Optional[str]) -> Optional[str]:
    """Convertit une date brute ('16 novembre 2026', '2026-11-16T...') en format ISO AAAA-MM-JJ."""
    if not raw_date:
        return None
    val = raw_date.strip()
    iso_m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", val)
    if iso_m:
        return iso_m.group(0)

    tokens = re.findall(r"[^\W\d_]+|\d+", _strip_accents(val))
    nums = [int(t) for t in tokens if t.isdigit()]
    months = [MONTHS_FR_EN[t] for t in tokens if t in MONTHS_FR_EN]
    year = next((n for n in nums if n > 1900), None)
    day = next((n for n in nums if 1 <= n <= 31), None)
    if year and day and months:
        try:
            return date(year, months[0], day).isoformat()
        except ValueError:
            pass
    return val


def extract_tech_skills(*texts: Optional[str]) -> list[str]:
    """Détecte les compétences TI présentes dans les textes fournis sans faux positifs."""
    combined = " ".join(t for t in texts if t)
    if not combined:
        return []
    found: list[str] = []
    for label, pattern in TECH_PATTERNS:
        if pattern.search(combined) and label not in found:
            found.append(label)
    return sorted(found)


def detect_stage_status(title: Optional[str], description: Optional[str], student_filter: bool = False) -> str:
    """Classifie si l'offre est un stage en excluant les mentions d'encadrement ('superviser des stagiaires')."""
    combined = f"{title or ''} {description or ''}".lower()
    cleaned = re.sub(
        r"\b(superviser|encadrer|former|accompagner|diriger)\s+(des|les|un|une|nos)?\s*(stagiaires?|étudiants?)\b",
        "",
        combined,
    )
    if re.search(r"\bstage\s*:\s*ce\s+poste\s+est\s+un\s+stage\b", _strip_accents(cleaned)):
        return "confirmed_stage"
    if re.search(r"\b(stage|stagiaire|intern|internship|co-op|coop|alternance|ate)\b", cleaned):
        return "confirmed_stage"
    if student_filter or re.search(r"\b(emploi\s+étudiant|étudiant\(e\)|student\s+job)\b", cleaned):
        return "possible_stage"
    return "not_indicated"


# ==============================================================================
# Classification CNP 2021 TI (14 codes) & Filtrage Anti-Bruit Hors TI (5 Sources)
# ==============================================================================
def classify_cnp_2021(
    title: Optional[str],
    description: Optional[str] = None,
    cnp_title: Optional[str] = None,
    competences: Optional[list[str]] = None,
    source: str = "",
) -> Optional[tuple[str, str]]:
    """
    Classifie une offre dans l'un des 14 codes CNP 2021 TI et retourne `(code_cnp, cnp_title_officiel)`.
    Retourne `None` si l'offre est hors TI (0 faux positif : vente, RH, audio, CNC, enneigement,
    menuiserie, épicerie, YouTube Creator, Office Assistant, etc.).
    """
    primary_norm = _normalize_for_match(title or cnp_title or "")
    secondary_norm = _normalize_for_match(cnp_title or "") if (title and cnp_title and title != cnp_title) else ""
    t_norm = f"{primary_norm} {secondary_norm}".strip()
    d_norm = _normalize_for_match((description or "")[:3000])

    if not t_norm:
        return None

    # 1. Exclusion stricte des postes hors TI par l'intitulé
    if NON_TI_TITLE_EXCLUSIONS.search(t_norm):
        return None

    def _match_cnp_on_title(cand_norm: str) -> Optional[tuple[str, str]]:
        if not cand_norm:
            return None
        # 21220 - Spécialistes en cybersécurité
        if re.search(
            r"\b(?:cybersecurit\w*|cyber\s*securit\w*|securite\s+informatique|securite\s+des\s+technologies|"
            r"securite\s+des\s+ti|securite\s+de\s+l\s+information|devsecops|pentest\w*|infosec)\b",
            cand_norm,
        ):
            return "21220", CNP_2021_TI_DICT["21220"]

        # 21211 - Spécialistes des données (Data Science, Data Engineering, BI, IA)
        if re.search(
            r"\b(?:data\s+scientist\w*|scientifique\w*\s+de\s+donnees|specialiste\w*\s+des\s+donnees|"
            r"data\s+engineer\w*|ingenieur\w*\s+de\s+donnees|data\s+analyst\w*|analyste\w*\s+de\s+donnees|"
            r"analyste\w*\s+des\s+operations.*donnees|intelligence\s+artificielle|artificial\s+intelligence|"
            r"\bia\b|\bai\b|machine\s+learning|intelligence\s+d\s+affaires|business\s+intelligence|\bbi\b|"
            r"valorisation\s+des\s+donnees|obiee)\b",
            cand_norm,
        ):
            return "21211", CNP_2021_TI_DICT["21211"]

        # 21223 - Analystes de bases de données et administrateurs de données
        if re.search(
            r"\b(?:bases?\s+de\s+donnees|databases?|\bdba\b|administrateur\w*\s+de\s+donnees|"
            r"gestion\s+des\s+donnees|donnees\s+maitres)\b",
            cand_norm,
        ):
            return "21223", CNP_2021_TI_DICT["21223"]

        # 22222 - Évaluateurs de systèmes informatiques (QA / Tests)
        if re.search(
            r"\b(?:assurance\s+qualite|assurance\s+de\s+la\s+qualite|quality\s+assurance|\bqa\b|"
            r"testeur\w*|testeuse\w*|tester\w*|sdet|evaluateur\w*\s+de\s+systemes|analyste\s+qualite)\b",
            cand_norm,
        ):
            return "22222", CNP_2021_TI_DICT["22222"]

        # 22221 - Agents de soutien aux utilisateurs (Helpdesk, Support TI, Technicien informatique)
        if re.search(
            r"\b(?:soutien\s+aux\s+utilisateurs|soutien\s+technique|support\s+technique|technical\s+support|"
            r"soutien\s+informatique|support\s+informatique|help\s*desk|service\s+desk|bureau\s+de\s+depannage|"
            r"desktop\s+support|technicien\w*\s+en\s+informatique|technicien\w*\s+informatique|"
            r"technicien\w*\s+ti|soutien\s+ti|support\s+applicatif|soutien\s+des\s+applications|"
            r"support\s+dynamics|end\s+user\s+computing|point\s+of\s+service|\bpos\b)\b",
            cand_norm,
        ):
            return "22221", CNP_2021_TI_DICT["22221"]

        # 22220 - Techniciens de réseaux informatiques (Réseaux, Sysadmin, Infrastructure)
        if re.search(
            r"\b(?:reseaux?|network\w*|administrateur\w*\s+de\s+systemes?|administrateur\w*\s+systemes?|"
            r"administrateur\w*\s+des\s+systemes|system\s+administrator|sysadmin|infrastructure\s+informatique|"
            r"infrastructure\s+ti|centre\s+de\s+donnees|data\s+center|telecommunications)\b",
            cand_norm,
        ):
            return "22220", CNP_2021_TI_DICT["22220"]

        # 20012 - Gestionnaires des systèmes informatiques (Directeur TI, Chef d'équipe TI, Gestionnaire TI)
        if re.search(
            r"\b(?:directeur\w*\s+ti|directeur\w*\s+technique\s+cloud|directeur\w*\s+des\s+operations\s+informatiques|"
            r"directeur\w*\s+de\s+l\s+ingenierie\s+logicielle|director\s+of\s+it|software\s+engineering\s+director|"
            r"head\s+of\s+engineering|chef\w*\s+d\s+equipe\s+ti|chef\w*\s+d\s+equipe\s+systemes|gestionnaire\s+ti|"
            r"gestionnaire.*gouvernance\s+ti|it\s+manager|chef\s+de\s+projet.*ti|gestionnaire\s+de\s+projet.*ti|"
            r"gestionnaire\s+du\s+programme\s+technique|technical\s+program\s+manager|gestionnaire\s+du\s+web|"
            r"delivery\s+lead)\b",
            cand_norm,
        ):
            return "20012", CNP_2021_TI_DICT["20012"]

        # 21233 - Concepteurs Web (Web Designer, UI/UX, Accessibilité Web, Médias numériques)
        if re.search(
            r"\b(?:concepteur\w*\s+web|conceptrice\w*\s+web|web\s+designer|ui\s+ux|ux\s+ui|"
            r"product\s+service\s+designer|designer\s+de\s+service|accessibility\s+specialist|"
            r"accessibilite\s+web|medias\s+numeriques|digital\s+media)\b",
            cand_norm,
        ):
            return "21233", CNP_2021_TI_DICT["21233"]

        # 21234 - Développeurs et programmeurs Web (Web, Frontend, Fullstack, React, Angular, PHP)
        if re.search(
            r"\b(?:developpeur\w*\s+web|developpeuse\w*\s+web|web\s+developer|programmeur\w*\s+web|"
            r"front\s*end|full\s*stack|react|angular|vue\s*js|node\s*js|php|wordpress|drupal)\b",
            cand_norm,
        ):
            return "21234", CNP_2021_TI_DICT["21234"]

        # 21231 - Ingénieurs et concepteurs en logiciel (Software Engineer, Architecte logiciel/cloud, DevOps, SRE)
        if re.search(
            r"\b(?:ingenieur\w*\s+logiciel|software\s+engineer\w*|architecte\w*\s+logiciel\w*|"
            r"architecte\w*\s+organique\s+en\s+logiciels|architecte\w*\s+d\s+applications|"
            r"architecte\w*\s+de\s+solutions|architecture\s+de\s+solution|architecte\w*\s+d\s+infrastructure|"
            r"architecte\w*\s+infrastructure|devops|processus\s+de\s+developpement\s+et\s+d\s+exploitation|"
            r"site\s+reliability|\bsre\b|infonuagique|cloud|microprocesseur\w*|ordinateur\s+quantique|"
            r"deploiement\s+d\s+applications|solutions\s+engineer)\b",
            cand_norm,
        ):
            return "21231", CNP_2021_TI_DICT["21231"]

        # 21232 - Développeurs et programmeurs de logiciels
        if re.search(
            r"\b(?:developpeur\w*\s+de\s+logiciels?|developpeuse\w*\s+de\s+logiciels?|"
            r"developpeur\w*\s+logiciel\w*|software\s+developer\w*|developpeur\w*|developpeuse\w*|"
            r"developer\w*|programmeur\w*|programmeuse\w*|programmer\w*|analyste\s+programmeur\w*|"
            r"analyste\s+programmeuse\w*|back\s*end|python|java|net\b|c#|c\+\+|rails|servicenow|netsuite)\b",
            cand_norm,
        ):
            return "21232", CNP_2021_TI_DICT["21232"]

        # 21230 - Développeurs de systèmes informatiques et programmeurs
        if re.search(
            r"\b(?:developpeur\w*\s+de\s+systemes|programmeur\w*\s+de\s+systemes|"
            r"integration\s+des\s+systemes|integration\s+de\s+donnees|systemes\s+embarques|embedded\s+systems)\b",
            cand_norm,
        ):
            return "21230", CNP_2021_TI_DICT["21230"]

        # 21221 - Spécialistes des systèmes d'affaires (Analyste d'affaires TI, Analyste fonctionnel, ERP/SAP/CRM)
        if re.search(
            r"\b(?:analyste\w*\s+d\s+affaires?|analyste\w*\s+d\s+affaies|business\s+analyst|"
            r"analyste\w*\s+fonctionnel\w*|systemes\s+d\s+affaires|architecte\w*\s+de\s+systemes\s+commerciaux|"
            r"\bsap\b|\berp\b|dynamics|\bd365\b|salesforce|product\s+owner|product\s+manager|"
            r"chef\s+de\s+produit|transformation\s+d\s+entreprise|implantation\s+de\s+processus|\becm\b)\b",
            cand_norm,
        ):
            return "21221", CNP_2021_TI_DICT["21221"]

        # 21222 - Spécialistes en informatique (Analyste en informatique, Analyste TI, Gouvernance/Audit TI)
        if re.search(
            r"\b(?:analyste\w*\s+en\s+informatique|analyste\w*\s+en\s+technologie|analyste\w*\s+ti|"
            r"analyste\w*\s+de\s+systemes|architecte\w*\s+de\s+systemes|specialiste\w*\s+en\s+informatique|"
            r"specialiste\w*\s+en\s+configuration\s+informatique|documentation\s+technique|"
            r"redacteur\w*\s+technique|redactrice\w*\s+technique|auditeur\w*\s+ti|gouvernance\s+ti)\b",
            cand_norm,
        ):
            return "21222", CNP_2021_TI_DICT["21222"]
        return None

    # 2. Priorité à l'intitulé principal (ex. titre_employeur réel), puis repli sur le titre CNP
    res_primary = _match_cnp_on_title(primary_norm)
    if res_primary is not None:
        return res_primary

    res_secondary = _match_cnp_on_title(secondary_norm)
    if res_secondary is not None:
        return res_secondary

    # 3. Repli strict sur la description si et seulement si l'informatique / logiciel est explicitement exigé
    if re.search(
        r"\b(?:baccalaureat\s+en\s+informatique|dec\s+en\s+informatique|developpement\s+logiciel|"
        r"software\s+development|infrastructure\s+informatique|systemes\s+informatiques)\b",
        d_norm,
    ):
        if re.search(r"\b(?:gestion\s+de\s+projets?|responsable\s+de\s+projets?|programme)\b", t_norm):
            return "20012", CNP_2021_TI_DICT["20012"]
        return "21222", CNP_2021_TI_DICT["21222"]

    if source == "guichet-emplois":
        return "21222", CNP_2021_TI_DICT["21222"]

    return None


def detect_ti_domain(
    title: Optional[str],
    description: Optional[str] = None,
    code_cnp: Optional[str] = None,
    competences: Optional[list[str]] = None,
) -> str:
    """
    Identifie le sous-domaine TI principal de l'offre (étendu de JobTailor_V3/src/pipeline/skills_catalog.py).
    Retourne l'une des 6 valeurs canoniques :
    `tech_backend`, `tech_frontend`, `tech_support`, `devops_cloud`, `data_ia`, `cybersecurite`.
    """
    t_norm = _normalize_for_match(title)
    d_norm = _normalize_for_match((description or "")[:1200])
    skills_set = {s.lower() for s in (competences or [])}

    if code_cnp == "21220" or re.search(
        r"\b(?:cybersecurit\w*|cyber\s*securit\w*|securite\s+informatique|securite\s+des\s+ti|devsecops|pentest\w*|infosec)\b",
        t_norm,
    ):
        return "cybersecurite"

    if code_cnp in ("21211", "21223") or re.search(
        r"\b(?:data|donnees|intelligence\s+artificielle|\bia\b|\bai\b|machine\s+learning|\bbi\b|business\s+intelligence|intelligence\s+d\s+affaires|database|\bdba\b|obiee|tableau|power\s+bi)\b",
        t_norm,
    ):
        return "data_ia"

    if re.search(
        r"\b(?:devops|infonuagique|cloud|site\s+reliability|\bsre\b|kubernetes|openshift|deploiement)\b",
        t_norm,
    ):
        return "devops_cloud"

    if code_cnp == "21233" or (
        re.search(
            r"\b(?:front\s*end|concepteur\w*\s+web|web\s+designer|ui\s+ux|ux\s+ui|react|angular|vue|integrateur\s+web|accessibilite|medias\s+numeriques|digital\s+media)\b",
            t_norm,
        )
        and not re.search(r"\b(?:full\s*stack|back\s*end|postgresql|python|java|c#)\b", t_norm)
    ):
        return "tech_frontend"

    if code_cnp in ("22220", "22221") or re.search(
        r"\b(?:soutien|support|help\s*desk|service\s+desk|depannage|technicien\w*|reseaux?|network\w*|administrateur\w*\s+systeme\w*|administrateur\w*\s+des\s+systemes|system\s+administrator|sysadmin|infrastructure|\bpos\b)\b",
        t_norm,
    ):
        return "tech_support"

    if code_cnp == "21234" and any(s in skills_set for s in ("react", "angular", "vue.js")) and "python" not in skills_set and "java" not in skills_set and "c#" not in skills_set:
        return "tech_frontend"

    if any(s in skills_set for s in ("kubernetes", "aws", "azure", "gcp")) and "ci/cd" in skills_set and re.search(r"\b(?:infrastructure|architecte|cloud|devops)\b", f"{t_norm} {d_norm}"):
        return "devops_cloud"

    if "ia / machine learning" in skills_set and re.search(r"\b(?:data|donnees|ia|ai|machine\s+learning)\b", d_norm):
        return "data_ia"

    return "tech_backend"


# ==============================================================================
# Extraction : Missions clés, Études, Expérience & Séniorité, Salaire, Régions QC
# ==============================================================================
def extract_key_missions(description: Optional[str], rdfa_tasks: Optional[list[str]] = None) -> list[str]:
    """
    Extrait la liste des responsabilités / tâches clés (`missions_cles`) d'une offre
    (RDFa `property="responsibilities"`, bloc `Tâches:` Guichet-Emplois, ou puces de description).
    """
    missions: list[str] = []
    seen: set[str] = set()

    def _add_mission(candidate: str) -> None:
        cleaned = re.sub(r"^[\s\-•*·▪‣\d.)]+", "", candidate).strip().rstrip(";")
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) < 18 or len(cleaned) > 220:
            return
        low = cleaned.lower()
        if any(
            noise in low
            for noise in (
                "semaines de vacances",
                "assurance collective",
                "régime de retraite",
                "programme d'accès à l'égalité",
                "équité en matière d'emploi",
                "numéro du permis cnesst",
                "veuillez envoyer votre cv",
                "horaire flexible",
                "options de conditions d'emploi",
            )
        ):
            return
        key = _normalize_for_match(cleaned)
        if key and key not in seen:
            seen.add(key)
            missions.append(cleaned)

    for task in rdfa_tasks or []:
        _add_mission(task)
        if len(missions) >= 6:
            return missions

    if not description:
        return missions

    # 1. Format Guichet-Emplois : "Tâches: Phrase 1. Phrase 2. Options de conditions..."
    m_ge_tasks = re.search(
        r"T[âa]ches\s*:\s*(.+?)(?:Options de conditions|Exp[ée]rience\s*:|Renseignements|$)",
        description,
        re.I,
    )
    if m_ge_tasks:
        for sent in re.split(r"(?<=\.)\s+", m_ge_tasks.group(1)):
            _add_mission(sent)
            if len(missions) >= 6:
                return missions

    # 2. Puces explicites (•, - ) ou phrases après une entête de responsabilités
    resp_section = description
    m_sec = re.search(
        r"(?:Principales\s+responsabilit[ée]s|Responsabilit[ée]s\s+principales|Responsabilit[ée]s\s+sp[ée]cifiques|"
        r"T[âa]ches\s+et\s+responsabilit[ée]s|Vos\s+responsabilit[ée]s|Ce\s+que\s+vous\s+ferez|"
        r"Les\s+t[âa]ches\s+typiques|VOTRE\s+R[ÔO]LE|Key\s+Responsibilities)\s*:?\s*(.+)",
        description,
        re.I,
    )
    if m_sec:
        resp_section = m_sec.group(1)[:2500]
        # Couper avant la section Exigences / Qualifications / Profil
        resp_section = re.split(
            r"\b(?:Qualifications\s+et\s+exp[ée]rience|Exigences|Profil\s+recherch[ée]|Ce\s+que\s+vous\s+apportez|"
            r"Formation\s+et\s+exp[ée]rience|Required\s+Qualifications|Scolarit[ée])\b",
            resp_section,
            maxsplit=1,
            flags=re.I,
        )[0]

    for chunk in re.split(r"(?:•|\s+-\s+|;\s+|\.\s+)", resp_section):
        _add_mission(chunk)
        if len(missions) >= 6:
            break

    return missions


def extract_education_level(existing_edu: Optional[str], description: Optional[str]) -> Optional[str]:
    """
    Détermine le niveau d'études mentionné dans l'offre sans jamais inventer de donnée.
    Conserve la valeur RDFa `property="educationRequirements"` lorsqu'elle est déjà extraite.
    """
    if existing_edu and existing_edu.strip():
        return existing_edu.strip()
    if not description:
        return None

    # Format Guichet-Emplois "Études: Baccalauréat."
    m_ge = re.search(r"[ÉE]tudes\s*:\s*([^\.]+)", description)
    if m_ge:
        val = m_ge.group(1).strip()
        if val and "aucun" not in val.lower():
            return val

    norm_d = _strip_accents(description.lower())
    has_dec = bool(
        re.search(
            r"\b(?:dec|aec|etudes\s+collegiales|diplome\s+collegial|cegep|college\s+diploma|"
            r"techniques\s+de\s+l\s*informatique)\b",
            norm_d,
        )
    )
    has_bac = bool(
        re.search(
            r"\b(?:baccalaureat|bachelor|diplome\s+universitaire|universitaire\s+de\s+premier\s+cycle)\b",
            norm_d,
        )
    )
    has_grad = bool(re.search(r"\b(?:doctorat|phd|maitrise\s+en\s+informatique)\b", norm_d))
    has_dep = bool(re.search(r"\b(?:dep|diplome\s+d\s*etudes\s+professionnelles|diplome\s+d\s*etudes\s+secondaires)\b", norm_d))

    if has_grad and not has_bac and not has_dec:
        return "Universitaire (Maîtrise / Doctorat)"
    if has_dec and has_bac:
        return "Collégial (DEC / AEC) ou Universitaire (Baccalauréat)"
    if has_dec:
        return "Collégial (DEC / AEC)"
    if has_bac:
        return "Universitaire (Baccalauréat)"
    if has_dep:
        return "Secondaire / DEP"
    if re.search(r"\b(?:diplome\s+en\s+informatique|certificat\s+ou\s+diplome\s+en\s+science\s+informatique|degree\s+or\s+diploma\s+in\s+computer\s+science)\b", norm_d):
        return "Diplôme postsecondaire en informatique (DEC ou Baccalauréat)"
    return None


def extract_experience_and_seniority(
    title: Optional[str],
    description: Optional[str],
    est_stage: bool = False,
    existing_exp: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Extrait `(experience_requise, niveau_seniorite)`.
    `niveau_seniorite` vaut toujours l'un des 4 niveaux :
    `Étudiant / Stage`, `Junior / DEC`, `Intermédiaire`, `Senior`.
    """
    exp_str: Optional[str] = existing_exp.strip() if existing_exp and existing_exp.strip() else None
    desc = description or ""

    if not exp_str and desc:
        m_ge_exp = re.search(r"Exp[ée]rience\s*:\s*([^\.]+)", desc)
        if m_ge_exp:
            exp_str = m_ge_exp.group(1).strip()

    if not exp_str and desc:
        norm_d = _strip_accents(desc.lower())
        m_range = re.search(
            r"\b(\d{1,2}\s*(?:a|-|–|to)\s*\d{1,2}|trois\s+a\s+cinq|deux\s+a\s+trois|un\s+a\s+trois)\s*(?:ans?|annees?|years?)\s+(?:d['’\s]*experience|of\s+experience|dans\s+un\s+environnement)",
            norm_d,
        )
        if m_range:
            raw_r = m_range.group(1).replace("trois a cinq", "3 à 5").replace("deux a trois", "2 à 3").replace("un a trois", "1 à 3")
            raw_r = re.sub(r"\s+a\s+", " à ", raw_r)
            exp_str = f"{raw_r} ans"
        else:
            m_min = re.search(
                r"(?:minimum\s+de\s+|au\s+moins\s+|at\s+least\s+|minimum\s+of\s+|posseder\s+un\s+minimum\s+de\s+(?:[a-z]+\s*\()?)(\d{1,2})\s*\)?\s*\+?\s*(?:ans?|annees?|years?)",
                norm_d,
            )
            if m_min:
                exp_str = f"{m_min.group(1)} ans minimum"
            else:
                m_yrs = re.search(
                    r"\b(\d{1,2})\s*\+?\s*(?:ans?|annees?|years?)\s+(?:ou\s+plus\s+|et\s+plus\s+)?(?:d['’\s]*experience|of\s+experience)",
                    norm_d,
                )
                if m_yrs:
                    exp_str = f"{m_yrs.group(1)} ans"
                else:
                    m_months = re.search(r"\b(\d{1,2})\s*mois\s+d['’\s]*experience", norm_d)
                    if m_months:
                        exp_str = f"{m_months.group(1)} mois"

    if not exp_str and est_stage:
        exp_str = "Aucune (Stage)"

    # Détermination de la séniorité
    t_norm = _normalize_for_match(title)
    if est_stage or re.search(r"\b(?:stage|stagiaire|intern|internship|co\s*op|etudiant\w*)\b", t_norm):
        return exp_str, "Étudiant / Stage"

    if re.search(r"\b(?:junior|jr|debutant\w*|entry\s+level|niveau\s+1)\b", t_norm):
        return exp_str, "Junior / DEC"

    if re.search(
        r"\b(?:senior|sr|principal\w*|lead|chef\w*|directeur\w*|directrice\w*|director|head|architecte\w*|architect|gestionnaire|manager)\b",
        t_norm,
    ):
        return exp_str, "Senior"

    if re.search(r"\b(?:intermediaire|intermediate|int)\b", t_norm):
        return exp_str, "Intermédiaire"

    # Analyse du nombre d'années dans exp_str
    if exp_str:
        exp_low = _strip_accents(exp_str.lower())
        if any(k in exp_low for k in ("aucune", "atout", "mois")) and "24 mois" not in exp_low and "36 mois" not in exp_low:
            return exp_str, "Junior / DEC"
        m_num = re.search(r"\b(\d{1,2})\b", exp_low)
        if m_num:
            yrs = int(m_num.group(1))
            if "mois" in exp_low:
                yrs = yrs // 12
            if yrs < 2:
                return exp_str, "Junior / DEC"
            if yrs >= 5:
                return exp_str, "Senior"
            return exp_str, "Intermédiaire"

    if re.search(r"\b(?:technicien\w*|agent\w*\s+de\s+soutien|soutien\s+technique|help\s*desk|desktop\s+support|bureau\s+de\s+depannage)\b", t_norm):
        return exp_str, "Junior / DEC"

    return exp_str, "Intermédiaire"


def _parse_number_token(token: str, has_k: bool = False) -> Optional[float]:
    cleaned = token.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not cleaned:
        return None
    dec = re.search(r"[.,](\d{1,2})$", cleaned)
    try:
        if dec:
            whole = re.sub(r"[.,]", "", cleaned[: dec.start()]) or "0"
            val = float(f"{whole}.{dec.group(1)}")
        else:
            val = float(re.sub(r"[.,]", "", cleaned))
        return round(val * 1000.0 if has_k else val, 2)
    except ValueError:
        return None


def parse_salary_details(
    salaire_str: Optional[str],
    description: Optional[str] = None,
    title: Optional[str] = None,
) -> tuple[Optional[str], Optional[float], Optional[float], Optional[str]]:
    """
    Extrait `(salaire_texte, salaire_min, salaire_max, unite_salaire)` sans jamais convertir
    un taux horaire en salaire annuel (conformité AGENTS.md).
    `unite_salaire` vaut `'heure'`, `'année'`, `'mois'`, `'semaine'`, `'jour'` ou `None`.
    """
    raw_sal = _clean_text(salaire_str)

    # Si salaire non renseigné dans l'en-tête, chercher une mention explicite dans la description ou le titre
    if not raw_sal and (description or title):
        search_space = f"{title or ''} {description or ''}"
        m_desc_sal = (
            re.search(
                r"Salaire\s*:\s*Entre\s+([\d\s,.]+)\s*\$\s*et\s*([\d\s,.]+)\s*\$\s*(?:/\s*(heure|an|ann[ée]e)|de\s+l[’']heure|par\s+ann[ée]e)",
                search_space,
                re.I,
            )
            or re.search(
                r"salaire[^.:\n]{0,45}peut\s+varier\s+entre\s+([\d\s,.]+)\s*\$\s*et\s*([\d\s,.]+)\s*\$\s*(de\s+l[’']heure|/\s*h|par\s+ann[ée]e)",
                search_space,
                re.I,
            )
            or re.search(
                r"Salaire\s*:\s*(\d{2,3}\s*000)\s*\$\s*[\?à\-–]\s*(\d{2,3}\s*000)\s*\$",
                search_space,
                re.I,
            )
            or re.search(
                r"\b(\d{2,3})\s*k\s*\$\s*à\s*(\d{2,3})\s*k\s*\$",
                search_space,
                re.I,
            )
            or re.search(
                r"[–\-]\s*(\d{2}(?:[,.]\d{1,2})?)\s*\$\s*/\s*h\b",
                search_space,
                re.I,
            )
        )
        if m_desc_sal:
            raw_sal = m_desc_sal.group(0).strip(" –-:")

    if not raw_sal:
        return None, None, None, None

    # Couper "/ 40 heures par semaine" pour ne pas capter "40" comme salaire_max
    sal_part = re.split(r"/\s*\d+\s*heures", raw_sal, flags=re.I)[0]
    norm_s = _strip_accents(sal_part.lower())

    unit: Optional[str] = None
    if re.search(r"\b(?:heure|hour|hourly|hr)\b|/\s*h(?:eure)?\b", norm_s):
        unit = "heure"
    elif re.search(r"\b(?:jour|day|daily)\b", norm_s):
        unit = "jour"
    elif re.search(r"\b(?:semaine|week|weekly)\b", norm_s):
        unit = "semaine"
    elif re.search(r"\b(?:mois|month|monthly)\b", norm_s):
        unit = "mois"
    elif re.search(r"\b(?:annee|annuel|annuelle|an|year|yearly|annual)\b", norm_s):
        unit = "année"

    amount_re = re.compile(
        r"(?P<num>\d{1,3}(?:[ \u00a0\u202f,.]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?P<k>[kK])?"
    )
    amounts: list[float] = []
    for m in amount_re.finditer(sal_part):
        val = _parse_number_token(m.group("num"), bool(m.group("k")))
        if val is not None and val > 0:
            amounts.append(val)
        if len(amounts) >= 2:
            break

    if not amounts:
        return raw_sal, None, None, unit

    min_v = amounts[0]
    max_v = amounts[1] if len(amounts) > 1 else amounts[0]
    if max_v < min_v:
        min_v, max_v = max_v, min_v

    if unit is None and min_v >= 25000:
        unit = "année"

    return raw_sal, min_v, max_v, unit


@lru_cache(maxsize=1)
def _load_quebec_regions_index() -> dict[str, str]:
    """
    Charge l'index des municipalités et arrondissements du Québec vers les 17 régions administratives.
    Combine la table autonome intégrée (`QUEBEC_CITY_TO_REGION_FALLBACK`) et `regions_quebec.csv` s'il est présent.
    """
    index = dict(QUEBEC_CITY_TO_REGION_FALLBACK)
    candidate_csvs = [
        Path(__file__).parent / "regions_quebec.csv",
        Path(__file__).parent.parent.parent / "kandet" / "03-amelioration-preuve-de-concept" / "regions_quebec.csv",
    ]
    for csv_path in candidate_csvs:
        if csv_path.is_file():
            try:
                with csv_path.open(encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f, delimiter=";"):
                        nom = _normalize_for_match(row.get("nom"))
                        reg = re.sub(r"\s*\(\d+\)\s*$", "", row.get("region") or "").strip()
                        if nom and reg and nom not in index:
                            index[nom] = reg
                break
            except OSError:
                continue
    return index


def resolve_quebec_location(
    lieu: Optional[str],
    province: Optional[str] = "QC",
    description: Optional[str] = None,
    code_postal: Optional[str] = None,
) -> tuple[Optional[str], str, Optional[str], Optional[str]]:
    """
    Extrait `(ville, province_normalisee, region_administrative, code_postal)`.
    Résout la région parmi les 17 régions administratives du Québec lorsque l'offre est située au Québec.
    """
    raw_loc = (lieu or "").strip()
    prov = (province or "QC").strip()
    if prov.lower() in ("quebec", "québec", "qc"):
        prov = "QC"

    # Détecter code province explicite dans lieu : "Montréal (QC)" ou "Ottawa, ON"
    m_prov = re.search(r"(?:\(([A-Z]{2})\)|,\s*([A-Z]{2})\b)", raw_loc)
    if m_prov:
        detected_p = m_prov.group(1) or m_prov.group(2)
        if detected_p in {"QC", "ON", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}:
            prov = detected_p

    # Extraction de la ville propre
    city: Optional[str] = None
    if raw_loc and not any(
        k in _strip_accents(raw_loc.lower())
        for k in (
            "teletravail",
            "differentes regions",
            "lieu de travail indetermine",
            "amerique du nord",
            "worldwide",
            "non specifie",
        )
    ):
        cleaned_city = re.sub(r"\s*\([^)]*\)", "", raw_loc)
        cleaned_city = re.sub(r",\s*[A-Za-z]{2,}\s*$", "", cleaned_city)
        cleaned_city = re.sub(r"\b(?:City|Hybride|Télétravail|Sur\s+place|Sur\s+la\s+route)\b", "", cleaned_city, flags=re.I).strip(" ,-")
        if cleaned_city and cleaned_city.lower() not in ("canada", "qc", "quebec", "ontario"):
            city = cleaned_city
        elif cleaned_city.lower() in ("quebec", "québec") and ("city" in raw_loc.lower() or "(qc)" in raw_loc.lower() or ", qc" in raw_loc.lower()):
            city = "Québec"

    # Résolution de la région administrative du Québec (17 régions)
    region_admin: Optional[str] = None
    if prov == "QC" and city:
        idx = _load_quebec_regions_index()
        city_key = _normalize_for_match(city)
        region_admin = idx.get(city_key)
        if not region_admin:
            # Essayer sans préfixe "ville de " ou par sous-partie
            city_key_short = re.sub(r"^ville\s+de\s+", "", city_key)
            region_admin = idx.get(city_key_short)

    # Code postal canadien s'il est présent dans code_postal ou dans la description
    postal = code_postal.strip().upper() if code_postal and code_postal.strip() else None
    if not postal and description:
        m_pc = POSTAL_CODE_RE.search(description)
        if m_pc:
            postal = f"{m_pc.group(1).upper()} {m_pc.group(2).upper()}"

    return city, prov, region_admin, postal


def compute_dec_relevance_score(offer: JobBankOffer) -> int:
    """
    Calcule le score de pertinence (`0` à `100`) d'une offre TI pour un étudiant
    ou finissant du DEC en Techniques de l'informatique (Collège O'Sullivan de Québec).
    """
    score = 0

    # 1. Statut de stage et niveau de séniorité (max 35 pts)
    if offer.statut_stage == "confirmed_stage":
        score += 35
    elif offer.statut_stage == "possible_stage":
        score += 28
    elif offer.niveau_seniorite == "Étudiant / Stage":
        score += 32
    elif offer.niveau_seniorite == "Junior / DEC":
        score += 26
    elif offer.niveau_seniorite == "Intermédiaire":
        score += 16
    else:
        score += 6

    # 2. Adéquation du niveau d'études avec le DEC (max 20 pts)
    edu_norm = _strip_accents((offer.niveau_etudes or "").lower())
    if any(k in edu_norm for k in ("collegial", "dec", "aec", "cegep", "dep")):
        score += 20
    elif not edu_norm or "diplome postsecondaire" in edu_norm:
        score += 14
    elif "baccalaureat" in edu_norm:
        score += 8
    else:
        score += 2

    # 3. Richesse des technologies enseignées au DEC (max 25 pts)
    num_skills = len(offer.competences_cles or [])
    if num_skills >= 1:
        score += min(25, 5 + num_skills * 4)

    # 4. Accessibilité géographique & modalité (max 12 pts)
    if offer.region_administrative in ("Capitale-Nationale", "Chaudière-Appalaches") or offer.modalite in ("Télétravail", "Hybride"):
        score += 12
    elif offer.province in ("QC", "QC/CA"):
        score += 9
    else:
        score += 5

    # 5. Qualité et complétude de la fiche (max 8 pts)
    if offer.description and len(offer.description) > 100:
        score += 3
    if offer.missions_cles:
        score += 3
    if offer.salaire_min is not None:
        score += 2

    return max(0, min(100, score))


def clean_guichet_partner_boilerplate(
    description: Optional[str],
    current_emp_title: Optional[str] = None,
    current_date_fin: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Nettoie le texte d'interface Guichet-Emplois ('Ajouter aux favoris Vos favoris...')
    lorsqu'une fiche partenaire a été extraite depuis le DOM global, et récupère
    `titre_employeur` et `date_fin` s'ils y figurent.
    """
    if not description:
        return None, current_emp_title, current_date_fin

    emp_title = current_emp_title
    date_fin = current_date_fin
    cleaned = re.sub(r"</span\s*$", "", description).strip()

    if not emp_title:
        m_app = re.search(
            r"Appellation affich[ée]e sur [^-]+-\s*(.+?)\s+Publi[ée]e le \d{1,2}\s+\w+\s+\d{4}",
            cleaned,
        )
        if m_app:
            emp_title = _clean_text(m_app.group(1))
        else:
            m_po = re.match(r"^Poste offert\s*:?\s*([^\(\n]{4,95})", cleaned)
            if m_po:
                emp_title = _clean_text(m_po.group(1))

    if not date_fin:
        m_exp = re.search(r"Publi[ée]e jusqu[’']au\s+(\d{4}-\d{2}-\d{2})", cleaned)
        if m_exp:
            date_fin = m_exp.group(1)

    if "Ajouter aux favoris Vos favoris" in cleaned:
        m_info = re.search(
            r"Renseignements sur l[’']emploi\s+(.+?)(?:\s+Voir l[’']offre d[’']emploi compl[èe]te|\s+Publi[ée]e jusqu[’']au|\s+Avis important)",
            cleaned,
        )
        parts = []
        if emp_title:
            parts.append(f"Intitulé employeur : {emp_title}.")
        if m_info:
            parts.append(f"Caractéristiques de l'offre : {m_info.group(1).strip()}.")
        if parts:
            cleaned = " ".join(parts)

    return _clean_text(cleaned), emp_title, date_fin


def enrich_offer_metadata(
    offer: JobBankOffer,
    rdfa_tasks: Optional[list[str]] = None,
    student_filter: bool = False,
) -> JobBankOffer:
    """
    Applique l'ensemble des enrichissements du Lot 4 (`JobTailor_V3` + briques de la classe)
    sur une offre `JobBankOffer`.
    """
    # 1. Nettoyage d'URL et de description
    offer.url = normalize_job_url(offer.url)
    if offer.url_partenaire:
        offer.url_partenaire = normalize_job_url(offer.url_partenaire)

    if offer.source == "guichet-emplois" and offer.description:
        offer.description, offer.titre_employeur, offer.date_fin = clean_guichet_partner_boilerplate(
            offer.description,
            offer.titre_employeur,
            offer.date_fin,
        )

    # 2. Compétences techniques TI et statut de stage
    combined_title = f"{offer.titre or ''} {offer.titre_employeur or ''} {offer.cnp_title or ''}".strip()
    detected_skills = extract_tech_skills(
        offer.titre,
        offer.titre_employeur,
        offer.cnp_title,
        offer.description,
        " ".join(offer.competences_cles or []),
    )
    offer.competences_cles = detected_skills

    stage_st = detect_stage_status(combined_title, offer.description, student_filter=student_filter)
    if stage_st == "confirmed_stage" or (stage_st == "possible_stage" and offer.statut_stage == "not_indicated"):
        offer.stage_status = stage_st
    if offer.est_stage and (not offer.type_poste or offer.type_poste in ("Temps plein", "FULL_TIME")):
        offer.type_poste = "Stage"

    # 3. Classification CNP 2021 (14 codes TI) et sous-domaine TI
    cnp_res = classify_cnp_2021(
        title=offer.titre_employeur or offer.titre,
        description=offer.description,
        cnp_title=offer.cnp_title or offer.titre,
        competences=offer.competences_cles,
        source=offer.source,
    )
    if cnp_res:
        offer.code_cnp = cnp_res[0]
        if not offer.cnp_title:
            offer.cnp_title = cnp_res[1]

    # Repli domain_hint (JobTailor_V3/src/pipeline/skills_catalog.py) si aucun outil explicite n'était cité dans l'annonce
    if not offer.competences_cles and offer.code_cnp and offer.code_cnp in CNP_DEFAULT_SKILLS:
        offer.competences_cles = list(CNP_DEFAULT_SKILLS[offer.code_cnp])

    offer.domaine_ti = detect_ti_domain(
        title=offer.titre_employeur or offer.titre,
        description=offer.description,
        code_cnp=offer.code_cnp,
        competences=offer.competences_cles,
    )

    # 4. Missions clés, études, expérience et séniorité
    if not offer.missions_cles or rdfa_tasks:
        extracted_missions = extract_key_missions(offer.description, rdfa_tasks=rdfa_tasks)
        if extracted_missions:
            offer.missions_cles = extracted_missions

    offer.niveau_etudes = extract_education_level(offer.niveau_etudes, offer.description)
    offer.experience_requise, offer.niveau_seniorite = extract_experience_and_seniority(
        title=offer.titre_employeur or offer.titre,
        description=offer.description,
        est_stage=offer.est_stage,
        existing_exp=offer.experience_requise,
    )

    # 5. Salaire structuré (texte, min, max, unité)
    sal_txt, sal_min, sal_max, sal_unit = parse_salary_details(
        offer.salaire,
        description=offer.description,
        title=offer.titre_employeur or offer.titre,
    )
    if offer.salaire is None and sal_txt:
        offer.salaire = sal_txt
    if offer.salaire_min is None and sal_min is not None:
        offer.salaire_min = sal_min
    if offer.salaire_max is None and sal_max is not None:
        offer.salaire_max = sal_max
    if not offer.unite_salaire and sal_unit:
        offer.unite_salaire = sal_unit

    # 6. Normalisation géographique (Ville, Province, 17 régions administratives du Québec, Code postal)
    ville, prov_norm, reg_admin, postal = resolve_quebec_location(
        lieu=offer.lieu,
        province=offer.province,
        description=offer.description,
        code_postal=offer.code_postal,
    )
    offer.ville = offer.ville or ville
    if offer.province in ("Quebec", "Québec", ""):
        offer.province = prov_norm
    offer.region_administrative = offer.region_administrative or reg_admin
    offer.code_postal = offer.code_postal or postal

    # 7. Modalité de travail si non renseignée mais explicite dans la description
    if not offer.modalite and offer.description:
        low_d = _strip_accents(offer.description.lower())
        if "hybride" in low_d or "hybrid" in low_d:
            offer.modalite = "Hybride"
        elif "teletravail" in low_d or "100% remote" in low_d:
            offer.modalite = "Télétravail"
        elif "sur place" in low_d or "presentiel" in low_d:
            offer.modalite = "Sur place"

    # 8. Empreinte SHA-256 (JobTailor_V3) et score de pertinence DEC (0-100)
    offer.content_hash = compute_content_hash(
        url=offer.url,
        title=offer.titre_employeur or offer.titre,
        company=offer.entreprise,
        summary=offer.description,
    )
    offer.score_pertinence_dec = compute_dec_relevance_score(offer)
    return offer


def check_robots_permission(
    session: requests.Session,
    base_url: str,
    target_url: str,
    default_delay: float = 2.0,
) -> tuple[bool, float]:
    """Vérifie robots.txt pour n'importe quel site et retourne (autorisé, crawl_delay)."""
    rp = RobotFileParser()
    try:
        resp = session.get(f"{base_url.rstrip('/')}/robots.txt", timeout=8)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            allowed = rp.can_fetch(USER_AGENT, target_url)
            delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*") or default_delay
            return allowed, float(delay)
    except requests.RequestException:
        pass
    return True, default_delay


# ==============================================================================
# Gestionnaire de Cache Disque Local (Expiration 24 h)
# ==============================================================================
def _cache_file_for_url(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    """Retourne le chemin du fichier JSON de cache associé à une URL."""
    digest = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def get_cached_or_fetch(
    session: requests.Session,
    url: str,
    cache_dir: Path = CACHE_DIR,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    delay: float = 0.0,
    use_cache: bool = True,
) -> tuple[str, bool]:
    """
    Récupère le contenu d'une URL depuis le cache disque (si valide < 24 h) ou via HTTP.
    Retourne `(contenu_texte, depuis_cache)`.
    """
    cache_file = _cache_file_for_url(url, cache_dir=cache_dir)
    now = time.time()

    if use_cache and cache_file.exists():
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            fetched_at = float(payload.get("fetched_at", 0.0))
            content = payload.get("content")
            if isinstance(content, str) and (now - fetched_at) < ttl_seconds:
                return content, True
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if delay > 0:
        time.sleep(delay)

    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    text_content = resp.text

    if use_cache:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_payload = {
                "url": url,
                "fetched_at": time.time(),
                "content": text_content,
            }
            cache_file.write_text(json.dumps(cache_payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    return text_content, False


# ==============================================================================
# SOURCE 1 : Guichet-Emplois Canada (14 codes CNP TI + Fiches RDFa & DOM)
# ==============================================================================
def build_cnp_search_url(
    province: str = "QC",
    cnp_codes: tuple[str, ...] = CNP_CODES_TI,
    student_only: bool = False,
    keyword: Optional[str] = None,
    page: int = 1,
    guichet_direct_only: bool = False,
) -> str:
    """
    Construit l'URL de recherche Guichet-Emplois avec les 14 codes CNP TI et filtres.
    Note Lot 4 : `fsrc=16` filtre la source Guichet-Emplois directe (excluant Jobillico/Talent.com)
    et non les stages (démontré par Kandet). Il n'est donc plus activé par `student_only=True`,
    mais uniquement si `guichet_direct_only=True`.
    """
    params: list[tuple[str, str]] = []
    if keyword:
        params.append(("searchstring", keyword.strip()))
    for code in cnp_codes:
        params.append(("fn21", code))
    if province:
        params.append(("fprov", province))
    if guichet_direct_only:
        params.append(("fsrc", "16"))
    params.append(("sort", "D"))
    if page > 1:
        params.append(("page", str(page)))
    return f"{GUICHET_BASE_URL}{GUICHET_SEARCH_PATH}?{urlencode(params)}"


def parse_search_results_html(html_text: str) -> list[JobBankOffer]:
    """Extrait les cartes d'offres de la page de résultats Guichet-Emplois."""
    soup = BeautifulSoup(html_text, "html.parser")
    offers: list[JobBankOffer] = []
    seen_ids: set[str] = set()

    for article in soup.select("article[id^='article-']"):
        art_id = str(article.get("id", "")).replace("article-", "").strip()
        if not art_id or art_id in seen_ids:
            continue
        seen_ids.add(art_id)

        title_node = article.select_one("span.noctitle")
        cnp_title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else None

        biz_node = article.select_one("li.business")
        employer = _clean_text(biz_node.get_text(" ", strip=True)) if biz_node else None

        tele_node = article.select_one("span.telework")
        workplace_mode = _clean_text(tele_node.get_text(" ", strip=True)) if tele_node else None

        loc_node = article.select_one("li.location")
        location = None
        if loc_node:
            loc_copy = BeautifulSoup(str(loc_node), "html.parser")
            for hidden in loc_copy.select(".wb-inv, .telework"):
                hidden.decompose()
            location = _clean_text(loc_copy.get_text(" ", strip=True))

        sal_node = article.select_one("li.salary")
        salary = None
        if sal_node:
            sal_copy = BeautifulSoup(str(sal_node), "html.parser")
            for hidden in sal_copy.select(".wb-inv"):
                hidden.decompose()
            raw_sal = _clean_text(sal_copy.get_text(" ", strip=True))
            if raw_sal:
                raw_sal = re.sub(r"^Salaire\s*:\s*", "", raw_sal, flags=re.I).strip()
            if raw_sal and not any(k in raw_sal.lower() for k in ("non disponible", "not available")):
                salary = raw_sal

        date_node = article.select_one("li.date")
        raw_date = _clean_text(date_node.get_text(" ", strip=True)) if date_node else None
        published_at = parse_iso_date(raw_date)

        partner_node = article.select_one("li.source span.wb-inv")
        origin_partner = _clean_text(partner_node.get_text(" ", strip=True)) if partner_node else "Guichet-Emplois"

        clean_url = f"{GUICHET_BASE_URL}/rechercheemplois/offredemploi/{art_id}"
        stage_st = detect_stage_status(cnp_title, None)

        off = JobBankOffer(
            id=f"ge-{art_id}",
            source_id=art_id,
            url=clean_url,
            cnp_title=cnp_title,
            titre=cnp_title,
            entreprise=employer,
            lieu=location,
            salaire=salary,
            date_publication=published_at,
            modalite=workplace_mode,
            source="guichet-emplois",
            source_partenaire=origin_partner,
            est_stage=(stage_st != "not_indicated"),
            statut_stage=stage_st,
            competences_cles=extract_tech_skills(cnp_title),
        )
        enrich_offer_metadata(off)
        offers.append(off)

    return offers


def collect_guichet_paginated_offers(
    session: requests.Session,
    pages: int = 1,
    province: str = "QC",
    student_only: bool = False,
    keyword: Optional[str] = None,
    delay: float = 0.0,
) -> list[JobBankOffer]:
    """Parcourt jusqu'à `pages` pages de résultats Guichet-Emplois CNP TI et déduplique par identifiant."""
    aggregated: list[JobBankOffer] = []
    seen_ids: set[str] = set()
    max_pages = max(1, pages)

    for page_num in range(1, max_pages + 1):
        if page_num > 1 and delay > 0:
            time.sleep(delay)
        page_url = build_cnp_search_url(
            province=province,
            student_only=student_only,
            keyword=keyword,
            page=page_num,
        )
        print(f"\n[Source 1 - Guichet-Emplois CNP TI] Page {page_num}/{max_pages} : {page_url}")
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
        page_offers = parse_search_results_html(resp.text)
        if not page_offers:
            break
        for off in page_offers:
            if off.id not in seen_ids:
                seen_ids.add(off.id)
                aggregated.append(off)

    return aggregated


def parse_job_detail_html(html_text: str, offer: JobBankOffer, student_filter: bool = False) -> JobBankOffer:
    """
    Enrichit une offre Guichet-Emplois à partir du HTML de sa fiche détaillée :
    1. Extrait le vrai titre de l'employeur (`.source-title-inner`) et le lien partenaire (`a#externalJobLink`).
    2. Extrait la modalité (`Sur place`, `Hybride`, `Télétravail`), le code postal, la ville et le salaire RDFa.
    3. Extrait les tâches RDFa (`[property='responsibilities'] li`) et la description complète via la cascade à 3 niveaux.
    4. Applique l'enrichissement Lot 4 (`code_cnp`, `domaine_ti`, `missions_cles`, `niveau_seniorite`, `score_pertinence_dec`).
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Titre RDFa sur la fiche
    title_prop = soup.find(attrs={"property": "title"})
    if title_prop:
        detail_title = _clean_text(title_prop.get_text(" ", strip=True))
        if detail_title:
            offer.titre = detail_title

    # 1.b Vrai titre de l'employeur affiché sur le site partenaire (.source-title-inner)
    source_title_tag = soup.select_one(".source-title-inner")
    if source_title_tag:
        sc_copy = BeautifulSoup(str(source_title_tag), "html.parser")
        for lbl in sc_copy.select(".orig-title-label"):
            lbl.decompose()
        emp_title = _clean_text(sc_copy.get_text(" ", strip=True))
        if emp_title:
            offer.titre_employeur = emp_title

    # 1.c Lien externe partenaire (a#externalJobLink)
    ext_link = soup.select_one("a#externalJobLink[href]")
    if ext_link:
        href_val = str(ext_link.get("href", "")).strip()
        if href_val.startswith("http"):
            offer.url_partenaire = normalize_job_url(href_val)

    # 2. Employeur RDFa (si absent de la liste)
    if not offer.entreprise:
        org_prop = soup.find(attrs={"property": "hiringOrganization"})
        if org_prop:
            name_prop = org_prop.find(attrs={"property": "name"}) or org_prop
            offer.entreprise = _clean_text(name_prop.get_text(" ", strip=True))

    # 2.b Localisation RDFa (ville et code postal)
    postal_node = soup.find(attrs={"property": "postalCode"})
    if postal_node:
        pc_val = _clean_text(postal_node.get_text(" ", strip=True))
        if pc_val:
            offer.code_postal = pc_val.upper()

    city_node = soup.find(attrs={"property": "addressLocality"})
    if city_node and not offer.ville:
        offer.ville = _clean_text(city_node.get_text(" ", strip=True))

    # 2.c Salaire RDFa (minValue, maxValue, unitText)
    min_sal_node = soup.find(attrs={"property": "minValue"})
    max_sal_node = soup.find(attrs={"property": "maxValue"})
    unit_sal_node = soup.find(attrs={"property": "unitText"})
    if min_sal_node:
        raw_min = str(min_sal_node.get("content") or min_sal_node.get_text(" ", strip=True))
        offer.salaire_min = _parse_number_token(raw_min)
        if max_sal_node:
            raw_max = str(max_sal_node.get("content") or max_sal_node.get_text(" ", strip=True))
            offer.salaire_max = _parse_number_token(raw_max) or offer.salaire_min
        else:
            offer.salaire_max = offer.salaire_min
    if unit_sal_node:
        raw_u = _clean_text(str(unit_sal_node.get("content") or unit_sal_node.get_text(" ", strip=True))) or ""
        unit_map = {"HOUR": "heure", "YEAR": "année", "MONTH": "mois", "WEEK": "semaine", "DAY": "jour"}
        offer.unite_salaire = unit_map.get(raw_u.upper(), offer.unite_salaire)

    # 3. Bandeau résumé (ul.job-posting-brief) pour modalité et conditions
    brief_node = soup.select_one("ul.job-posting-brief")
    brief_summary: Optional[str] = None
    if brief_node:
        brief_summary = _clean_text(brief_node.get_text(" | ", strip=True))
        brief_low = (brief_summary or "").lower()
        if not offer.modalite:
            if "télétravail" in brief_low or "remote" in brief_low:
                offer.modalite = "Télétravail"
            elif "hybride" in brief_low or "hybrid" in brief_low:
                offer.modalite = "Hybride"
            elif "sur place" in brief_low or "on site" in brief_low:
                offer.modalite = "Sur place"

    # 3.b Tâches RDFa (property="responsibilities")
    rdfa_tasks: list[str] = []
    for resp_block in soup.find_all(attrs={"property": "responsibilities"}):
        for li in resp_block.find_all("li"):
            t_txt = _clean_text(li.get_text(" ", strip=True))
            if t_txt:
                rdfa_tasks.append(t_txt)

    # 4. Cascade d'extraction de la description complète
    description_text: Optional[str] = None

    # Niveau A : RDFa property="description" (seulement si non vide !)
    for desc_candidate in soup.find_all(attrs={"property": "description"}):
        raw_desc = desc_candidate.get_text(" ", strip=True)
        if "<" in raw_desc and ">" in raw_desc:
            raw_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)
        cleaned_candidate = _clean_text(raw_desc)
        if cleaned_candidate and len(cleaned_candidate) > 25:
            description_text = cleaned_candidate
            break

    # Niveau B : Conteneurs DOM (#job-posting-detail, .job-posting-detail-requirements)
    if not description_text:
        for selector in ("#job-posting-detail", "section.job-posting-detail-requirements", "div.job-posting-detail-requirements"):
            dom_node = soup.select_one(selector)
            if dom_node:
                cleaned_dom = _clean_text(dom_node.get_text(" ", strip=True))
                if cleaned_dom and len(cleaned_dom) > 30:
                    description_text = cleaned_dom
                    break

    # Niveau C : Synthèse des informations de la fiche pour les offres partenaires sans corps de texte
    if not description_text and brief_summary:
        parts = []
        if offer.titre_employeur:
            parts.append(f"Intitulé employeur : {offer.titre_employeur}.")
        parts.append(f"Caractéristiques de l'offre ({offer.source_partenaire or 'Guichet-Emplois'}) : {brief_summary}")
        description_text = " ".join(parts)

    offer.description = description_text

    # 5. Date limite (validThrough), type d'emploi, niveau d'études et expérience RDFa
    valid_node = soup.find(attrs={"property": "validThrough"})
    if valid_node:
        offer.date_fin = _clean_text(valid_node.get_text(" ", strip=True))

    emp_parts: list[str] = []
    for prop_name in ("employmentType", "workHours"):
        node = soup.find(attrs={"property": prop_name})
        if node:
            val = _clean_text(node.get_text(" ", strip=True))
            if val and val not in emp_parts:
                emp_parts.append(val)
    if emp_parts:
        offer.type_poste = ", ".join(emp_parts)

    edu_node = soup.find(attrs={"property": "educationRequirements"})
    if edu_node:
        offer.niveau_etudes = _clean_text(edu_node.get_text(" ", strip=True))

    exp_node = soup.find(attrs={"property": "experienceRequirements"})
    if exp_node:
        offer.experience_requise = _clean_text(exp_node.get_text(" ", strip=True))

    # 6. Enrichissement Lot 4 complet
    return enrich_offer_metadata(offer, rdfa_tasks=rdfa_tasks, student_filter=student_filter)


# ==============================================================================
# SOURCE 2 : Talent.com Canada (Double JSON-LD @graph + Coordonnées GPS + CNP TI)
# ==============================================================================
def parse_talent_search_json_ld(html_text: str) -> list[str]:
    """Extrait les URLs d'offres depuis l'objet JSON-LD ItemList (#jobList) de Talent.com."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else []
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for item in node.get("itemListElement", []):
                        u = item.get("item", {}).get("url")
                        if u and u not in urls:
                            urls.append(u)
        except json.JSONDecodeError:
            continue
    return urls


def parse_talent_job_detail_html(html_text: str, url: str) -> Optional[JobBankOffer]:
    """
    Extrait l'offre complète et ses coordonnées GPS depuis le JSON-LD JobPosting de Talent.com.
    Filtre strictement toute offre hors TI via `classify_cnp_2021` (retourne `None` si hors TI).
    """
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            graph = data.get("@graph", [data]) if isinstance(data, dict) else []
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "JobPosting":
                    raw_id = url.split("id=")[-1].split("&")[0] if "id=" in url else str(abs(hash(url)))[:10]
                    title = _clean_text(node.get("title"))
                    org = node.get("hiringOrganization") or {}
                    company = _clean_text(org.get("name")) if isinstance(org, dict) else None
                    loc = node.get("jobLocation") or {}
                    if isinstance(loc, list) and loc:
                        loc = loc[0]
                    addr = loc.get("address") or {} if isinstance(loc, dict) else {}
                    geo = loc.get("geo") or {} if isinstance(loc, dict) else {}
                    city = _clean_text(addr.get("addressLocality"))
                    region = _clean_text(addr.get("addressRegion")) or "QC"
                    postal = _clean_text(addr.get("postalCode"))

                    raw_desc_html = str(node.get("description") or "")
                    desc_clean = _clean_text(BeautifulSoup(raw_desc_html, "html.parser").get_text(" ", strip=True))
                    skills = extract_tech_skills(title, desc_clean)

                    # Filtrage et classification CNP 2021 TI (0 faux positif hors TI)
                    cnp_match = classify_cnp_2021(title, desc_clean, competences=skills, source="talent-canada")
                    if cnp_match is None:
                        return None

                    stage_st = detect_stage_status(title, desc_clean)
                    lat = float(geo["latitude"]) if geo.get("latitude") is not None else None
                    lon = float(geo["longitude"]) if geo.get("longitude") is not None else None

                    offer = JobBankOffer(
                        id=f"tc-{raw_id}",
                        source_id=raw_id,
                        url=normalize_job_url(url),
                        titre=title,
                        titre_employeur=title,
                        code_cnp=cnp_match[0],
                        cnp_title=cnp_match[1],
                        entreprise=company,
                        lieu=f"{city} ({region})" if city else region,
                        code_postal=postal,
                        province=region,
                        source="talent-canada",
                        date_publication=parse_iso_date(node.get("datePosted")),
                        type_poste="Stage" if stage_st == "confirmed_stage" else _clean_text(str(node.get("employmentType") or "Temps plein")),
                        est_stage=(stage_st != "not_indicated"),
                        statut_stage=stage_st,
                        competences_cles=skills,
                        latitude=lat,
                        longitude=lon,
                        description=desc_clean,
                    )
                    return enrich_offer_metadata(offer)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


# ==============================================================================
# SOURCE 3 : Jobboom Québec (Secteur Technologies _i10lfr + JSON-LD + CNP TI)
# ==============================================================================
def build_jobboom_listing_url(page: int = 1) -> str:
    """Construit l'URL de la catégorie Technologies (_i10lfr) de Jobboom pour la page demandée."""
    return f"https://www.jobboom.com/fr/technologies-medias-numeriques/_i10lfr?sortBy=date&page={max(1, page)}"


def parse_jobboom_listing_html(html_text: str) -> list[str]:
    """Extrait les URLs d'offres TI sur Jobboom dans l'ordre d'affichage (hors commandites)."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for card in soup.select("div.job_item[data-url]"):
        classes = card.get("class") or []
        if "job_item_sponsorship" in classes:
            continue
        path = str(card.get("data-url", "")).strip()
        if path.startswith("/fr/offre-emploi/"):
            full_u = f"https://www.jobboom.com{path}"
            if full_u not in urls:
                urls.append(full_u)
    return urls


def collect_jobboom_paginated_urls(
    session: requests.Session,
    pages: int = 1,
    delay: float = 0.0,
) -> list[str]:
    """Parcourt jusqu'à `pages` pages de la catégorie TI de Jobboom et agrège les URLs sans doublons."""
    aggregated_urls: list[str] = []
    max_pages = max(1, pages)

    for page_num in range(1, max_pages + 1):
        if page_num > 1 and delay > 0:
            time.sleep(delay)
        jb_url = build_jobboom_listing_url(page=page_num)
        print(f"\n[Source 3 - Jobboom Québec TI] Page {page_num}/{max_pages} : {jb_url}")
        jb_resp = session.get(jb_url, timeout=15)
        jb_resp.raise_for_status()
        page_urls = parse_jobboom_listing_html(jb_resp.text)
        if not page_urls:
            break
        for u in page_urls:
            if u not in aggregated_urls:
                aggregated_urls.append(u)

    return aggregated_urls


def parse_json_ld_job_posting(html_text: str, url: str, source_name: str, id_prefix: str) -> Optional[JobBankOffer]:
    """
    Parseur générique de fiche JSON-LD Schema.org JobPosting (Jobboom & Jobillico).
    Filtre strictement toute offre hors TI via `classify_cnp_2021` (retourne `None` si hors TI).
    """
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            if not (isinstance(data, dict) and data.get("@type") == "JobPosting"):
                continue
            m_id = re.search(r"(\d{5,})", url)
            raw_id = m_id.group(1) if m_id else str(abs(hash(url)))[:8]
            title = _clean_text(data.get("title"))
            org = data.get("hiringOrganization") or {}
            company = _clean_text(org.get("name")) if isinstance(org, dict) else None

            loc = data.get("jobLocation") or {}
            if isinstance(loc, list) and loc:
                loc = loc[0]
            addr = loc.get("address") or {} if isinstance(loc, dict) else {}
            city = _clean_text(addr.get("addressLocality"))
            region = _clean_text(addr.get("addressRegion")) or "QC"
            postal = _clean_text(addr.get("postalCode"))

            raw_desc = str(data.get("description") or "")
            desc_clean = _clean_text(BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True))
            skills = extract_tech_skills(title, desc_clean)

            # Filtrage et classification CNP 2021 TI (0 faux positif hors TI)
            cnp_match = classify_cnp_2021(title, desc_clean, competences=skills, source=source_name)
            if cnp_match is None:
                return None

            stage_st = detect_stage_status(title, desc_clean)

            # Salaire éventuel dans baseSalary
            salary_str: Optional[str] = None
            base_sal = data.get("baseSalary")
            if isinstance(base_sal, dict):
                val_obj = base_sal.get("value")
                if isinstance(val_obj, dict):
                    min_v = val_obj.get("minValue")
                    max_v = val_obj.get("maxValue")
                    unit = val_obj.get("unitText", "")
                    if min_v and max_v:
                        salary_str = f"{min_v} $ à {max_v} $ ({unit})"
                    elif min_v:
                        salary_str = f"{min_v} $ ({unit})"

            modalite = None
            if desc_clean:
                low_d = desc_clean.lower()
                if "télétravail" in low_d or "100% remote" in low_d:
                    modalite = "Télétravail"
                elif "hybride" in low_d:
                    modalite = "Hybride"

            offer = JobBankOffer(
                id=f"{id_prefix}-{raw_id}",
                source_id=raw_id,
                url=normalize_job_url(url),
                titre=title,
                titre_employeur=title,
                code_cnp=cnp_match[0],
                cnp_title=cnp_match[1],
                entreprise=company,
                lieu=f"{city} ({region})" if city else region,
                code_postal=postal,
                province=region,
                source=source_name,
                date_publication=parse_iso_date(data.get("datePosted")),
                date_fin=parse_iso_date(data.get("validThrough")),
                type_poste="Stage" if stage_st == "confirmed_stage" else "Temps plein",
                modalite=modalite,
                salaire=salary_str,
                est_stage=(stage_st != "not_indicated"),
                statut_stage=stage_st,
                competences_cles=skills,
                description=desc_clean,
            )
            return enrich_offer_metadata(offer)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


# ==============================================================================
# SOURCE 4 : Jobillico Québec (Recherche TI + JSON-LD JobPosting + CNP TI)
# ==============================================================================
def parse_jobillico_listing_html(html_text: str) -> list[str]:
    """Extrait les URLs d'offres depuis la page de résultats Jobillico."""
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for a_tag in soup.select("a[href*='/fr/offre-d-emploi/']"):
        href = str(a_tag.get("href", "")).split("?")[0].split("#")[0].strip()
        if href.startswith("/fr/offre-d-emploi/"):
            full_u = f"https://www.jobillico.com{href}"
            if full_u not in urls:
                urls.append(full_u)
    return urls


# ==============================================================================
# SOURCE 5 : Remotive API (API REST JSON officielle - Télétravail Canada + CNP TI)
# ==============================================================================
def parse_remotive_job_item(item: dict[str, Any]) -> Optional[JobBankOffer]:
    """
    Transforme un objet JSON d'offre Remotive en `JobBankOffer` si et seulement si :
    1. L'offre est accessible depuis le Canada (`Canada`, `Quebec`, `North America`, `Americas`, `Worldwide`, `Anywhere`).
    2. L'offre appartient à l'un des 14 codes CNP 2021 TI via `classify_cnp_2021` (0 bruit hors TI).
    """
    req_loc = str(item.get("candidate_required_location") or "").lower()
    if not any(k in req_loc for k in ("canada", "quebec", "montreal", "north america", "americas", "worldwide", "anywhere")):
        return None

    raw_id = str(item.get("id") or "").strip()
    if not raw_id:
        return None
    title = _clean_text(item.get("title"))
    company = _clean_text(item.get("company_name"))
    raw_desc = str(item.get("description") or "")
    desc_clean = _clean_text(BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True))
    tags_str = " ".join(str(t) for t in (item.get("tags") or []))
    skills = extract_tech_skills(title, desc_clean, tags_str)

    # Classification CNP 2021 TI & filtrage anti-bruit (rejette YouTube Creator, Office Assistant, AI Trainer non-TI...)
    cnp_match = classify_cnp_2021(title, desc_clean, competences=skills, source="remotive")
    if cnp_match is None:
        return None

    job_type_raw = str(item.get("job_type") or "").lower()
    stage_st = "confirmed_stage" if "intern" in job_type_raw else detect_stage_status(title, desc_clean)

    offer = JobBankOffer(
        id=f"rem-{raw_id}",
        source_id=raw_id,
        url=normalize_job_url(str(item.get("url") or "")),
        titre=title,
        titre_employeur=title,
        code_cnp=cnp_match[0],
        cnp_title=cnp_match[1],
        entreprise=company,
        lieu=f"Télétravail ({item.get('candidate_required_location', 'Canada')})",
        province="QC/CA",
        source="remotive",
        date_publication=parse_iso_date(item.get("publication_date")),
        type_poste="Stage" if stage_st == "confirmed_stage" else "Temps plein",
        modalite="Télétravail",
        salaire=_clean_text(item.get("salary")) or None,
        est_stage=(stage_st != "not_indicated"),
        statut_stage=stage_st,
        competences_cles=skills,
        description=desc_clean,
    )
    return enrich_offer_metadata(offer)


def fetch_remotive_canada_offers(
    session: requests.Session,
    limit: int = 4,
    use_cache: bool = True,
    cache_dir: Path = CACHE_DIR,
) -> list[JobBankOffer]:
    """Interroge l'API publique Remotive (avec cache 24 h) et filtre les offres TI accessibles au Canada."""
    api_url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=50"
    print(f"\n[Source 5 - Remotive API] Requête JSON : {api_url}")
    offers: list[JobBankOffer] = []
    try:
        raw_json, from_cache = get_cached_or_fetch(
            session,
            api_url,
            cache_dir=cache_dir,
            use_cache=use_cache,
        )
        payload = json.loads(raw_json)
        for item in payload.get("jobs", []):
            if len(offers) >= limit:
                break
            parsed = parse_remotive_job_item(item)
            if parsed is not None:
                offers.append(parsed)
        tag = "[CACHE]" if from_cache else "[HTTP]"
        print(f"  -> {len(offers)} offres Remotive TI éligibles Canada extraites {tag}.")
    except (requests.RequestException, json.JSONDecodeError) as exc:
        print(f"  ! Erreur Remotive API : {exc}")
    return offers


# ==============================================================================
# Déduplication Intra/Inter-Sources, Fusion Intelligente Sans Perte & Exports
# ==============================================================================
STAGE_PRIORITY: dict[str, int] = {
    "confirmed_stage": 2,
    "possible_stage": 1,
    "not_indicated": 0,
}

LEGAL_SUFFIXES_RE = re.compile(
    r"\b(?:inc|ltee|ltd|corp|corporation|llc|gmbh|co|cie|solutions|technologies|groupe|group|canada|quebec|qc)\b",
    re.I,
)


def _normalize_company_for_dedup(company: Optional[str]) -> str:
    norm = _normalize_for_match(company)
    if not norm:
        return ""
    norm = LEGAL_SUFFIXES_RE.sub(" ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def _normalize_title_for_dedup(offer: JobBankOffer) -> str:
    raw_t = offer.titre_employeur or offer.titre or ""
    norm = _normalize_for_match(raw_t)
    # Retirer les codes de référence d'affichage (ex. 26085-96069, P2627-40)
    norm = re.sub(r"\b(?:p?\d{4,}\s+\d{2,}|\d{5,})\b", " ", norm)
    norm = re.sub(r"\b(?:developpeur\s+developpeuse|developpeuse\s+developpeur)\b", "developpeur", norm)
    norm = re.sub(r"\b(?:programmeur\s+programmeuse|programmeuse\s+programmeur)\b", "programmeur", norm)
    norm = re.sub(r"\b(?:administrateur\s+administratrice|administratrice\s+administrateur)\b", "administrateur", norm)
    norm = re.sub(r"\b(?:technicien\s+technicienne|technicienne\s+technicien)\b", "technicien", norm)
    norm = re.sub(r"\b(?:ingenieur\s+ingenieure|ingenieure\s+ingenieur)\b", "ingenieur", norm)
    norm = re.sub(
        r"\b(?:analyste\s+fonctionnel\s+analyste\s+fonctionnelle|analyste\s+fonctionnelle\s+analyste\s+fonctionnel)\b",
        "analyste fonctionnel",
        norm,
    )
    norm = re.sub(r"\b(?:programmeur\s+analyste|analyste\s+programmeur|analyste\s+programmeuse)\b", "analyste programmeur", norm)
    norm = re.sub(r"\breseaux\b", "reseau", norm)
    norm = re.sub(r"\b(?:h\s*f|f\s*h|m\s*f|permanent|temporaire|temps\s+plein)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def _normalize_city_for_dedup(offer: JobBankOffer) -> str:
    if offer.ville:
        return _normalize_for_match(offer.ville)
    loc_norm = _normalize_for_match(offer.lieu)
    if any(k in loc_norm for k in ("teletravail", "remote", "worldwide", "anywhere")):
        return "teletravail"
    return loc_norm


def is_intra_source_duplicate(a: JobBankOffer, b: JobBankOffer) -> bool:
    """Vérifie si deux offres proviennent de la même source avec le même identifiant ou la même URL propre."""
    if a.source.strip().lower() != b.source.strip().lower():
        return False
    if a.id and b.id and a.id.strip().lower() == b.id.strip().lower():
        return True
    if a.source_id and b.source_id and a.source_id.strip().lower() == b.source_id.strip().lower():
        return True
    url_a = normalize_job_url(a.url)
    url_b = normalize_job_url(b.url)
    return bool(url_a and url_b and url_a == url_b)


def is_cross_source_duplicate(a: JobBankOffer, b: JobBankOffer) -> bool:
    """
    Détermine si deux offres provenant de diffuseurs distincts (sources ou partenaires distincts)
    décrivent le même poste (ex. une offre Jobillico, Talent.com ou Jobboom rediffusée sur Guichet-Emplois).
    """
    pub_a = (a.source.strip().lower(), (a.source_partenaire or "").strip().lower())
    pub_b = (b.source.strip().lower(), (b.source_partenaire or "").strip().lower())
    if pub_a == pub_b:
        return False

    # 1. Correspondance directe par url_partenaire ou source_id croisé
    if a.url_partenaire and normalize_job_url(a.url_partenaire) == normalize_job_url(b.url):
        return True
    if b.url_partenaire and normalize_job_url(b.url_partenaire) == normalize_job_url(a.url):
        return True
    if a.description and b.source_id and len(b.source_id) >= 6 and f"#{b.source_id}" in a.description:
        return True
    if b.description and a.source_id and len(a.source_id) >= 6 and f"#{a.source_id}" in b.description:
        return True

    # 2. Correspondance par empreinte normalisée (titre employeur + entreprise + ville)
    comp_a = _normalize_company_for_dedup(a.entreprise)
    comp_b = _normalize_company_for_dedup(b.entreprise)
    if not comp_a or not comp_b or comp_a in ("non specifie", "confidentiel") or comp_a != comp_b:
        return False

    title_a = _normalize_title_for_dedup(a)
    title_b = _normalize_title_for_dedup(b)
    if len(title_a) < 4 or len(title_b) < 4 or title_a != title_b:
        return False

    city_a = _normalize_city_for_dedup(a)
    city_b = _normalize_city_for_dedup(b)
    if not city_a or not city_b:
        return True
    return city_a == city_b or city_a in city_b or city_b in city_a or "teletravail" in (city_a, city_b)


def merge_two_offers(base: JobBankOffer, other: JobBankOffer) -> JobBankOffer:
    """
    Fusionne deux offres redondantes en préservant la richesse maximale sans aucune perte :
    - Description la plus détaillée
    - Union sans doublon de `competences_cles` et `missions_cles`
    - Conservation des coordonnées GPS (`latitude`, `longitude`), du salaire, du code postal et de `url_partenaire`
    - Priorité au statut de stage le plus élevé (`confirmed_stage` > `possible_stage` > `not_indicated`).
    """
    desc_base = base.description or ""
    desc_other = other.description or ""
    best_desc = desc_base if len(desc_base) >= len(desc_other) else desc_other

    merged_skills = sorted(list({*(base.competences_cles or []), *(other.competences_cles or [])}))

    missions_seen: set[str] = set()
    merged_missions: list[str] = []
    for m in (base.missions_cles or []) + (other.missions_cles or []):
        k = _normalize_for_match(m)
        if k and k not in missions_seen:
            missions_seen.add(k)
            merged_missions.append(m)

    st_base = STAGE_PRIORITY.get(base.statut_stage, 0)
    st_other = STAGE_PRIORITY.get(other.statut_stage, 0)
    best_stage_status = other.statut_stage if st_other > st_base else base.statut_stage
    best_est_stage = (best_stage_status != "not_indicated") or base.est_stage or other.est_stage

    merged = JobBankOffer(
        id=base.id,
        source_id=base.source_id,
        url=base.url,
        titre=base.titre or other.titre,
        titre_employeur=base.titre_employeur or other.titre_employeur,
        code_cnp=base.code_cnp or other.code_cnp,
        cnp_title=base.cnp_title or other.cnp_title,
        domaine_ti=base.domaine_ti or other.domaine_ti,
        entreprise=base.entreprise if base.entreprise not in (None, "", "Non spécifié") else other.entreprise,
        lieu=base.lieu if base.lieu not in (None, "", "Non spécifié") else other.lieu,
        ville=base.ville or other.ville,
        region_administrative=base.region_administrative or other.region_administrative,
        code_postal=base.code_postal or other.code_postal,
        province=base.province or other.province or "QC",
        pays=base.pays or other.pays or "Canada",
        source=base.source,
        source_partenaire=base.source_partenaire or (other.source if other.source != base.source else other.source_partenaire),
        url_partenaire=base.url_partenaire or (other.url if other.source != base.source else other.url_partenaire),
        date_publication=min(base.date_publication, other.date_publication)
        if (base.date_publication and other.date_publication)
        else (base.date_publication or other.date_publication),
        date_fin=base.date_fin or other.date_fin,
        type_poste="Stage" if best_est_stage and base.type_poste != "Stage" else (base.type_poste or other.type_poste),
        modalite=base.modalite or other.modalite,
        niveau_etudes=base.niveau_etudes or other.niveau_etudes,
        experience_requise=base.experience_requise or other.experience_requise,
        niveau_seniorite=base.niveau_seniorite or other.niveau_seniorite,
        salaire=base.salaire or other.salaire,
        salaire_min=base.salaire_min if base.salaire_min is not None else other.salaire_min,
        salaire_max=base.salaire_max if base.salaire_max is not None else other.salaire_max,
        unite_salaire=base.unite_salaire or other.unite_salaire,
        est_stage=best_est_stage,
        statut_stage=best_stage_status,
        competences_cles=merged_skills,
        missions_cles=merged_missions[:6],
        latitude=base.latitude if base.latitude is not None else other.latitude,
        longitude=base.longitude if base.longitude is not None else other.longitude,
        http_status=base.http_status or 200,
        description=best_desc or None,
        date_extraction=base.date_extraction,
    )
    return enrich_offer_metadata(merged)


def unify_and_deduplicate_offers(
    offers: list[JobBankOffer],
) -> tuple[list[JobBankOffer], dict[str, int]]:
    """
    Exécute la déduplication intra-source et inter-sources avec fusion intelligente sans perte.
    Retourne `(offres_unifiees, compteurs_deduplication)`.
    """
    unified: list[JobBankOffer] = []
    intra_merged = 0
    cross_merged = 0

    for off in offers:
        # 1. Doublon intra-source
        intra_idx = next((i for i, ex in enumerate(unified) if is_intra_source_duplicate(ex, off)), -1)
        if intra_idx >= 0:
            unified[intra_idx] = merge_two_offers(unified[intra_idx], off)
            intra_merged += 1
            continue

        # 2. Doublon inter-sources
        cross_idx = next((i for i, ex in enumerate(unified) if is_cross_source_duplicate(ex, off)), -1)
        if cross_idx >= 0:
            unified[cross_idx] = merge_two_offers(unified[cross_idx], off)
            cross_merged += 1
            continue

        unified.append(off)

    stats = {
        "total_entree": len(offers),
        "doublons_intra_fusionnes": intra_merged,
        "doublons_inter_fusionnes": cross_merged,
        "total_unifie": len(unified),
    }
    return unified, stats


def export_offers_to_csv(
    offers: list[JobBankOffer],
    output_path: Path,
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
) -> Path:
    """
    Exporte les offres unifiées au format CSV compatible Microsoft Excel Windows (`utf-8-sig`, séparateur `;`).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "source",
        "source_partenaire",
        "code_cnp",
        "cnp_title",
        "domaine_ti",
        "titre",
        "titre_employeur",
        "entreprise",
        "ville",
        "region_administrative",
        "code_postal",
        "lieu",
        "province",
        "pays",
        "latitude",
        "longitude",
        "date_publication",
        "date_fin",
        "type_poste",
        "modalite",
        "niveau_etudes",
        "experience_requise",
        "niveau_seniorite",
        "salaire",
        "salaire_min",
        "salaire_max",
        "unite_salaire",
        "est_stage",
        "statut_stage",
        "score_pertinence_dec",
        "competences_cles",
        "missions_cles",
        "url",
        "url_partenaire",
        "http_status",
        "content_hash",
        "date_extraction",
        "description",
    ]

    with output_path.open("w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for off in offers:
            desc_one_line = re.sub(r"[\r\n\t]+", " ", off.description or "").strip()
            row = {
                "id": off.id,
                "source": off.source,
                "source_partenaire": off.source_partenaire or "",
                "code_cnp": off.code_cnp or "",
                "cnp_title": off.cnp_title or "",
                "domaine_ti": off.domaine_ti or "",
                "titre": off.titre or "",
                "titre_employeur": off.titre_employeur or "",
                "entreprise": off.entreprise or "",
                "ville": off.ville or "",
                "region_administrative": off.region_administrative or "",
                "code_postal": off.code_postal or "",
                "lieu": off.lieu or "",
                "province": off.province or "QC",
                "pays": off.pays or "Canada",
                "latitude": off.latitude if off.latitude is not None else "",
                "longitude": off.longitude if off.longitude is not None else "",
                "date_publication": off.date_publication or "",
                "date_fin": off.date_fin or "",
                "type_poste": off.type_poste or "",
                "modalite": off.modalite or "",
                "niveau_etudes": off.niveau_etudes or "",
                "experience_requise": off.experience_requise or "",
                "niveau_seniorite": off.niveau_seniorite or "",
                "salaire": off.salaire or "",
                "salaire_min": off.salaire_min if off.salaire_min is not None else "",
                "salaire_max": off.salaire_max if off.salaire_max is not None else "",
                "unite_salaire": off.unite_salaire or "",
                "est_stage": "True" if off.est_stage else "False",
                "statut_stage": off.statut_stage,
                "score_pertinence_dec": off.score_pertinence_dec,
                "competences_cles": ", ".join(off.competences_cles or []),
                "missions_cles": " | ".join(off.missions_cles or []),
                "url": off.url,
                "url_partenaire": off.url_partenaire or "",
                "http_status": off.http_status,
                "content_hash": off.content_hash or "",
                "date_extraction": off.date_extraction,
                "description": desc_one_line,
            }
            writer.writerow(row)

    return output_path


def build_collection_report(
    per_source_counts: dict[str, dict[str, int]],
    dedup_stats: dict[str, int],
    unified_offers: list[JobBankOffer],
) -> dict[str, Any]:
    """
    Construit le rapport statistique complet `data/rapport_collecte.json` :
    - Statistiques par source (brutes vs retenues TI après filtrage CNP 2021)
    - Doublons intra-source et inter-sources fusionnés
    - Répartition par code CNP 2021 (14 codes TI)
    - Répartition par sous-domaine TI (`domaine_ti`)
    - Répartition par région administrative du Québec (17 régions)
    - Répartition par niveau de séniorité et statut de stage
    - Top 25 des technologies demandées.
    """
    by_source = Counter(o.source for o in unified_offers)
    by_cnp = Counter(f"{o.code_cnp} - {CNP_2021_TI_DICT.get(o.code_cnp or '', o.cnp_title or '')}" for o in unified_offers if o.code_cnp)
    by_domain = Counter(o.domaine_ti or "non_specifie" for o in unified_offers)
    by_region = Counter(o.region_administrative or "Hors QC / Télétravail" for o in unified_offers)
    by_seniority = Counter(o.niveau_seniorite or "Intermédiaire" for o in unified_offers)
    by_stage = Counter(o.statut_stage for o in unified_offers)
    by_modalite = Counter(o.modalite or "Non spécifié" for o in unified_offers)

    tech_counter: Counter[str] = Counter()
    for o in unified_offers:
        for sk in o.competences_cles or []:
            tech_counter[sk] += 1

    scores = [o.score_pertinence_dec for o in unified_offers]
    avg_dec_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return {
        "date_generation": datetime.now(timezone.utc).isoformat(),
        "auteur": "Mamadou (Livrable 3 - Lot 4 final)",
        "total_offres_unifiees_ti": len(unified_offers),
        "deduplication": dedup_stats,
        "collecte_par_source": per_source_counts,
        "repartition_sources_unifiees": dict(by_source.most_common()),
        "repartition_codes_cnp_2021": dict(by_cnp.most_common()),
        "repartition_domaines_ti": dict(by_domain.most_common()),
        "repartition_regions_administratives_qc": dict(by_region.most_common()),
        "repartition_niveaux_seniorite": dict(by_seniority.most_common()),
        "repartition_statuts_stage": dict(by_stage.most_common()),
        "repartition_modalites": dict(by_modalite.most_common()),
        "top_technologies_ti": dict(tech_counter.most_common(30)),
        "score_pertinence_dec_moyen": avg_dec_score,
        "offres_avec_coordonnees_gps": sum(1 for o in unified_offers if o.latitude is not None and o.longitude is not None),
        "offres_avec_salaire_chiffre": sum(1 for o in unified_offers if o.salaire_min is not None),
        "offres_avec_description_complete": sum(1 for o in unified_offers if o.description),
    }


# ==============================================================================
# Orchestrateur Multi-Sources (5 plateformes, Cache 24h & Pagination)
# ==============================================================================
def collect_all_sources(
    guichet_limit: int = 8,
    other_limit: int = 4,
    student_only: bool = False,
    keyword: Optional[str] = None,
    delay: float = 2.0,
    pages: int = 1,
    use_cache: bool = True,
    cache_dir: Path = CACHE_DIR,
) -> list[dict[str, Any]]:
    """Collecte et enrichit les offres sur les 5 sources avec cache disque 24 h et pagination."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-CA,fr;q=0.9"})

    all_offers: list[JobBankOffer] = []

    # 1. Guichet-Emplois Canada (14 codes CNP TI, multi-pages)
    first_url = build_cnp_search_url(province="QC", student_only=student_only, keyword=keyword, page=1)
    allowed, _ = check_robots_permission(session, GUICHET_BASE_URL, first_url, default_delay=DEFAULT_CRAWL_DELAY)
    if allowed:
        try:
            ge_offers = collect_guichet_paginated_offers(
                session=session,
                pages=pages,
                province="QC",
                student_only=student_only,
                keyword=keyword,
                delay=delay,
            )
            print(f"  -> {len(ge_offers)} offres TI détectées sur {max(1, pages)} page(s) CNP. Enrichissement de {guichet_limit} fiches...")
            for idx, off in enumerate(ge_offers[:guichet_limit], start=1):
                try:
                    detail_html, from_cache = get_cached_or_fetch(
                        session,
                        off.url,
                        cache_dir=cache_dir,
                        delay=delay,
                        use_cache=use_cache,
                    )
                    parse_job_detail_html(detail_html, off, student_filter=student_only)
                    tag = "CACHE" if from_cache else "HTTP"
                    print(
                        f"  ✓ ({idx}/{guichet_limit}) [ge|{tag}|CNP:{off.code_cnp}] "
                        f"{off.titre_employeur or off.titre} — {off.entreprise} ({len(off.competences_cles)} technos)"
                    )
                    all_offers.append(off)
                except requests.RequestException as exc:
                    print(f"  ! Erreur fiche {off.url}: {exc}")
        except requests.RequestException as exc:
            print(f"  ! Erreur recherche Guichet-Emplois : {exc}")

    # 2. Talent.com Canada (JSON-LD @graph + GPS + filtre CNP TI)
    tc_query = keyword or ("stage informatique" if student_only else "développeur informatique")
    tc_url = f"https://ca.talent.com/fr/jobs?k={quote_plus(tc_query)}&l={quote_plus('Québec, QC')}"
    print(f"\n[Source 2 - Talent.com Canada] Recherche : {tc_url}")
    try:
        tc_resp = session.get(tc_url, timeout=15)
        tc_resp.raise_for_status()
        tc_links = parse_talent_search_json_ld(tc_resp.text)
        print(f"  -> {len(tc_links)} offres détectées dans l'ItemList JSON-LD.")
        tc_count = 0
        for u in tc_links:
            if tc_count >= other_limit:
                break
            detail_html, from_cache = get_cached_or_fetch(
                session,
                u,
                cache_dir=cache_dir,
                delay=delay,
                use_cache=use_cache,
            )
            parsed = parse_talent_job_detail_html(detail_html, u)
            if parsed:
                tc_count += 1
                tag = "CACHE" if from_cache else "HTTP"
                print(
                    f"  ✓ [tc|{tag}|CNP:{parsed.code_cnp}] {parsed.titre} — {parsed.entreprise} "
                    f"(GPS: {parsed.latitude}, {parsed.longitude})"
                )
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Talent.com : {exc}")

    # 3. Jobboom Québec (Secteur TI _i10lfr, multi-pages + filtre CNP TI)
    try:
        jb_links = collect_jobboom_paginated_urls(session=session, pages=pages, delay=delay)
        print(f"  -> {len(jb_links)} offres organiques trouvées sur {max(1, pages)} page(s) Jobboom.")
        jb_count = 0
        for u in jb_links:
            if jb_count >= other_limit:
                break
            detail_html, from_cache = get_cached_or_fetch(
                session,
                u,
                cache_dir=cache_dir,
                delay=delay,
                use_cache=use_cache,
            )
            parsed = parse_json_ld_job_posting(detail_html, u, source_name="jobboom", id_prefix="jb")
            if parsed:
                jb_count += 1
                tag = "CACHE" if from_cache else "HTTP"
                print(f"  ✓ [jb|{tag}|CNP:{parsed.code_cnp}] {parsed.titre} — {parsed.entreprise} ({len(parsed.competences_cles)} technos)")
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Jobboom : {exc}")

    # 4. Jobillico Québec (JSON-LD JobPosting + filtre CNP TI)
    ji_query = keyword or ("stage informatique" if student_only else "développeur")
    ji_url = f"https://www.jobillico.com/recherche-emploi?skwd={quote(ji_query)}&scty={quote('Québec, QC')}"
    print(f"\n[Source 4 - Jobillico Québec] Recherche : {ji_url}")
    try:
        ji_resp = session.get(ji_url, timeout=15)
        ji_resp.raise_for_status()
        ji_links = parse_jobillico_listing_html(ji_resp.text)
        print(f"  -> {len(ji_links)} offres détectées sur Jobillico.")
        ji_count = 0
        for u in ji_links:
            if ji_count >= other_limit:
                break
            detail_html, from_cache = get_cached_or_fetch(
                session,
                u,
                cache_dir=cache_dir,
                delay=delay,
                use_cache=use_cache,
            )
            parsed = parse_json_ld_job_posting(detail_html, u, source_name="jobillico", id_prefix="ji")
            if parsed:
                ji_count += 1
                tag = "CACHE" if from_cache else "HTTP"
                print(f"  ✓ [ji|{tag}|CNP:{parsed.code_cnp}] {parsed.titre} — {parsed.entreprise} ({len(parsed.competences_cles)} technos)")
                all_offers.append(parsed)
    except requests.RequestException as exc:
        print(f"  ! Erreur Jobillico : {exc}")

    # 5. Remotive API (Télétravail Canada, avec cache 24 h + filtre CNP TI)
    all_offers.extend(fetch_remotive_canada_offers(session, limit=other_limit, use_cache=use_cache, cache_dir=cache_dir))

    return [asdict(o) for o in all_offers]


def consolidate_data_directory(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    """
    Charge les 5 fichiers JSON par source sous `data/` (`offres_guichet_emplois.json`,
    `offres_jobboom.json`, `offres_talent.json`, `offres_jobillico.json`, `offres_remotive.json`),
    applique le filtrage CNP 2021 TI, l'enrichissement Lot 4 et la déduplication/fusion,
    puis génère `data/offres_unifiees.json`, `data/offres_unifiees.csv` et `data/rapport_collecte.json`.
    """
    source_files = [
        ("guichet-emplois", "ge", "offres_guichet_emplois.json"),
        ("jobboom", "jb", "offres_jobboom.json"),
        ("talent-canada", "tc", "offres_talent.json"),
        ("jobillico", "ji", "offres_jobillico.json"),
        ("remotive", "rem", "offres_remotive.json"),
    ]
    all_offers: list[JobBankOffer] = []
    per_source_counts: dict[str, dict[str, int]] = {}

    for src_name, prefix, filename in source_files:
        fpath = data_dir / filename
        if not fpath.is_file():
            continue
        raw_items = json.loads(fpath.read_text(encoding="utf-8"))
        retained = 0
        rejected = 0
        for item in raw_items:
            raw_id = str(item.get("source_id") or str(item.get("id", "")).split("-")[-1])
            oid = str(item.get("id") or f"{prefix}-{raw_id}")
            off = JobBankOffer(
                id=oid,
                source_id=raw_id,
                url=normalize_job_url(item.get("url") or ""),
                titre=item.get("titre"),
                titre_employeur=item.get("titre_employeur"),
                code_cnp=item.get("code_cnp"),
                cnp_title=item.get("cnp_title"),
                domaine_ti=item.get("domaine_ti"),
                entreprise=item.get("entreprise"),
                lieu=item.get("lieu"),
                ville=item.get("ville"),
                region_administrative=item.get("region_administrative"),
                code_postal=item.get("code_postal"),
                province=item.get("province") or "QC",
                pays=item.get("pays") or "Canada",
                source=src_name,
                source_partenaire=item.get("source_partenaire"),
                url_partenaire=item.get("url_partenaire"),
                date_publication=parse_iso_date(item.get("date_publication")),
                date_fin=parse_iso_date(item.get("date_fin")),
                type_poste=item.get("type_poste"),
                modalite=item.get("modalite"),
                niveau_etudes=item.get("niveau_etudes"),
                experience_requise=item.get("experience_requise"),
                niveau_seniorite=item.get("niveau_seniorite"),
                salaire=item.get("salaire"),
                salaire_min=item.get("salaire_min"),
                salaire_max=item.get("salaire_max"),
                unite_salaire=item.get("unite_salaire"),
                est_stage=bool(item.get("est_stage", False)),
                statut_stage=item.get("statut_stage") or "not_indicated",
                competences_cles=list(item.get("competences_cles") or []),
                missions_cles=list(item.get("missions_cles") or []),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                http_status=int(item.get("http_status") or 200),
                description=item.get("description"),
                date_extraction=item.get("date_extraction") or datetime.now(timezone.utc).isoformat(),
            )
            cnp_res = classify_cnp_2021(
                off.titre_employeur or off.titre,
                off.description,
                off.cnp_title,
                off.competences_cles,
                source=src_name,
            )
            if cnp_res is None:
                rejected += 1
                continue
            off.code_cnp = cnp_res[0]
            if not off.cnp_title:
                off.cnp_title = cnp_res[1]
            enrich_offer_metadata(off)
            all_offers.append(off)
            retained += 1

        per_source_counts[src_name] = {
            "brutes_lues": len(raw_items),
            "retenues_ti_cnp": retained,
            "rejetees_hors_ti": rejected,
        }

    unified, dedup_stats = unify_and_deduplicate_offers(all_offers)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "offres_unifiees.json").write_text(
        json.dumps([asdict(o) for o in unified], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    export_offers_to_csv(unified, data_dir / "offres_unifiees.csv")
    report = build_collection_report(per_source_counts, dedup_stats, unified)
    (data_dir / "rapport_collecte.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def run_autonomous_full_collection(
    data_dir: Path = DATA_DIR,
    cache_dir: Path = CACHE_DIR,
    guichet_pages: int = 9,
    jobboom_pages: int = 10,
    delay: float = 0.25,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Exécute la collecte autonome de bout en bout par notre propre système (`poc_guichet_cnp_v2.py`)
    sur les 5 plateformes (Guichet-Emplois, Jobboom, Talent.com, Jobillico, Remotive) avec cache disque 24 h :
    1. Guichet-Emplois : parcourt les pages CNP TI (`fn21`) ET télécharge chaque fiche individuelle (`offredemploi/<id>`)
       pour extraire la description RDFa/DOM, le vrai titre employeur, l'URL partenaire, les tâches et compétences.
    2. Jobboom : parcourt les pages de la catégorie TI (`_i10lfr`), télécharge chaque fiche JSON-LD et filtre par CNP TI.
    3. Talent.com : interroge plusieurs requêtes/villes TI au Québec, télécharge chaque fiche JSON-LD (avec GPS) et filtre par CNP TI.
    4. Jobillico : interroge plusieurs requêtes/villes TI au Québec, télécharge chaque fiche JSON-LD et filtre par CNP TI.
    5. Remotive : interroge l'API REST par catégories TI et filtre les postes ouverts au Canada et classifiés CNP TI.
    Enregistre sous `data/` les 5 fichiers JSON par source, `offres_unifiees.json`, `offres_unifiees.csv` et `rapport_collecte.json`.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-CA,fr;q=0.9"})
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    per_source_counts: dict[str, dict[str, int]] = {}
    total_intra_merged = 0

    # --------------------------------------------------------------------------
    # 1. GUICHET-EMPLOIS CANADA (Pagination CNP TI + Lecture de TOUTES les fiches)
    # --------------------------------------------------------------------------
    print("\n==================================================================")
    print(" [1/5] Collecte autonome Guichet-Emplois Canada (14 codes CNP TI)")
    print("==================================================================")
    ge_cards: list[JobBankOffer] = []
    seen_ge_ids: set[str] = set()
    for page_num in range(1, max(1, guichet_pages) + 1):
        page_url = build_cnp_search_url(province="QC", page=page_num)
        try:
            page_html, _ = get_cached_or_fetch(session, page_url, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            page_offers = parse_search_results_html(page_html)
            if not page_offers:
                break
            new_on_page = 0
            for off in page_offers:
                if off.id not in seen_ge_ids:
                    seen_ge_ids.add(off.id)
                    ge_cards.append(off)
                    new_on_page += 1
            print(f"  -> Page {page_num} : {len(page_offers)} cartes lues ({new_on_page} nouvelles, total: {len(ge_cards)})")
            if new_on_page == 0:
                break
        except requests.RequestException as exc:
            print(f"  ! Erreur page {page_num} Guichet-Emplois : {exc}")
            break

    ge_enriched: list[JobBankOffer] = []
    for idx, off in enumerate(ge_cards, start=1):
        try:
            detail_html, from_cache = get_cached_or_fetch(
                session,
                off.url,
                cache_dir=cache_dir,
                delay=0.0 if from_cache_check(off.url, cache_dir) else delay,
                use_cache=use_cache,
            )
            parse_job_detail_html(detail_html, off)
            ge_enriched.append(off)
            if idx % 25 == 0 or idx == len(ge_cards):
                tag = "CACHE" if from_cache else "HTTP"
                print(f"  ✓ Fiches Guichet-Emplois enrichies : {idx}/{len(ge_cards)} (dernière [{tag}] : {off.id})")
        except requests.RequestException as exc:
            print(f"  ! Erreur fiche {off.url} : {exc}")
            enrich_offer_metadata(off)
            ge_enriched.append(off)

    ge_dedup, ge_dstats = unify_and_deduplicate_offers(ge_enriched)
    total_intra_merged += ge_dstats["doublons_intra_fusionnes"]
    per_source_counts["guichet-emplois"] = {
        "brutes_lues": len(ge_enriched),
        "retenues_ti_cnp": len(ge_dedup),
        "rejetees_hors_ti": 0,
    }

    # --------------------------------------------------------------------------
    # 2. JOBBOOM QUÉBEC (Pagination _i10lfr + Fiches JSON-LD + Filtre CNP TI)
    # --------------------------------------------------------------------------
    print("\n==================================================================")
    print(" [2/5] Collecte autonome Jobboom Québec (Secteur TI _i10lfr)")
    print("==================================================================")
    jb_urls: list[str] = []
    for page_num in range(1, max(1, jobboom_pages) + 1):
        jb_list_url = build_jobboom_listing_url(page=page_num)
        try:
            list_html, _ = get_cached_or_fetch(session, jb_list_url, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            p_urls = parse_jobboom_listing_html(list_html)
            if not p_urls:
                break
            new_u = [u for u in p_urls if u not in jb_urls]
            jb_urls.extend(new_u)
            print(f"  -> Page {page_num} : {len(p_urls)} cartes organiques ({len(new_u)} nouvelles, total: {len(jb_urls)})")
            if not new_u:
                break
        except requests.RequestException as exc:
            print(f"  ! Erreur page {page_num} Jobboom : {exc}")
            break

    jb_offers: list[JobBankOffer] = []
    jb_rejected = 0
    for idx, u in enumerate(jb_urls, start=1):
        try:
            d_html, _ = get_cached_or_fetch(session, u, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            parsed = parse_json_ld_job_posting(d_html, u, source_name="jobboom", id_prefix="jb")
            if parsed is not None:
                jb_offers.append(parsed)
            else:
                jb_rejected += 1
        except requests.RequestException:
            continue

    jb_dedup, jb_dstats = unify_and_deduplicate_offers(jb_offers)
    total_intra_merged += jb_dstats["doublons_intra_fusionnes"]
    per_source_counts["jobboom"] = {
        "brutes_lues": len(jb_offers) + jb_rejected,
        "retenues_ti_cnp": len(jb_dedup),
        "rejetees_hors_ti": jb_rejected,
    }
    print(f"  ✓ Jobboom : {len(jb_dedup)} offres TI uniques retenues ({jb_rejected} hors-TI rejetées)")

    # --------------------------------------------------------------------------
    # 3. TALENT.COM CANADA (Multi-requêtes TI QC + JSON-LD @graph + GPS)
    # --------------------------------------------------------------------------
    print("\n==================================================================")
    print(" [3/5] Collecte autonome Talent.com Canada (JSON-LD + GPS)")
    print("==================================================================")
    tc_queries = [
        ("développeur informatique", "Québec, QC"),
        ("programmeur analyste", "Montréal, QC"),
        ("technicien informatique", "Québec, QC"),
        ("cybersécurité", "Montréal, QC"),
        ("stage informatique", "Québec, QC"),
        ("administrateur système réseau", "Montréal, QC"),
        ("data analyst", "Montréal, QC"),
        ("devops cloud", "Montréal, QC"),
    ]
    tc_urls: list[str] = []
    for q_kw, q_loc in tc_queries:
        s_url = f"https://ca.talent.com/fr/jobs?k={quote_plus(q_kw)}&l={quote_plus(q_loc)}"
        try:
            s_html, _ = get_cached_or_fetch(session, s_url, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            for u in parse_talent_search_json_ld(s_html):
                if u not in tc_urls:
                    tc_urls.append(u)
        except requests.RequestException:
            continue

    tc_offers: list[JobBankOffer] = []
    tc_rejected = 0
    for u in tc_urls:
        try:
            d_html, _ = get_cached_or_fetch(session, u, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            parsed = parse_talent_job_detail_html(d_html, u)
            if parsed is not None:
                tc_offers.append(parsed)
            else:
                tc_rejected += 1
        except requests.RequestException:
            continue

    tc_dedup, tc_dstats = unify_and_deduplicate_offers(tc_offers)
    total_intra_merged += tc_dstats["doublons_intra_fusionnes"]
    per_source_counts["talent-canada"] = {
        "brutes_lues": len(tc_offers) + tc_rejected,
        "retenues_ti_cnp": len(tc_dedup),
        "rejetees_hors_ti": tc_rejected,
    }
    print(f"  ✓ Talent.com : {len(tc_dedup)} offres TI uniques avec GPS retenues ({tc_rejected} hors-TI rejetées)")

    # --------------------------------------------------------------------------
    # 4. JOBILLICO QUÉBEC (Multi-requêtes TI QC + JSON-LD + Filtre CNP TI)
    # --------------------------------------------------------------------------
    print("\n==================================================================")
    print(" [4/5] Collecte autonome Jobillico Québec (JSON-LD JobPosting)")
    print("==================================================================")
    ji_queries = [
        ("développeur", "Québec, QC"),
        ("technicien informatique", "Québec, QC"),
        ("analyste programmeur", "Montréal, QC"),
        ("stage informatique", "Montréal, QC"),
        ("administrateur système", "Québec, QC"),
        ("cybersécurité", "Montréal, QC"),
    ]
    ji_urls: list[str] = []
    for q_kw, q_loc in ji_queries:
        s_url = f"https://www.jobillico.com/recherche-emploi?skwd={quote(q_kw)}&scty={quote(q_loc)}"
        try:
            s_html, _ = get_cached_or_fetch(session, s_url, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            for u in parse_jobillico_listing_html(s_html):
                if u not in ji_urls:
                    ji_urls.append(u)
        except requests.RequestException:
            continue

    ji_offers: list[JobBankOffer] = []
    ji_rejected = 0
    for u in ji_urls:
        try:
            d_html, _ = get_cached_or_fetch(session, u, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            parsed = parse_json_ld_job_posting(d_html, u, source_name="jobillico", id_prefix="ji")
            if parsed is not None:
                ji_offers.append(parsed)
            else:
                ji_rejected += 1
        except requests.RequestException:
            continue

    ji_dedup, ji_dstats = unify_and_deduplicate_offers(ji_offers)
    total_intra_merged += ji_dstats["doublons_intra_fusionnes"]
    per_source_counts["jobillico"] = {
        "brutes_lues": len(ji_offers) + ji_rejected,
        "retenues_ti_cnp": len(ji_dedup),
        "rejetees_hors_ti": ji_rejected,
    }
    print(f"  ✓ Jobillico : {len(ji_dedup)} offres TI uniques retenues ({ji_rejected} hors-TI rejetées)")

    # --------------------------------------------------------------------------
    # 5. REMOTIVE API (API REST officielle - Télétravail Canada + CNP TI)
    # --------------------------------------------------------------------------
    print("\n==================================================================")
    print(" [5/5] Collecte autonome Remotive API (Télétravail Canada TI)")
    print("==================================================================")
    rem_offers: list[JobBankOffer] = []
    rem_rejected = 0
    for cat in ("software-dev", "data", "devops", "qa"):
        api_u = f"https://remotive.com/api/remote-jobs?category={cat}&limit=60"
        try:
            raw_json, _ = get_cached_or_fetch(session, api_u, cache_dir=cache_dir, delay=delay, use_cache=use_cache)
            payload = json.loads(raw_json)
            for job_item in payload.get("jobs", []):
                parsed = parse_remotive_job_item(job_item)
                if parsed is not None:
                    rem_offers.append(parsed)
                else:
                    rem_rejected += 1
        except (requests.RequestException, json.JSONDecodeError):
            continue

    rem_dedup, rem_dstats = unify_and_deduplicate_offers(rem_offers)
    total_intra_merged += rem_dstats["doublons_intra_fusionnes"]
    per_source_counts["remotive"] = {
        "brutes_lues": len(rem_offers) + rem_rejected,
        "retenues_ti_cnp": len(rem_dedup),
        "rejetees_hors_ti": rem_rejected,
    }
    print(f"  ✓ Remotive : {len(rem_dedup)} offres TI uniques retenues ({rem_rejected} hors-TI/hors-Canada filtrées)")

    # --------------------------------------------------------------------------
    # Sauvegarde des 5 JSON par source + Unification + CSV + Rapport
    # --------------------------------------------------------------------------
    datasets = [
        ("offres_guichet_emplois.json", ge_dedup),
        ("offres_jobboom.json", jb_dedup),
        ("offres_talent.json", tc_dedup),
        ("offres_jobillico.json", ji_dedup),
        ("offres_remotive.json", rem_dedup),
    ]
    all_combined: list[JobBankOffer] = []
    for fname, dset in datasets:
        (data_dir / fname).write_text(
            json.dumps([asdict(o) for o in dset], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        all_combined.extend(dset)

    unified, cross_dstats = unify_and_deduplicate_offers(all_combined)
    dedup_stats = {
        "total_entree": len(all_combined) + total_intra_merged,
        "doublons_intra_fusionnes": total_intra_merged + cross_dstats["doublons_intra_fusionnes"],
        "doublons_inter_fusionnes": cross_dstats["doublons_inter_fusionnes"],
        "total_unifie": len(unified),
    }

    (data_dir / "offres_unifiees.json").write_text(
        json.dumps([asdict(o) for o in unified], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    export_offers_to_csv(unified, data_dir / "offres_unifiees.csv")
    report = build_collection_report(per_source_counts, dedup_stats, unified)
    (data_dir / "rapport_collecte.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def from_cache_check(url: str, cache_dir: Path = CACHE_DIR, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> bool:
    """Vérifie rapidement si une URL est déjà présente et valide dans le cache disque local."""
    cf = _cache_file_for_url(url, cache_dir=cache_dir)
    if not cf.exists():
        return False
    try:
        payload = json.loads(cf.read_text(encoding="utf-8"))
        return (time.time() - float(payload.get("fetched_at", 0.0))) < ttl_seconds
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecteur Multi-Sources Enrichi (5 sites Québec/Canada - Livrable 3 Lot 4)")
    parser.add_argument("--limite-guichet", type=int, default=8, help="Offres Guichet-Emplois CNP à enrichir (défaut: 8)")
    parser.add_argument("--limite-autres", type=int, default=4, help="Offres par autre source à enrichir (défaut: 4)")
    parser.add_argument("--pages", type=int, default=1, help="Nombre de pages de résultats à parcourir sur Guichet-Emplois et Jobboom (défaut: 1)")
    parser.add_argument("--stages", action="store_true", help="Cibler en priorité les stages TI")
    parser.add_argument("--mot-cle", type=str, default=None, help="Mot-clé optionnel")
    parser.add_argument("--delai", type=float, default=2.0, help="Délai en secondes entre les nouvelles fiches HTTP (défaut: 2.0s)")
    parser.add_argument("--sans-cache", action="store_true", help="Désactiver le cache disque local 24 h")
    parser.add_argument("--collecte-complete", action="store_true", help="Lancer la collecte autonome complète par notre système sur les 5 sources (avec lecture de toutes les fiches détaillées) vers data/*.json et .csv")
    parser.add_argument("--consolider-data", action="store_true", help="Unifier et dédupliquer hors ligne les 5 fichiers data/offres_*.json vers offres_unifiees.json/.csv et rapport_collecte.json")
    parser.add_argument("--sortie", type=str, default="echantillon_v2.json", help="Fichier JSON de sortie")
    args = parser.parse_args()

    if args.collecte_complete:
        report = run_autonomous_full_collection(
            data_dir=DATA_DIR,
            cache_dir=CACHE_DIR,
            delay=args.delai if args.delai != 2.0 else 0.25,
            use_cache=not args.sans_cache,
        )
        print(
            f"\nCollecte autonome complète terminée : {report['total_offres_unifiees_ti']} offres TI uniques "
            f"(descriptions: {report['offres_avec_description_complete']}/{report['total_offres_unifiees_ti']}) "
            f"enregistrées sous data/"
        )
        return

    if args.consolider_data:
        report = consolidate_data_directory(DATA_DIR)
        print(
            f"Consolidation hors ligne terminée : {report['total_offres_unifiees_ti']} offres TI uniques "
            f"(intra: {report['deduplication']['doublons_intra_fusionnes']}, "
            f"inter: {report['deduplication']['doublons_inter_fusionnes']}) dans data/offres_unifiees.json et .csv"
        )
        return

    results = collect_all_sources(
        guichet_limit=args.limite_guichet,
        other_limit=args.limite_autres,
        student_only=args.stages,
        keyword=args.mot_cle,
        delay=args.delai,
        pages=args.pages,
        use_cache=not args.sans_cache,
    )

    out_path = Path(__file__).parent / args.sortie
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTerminé : {len(results)} offres multi-sources enrichies enregistrées dans {out_path.name}")


if __name__ == "__main__":
    main()
