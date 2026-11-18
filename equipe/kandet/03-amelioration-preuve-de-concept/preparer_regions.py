"""Crée regions_quebec.csv à partir du Répertoire des municipalités du Québec.

À lancer seulement pour mettre la liste à jour (elle change rarement) :
    python preparer_regions.py

Source : ministère des Affaires municipales et de l'Habitation (MAMH),
licence CC-BY 4.0. Les fichiers d'origine contiennent aussi les noms des élus :
on ne garde que le nom de la municipalité ou de l'arrondissement, son type et
sa région administrative.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
import time

from collecte import fetch_url
from regions import REGIONS_FILE


MUNICIPALITIES_URL = "https://donneesouvertes.affmunqc.net/repertoire/MUN.csv"
BOROUGHS_URL = "https://donneesouvertes.affmunqc.net/repertoire/ARR.csv"


def reduce_rows(municipalities_csv: str, boroughs_csv: str) -> list[dict[str, str]]:
    """Garde 3 colonnes : nom, type et région."""
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(municipalities_csv)):
        rows.append({"nom": row["munnom"].strip(), "type": "municipalité", "region": row["regadm"].strip()})
    for row in csv.DictReader(io.StringIO(boroughs_csv)):
        rows.append({"nom": row["arrnom"].strip(), "type": "arrondissement", "region": row["arrregion"].strip()})
    # Une même municipalité peut apparaître deux fois (ex. village et canton du même nom).
    unique = {(row["nom"], row["type"], row["region"]): row for row in rows if row["nom"]}
    return sorted(unique.values(), key=lambda row: (row["type"], row["nom"]))


def write_regions(rows: list[dict[str, str]], path: Path = REGIONS_FILE) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["nom", "type", "region"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    municipalities = fetch_url(MUNICIPALITIES_URL, "text/csv").decode("utf-8-sig")
    time.sleep(2)
    boroughs = fetch_url(BOROUGHS_URL, "text/csv").decode("utf-8-sig")
    rows = reduce_rows(municipalities, boroughs)
    write_regions(rows)
    print(f"{len(rows)} lignes écrites dans {REGIONS_FILE}")


if __name__ == "__main__":
    main()
