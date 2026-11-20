"""Tests hors ligne de la collecte régulière (historique.py et options de main.py)."""

import contextlib
from datetime import date, datetime, timedelta
from dataclasses import asdict
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fixtures import REMOTIVE_PAYLOAD, make_article, make_page, make_posting
from fusion import aggregate_records
from historique import append_history, clean_cache, compare_with_previous, load_previous, offer_keys
import main
from modele import SourceRecord
from texte import french_date


def offer(number: int, **changes: object):
    item = aggregate_records(
        [SourceRecord(source="Guichet-Emplois", source_id=str(number), url=f"https://example.test/{number}",
                      title=f"poste {number}", employer="Exemple inc.")]
    )[0]
    for name, value in changes.items():
        setattr(item, name, value)
    return item


def previous_document(*offers, generated_at: str = "2026-11-17T13:00:00+00:00") -> dict:
    return {"generated_at": generated_at, "offers": [asdict(item) for item in offers]}


class CompareTests(unittest.TestCase):
    def test_keys_from_json_or_program(self) -> None:
        item = offer(7)
        self.assertEqual(offer_keys(item.source_records), {("Guichet-Emplois", "7")})
        self.assertEqual(offer_keys(asdict(item)["source_records"]), {("Guichet-Emplois", "7")})

    def test_new_gone_and_kept(self) -> None:
        later = (date.today() + timedelta(days=10)).isoformat()
        earlier = (date.today() - timedelta(days=1)).isoformat()
        previous = previous_document(offer(1), offer(2, expires_at=later), offer(3, expires_at=earlier, original_title="Analyste TI"))
        current = [offer(1), offer(4)]

        changes = compare_with_previous(previous, current)

        self.assertEqual((changes.new_count, changes.kept_count, len(changes.gone)), (1, 1, 2))
        self.assertEqual([item.new_since_previous for item in current], [False, True])
        self.assertEqual([gone.title for gone in changes.gone], ["poste 2", "Analyste TI"])
        self.assertEqual(changes.gone[0].url, "https://example.test/2")
        # Retirée avant sa date limite : seulement l'offre 2 (l'offre 3 avait déjà expiré).
        self.assertEqual(changes.gone_before_expiry, 1)
        self.assertEqual(changes.previous_count, 3)
        self.assertEqual(changes.as_dict()["new_offers"], 1)

    def test_offer_found_again_on_another_partner_is_not_new(self) -> None:
        # Même offre fusionnée : une de ses annonces était déjà là.
        both = aggregate_records([
            SourceRecord(source="Guichet-Emplois", source_id="1", url="https://example.test/1", title="t", employer="e",
                         location="Québec (QC)"),
            SourceRecord(source="Remotive", source_id="r9", url="https://remotive.com/9", title="t", employer="e",
                         location="Québec (QC)"),
        ])
        self.assertEqual(len(both), 1)  # les deux annonces sont bien regroupées en une offre
        changes = compare_with_previous(previous_document(offer(1)), both)
        self.assertEqual((changes.new_count, len(changes.gone)), (0, 0))

    def test_missing_or_broken_previous_file(self) -> None:
        with TemporaryDirectory() as folder:
            self.assertIsNone(load_previous(Path(folder) / "absent.json"))
            broken = Path(folder) / "offres.json"
            broken.write_text("{pas du json", encoding="utf-8")
            self.assertIsNone(load_previous(broken))
            broken.write_text('{"jobs": []}', encoding="utf-8")
            self.assertIsNone(load_previous(broken))


class HistoryAndCacheTests(unittest.TestCase):
    def test_history_has_one_header_and_one_line_per_collection(self) -> None:
        changes = compare_with_previous(previous_document(offer(1), offer(2)), [offer(1), offer(3)])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "historique-collectes.csv"
            append_history(path, 2, None, 2, 0, when=datetime(2026, 11, 17, 8, 0))
            append_history(path, 2, changes, 2, 1, when=datetime(2026, 11, 20, 8, 0))
            raw = path.read_bytes()
            lines = raw.decode("utf-8-sig").splitlines()
        self.assertEqual(raw.count(b"\xef\xbb\xbf"), 1)  # marqueur pour Excel une seule fois, au début
        self.assertEqual(lines, [
            "date;offres;nouvelles;disparues;retirees_avant_expiration;fiches_lues;erreurs",
            "2026-11-17 08:00;2;;;;2;0",
            "2026-11-20 08:00;2;1;1;0;2;1",
        ])

    def test_clean_cache_only_removes_old_postings(self) -> None:
        with TemporaryDirectory() as folder:
            cache = Path(folder)
            for name in ("1.html", "2.html", "3.html", "notes.txt"):
                (cache / name).write_text("x", encoding="utf-8")
            removed = clean_cache(cache, {"1", "3"})
            remaining = sorted(path.name for path in cache.iterdir())
        self.assertEqual(removed, 1)
        self.assertEqual(remaining, ["1.html", "3.html", "notes.txt"])

    def test_french_dates(self) -> None:
        self.assertEqual(french_date("2026-11-20"), "20 novembre 2026")
        self.assertEqual(french_date("2026-02-01"), "1 février 2026")
        self.assertEqual(french_date("pas une date"), "pas une date")


