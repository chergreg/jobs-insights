"""Extraction déterministe depuis les descriptions et titres d'offres Adzuna.

Ce module extrait, avec des expressions régulières ancrées et des règles explicites :
1. Les salaires (minimum, maximum, plafond, grille à plusieurs niveaux, devise, période).
2. Le type de contrat (Permanent, Contrat, Stage, Remplacement, Pigiste / Consultant, cas mixtes)
   et la durée du contrat lorsqu'elle est mentionnée.
3. Le temps de travail / horaire (Temps plein, Temps partiel, volume d'heures et unité d'origine).
4. La modalité de travail (Présentiel, Hybride, Télétravail).
5. La consolidation et la détection des anomalies/divergences entre l'API Adzuna et le texte.

Contributions de l'équipe réutilisées et adaptées :
- `equipe/kandet/03-amelioration-preuve-de-concept/normalisation.py` :
  logique de conversion numérique `_to_number` et dictionnaire d'unités salariales `TEXT_UNITS`,
  adaptés pour gérer les nombres avec milliers ET décimales (`110,600.00`), les entiers à 6 chiffres
  sans séparateur (`$100000`) et l'ancrage contextuel (afin de ne pas capturer `12 mois`, `Réf n°: 4955`,
  `80` heures ou `ÉCHELLE : 4278` comme des salaires).
- `equipe/elvira/03-amelioration-preuve-de-concept/models.py` :
  suppression des accents (`strip_accents`) et détection de la modalité.

Règles de rigueur appliquées :
- Aucune période salariale n'est devinée si elle n'est pas écrite dans le texte.
- Une valeur salariale suspecte (ex. `1 $` de la SODEC) n'est pas écrasée silencieusement :
  elle est conservée dans `api_salary_min`, signalée dans `anomalies` et la règle d'arbitrage
  est documentée dans `provenance_salaire`.
- Une différence entre un salaire annuel de l'API (ex. `93 600 - 104 000`) et un taux horaire dans le
  texte (ex. `$45.00hr - $50.00hr`) est vérifiée avec l'hypothèse explicite de `2 080 h/an` (40 h × 52 sem.)
  et signalée comme `equivalence_probable_annuel_horaire_2080h` sans écraser les valeurs d'origine.
- `80 heures par période de paie` est conservé avec son unité `"période de paie"`, sans conversion en
  `40 h/semaine`.
- Une modalité hybride (`2 jours/semaine au bureau`) n'est jamais confondue avec un temps partiel.
- Les faux positifs identifiés (`vision de détention permanente`, `avoir réalisé 2 mandats au cours des
  6 dernières années`, préfixe `intern` dans `international`/`internes`) sont formellement exclus.
"""

from __future__ import annotations

import re
import unicodedata

from models import ExtractionConditionsTexte, ExtractionSalaireTexte, OffreAdzuna


# Seuil indicatif d'alerte pour une valeur salariale API manifestement symbolique / placeholder (ex. 1 $ SODEC).
# Toute valeur sous ce seuil est signalée dans `anomalies` (jamais supprimée de `api_salary_min`).
SEUIL_SALAIRE_SUSPECT = 10.0
HEURES_ANNUELLES_STANDARD = 2080.0  # Hypothèse explicite : 40 h/semaine * 52 semaines


def sans_accents(texte: str | None) -> str:
    """Supprime les diacritiques pour fiabiliser certaines comparaisons."""
    decomposed = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def convertir_montant(jeton: str, facteur_milliers: bool = False) -> float | None:
    """Convertit un nombre écrit en français ou en anglais en `float`.

    Adapté de `_to_number` de Kandet (`equipe/kandet/03-amelioration-preuve-de-concept/normalisation.py`)
    pour supporter :
    - `56 647` -> 56647.0
    - `110,600.00` -> 110600.0
    - `28,40` -> 28.4
    - `31.51` -> 31.51
    - `100000` -> 100000.0
    """
    if not jeton:
        return None
    propre = jeton.strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not propre:
        return None

    decimale = re.search(r"[.,](\d{1,2})$", propre)
    if decimale:
        partie_entiere = re.sub(r"[.,]", "", propre[: decimale.start()]) or "0"
        valeur = float(f"{partie_entiere}.{decimale.group(1)}")
    else:
        chiffres = re.sub(r"[.,]", "", propre)
        if not chiffres.isdigit():
            return None
        valeur = float(chiffres)

    return valeur * 1000.0 if facteur_milliers else valeur


def normaliser_devise(devise_brute: str | None) -> str | None:
    """Normalise une mention explicite de devise sans l'inventer si absente."""
    if not devise_brute:
        return None
    d = devise_brute.strip().upper()
    if d in {"CA$", "CAD", "$ CA", "$CA", "CAD$"}:
        return "CAD"
    if d in {"US$", "USD", "$ US", "$US"}:
        return "USD"
    if "$" in d:
        return "$"
    return None


