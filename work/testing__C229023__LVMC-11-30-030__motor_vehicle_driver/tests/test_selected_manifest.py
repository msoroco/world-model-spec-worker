"""CPU check that selected delivery binds every exact crosswalk construction."""

import json
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
        manifest = build()
        self.assertEqual(manifest["status"], "partial_selected_delivery")
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {ASSIGNMENT_ID + "__" + suffix for suffix in CASES})
        for row in manifest["cases"]:
            self.assertEqual(row["measurement_procedure"]["entrypoint"], "analysis.py")
            self.assertTrue((HERE / row["construction"]).is_file())
            self.assertTrue((HERE / row["measurement_contract"]).is_file())
            self.assertEqual(len(row["missing_proofs"]), 4)
        self.assertEqual(json.loads((HERE / "execution-manifest.json").read_text()), manifest)


if __name__ == "__main__":
    unittest.main()
