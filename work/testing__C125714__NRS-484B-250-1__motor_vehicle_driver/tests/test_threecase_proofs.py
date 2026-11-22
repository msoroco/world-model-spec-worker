"""Keep exact diagnostic receipts tied to their current case bundles."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ThreeCaseProofTests(unittest.TestCase):
    def test_three_case_ids_and_source_bound_receipts(self):
        manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
        proposal = json.loads((ROOT / "proposals/cases.json").read_text())
        proposed = {case["case_id"] for case in proposal["cases"]}
        entries = manifest["cases"]
        self.assertEqual([entry["case_id"].rsplit("__", 1)[1] for entry in entries],
                         ["precedence", "advance", "other_later",
                          "opposite_straight", "opposite_intends_left",
                          "opposite_makes_left", "wide_same_crossing"])
        for entry in entries:
            case_id = entry["case_id"]
            self.assertIn(case_id, proposed)
            self.assertEqual(entry["kind"], "diagnostic")
            construction = ROOT / entry["construction"]
            self.assertEqual(sha(construction), entry["construction_sha256"])
            folder = construction.parent
            receipt = json.loads((folder / "diagnostic-saved-proof.json").read_text())
            self.assertEqual(receipt["case_id"], case_id)
            self.assertEqual(receipt["construction_sha256"], sha(construction))
            self.assertEqual(receipt["fixture_recipe_sha256"],
                             sha(folder / "diagnostic-recipe.json"))
            self.assertEqual(receipt["positive_result_sha256"],
                             sha(folder / receipt["positive_result"]))
            self.assertEqual(receipt["negative_log_sha256"],
                             sha(folder / receipt["negative_log"]))
            self.assertFalse(receipt["compatibility_claimed"])
            self.assertFalse(receipt["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