# Unités salariales adaptées de `TEXT_UNITS` de Kandet, restreintes au contexte salarial
UNITES_SALAIRE_CONTEXTE = (
    ("heure", re.compile(r"(?:/\s*h(?:eure|our|r)?\b|\b(?:par|per|de\s+l['’])\s*(?:heure|hour|hr)\b|\b(?:hourly|taux\s+horaire)\b|\d(?:[.,]\d+)?\s*hr\b)", re.I)),
    ("semaine", re.compile(r"(?:/\s*(?:semaine|week|wk)\b|\b(?:par|per)\s*(?:semaine|week)\b|\b(?:hebdomadaire|weekly)\b)", re.I)),
    ("mois", re.compile(r"(?:/\s*(?:mois|month|mo)\b|\b(?:par|per)\s*(?:mois|month)\b|\b(?:mensuel(?:le)?|monthly)\b)", re.I)),
    ("année", re.compile(r"(?:/\s*(?:an|année|annee|year|yr)\b|\b(?:par|per)\s*(?:an|année|annee|year)\b|\b(?:annuel(?:le)?|yearly|annual|annum|first-year\s+base\s+compensation)\b)", re.I)),
)


def detecter_periode_salaire(segment: str, contexte_proche: str = "") -> str | None:
    """Détecte la période salariale uniquement si elle est explicitement écrite dans le segment salarial.

    Ne regarde jamais une durée de contrat voisine (ex. `Duration: 12 months` ou `DURÉE DU CONTRAT : 12 mois`).
    """
    for unite, patron in UNITES_SALAIRE_CONTEXTE:
        if patron.search(segment):
            return unite
    if contexte_proche:
        # Ex. "La fourchette salariale annuelle prévue pour ce poste est de 92 000$ à 115 000$."
        if re.search(r"\b(?:salariale\s+annuelle|salaire\s+annuel|annual\s+salary|first-year\s+base\s+compensation)\b", contexte_proche, re.I):
            return "année"
        if re.search(r"\b(?:taux\s+horaire|salaire\s+horaire|hourly\s+(?:rate|pay))\b", contexte_proche, re.I):
            return "heure"
    return None


# --- Patrons ordonnés d'extraction salariale ----------------------------------

#expression pour un nombre monétaire : ex. "110,600.00", "56 647", "100000", "28,40", "45.00"
_NB = r"(?:\d{1,3}(?:[ \u00a0\u202f,]\d{3})+(?:[.,]\d{1,2})?|\d{4,6}(?:[.,]\d{1,2})?|\d{2,3}(?:[.,]\d{1,2})?)"

# 1. Grille salariale à plusieurs échelons (ex. BCG X : Engineer I: $110,000 CAD ... Engineer II: $150,000 CAD ...)
PATRON_ITEM_GRILLE = re.compile(
    r"(?:CA\$|CAD|\$)\s*(?P<val>" + _NB + r")\s*(?P<cur2>CAD|\$)?",
    re.I,
)

# 2. Format SODEC : "SALAIRE : Minimum : 56 647 $ Maximum : 103 015 $"
PATRON_MIN_MAX_EXPLICITE = re.compile(
    r"SALAIRE\s*:\s*Minimum\s*:\s*(?P<min>" + _NB + r")\s*(?P<cur1>\$|CAD)\s*"
    r"Maximum\s*:\s*(?P<max>" + _NB + r")\s*(?P<cur2>\$|CAD)"
    r"(?P<unit_tail>\s*(?:/|\bpar\b)\s*(?:heure|an|année|mois|semaine))?",
    re.I,
)

# 3. Format fonction publique CIUSSS : "Base (min.): 31.51 Base (max.): 57.81"
PATRON_BASE_MIN_MAX = re.compile(
    r"Base\s*\(min\.?\)\s*:\s*(?P<min>\d{2,6}(?:[.,]\d{1,2})?)\s*(?P<cur1>\$|CAD)?\s*"
    r"Base\s*\(max\.?\)\s*:\s*(?P<max>\d{2,6}(?:[.,]\d{1,2})?)\s*(?P<cur2>\$|CAD)?",
    re.I,
)

# 4. Format échelle secteur public : "ÉCHELLE : 4278 - 28,40 à 40,88 $/heure"
PATRON_ECHELLE_PUBLIQUE = re.compile(
    r"[ÉE]CHELLE\s*:\s*\d+\s*[-–]\s*(?P<min>\d{2,6}(?:[.,]\d{1,2})?)\s*(?:à|to|-|–)\s*"
    r"(?P<max>\d{2,6}(?:[.,]\d{1,2})?)\s*(?P<cur>\$|CAD)\s*(?P<unit>/\s*heure|/\s*h\b|par\s+heure|/\s*an|par\s+an(?:née)?)?",
    re.I,
)

# 5. Fourchette avec devise préfixée : "$100000 - $120000", "CAD 108,100 - CAD 222,800 - yearly",
#    "CA$110,600.00–CA$166,000.00 yearly", "$70- $110 per hour", "$45.00hr - $50.00hr"
PATRON_FOURCHETTE_DEVISE_PREFIXE = re.compile(
    r"(?P<cur1>CA\$|US\$|CAD|USD|\$)\s*(?P<min>" + _NB + r")\s*(?P<u1>hr|/h|/hr)?\s*"
    r"(?:à|to|-|–)\s*(?P<cur2>CA\$|US\$|CAD|USD|\$)?\s*(?P<max>" + _NB + r")\s*(?P<cur3>CAD|USD|\$)?\s*"
    r"(?P<unit>(?:[-–]\s*)?(?:yearly|annual(?:ly)?|per\s+hour|/\s*heure|/\s*hr?\b|hr\b|par\s+heure|par\s+an(?:née)?|per\s+year|monthly|par\s+mois|weekly|par\s+semaine))?",
    re.I,
)

