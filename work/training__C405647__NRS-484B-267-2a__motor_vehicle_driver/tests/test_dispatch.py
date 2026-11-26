"""Check that the root dispatcher selects every exact construction."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


FOLDER = Path(__file__).resolve().parents[1]


class DispatchTest(unittest.TestCase):
    def test_every_selected_case_checks_its_own_bundle(self):
        manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 4)
        for entry in manifest["cases"]:
            with self.subTest(case=entry["case_id"]):
                result = subprocess.run(
                    [sys.executable, "-B", str(FOLDER / "runner.py"),
                     "--case", entry["case_id"], "--check"],
                    capture_output=True, text=True, check=True)
                checked = json.loads(result.stdout)
                self.assertEqual(checked["case_id"], entry["case_id"])


if __name__ == "__main__":
    unittest.main()
