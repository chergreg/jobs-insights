"""Tests hors ligne du point d'entrée : une collecte complète avec réponses simulées."""

import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fixtures import FIXTURE_PAGE, REMOTIVE_PAYLOAD
import main


class MainTests(unittest.TestCase):
    def run_main(self, *args: str) -> str:
        output = io.StringIO()
        with (
            patch("guichet.fetch_url", return_value=FIXTURE_PAGE.encode("utf-8")),
            patch("guichet.time.sleep"),
            patch("main.load_remotive_payload", return_value=REMOTIVE_PAYLOAD) as remotive,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            main.main(list(args))
        self.remotive = remotive
        return output.getvalue()

    def test_full_run_writes_results_and_sample(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = Path(folder) / "offres.json"
            sample_path = Path(folder) / "echantillon.json"
            text = self.run_main("--sortie", str(result_path), "--echantillon", str(sample_path))
            document = json.loads(result_path.read_text(encoding="utf-8"))
            sample = json.loads(sample_path.read_text(encoding="utf-8"))

        # 3 offres Guichet-Emplois + 2 offres Remotive des catégories TI
        self.assertEqual(document["offer_count"], 5)
        self.assertEqual(document["guichet_searches"][0]["collected"], 3)
        self.assertEqual(document["guichet_searches"][0]["announced_total"], 3)
        self.assertEqual(document["summary"]["offers_by_source"], {"Guichet-Emplois": 3, "Remotive": 2})
        self.assertEqual(document["remotive_total_in_api"], 3)
        self.assertEqual(len(sample["offers"]), 3)
        self.assertIn("5 offres uniques", text)

    def test_no_file_without_save(self) -> None:
        with TemporaryDirectory() as folder:
            result_path = Path(folder) / "offres.json"
            text = self.run_main("--sans-sauvegarde", "--sans-remotive", "--sortie", str(result_path))
            self.assertFalse(result_path.exists())

        self.remotive.assert_not_called()
        self.assertIn("3 offres uniques", text)


if __name__ == "__main__":
    unittest.main()