# 6. Fourchette avec devise suffixée : "de 92 000$ à 115 000$", "28,40 à 40,88 $/heure"
PATRON_FOURCHETTE_DEVISE_SUFFIXE = re.compile(
    r"(?P<min>" + _NB + r")\s*(?P<cur1>\$|CAD)?\s*(?:à|to|-|–)\s*(?P<max>" + _NB + r")\s*"
    r"(?P<cur2>CA\$|CAD|USD|\$)\s*"
    r"(?P<unit>(?:/\s*(?:heure|h\b|an|année|mois|semaine)|par\s+(?:heure|an|année|mois|semaine)|per\s+(?:hour|year|month|week)|yearly|hourly))?",
    re.I,
)

# 7. Plafond salarial explicite : "Salary – Up to $210,000", "Salaire : jusqu'à 110 000 $"
PATRON_PLAFOND_SALAIRE = re.compile(
    r"(?:Salary|Salaire|Compensation|R[ée]mun[ée]ration)\s*[-–:]?\s*(?:Up\s+to|Jusqu['’]à)\s*"
    r"(?P<cur1>CA\$|CAD|USD|\$)?\s*(?P<max>" + _NB + r")\s*(?P<cur2>CAD|USD|\$)?\s*"
    r"(?P<unit>yearly|per\s+year|par\s+an(?:née)?|per\s+hour|/\s*h(?:eure)?)?",
    re.I,
)


def extraire_salaire_texte(titre: str | None, description: str | None) -> ExtractionSalaireTexte:
    """Extrait de manière déterministe les informations salariales d'un extrait de description (et titre).

    Priorise la description et ne consulte le titre que si aucune mention n'est trouvée dans la description.
    """
    desc = (description or "").strip()
    tit = (titre or "").strip()

    for source_texte in (desc, tit):
        if not source_texte:
            continue

        # A. Détection d'une grille salariale à plusieurs niveaux (ex. BCG X avec 4 échelons)
        if re.search(r"Base\s+Compensation\s+For\s+This\s+Role", source_texte, re.I):
            paliers: list[float] = []
            devises_grille: list[str] = []
            for m in PATRON_ITEM_GRILLE.finditer(source_texte):
                val = convertir_montant(m.group("val"))
                if val is not None and val >= 15.0:
                    paliers.append(val)
                dev = normaliser_devise(m.group("cur2") or "$")
                if dev:
                    devises_grille.append(dev)
            if len(paliers) >= 3:
                deb = source_texte.find("The First-year")
                segment = source_texte[deb if deb >= 0 else 0 : (deb if deb >= 0 else 0) + 235].strip()
                periode = detecter_periode_salaire(segment, source_texte)
                devise = "CAD" if "CAD" in devises_grille else (devises_grille[0] if devises_grille else "$")
                return ExtractionSalaireTexte(
                    salaire_min=min(paliers),
                    salaire_max=max(paliers),
                    devise=devise,
                    periode=periode,
                    type_mention="grille_multi_niveaux",
                    paliers_detectes=paliers,
                    segment_extrait=segment,
                )

        # B. Format SODEC ("SALAIRE : Minimum : 56 647 $ Maximum : 103 015 $")
        m = PATRON_MIN_MAX_EXPLICITE.search(source_texte)
        if m:
            s_min = convertir_montant(m.group("min"))
            s_max = convertir_montant(m.group("max"))
            devise = normaliser_devise(m.group("cur1") or m.group("cur2"))
            segment = m.group(0).strip()
            periode = detecter_periode_salaire(segment)
            return ExtractionSalaireTexte(
                salaire_min=s_min,
                salaire_max=s_max,
                devise=devise,
                periode=periode,
                type_mention="fourchette",
                segment_extrait=segment,
            )

        # C. Format Base (min.): 31.51 Base (max.): 57.81 (CIUSSS)
        m = PATRON_BASE_MIN_MAX.search(source_texte)
        if m:
            s_min = convertir_montant(m.group("min"))
            s_max = convertir_montant(m.group("max"))
            devise = normaliser_devise(m.group("cur1") or m.group("cur2"))
            segment = m.group(0).strip()
            periode = detecter_periode_salaire(segment)
            return ExtractionSalaireTexte(
                salaire_min=s_min,
                salaire_max=s_max,
                devise=devise,
                periode=periode,
                type_mention="fourchette",
                segment_extrait=segment,
            )

        # D. Format Échelle secteur public ("ÉCHELLE : 4278 - 28,40 à 40,88 $/heure")
        m = PATRON_ECHELLE_PUBLIQUE.search(source_texte)
        if m:
            s_min = convertir_montant(m.group("min"))
            s_max = convertir_montant(m.group("max"))
            devise = normaliser_devise(m.group("cur"))
            segment = m.group(0).strip()
            periode = detecter_periode_salaire(segment)
            return ExtractionSalaireTexte(
                salaire_min=s_min,
                salaire_max=s_max,
                devise=devise,
                periode=periode,
                type_mention="fourchette",
                segment_extrait=segment,
            )

        # E. Fourchette avec devise préfixée ("$100000 - $120000", "CA$110,600.00–CA$166,000.00 yearly", "$45.00hr - $50.00hr")
        m = PATRON_FOURCHETTE_DEVISE_PREFIXE.search(source_texte)
        if m:
            s_min = convertir_montant(m.group("min"))
            s_max = convertir_montant(m.group("max"))
            if s_min is not None and s_max is not None and s_max >= s_min:
                devise = normaliser_devise(m.group("cur1") or m.group("cur2") or m.group("cur3"))
                segment = m.group(0).strip()
                contexte = source_texte[max(0, m.start() - 60) : min(len(source_texte), m.end() + 40)]
                periode = detecter_periode_salaire(segment, contexte)
                return ExtractionSalaireTexte(
                    salaire_min=s_min,
                    salaire_max=s_max,
                    devise=devise,
                    periode=periode,
                    type_mention="fourchette",
                    segment_extrait=segment,
                )

        # F. Fourchette avec devise suffixée ("92 000$ à 115 000$")
        m = PATRON_FOURCHETTE_DEVISE_SUFFIXE.search(source_texte)
        if m:
            s_min = convertir_montant(m.group("min"))
            s_max = convertir_montant(m.group("max"))
            if s_min is not None and s_max is not None and s_max >= s_min:
                devise = normaliser_devise(m.group("cur2") or m.group("cur1"))
                segment = m.group(0).strip()
                contexte = source_texte[max(0, m.start() - 60) : min(len(source_texte), m.end() + 40)]
                periode = detecter_periode_salaire(segment, contexte)
                return ExtractionSalaireTexte(
                    salaire_min=s_min,
                    salaire_max=s_max,
                    devise=devise,
                    periode=periode,
                    type_mention="fourchette",
                    segment_extrait=segment,
                )

        # G. Plafond salarial ("Salary – Up to $210,000")
        m = PATRON_PLAFOND_SALAIRE.search(source_texte)
        if m:
            s_max = convertir_montant(m.group("max"))
            devise = normaliser_devise(m.group("cur1") or m.group("cur2"))
            segment = m.group(0).strip()
            contexte = source_texte[max(0, m.start() - 40) : min(len(source_texte), m.end() + 40)]
            periode = detecter_periode_salaire(segment, contexte)
            return ExtractionSalaireTexte(
                salaire_min=None,
                salaire_max=s_max,
                devise=devise,
                periode=periode,
                type_mention="plafond",
                segment_extrait=segment,
            )

    return ExtractionSalaireTexte()


