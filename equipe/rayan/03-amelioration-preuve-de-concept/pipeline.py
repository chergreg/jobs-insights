"""Pipeline de déduplication, statistiques comparatives Avant/Après et exports (JSON, CSV, Format commun).

Inspiré de :
- `equipe/dan/livrable3/regroupement.py` et `modele.py` (regroupement par ID et empreinte,
  champ `doublons`, export CSV `utf-8-sig` avec séparateur `;`) ;
- `equipe/kandet/03-amelioration-preuve-de-concept/fusion.py` et `export.py`
  (cumul de `mots_cles_recherche` lors de la déduplication) ;
- `equipe/kandet/format-commun/convertir.py` et `equipe/ferdinand/format-commun/convertir.py`
  (export vers les 18 champs du format commun de la classe).
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from models import CHAMPS_FORMAT_COMMUN, OffreAdzuna
from normalisation import construire_offre_adzuna, normaliser_cle


FORMES_JURIDIQUES = re.compile(
    r"\b(?:inc|incorporee|ltee|ltd|limitee|corp|corporation|senc|llc|sec)\b\.?",
    re.I,
)


def _simplifier_texte(texte: str | None) -> str:
    if not texte:
        return ""
    propre = re.sub(r"[^a-z0-9]+", " ", normaliser_cle(texte))
    return " ".join(propre.split())


def empreinte_offre(offre: OffreAdzuna) -> tuple[str, str, str] | None:
    """Calcule l'empreinte `(titre, entreprise, ville)` pour repérer les republications sous IDs différents."""
    titre = _simplifier_texte(offre.titre)
    entreprise = " ".join(FORMES_JURIDIQUES.sub(" ", _simplifier_texte(offre.entreprise)).split())
    ville = _simplifier_texte(offre.ville or offre.lieu_brut)
    if not (titre and entreprise and ville):
        return None
    return (titre, entreprise, ville)


