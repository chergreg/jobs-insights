"""Petites fonctions de texte partagées par les scrapers (aucun appel réseau).

Les expressions régulières ne s'appliquent qu'à du texte déjà extrait, jamais au HTML brut :
le HTML est toujours lu avec BeautifulSoup.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from bs4 import BeautifulSoup, Tag

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
UNITES_SALAIRE = {
    "HOUR": "de l'heure", "DAY": "par jour", "WEEK": "par semaine",
    "MONTH": "par mois", "YEAR": "par année",
}
MOTS_STAGE = re.compile(r"\b(stagiaires?|stages?|internship|intern|co-?op)\b")


def sans_accents(texte: str) -> str:
    """Minuscules sans accents, pour comparer des textes : « Février » → « fevrier »."""
    decompose = unicodedata.normalize("NFKD", texte.casefold())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def espaces(texte: str) -> str:
    """Espaces, tabulations et retours à la ligne réduits à une seule espace."""
    return " ".join(texte.split())


BLOCS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
         "tr", "table", "section", "article", "header", "footer", "blockquote", "pre"}


def texte_multiligne(balise: Tag | BeautifulSoup | None) -> str | None:
    """Texte d'un bloc avec une ligne par paragraphe ou puce, sans balises HTML. ``None`` si vide.

    Seuls les blocs (``<p>``, ``<li>``, ``<br>``…) passent à la ligne : un ``<strong>`` ou un ``<a>``
    au milieu d'une phrase ne la coupe pas. On travaille sur une copie pour ne pas modifier la page.
    """
    if balise is None:
        return None
    copie = BeautifulSoup(str(balise), "html.parser")
    for br in copie.find_all("br"):
        br.replace_with("\n")
    for bloc in copie.find_all(BLOCS):
        bloc.insert_before("\n")
        bloc.insert_after("\n")
    lignes = [espaces(ligne) for ligne in copie.get_text().splitlines()]
    texte = "\n".join(ligne for ligne in lignes if ligne)
    return texte or None


def html_vers_texte(contenu: str | None) -> str | None:
    """Texte propre d'un fragment HTML, même s'il est encodé deux fois (``&lt;p&gt;…``).

    1re lecture : ``&lt;p&gt;`` devient ``<p>`` ; s'il reste des balises, on relit une 2e fois.
    """
    if not contenu:
        return None
    soupe = BeautifulSoup(contenu, "html.parser")
    texte = soupe.get_text()
    if "<" in texte and ">" in texte:
        soupe = BeautifulSoup(texte, "html.parser")
    return texte_multiligne(soupe)


def date_iso(texte: str | None) -> str | None:
    """« Publiée le 16 novembre 2026 », « November 16, 2026 », « 2026-11-16T08:00 » → « 2026-11-16 »."""
    if not texte:
        return None
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})", texte)
    if iso:
        return iso.group(0)
    mots = re.findall(r"[a-z]+|\d+", sans_accents(texte))
    mois = next((MOIS[m] for m in mots if m in MOIS), None)
    nombres = [int(m) for m in mots if m.isdigit()]
    annee = next((n for n in nombres if n > 1900), None)
    jour = next((n for n in nombres if 1 <= n <= 31), None)
    if not (mois and annee and jour):
        return None
    try:
        return date(annee, mois, jour).isoformat()
    except ValueError:
        return None


def est_un_stage(*textes: str | None) -> bool | None:
    """True si un des textes parle de stage. ``None`` (inconnu) sinon : on ne conclut jamais « non »."""
    if any(t and MOTS_STAGE.search(sans_accents(t)) for t in textes):
        return True
    return None


def montant(valeur: object) -> str:
    """22 → « 22 », 22.5 → « 22,5 », « 52000 » → « 52 000 » (écriture québécoise)."""
    texte = str(valeur).strip()
    try:
        nombre = float(texte.replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except ValueError:
        return texte                                    # déjà mis en forme par le site : on garde
    if nombre.is_integer():
        return f"{int(nombre):,}".replace(",", " ")
    return f"{nombre:,.2f}".replace(",", " ").replace(".", ",")