# --- Extraction du contrat, du temps de travail et de la modalité -------------

# 1. Types de contrat (ancrés sur le poste proposé, excluant les descriptions d'entreprise et d'expérience passée)
PATRON_CONTRAT_MIXTE = re.compile(
    r"\b(?:Type|Statut|Employment\s+Type)\s*:\s*(?:Permanent\s+or\s+(?:Long\s+Term\s+)?Contract|Permanent\s+ou\s+(?:contrat|temporaire))\b",
    re.I,
)

PATRON_STAGE_TITRE = re.compile(
    r"\b(?:stages?|stagiaires?|internships?)\b",
    re.I,
)
PATRON_STAGE_DESC = re.compile(
    r"\b(?:offre\s+un\s+stage|stage\s+de\s+\d+\s*mois|stage\s+en\s+|recherche\s+des\s+stagiaires|convention\s+de\s+stage|internship\s+opportunity)\b",
    re.I,
)

PATRON_REMPLACEMENT = re.compile(
    r"\b(?:STATUT\s*:\s*)?Remplacement(?:\s+cong[ée]\s+de\s+maternit[ée]|\s+temporaire)?\b",
    re.I,
)

PATRON_PIGISTE = re.compile(
    r"\b(?:Pigistes?\s*/\s*consultant(?:\(e\))?s?\s+sont\s+bienvenu|poste\s+de\s+pigiste|freelance\s+position)\b",
    re.I,
)

# Durée explicite d'un contrat, mandat ou stage proposé (exclut "2 mandats ... au cours des 6 dernières années")
PATRON_DUREE_CONTRAT = re.compile(
    r"(?:"
    r"DUR[ÉE]E(?:\s+DU\s+CONTRAT)?\s*:\s*(?P<d1>\d+(?:\s*[-–à]\s*\d+)?\s*(?:mois|ans?)(?:\s+(?:renouvelable|possibilit[ée]\s+de\s+renouvellement))?)"
    r"|Duration\s*:\s*(?P<d2>\d+(?:\s*[-–]\s*\d+)?\s*(?:months?|years?))"
    r"|Mandat\s+de\s+(?P<d3>\d+(?:\s*[-–à]\s*\d+)?\s*(?:mois|ans?)(?:\s+renouvelable)?)"
    r"|contrat\s+(?:à\s+temps\s+(?:plein|partiel)\s*)?(?:\([^)]+\)\s*)?d['’]une\s+dur[ée]e\s+de\s+(?P<d4>\d+\s*(?:mois|ans?))"
    r"|\bstage\s+de\s+(?P<d5>\d+(?:\s*[-–à]\s*\d+)?\s*(?:mois|semaines?))"
    r")",
    re.I,
)

PATRON_CONTRAT_EXPLICITE = re.compile(
    r"(?:"
    r"Employment\s+Type\s*:\s*Contract\b"
    r"|\((?:Contrat|Contract)\)"
    r"|\bcombler\s+un\s+contrat\b"
    r"|\bposte\s+(?:contractuel|temporaire)\b"
    r")",
    re.I,
)