@dataclass
class StatistiquesPipeline:
    """Mesures exactes permettant de comparer l'API brute (Livrable 2) et la version enrichie (Livrable 3)."""

    fichiers_lus: int = 0
    annonces_brutes_recues: int = 0
    offres_uniques_par_id: int = 0
    doublons_meme_id_fusionnes: int = 0
    republications_meme_empreinte_detectees: int = 0
    exemples_republications: list[str] = field(default_factory=list)

    # --- Comparaison Avant (API seule) vs Après (API + Extraction Description) sur les offres uniques ---
    api_salaires_presents: int = 0
    api_salaires_suspects: int = 0
    api_salaires_valides: int = 0
    api_periodes_salariales: int = 0
    texte_salaires_extraits: int = 0
    texte_periodes_salariales_extraites: int = 0
    consolide_salaires_valides: int = 0
    consolide_periodes_salariales: int = 0
    repartition_provenance_salaire: dict[str, int] = field(default_factory=dict)

    api_contrats_presents: int = 0
    texte_contrats_extraits: int = 0
    texte_durees_contrat_extraites: int = 0
    consolide_contrats_presents: int = 0
    repartition_types_contrat: dict[str, int] = field(default_factory=dict)
    repartition_provenance_contrat: dict[str, int] = field(default_factory=dict)

    api_horaires_presents: int = 0
    texte_horaires_extraits: int = 0
    texte_heures_extraites: int = 0
    consolide_horaires_presents: int = 0
    repartition_horaires: dict[str, int] = field(default_factory=dict)
    repartition_provenance_horaire: dict[str, int] = field(default_factory=dict)

    api_modalites_presentes: int = 0  # Toujours 0 dans l'API Adzuna
    texte_modalites_extraites: int = 0
    repartition_modalites: dict[str, int] = field(default_factory=dict)

    # --- Géographie, Pertinence TI, Stages et Anomalies ---
    offres_pertinentes_ti: int = 0
    offres_hors_ti_signalees: int = 0
    stages_confirmes: int = 0
    repartition_precision_lieu: dict[str, int] = field(default_factory=dict)
    repartition_regions_quebec: dict[str, int] = field(default_factory=dict)
    offres_avec_anomalies: int = 0
    top_competences: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fichiers_lus": self.fichiers_lus,
            "annonces_brutes_recues": self.annonces_brutes_recues,
            "offres_uniques_par_id": self.offres_uniques_par_id,
            "doublons_meme_id_fusionnes": self.doublons_meme_id_fusionnes,
            "republications_meme_empreinte_detectees": self.republications_meme_empreinte_detectees,
            "exemples_republications": self.exemples_republications,
            "comparaison_avant_apres": {
                "salaires": {
                    "avant_api_brut": self.api_salaires_presents,
                    "avant_api_suspects_signales": self.api_salaires_suspects,
                    "avant_api_valides": self.api_salaires_valides,
                    "avant_api_periodes_connues": self.api_periodes_salariales,
                    "extraits_description": self.texte_salaires_extraits,
                    "extraits_periodes_connues": self.texte_periodes_salariales_extraites,
                    "apres_consolide_valides": self.consolide_salaires_valides,
                    "apres_consolide_periodes_connues": self.consolide_periodes_salariales,
                    "provenance": self.repartition_provenance_salaire,
                },
                "contrats": {
                    "avant_api": self.api_contrats_presents,
                    "extraits_description": self.texte_contrats_extraits,
                    "extraits_duree_contrat": self.texte_durees_contrat_extraites,
                    "apres_consolide": self.consolide_contrats_presents,
                    "types_consolides": self.repartition_types_contrat,
                    "provenance": self.repartition_provenance_contrat,
                },
                "horaires": {
                    "avant_api": self.api_horaires_presents,
                    "extraits_description": self.texte_horaires_extraits,
                    "extraits_volume_heures": self.texte_heures_extraites,
                    "apres_consolide": self.consolide_horaires_presents,
                    "horaires_consolides": self.repartition_horaires,
                    "provenance": self.repartition_provenance_horaire,
                },
                "modalites": {
                    "avant_api": self.api_modalites_presentes,
                    "apres_extraits_description": self.texte_modalites_extraites,
                    "modalites_consolidees": self.repartition_modalites,
                },
            },
            "pertinence_ti": {
                "offres_pertinentes_ti": self.offres_pertinentes_ti,
                "offres_hors_ti_signalees": self.offres_hors_ti_signalees,
                "stages_confirmes": self.stages_confirmes,
            },
            "geographie": {
                "precision_lieu": self.repartition_precision_lieu,
                "regions_administratives": self.repartition_regions_quebec,
            },
            "offres_avec_anomalies": self.offres_avec_anomalies,
            "top_competences": self.top_competences,
        }

    def formater_rapport_console(self) -> str:
        lignes = [
            "==========================================================================",
            "   RAPPORT LIVRABLE 3 — ENRICHISSEMENT & PROVENANCE ADZUNA CANADA (QC)    ",
            "==========================================================================",
            f" Fichiers de recherche analysés          : {self.fichiers_lus}",
            f" Annonces brutes reçues                  : {self.annonces_brutes_recues}",
            f" Doublons inter-recherches (même ID)     : {self.doublons_meme_id_fusionnes}",
            f" Offres uniques (par ID Adzuna)          : {self.offres_uniques_par_id}",
            f" Republications détectées (même poste)   : {self.republications_meme_empreinte_detectees}",
            "--------------------------------------------------------------------------",
            " COMPARAISON AVANT (API Adzuna seule) vs APRÈS (API + Description) :",
            f"  1. Salaires exploitables               : {self.api_salaires_valides:>3} (API brute: {self.api_salaires_presents} dont {self.api_salaires_suspects} suspects à 1$) -> {self.consolide_salaires_valides:>3} (+{self.consolide_salaires_valides - self.api_salaires_valides})",
            f"     Périodes salariales explicites      : {self.api_periodes_salariales:>3} (API) -> {self.consolide_periodes_salariales:>3} (extraites du texte)",
            f"  2. Types de contrat renseignés         : {self.api_contrats_presents:>3} (API) -> {self.consolide_contrats_presents:>3} (+{self.consolide_contrats_presents - self.api_contrats_presents} via description, {self.texte_durees_contrat_extraites} avec durée)",
            f"  3. Horaires (temps plein/partiel)      : {self.api_horaires_presents:>3} (API) -> {self.consolide_horaires_presents:>3} (+{self.consolide_horaires_presents - self.api_horaires_presents} via description, {self.texte_heures_extraites} avec heures)",
            f"  4. Modalités (Présentiel/Hybride/Télé) : {self.api_modalites_presentes:>3} (API) -> {self.texte_modalites_extraites:>3} (+{self.texte_modalites_extraites} via description)",
            "--------------------------------------------------------------------------",
            f" Pertinence TI : {self.offres_pertinentes_ti} offres TI retenues | {self.offres_hors_ti_signalees} hors-TI signalées | {self.stages_confirmes} stages confirmés",
            f" Précision géographique : {self.repartition_precision_lieu}",
            f" Offres avec anomalies / divergences documentées : {self.offres_avec_anomalies}",
            "==========================================================================",
        ]
        return "\n".join(lignes)


