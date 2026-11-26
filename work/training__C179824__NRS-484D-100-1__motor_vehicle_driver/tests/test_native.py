"""CPU checks for exact case selection and construction identity."""
import hashlib
import json
import unittest
from pathlib import Path

from runner import check, selected

ROOT = Path(__file__).resolve().parents[1]


class ExactNativeSelection(unittest.TestCase):
    def test_all_selected_case_sources(self):
        self.assertEqual(check()["selected_cases"], 13)
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        for entry in manifest["cases"]:
            case = entry["case_id"]
            self.assertEqual(selected(case)["case_id"], case)
            construction = ROOT / entry["construction"]
            self.assertEqual(hashlib.sha256(construction.read_bytes()).hexdigest(),
                             entry["construction_sha256"])
            self.assertEqual(len(entry["candidates"]), 1)

    def test_unknown_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown or duplicated"):
            selected(ROOT.name + "__not_selected")


if __name__ == "__main__":
    unittest.main()