# Permanent : uniquement lorsqu'il qualifie le poste/statut (exclut "vision de détention permanente")
PATRON_PERMANENT = re.compile(
    r"(?:"
    r"statusPermanent"
    r"|(?:Statut(?:\s+de\s+l['’]emploi)?|Type\s+de\s+poste|Employment\s+Type)\s*:\s*(?:Poste\s+)?Permanent\b"
    r"|\b(?:poste|position|emploi|rôle|role)\s+permanent(?:e)?\b"
    r"|\bpermanent\s+(?:position|role|job|full[\s-]?time)\b"
    r")",
    re.I,
)

# 2. Temps de travail / Horaire
PATRON_TEMPS_PLEIN = re.compile(
    r"(?:"
    r"\btemps\s+plein\b"
    r"|\bfull[\s-]time\b"
    r")",
    re.I,
)

PATRON_TEMPS_PARTIEL = re.compile(
    r"(?:"
    r"\btemps\s+partiel\b"
    r"|\bpart[\s-]time\b"
    r")",
    re.I,
)

PATRON_HEURES_SEMAINE = re.compile(
    r"\b(?P<val>\d{2}(?:[.,]\d+)?)\s*(?:h|heures?|hours?)\s*(?:/|par|per)\s*(?:semaine|week)\b",
    re.I,
)

PATRON_HEURES_PERIODE_PAIE = re.compile(
    r"Nombre\s+d['’]heures\s+par\s+p[ée]riode\s+de\s+paie\s*:\s*(?P<val>\d{2,3}(?:[.,]\d+)?)",
    re.I,
)

PATRON_JOURS_TEMPS_PARTIEL = re.compile(
    r"temps\s+partiel\s*\((?P<details>\d+\s*(?:à|-)\s*\d+\s*jours?\s+par\s+semaine)\)",
    re.I,
)

PATRON_QUART_TRAVAIL = re.compile(
    r"Quart\s+de\s+travail\s*:\s*(?P<quart>Jour|Soir|Nuit|Variable)",
    re.I,
)

# 3. Modalité de travail (Présentiel, Hybride, Télétravail)
PATRON_HYBRIDE_DETAILS = re.compile(
    r"(?:"
    r"Hybrid\s+work\s*:\s*(?P<h1>\d+\s*days?\s+in\s+the\s+office(?:\s*/\s*\d+\s*days?\s+remote|\s+per\s+week)?)"
    r"|(?P<h2>\d+\s*j(?:ours?)?\s*/\s*semaine\s+au\s+bureau(?:\s+de\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)?)"
    r"|en\s+mode\s+hybride\s+(?P<h3>\d+\s*jours?\s+au\s+centre-ville)"
    r")",
    re.I,
)

PATRON_HYBRIDE = re.compile(
    r"(?:"
    r"typeHybrid"
    r"|\bmode\s+hybride\b"
    r"|\btravail\s+hybride\b"
    r"|\bhybrid\s+work\b"
    r"|\(hybride\)"
    r"|\bPostuler\s*:\s*Hybride\b"
    r"|\bTemps\s+plein\s*·\s*Hybride\b"
    r"|\bMontreal\s+QC/Hybrid\b"
    r"|\bTélétravail\s+et\s+présentiel\b"
    r")",
    re.I,
)

PATRON_TELETRAVAIL = re.compile(
    r"(?:"
    r"\bmode\s+t[ée]l[ée]travail\b"
    r"|\bFull-time\s+Remote\b"
    r"|\b100\s*%\s*(?:t[ée]l[ée]travail|remote|à\s+distance)\b"
    r"|\bTélétravail\s+avec\s+déplacements\s+occasionnels\b"
    r"|\bSTAGE\s+Télétravail\b"
    r"|\blieu\s+de\s+travail\s*:\s*N['’]importe\s+où\s+au\s+Québec\b"
    r")",
    re.I,
)

PATRON_PRESENTIEL = re.compile(
    r"(?:"
    r"\bMode\s+Pr[ée]sentiel\b"
    r"|\bPoste\s+en\s+pr[ée]sentiel\b"
    r"|\[Montr[ée]al\s*/\s*Sur\s+place\]"
    r"|\b100\s*%\s*(?:sur\s+place|pr[ée]sentiel|on[\s-]site)\b"
    r")",
    re.I,
)