def executer_pipeline_documents(
    documents: list[dict[str, Any]],
    date_extraction: str | None = None,
) -> tuple[list[OffreAdzuna], StatistiquesPipeline]:
    """Transforme les documents JSON de recherche Adzuna en une liste dédupliquée d'`OffreAdzuna`."""
    horodatage = date_extraction or datetime.now(timezone.utc).isoformat(timespec="seconds")
    stats = StatistiquesPipeline(fichiers_lus=len(documents))

    offres_par_id: dict[str, OffreAdzuna] = {}
    ordre_ids: list[str] = []

    for doc in documents:
        meta = doc.get("search") or {}
        mot_cle = str(meta.get("keyword") or "").strip()
        ville_rech = str(meta.get("location") or "").strip()
        resultats = doc.get("results") or []

        for raw_job in resultats:
            stats.annonces_brutes_recues += 1
            id_brut = str(raw_job.get("id") or "").strip()
            if not id_brut:
                continue

            if id_brut in offres_par_id:
                # Même annonce vue dans une autre recherche : on cumule les mots-clés et villes de recherche
                stats.doublons_meme_id_fusionnes += 1
                existante = offres_par_id[id_brut]
                if mot_cle and mot_cle not in existante.mots_cles_recherche:
                    existante.mots_cles_recherche.append(mot_cle)
                if ville_rech and ville_rech not in existante.villes_recherche:
                    existante.villes_recherche.append(ville_rech)
                continue

            offre = construire_offre_adzuna(
                raw_job=raw_job,
                mot_cle_recherche=mot_cle,
                ville_recherche=ville_rech,
                date_extraction=horodatage,
            )
            offres_par_id[id_brut] = offre
            ordre_ids.append(id_brut)

    offres_uniques = [offres_par_id[jid] for jid in ordre_ids]
    stats.offres_uniques_par_id = len(offres_uniques)

    # Détection et traçabilité des republications sous IDs différents (même titre + entreprise + ville)
    # On ne supprime pas l'enregistrement de la liste des 229 IDs uniques, mais on renseigne `doublons_ids`
    # et `anomalies` pour documenter la republication sans perte d'identifiant.
    vus_par_empreinte: dict[tuple[str, str, str], OffreAdzuna] = {}
    for offre in offres_uniques:
        emp = empreinte_offre(offre)
        if emp is None:
            continue
        if emp in vus_par_empreinte:
            premiere = vus_par_empreinte[emp]
            stats.republications_meme_empreinte_detectees += 1
            if offre.id not in premiere.doublons_ids:
                premiere.doublons_ids.append(offre.id)
            if premiere.id not in offre.doublons_ids:
                offre.doublons_ids.append(premiere.id)
            offre.anomalies.append(f"republication_meme_empreinte_que:{premiere.id}")
            if len(stats.exemples_republications) < 10:
                stats.exemples_republications.append(f"{offre.id} == {premiere.id} ({offre.titre} | {offre.entreprise})")
        else:
            vus_par_empreinte[emp] = offre

    # Calcul des statistiques exactes sur les 229 offres uniques
    prov_sal = Counter()
    prov_ct = Counter()
    types_ct = Counter()
    prov_tm = Counter()
    types_tm = Counter()
    types_mod = Counter()
    prec_lieu = Counter()
    reg_qc = Counter()
    comp_cnt = Counter()

    for o in offres_uniques:
        # Salaires
        if o.api_salary_min is not None or o.api_salary_max is not None:
            stats.api_salaires_presents += 1
            if (o.api_salary_min is not None and o.api_salary_min < 10.0) or (
                o.api_salary_max is not None and o.api_salary_max < 10.0
            ):
                stats.api_salaires_suspects += 1
            else:
                stats.api_salaires_valides += 1
        if o.texte_salaire_min is not None or o.texte_salaire_max is not None:
            stats.texte_salaires_extraits += 1
        if o.texte_periode_salaire:
            stats.texte_periodes_salariales_extraites += 1
        if o.salaire_min is not None or o.salaire_max is not None:
            stats.consolide_salaires_valides += 1
        if o.periode_salaire:
            stats.consolide_periodes_salariales += 1
        prov_sal[o.provenance_salaire] += 1

        # Contrats
        if o.api_contract_type:
            stats.api_contrats_presents += 1
        if o.texte_type_contrat:
            stats.texte_contrats_extraits += 1
        if o.texte_duree_contrat:
            stats.texte_durees_contrat_extraites += 1
        if o.type_contrat:
            stats.consolide_contrats_presents += 1
            types_ct[o.type_contrat] += 1
        prov_ct[o.provenance_contrat] += 1

        # Horaires
        if o.api_contract_time:
            stats.api_horaires_presents += 1
        if o.texte_horaire:
            stats.texte_horaires_extraits += 1
        if o.texte_heures_valeur is not None:
            stats.texte_heures_extraites += 1
        if o.horaire_travail:
            stats.consolide_horaires_presents += 1
            types_tm[o.horaire_travail] += 1
        prov_tm[o.provenance_horaire] += 1

        # Modalités
        if o.texte_modalite:
            stats.texte_modalites_extraites += 1
            types_mod[o.texte_modalite] += 1

        # Pertinence TI et stages
        if o.est_pertinent_ti:
            stats.offres_pertinentes_ti += 1
        else:
            stats.offres_hors_ti_signalees += 1
        if o.est_stage:
            stats.stages_confirmes += 1

        # Géographie
        prec_lieu[o.precision_lieu] += 1
        if o.region_administrative:
            reg_qc[o.region_administrative] += 1

        if o.anomalies:
            stats.offres_avec_anomalies += 1

        for c in o.competences_cles:
            comp_cnt[c] += 1

    stats.repartition_provenance_salaire = dict(prov_sal.most_common())
    stats.repartition_provenance_contrat = dict(prov_ct.most_common())
    stats.repartition_types_contrat = dict(types_ct.most_common())
    stats.repartition_provenance_horaire = dict(prov_tm.most_common())
    stats.repartition_horaires = dict(types_tm.most_common())
    stats.repartition_modalites = dict(types_mod.most_common())
    stats.repartition_precision_lieu = dict(prec_lieu.most_common())
    stats.repartition_regions_quebec = dict(reg_qc.most_common())
    stats.top_competences = comp_cnt.most_common(15)

    return offres_uniques, stats