class RegularCollectionTests(unittest.TestCase):
    """Deux collectes simulées de suite : 101, 102, 103 le 17 novembre, puis 101, 102, 104."""

    def collect(self, folder: str, numbers: list[int], *args: str) -> str:
        page = make_page([make_article(number) for number in numbers], total=len(numbers)).encode("utf-8")
        output = io.StringIO()
        with (
            patch("guichet.fetch_url", return_value=page),
            patch("guichet.time.sleep"),
            patch("fiches.fetch_url", return_value=make_posting().encode("utf-8")),
            patch("fiches.time.sleep"),
            patch("main.load_remotive_payload", return_value={"jobs": []}),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            main.main(["--sortie", str(Path(folder) / "offres.json"), "--cache-fiches", str(Path(folder) / "cache"), *args])
        return output.getvalue()

    def test_second_collection_shows_what_changed(self) -> None:
        with TemporaryDirectory() as folder:
            first = self.collect(folder, [101, 102, 103])
            second = self.collect(folder, [101, 102, 104], "--html", str(Path(folder) / "offres.html"))
            document = json.loads((Path(folder) / "offres.json").read_text(encoding="utf-8"))
            history = (Path(folder) / "historique-collectes.csv").read_text(encoding="utf-8-sig").splitlines()
            page = (Path(folder) / "offres.html").read_text(encoding="utf-8")

        self.assertNotIn("Depuis la collecte", first)  # première collecte : rien à comparer
        self.assertIn("1 nouvelle(s) offre(s), 1 disparue(s)", second)
        self.assertEqual(document["changes_since_previous"]["new_offers"], 1)
        self.assertEqual(document["changes_since_previous"]["gone"][0]["url"],
                         "https://www.guichetemplois.gc.ca/rechercheemplois/offredemploi/103")
        flags = {o["source_records"][0]["source_id"]: o["new_since_previous"] for o in document["offers"]}
        self.assertEqual(flags, {"101": False, "102": False, "104": True})
        self.assertEqual(len(history), 3)  # en-tête + 2 collectes
        self.assertIn("1 nouvelle offre depuis la collecte du", page)
        self.assertIn('"nouvelle": true', page)

    def test_clean_cache_after_complete_collection(self) -> None:
        with TemporaryDirectory() as folder:
            self.collect(folder, [101, 102, 103])
            text = self.collect(folder, [101, 102, 104], "--nettoyer-cache")
            cached = sorted(path.stem for path in (Path(folder) / "cache").glob("*.html"))
        self.assertIn("Cache nettoyé : 1 fiche(s)", text)
        self.assertEqual(cached, ["101", "102", "104"])

    def test_cache_is_kept_after_a_partial_collection(self) -> None:
        with TemporaryDirectory() as folder:
            self.collect(folder, [101, 102, 103])
            text = self.collect(folder, [101, 102, 104], "--nettoyer-cache", "--max-fiches", "1")
            cached = sorted(path.stem for path in (Path(folder) / "cache").glob("*.html"))
        self.assertIn("Cache non nettoyé", text)
        self.assertEqual(cached, ["101", "102", "103"])

    def test_page_from_saved_file_keeps_the_news(self) -> None:
        with TemporaryDirectory() as folder:
            self.collect(folder, [101, 102, 103])
            self.collect(folder, [101, 102, 104])
            page_path = Path(folder) / "relue.html"
            with contextlib.redirect_stdout(io.StringIO()):
                main.main(["--depuis", str(Path(folder) / "offres.json"), "--html", str(page_path)])
            page = page_path.read_text(encoding="utf-8")
        self.assertIn("1 nouvelle offre depuis la collecte du", page)


class PowerShellScriptTests(unittest.TestCase):
    """Les scripts PowerShell doivent garder leurs accents sous Windows PowerShell 5.1."""

    def test_scripts_start_with_utf8_marker(self) -> None:
        folder = Path(__file__).resolve().parent
        for name in ("collecte-reguliere.ps1", "planifier-collecte.ps1"):
            with self.subTest(script=name):
                self.assertTrue((folder / name).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_regular_script_cleans_cache_and_updates_page(self) -> None:
        script = (Path(__file__).resolve().parent / "collecte-reguliere.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('"--nettoyer-cache", "--html"', script)


if __name__ == "__main__":
    unittest.main()