def extraire_conditions_texte(titre: str | None, description: str | None) -> ExtractionConditionsTexte:
    """Extrait le type de contrat, l'horaire et la modalité à partir du titre et de la description."""
    tit = (titre or "").strip()
    desc = (description or "").strip()
    texte_complet = f"{tit} \n {desc}".strip()

    res = ExtractionConditionsTexte()

    # --- 1. Extraction de la durée du contrat (si mentionnée) ---
    m_duree = PATRON_DUREE_CONTRAT.search(texte_complet)
    if m_duree:
        res.duree_contrat = (
            m_duree.group("d1")
            or m_duree.group("d2")
            or m_duree.group("d3")
            or m_duree.group("d4")
            or m_duree.group("d5")
        )
        if res.duree_contrat:
            res.duree_contrat = " ".join(res.duree_contrat.split())

    # --- 2. Extraction du type de contrat ---
    m_mixte = PATRON_CONTRAT_MIXTE.search(texte_complet)
    if m_mixte:
        res.type_contrat = "Permanent ou Contrat"
        res.segment_contrat = m_mixte.group(0).strip()
    elif PATRON_STAGE_TITRE.search(tit) or PATRON_STAGE_DESC.search(desc):
        m_st = PATRON_STAGE_TITRE.search(tit) or PATRON_STAGE_DESC.search(desc)
        res.type_contrat = "Stage"
        res.segment_contrat = m_st.group(0).strip() if m_st else "Stage"
    elif PATRON_REMPLACEMENT.search(texte_complet):
        m_remp = PATRON_REMPLACEMENT.search(texte_complet)
        res.type_contrat = "Remplacement"
        res.segment_contrat = m_remp.group(0).strip() if m_remp else "Remplacement"
    elif PATRON_PIGISTE.search(texte_complet):
        m_pig = PATRON_PIGISTE.search(texte_complet)
        res.type_contrat = "Pigiste / Consultant"
        res.segment_contrat = m_pig.group(0).strip() if m_pig else "Pigiste / Consultant"
    elif PATRON_CONTRAT_EXPLICITE.search(texte_complet) or m_duree:
        m_ct = PATRON_CONTRAT_EXPLICITE.search(texte_complet) or m_duree
        res.type_contrat = "Contrat"
        res.segment_contrat = m_ct.group(0).strip() if m_ct else None
    elif PATRON_PERMANENT.search(texte_complet):
        m_perm = PATRON_PERMANENT.search(texte_complet)
        res.type_contrat = "Permanent"
        res.segment_contrat = m_perm.group(0).strip() if m_perm else "Permanent"

    # --- 3. Extraction du temps de travail / horaire ---
    segments_horaire: list[str] = []
    details_horaire: list[str] = []

    m_tp = PATRON_TEMPS_PARTIEL.search(texte_complet)
    m_tf = PATRON_TEMPS_PLEIN.search(texte_complet)
    if m_tp:
        res.horaire = "Temps partiel"
        segments_horaire.append(m_tp.group(0).strip())
        m_jtp = PATRON_JOURS_TEMPS_PARTIEL.search(texte_complet)
        if m_jtp:
            details_horaire.append(m_jtp.group("details").strip())
    elif m_tf:
        res.horaire = "Temps plein"
        segments_horaire.append(m_tf.group(0).strip())

    # Heures par semaine (ex. "35 h/semaine", "40 h / semaine")
    m_hs = PATRON_HEURES_SEMAINE.search(texte_complet)
    if m_hs:
        res.heures_valeur = convertir_montant(m_hs.group("val"))
        res.heures_unite = "semaine"
        segments_horaire.append(m_hs.group(0).strip())
    else:
        # Heures par période de paie (ex. "Nombre d'heures par période de paie: 80")
        # Règle : on conserve l'unité "période de paie" sans diviser par 2
        m_hp = PATRON_HEURES_PERIODE_PAIE.search(texte_complet)
        if m_hp:
            res.heures_valeur = convertir_montant(m_hp.group("val"))
            res.heures_unite = "période de paie"
            segments_horaire.append(m_hp.group(0).strip())

    m_quart = PATRON_QUART_TRAVAIL.search(texte_complet)
    if m_quart:
        details_horaire.append(f"Quart: {m_quart.group('quart')}")
        segments_horaire.append(m_quart.group(0).strip())

    if details_horaire:
        res.details_horaire = " | ".join(details_horaire)
    if segments_horaire:
        res.segment_horaire = " ; ".join(dict.fromkeys(segments_horaire))

    # --- 4. Extraction de la modalité (Présentiel, Hybride, Télétravail) ---
    m_hyb_det = PATRON_HYBRIDE_DETAILS.search(texte_complet)
    m_hyb = PATRON_HYBRIDE.search(texte_complet)
    m_tel = PATRON_TELETRAVAIL.search(texte_complet)
    m_pres = PATRON_PRESENTIEL.search(texte_complet)

    if m_hyb_det or m_hyb:
        res.modalite = "Hybride"
        if m_hyb_det:
            detail = m_hyb_det.group("h1") or m_hyb_det.group("h2") or m_hyb_det.group("h3")
            res.details_modalite = " ".join(detail.split()) if detail else None
            res.segment_modalite = m_hyb_det.group(0).strip()
        elif m_hyb:
            res.segment_modalite = m_hyb.group(0).strip()
    elif m_tel:
        res.modalite = "Télétravail"
        res.segment_modalite = m_tel.group(0).strip()
    elif m_pres:
        res.modalite = "Présentiel"
        res.segment_modalite = m_pres.group(0).strip()

    return res


# --- Consolidation, arbitrage et détection des anomalies ----------------------

MAP_API_CONTRAT = {
    "permanent": "Permanent",
    "contract": "Contrat",
}

MAP_API_HORAIRE = {
    "full_time": "Temps plein",
    "part_time": "Temps partiel",
}


def _formater_montant_court(val: float | None) -> str:
    if val is None:
        return ""
    if float(val).is_integer():
        return f"{int(val):,}".replace(",", " ")
    return f"{val:.2f}".replace(".", ",")