# --- Fonctions d'export (JSON complet, CSV Excel utf-8-sig, Format commun) ----

COLONNES_CSV_ENRICHI = [
    "id",
    "titre",
    "entreprise",
    "ville",
    "region_administrative",
    "province",
    "precision_lieu",
    "est_pertinent_ti",
    "est_stage",
    "api_salary_min",
    "api_salary_max",
    "texte_salaire_min",
    "texte_salaire_max",
    "texte_devise",
    "texte_periode_salaire",
    "salaire_min",
    "salaire_max",
    "devise",
    "periode_salaire",
    "salaire_resume",
    "provenance_salaire",
    "api_contract_type",
    "texte_type_contrat",
    "texte_duree_contrat",
    "type_contrat",
    "provenance_contrat",
    "api_contract_time",
    "texte_horaire",
    "texte_heures_valeur",
    "texte_heures_unite",
    "horaire_travail",
    "provenance_horaire",
    "modalite",
    "provenance_modalite",
    "competences_cles",
    "mots_cles_recherche",
    "villes_recherche",
    "anomalies",
    "date_publication",
    "url",
]


def _formater_cellule_csv(valeur: Any) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, list):
        return ", ".join(str(x) for x in valeur)
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    return re.sub(r"[\r\n]+", " ", str(valeur)).strip()


def exporter_json_enrichi(
    offres: list[OffreAdzuna],
    stats: StatistiquesPipeline,
    chemin: Path,
) -> Path:
    """Exporte les offres enrichies (avec valeurs API, valeurs texte, provenance et statistiques) en JSON UTF-8."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "statistiques": stats.to_dict(),
        "offres": [o.to_dict() for o in offres],
    }
    chemin.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def exporter_csv_enrichi(offres: list[OffreAdzuna], chemin: Path) -> Path:
    """Exporte les offres enrichies en CSV (`utf-8-sig`, séparateur `;`) pour Excel sous Windows."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(COLONNES_CSV_ENRICHI)
        for o in offres:
            d = o.to_dict()
            writer.writerow([_formater_cellule_csv(d.get(col)) for col in COLONNES_CSV_ENRICHI])
    return chemin


def exporter_format_commun_json(offres: list[OffreAdzuna], chemin: Path, filtrer_ti: bool = False) -> Path:
    """Exporte les offres au format commun de la classe (18 champs du modèle `JobOffer`)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    selection = [o for o in offres if (o.est_pertinent_ti if filtrer_ti else True)]
    donnees = [o.to_format_commun() for o in selection]
    # Vérification stricte de la présence des 18 clés sur chaque élément
    for elem in donnees:
        assert list(elem.keys()) == CHAMPS_FORMAT_COMMUN
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin
