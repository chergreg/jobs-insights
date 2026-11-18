"""Tests hors ligne de la page HTML (interface.py et interface_modele.html)."""

import contextlib
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fusion import aggregate_records
from interface import TEMPLATE_FILE, build_html, offer_to_row
import main
from modele import AggregatedOffer, SourceRecord
from test_filtres_export import CollecteSimulee


def offer(number: int, **changes: object) -> AggregatedOffer:
    item = aggregate_records(
        [
            SourceRecord(
                source="Guichet-Emplois",
                source_id=str(number),
                url=f"https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/{number}",
                title="analyste en informatique",
                employer="Exemple inc.",
                origin_site="Jobillico",
            )
        ]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


def embedded_rows(page: str) -> list[dict[str, object]]:
    match = re.search(r'<script type="application/json" id="donnees">(.*?)</script>', page, re.S)
    assert match is not None
    return json.loads(match.group(1))


class RowTests(unittest.TestCase):
    def test_employer_title_first_and_cnp_title_kept(self) -> None:
        row = offer_to_row(offer(1, original_title="Analyste TI - Développeur"), 1)
        self.assertEqual(row["titre"], "Analyste TI - Développeur")
        self.assertEqual(row["titreCnp"], "analyste en informatique")

    def test_no_cnp_line_when_titles_are_the_same(self) -> None:
        row = offer_to_row(offer(1), 1)
        self.assertEqual((row["titre"], row["titreCnp"]), ("analyste en informatique", ""))

    def test_labels_are_in_french(self) -> None:
        row = offer_to_row(offer(1, job_type="full_time", stage_status="confirmed_stage"), 1)
        self.assertEqual((row["type"], row["stage"]), ("Temps plein", "Stage"))
        row = offer_to_row(offer(2, job_type="Permanent, Temps plein"), 2)
        self.assertEqual(row["type"], "Permanent, Temps plein")

    def test_links_and_sites(self) -> None:
        row = offer_to_row(offer(7, original_url="https://www.jobillico.com/fr/offre/7"), 7)
        self.assertEqual(row["lien"], "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/7")
        self.assertEqual(row["lienOrigine"], "https://www.jobillico.com/fr/offre/7")
        self.assertEqual(row["sites"], ["Jobillico"])


class PageTests(unittest.TestCase):
    def test_offers_are_embedded_and_counted(self) -> None:
        offers = [offer(1, city="Québec", region="Capitale-Nationale"), offer(2, technologies=["SQL"])]
        page = build_html(offers, generated_on="2026-11-17")
        rows = embedded_rows(page)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["region"], "Capitale-Nationale")
        self.assertEqual(rows[1]["technos"], ["SQL"])
        self.assertIn("2 offres · collecte du 2026-11-17", page)
        self.assertNotIn("{{", page)

    def test_text_from_a_job_offer_cannot_break_the_page(self) -> None:
        piege = "</script><script>alert('piège')</script>"
        page = build_html([offer(1, original_title=piege, employer="<b>Gras</b>")], generated_on="2026-11-17")
        # Seules nos deux balises <script> sont fermées dans la page.
        self.assertEqual(page.count("</script>"), 2)
        rows = embedded_rows(page)
        self.assertEqual(rows[0]["titre"], piege)  # le texte est gardé tel quel, comme donnée
        self.assertEqual(rows[0]["employeur"], "<b>Gras</b>")

    def test_page_works_offline(self) -> None:
        template = TEMPLATE_FILE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'<(?:script|img|iframe)[^>]+src=|<link[^>]+href=|@import|url\(', template))

    def test_offer_text_is_never_inserted_as_html(self) -> None:
        # Le JavaScript utilise textContent, jamais innerHTML : un texte d'offre ne peut pas devenir du code.
        template = TEMPLATE_FILE.read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", template)
        self.assertNotIn("insertAdjacentHTML", template)
        self.assertIn("textContent", template)

    def test_empty_list(self) -> None:
        page = build_html([], generated_on="2026-11-17")
        self.assertEqual(embedded_rows(page), [])
        self.assertIn("0 offres", page)


class MainHtmlTests(CollecteSimulee, unittest.TestCase):
    """Réutilise la collecte simulée de test_filtres_export.py."""

    def test_html_with_filter_from_saved_file(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            page_path = Path(folder) / "page.html"
            text = self.run_offline("--depuis", str(result_path), "--techno", "python", "--html", str(page_path))
            page = page_path.read_text(encoding="utf-8")

        rows = embedded_rows(page)
        self.assertIn("Page à ouvrir dans le navigateur", text)
        self.assertEqual([row["titre"] for row in rows], ["Software Engineer Intern"])
        self.assertEqual(rows[0]["stage"], "Stage")

    def test_html_after_a_collection_has_all_offers(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = self.collect_into(folder)
            page_path = Path(folder) / "toutes.html"
            self.run_offline("--depuis", str(result_path), "--html", str(page_path))
            rows = embedded_rows(page_path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