def formater_resume_salaire(
    s_min: float | None,
    s_max: float | None,
    devise: str | None,
    periode: str | None,
    type_mention: str | None = None,
) -> str | None:
    """Construit une représentation textuelle fidèle du salaire sans inventer la période."""
    if s_min is None and s_max is None:
        return None
    dev = devise or "$"
    per = f" / {periode}" if periode else ""

    if type_mention == "plafond" and s_max is not None and s_min is None:
        return f"Jusqu'à {_formater_montant_court(s_max)} {dev}{per}"
    if type_mention == "grille_multi_niveaux" and s_min is not None and s_max is not None:
        return f"{_formater_montant_court(s_min)} à {_formater_montant_court(s_max)} {dev}{per} (grille multi-échelons)"
    if s_min is not None and s_max is not None:
        if s_min == s_max:
            return f"{_formater_montant_court(s_min)} {dev}{per}"
        return f"{_formater_montant_court(s_min)} à {_formater_montant_court(s_max)} {dev}{per}"
    if s_min is not None:
        return f"À partir de {_formater_montant_court(s_min)} {dev}{per}"
    return f"Jusqu'à {_formater_montant_court(s_max)} {dev}{per}"


def enrichir_et_consolider_offre(offre: OffreAdzuna) -> None:
    """Exécute l'extraction textuelle sur une `OffreAdzuna` et consolide les champs avec leur provenance."""
    ext_sal = extraire_salaire_texte(offre.titre, offre.description)
    ext_cond = extraire_conditions_texte(offre.titre, offre.description)

    # 1. Enregistrement des valeurs extraites du texte
    offre.texte_salaire_min = ext_sal.salaire_min
    offre.texte_salaire_max = ext_sal.salaire_max
    offre.texte_devise = ext_sal.devise
    offre.texte_periode_salaire = ext_sal.periode
    offre.texte_type_mention_salaire = ext_sal.type_mention
    offre.texte_paliers_salariaux = list(ext_sal.paliers_detectes)
    offre.texte_segment_salaire = ext_sal.segment_extrait

    offre.texte_type_contrat = ext_cond.type_contrat
    offre.texte_duree_contrat = ext_cond.duree_contrat
    offre.texte_segment_contrat = ext_cond.segment_contrat

    offre.texte_horaire = ext_cond.horaire
    offre.texte_heures_valeur = ext_cond.heures_valeur
    offre.texte_heures_unite = ext_cond.heures_unite
    offre.texte_details_horaire = ext_cond.details_horaire
    offre.texte_segment_horaire = ext_cond.segment_horaire

    offre.texte_modalite = ext_cond.modalite
    offre.texte_details_modalite = ext_cond.details_modalite
    offre.texte_segment_modalite = ext_cond.segment_modalite

    # 2. Arbitrage et provenance du SALAIRE
    api_a_salaire = offre.api_salary_min is not None or offre.api_salary_max is not None
    txt_a_salaire = ext_sal.salaire_min is not None or ext_sal.salaire_max is not None

    api_suspect = (
        (offre.api_salary_min is not None and offre.api_salary_min < SEUIL_SALAIRE_SUSPECT)
        or (offre.api_salary_max is not None and offre.api_salary_max < SEUIL_SALAIRE_SUSPECT)
    )

    if api_suspect:
        offre.anomalies.append(
            f"salaire_api_suspect: api_salary_min={offre.api_salary_min}, api_salary_max={offre.api_salary_max} "
            f"(< {SEUIL_SALAIRE_SUSPECT:g}, valeur symbolique probable)"
        )

    if ext_sal.type_mention == "grille_multi_niveaux":
        paliers_str = ", ".join(str(int(p) if p.is_integer() else p) for p in ext_sal.paliers_detectes)
        offre.anomalies.append(
            f"grille_salariale_multi_niveaux: {len(ext_sal.paliers_detectes)} paliers détectés ({paliers_str})"
        )

    if api_a_salaire and not txt_a_salaire:
        if api_suspect:
            # Valeur suspecte sans mention dans le texte : on ne la promeut pas en salaire consolidé
            offre.salaire_min = None
            offre.salaire_max = None
            offre.provenance_salaire = "api_suspect_ignore"
        else:
            offre.salaire_min = offre.api_salary_min
            offre.salaire_max = offre.api_salary_max
            offre.devise = "CAD"
            offre.periode_salaire = None  # L'API Adzuna ne fournit aucune unité
            offre.provenance_salaire = "api"
            # Signalement informatif si montant inhabituel (ex. 50 ou 1500 sans période)
            if offre.api_salary_min is not None and offre.api_salary_min < 2000:
                offre.anomalies.append(
                    f"periode_salaire_api_inconnue: montant={offre.api_salary_min} sans unité fournie par l'API"
                )
    elif not api_a_salaire and txt_a_salaire:
        offre.salaire_min = ext_sal.salaire_min
        offre.salaire_max = ext_sal.salaire_max
        offre.devise = ext_sal.devise
        offre.periode_salaire = ext_sal.periode
        offre.provenance_salaire = (
            "description_grille_multi_niveaux"
            if ext_sal.type_mention == "grille_multi_niveaux"
            else "description"
        )
    elif api_a_salaire and txt_a_salaire:
        if api_suspect:
            # Cas SODEC : api_salary_min = 1 vs description = 56 647 $ à 103 015 $
            offre.salaire_min = ext_sal.salaire_min
            offre.salaire_max = ext_sal.salaire_max
            offre.devise = ext_sal.devise
            offre.periode_salaire = ext_sal.periode
            offre.provenance_salaire = "description_remplace_api_suspect"
            offre.anomalies.append(
                f"arbitrage_salaire: valeur API suspecte ({offre.api_salary_min}) remplacée par la fourchette "
                f"extraite de la description ({ext_sal.salaire_min} - {ext_sal.salaire_max})"
            )
        else:
            # Les deux sont présents et >= 10 : vérifier concordance ou équivalence horaire/annuelle (2 080 h/an)
            if (
                offre.api_salary_min == ext_sal.salaire_min
                and offre.api_salary_max == ext_sal.salaire_max
            ):
                offre.salaire_min = offre.api_salary_min
                offre.salaire_max = offre.api_salary_max
                offre.devise = ext_sal.devise or "CAD"
                offre.periode_salaire = ext_sal.periode
                offre.provenance_salaire = "api+description"
            elif (
                ext_sal.periode == "heure"
                and ext_sal.salaire_min is not None
                and offre.api_salary_min is not None
                and abs(ext_sal.salaire_min * HEURES_ANNUELLES_STANDARD - offre.api_salary_min) <= 500.0
            ):
                # Cas 5966889227 : API=(93600, 104000) vs Texte=($45.00hr - $50.00hr) -> 45 * 2080 = 93600
                # On ne remplace pas silencieusement la valeur API : on conserve la valeur API et on documente l'équivalence
                offre.salaire_min = offre.api_salary_min
                offre.salaire_max = offre.api_salary_max
                offre.devise = ext_sal.devise or "CAD"
                offre.periode_salaire = "année (équivalent 2080h du taux horaire texte)"
                offre.provenance_salaire = "equivalence_probable_annuel_horaire_2080h"
                offre.anomalies.append(
                    f"equivalence_probable_annuel_horaire_2080h: API=({offre.api_salary_min}, {offre.api_salary_max}) "
                    f"correspond à Texte=({ext_sal.salaire_min}, {ext_sal.salaire_max} / heure) * 2080 h/an"
                )
            else:
                # Divergence réelle non explicable par 2080 h : on conserve la valeur API et on signale la divergence
                offre.salaire_min = offre.api_salary_min
                offre.salaire_max = offre.api_salary_max
                offre.devise = ext_sal.devise or "CAD"
                offre.periode_salaire = None
                offre.provenance_salaire = "divergence_api_description"
                offre.anomalies.append(
                    f"divergence_salaire: API=({offre.api_salary_min}, {offre.api_salary_max}) "
                    f"vs Texte=({ext_sal.salaire_min}, {ext_sal.salaire_max}, periode={ext_sal.periode})"
                )

    offre.salaire_resume = formater_resume_salaire(
        offre.salaire_min,
        offre.salaire_max,
        offre.devise,
        offre.periode_salaire,
        ext_sal.type_mention if offre.provenance_salaire.startswith("description") else None,
    )

    # 3. Arbitrage et provenance du TYPE DE CONTRAT
    api_ct_norm = MAP_API_CONTRAT.get((offre.api_contract_type or "").lower())
    txt_ct = ext_cond.type_contrat
    offre.duree_contrat = ext_cond.duree_contrat

    if api_ct_norm and not txt_ct:
        offre.type_contrat = api_ct_norm
        offre.provenance_contrat = "api"
    elif not api_ct_norm and txt_ct:
        offre.type_contrat = txt_ct
        offre.provenance_contrat = "description"
    elif api_ct_norm and txt_ct:
        if api_ct_norm == txt_ct:
            offre.type_contrat = api_ct_norm
            offre.provenance_contrat = "api+description"
        elif txt_ct == "Permanent ou Contrat":
            # L'API n'a retenu qu'un seul des deux statuts (ex. "contract") alors que le texte offre les deux
            offre.type_contrat = api_ct_norm
            offre.provenance_contrat = "nuance_api_description"
            offre.anomalies.append(
                f"nuance_type_contrat: API='{offre.api_contract_type}' alors que le texte indique '{ext_cond.segment_contrat}'"
            )
        else:
            # On ne remplace pas silencieusement la valeur structurée de l'API
            offre.type_contrat = api_ct_norm
            offre.provenance_contrat = "divergence_api_description"
            offre.anomalies.append(
                f"divergence_type_contrat: API='{api_ct_norm}' vs Texte='{txt_ct}'"
            )

    # 4. Arbitrage et provenance du TEMPS DE TRAVAIL / HORAIRE
    api_tm_norm = MAP_API_HORAIRE.get((offre.api_contract_time or "").lower())
    txt_tm = ext_cond.horaire

    if api_tm_norm and not txt_tm:
        offre.horaire_travail = api_tm_norm
        offre.provenance_horaire = "api"
    elif not api_tm_norm and txt_tm:
        offre.horaire_travail = txt_tm
        offre.provenance_horaire = "description"
    elif api_tm_norm and txt_tm:
        if api_tm_norm == txt_tm:
            offre.horaire_travail = api_tm_norm
            offre.provenance_horaire = "api+description"
        else:
            offre.horaire_travail = api_tm_norm
            offre.provenance_horaire = "divergence_api_description"
            offre.anomalies.append(
                f"divergence_horaire: API='{api_tm_norm}' vs Texte='{txt_tm}'"
            )

    # 5. Provenance de la MODALITÉ (l'API Adzuna n'a aucun champ structuré de modalité)
    if ext_cond.modalite:
        offre.modalite = ext_cond.modalite
        offre.provenance_modalite = "description"
    else:
        offre.modalite = None
        offre.provenance_modalite = "aucune"
