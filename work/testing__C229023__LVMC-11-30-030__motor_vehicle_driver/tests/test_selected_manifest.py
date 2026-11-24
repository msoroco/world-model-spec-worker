"""CPU check that selected delivery binds every exact crosswalk construction."""

import json
import hashlib
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from build_selected_manifest import build
from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID


class SelectedManifestTests(unittest.TestCase):
    def test_six_selected_entries_bind_saved_analysis_and_contracts(self):
        manifest = build(seal_offline=True)
        self.assertEqual(manifest["status"], "partial_selected_delivery")
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {ASSIGNMENT_ID + "__" + suffix for suffix in CASES})
        for row in manifest["cases"]:
            self.assertEqual(row["measurement_procedure"]["entrypoint"], "analysis.py")
            self.assertTrue((HERE / row["construction"]).is_file())
            self.assertTrue((HERE / row["measurement_contract"]).is_file())
            self.assertEqual(row["offline"]["exit_code"], 0)
            self.assertEqual(len(row["missing_proofs"]), 2)
            compatibility = row["compatibility"]
            receipt = HERE / compatibility["receipt"]
            self.assertEqual(compatibility["exit_code"], 0)
            self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(), compatibility["sha256"])
            self.assertTrue(json.loads(receipt.read_text())["passed"])
            self.assertTrue((HERE / row["negative"]["log"]).is_file())
        self.assertEqual(json.loads((HERE / "execution-manifest.json").read_text()), manifest)


if __name__ == "__main__":
    unittest.main()
