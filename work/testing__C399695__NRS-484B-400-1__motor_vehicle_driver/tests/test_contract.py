"""Selected package CPU contract and exact-case static runner checks."""

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    def test_five_exact_bundles_and_source_bound_proofs(self):
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual({entry["case_id"] for entry in manifest["cases"]},
                         {case["case_id"] for case in plan["cases"]})
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(len(plan["comparisons"]), 4)
        for entry in manifest["cases"]:
            self.assertEqual(entry["kind"], "delivery")
            self.assertEqual(entry["candidate_risk"]["status"], "physical")
            self.assertEqual(len(entry["candidates"]), 1)
            self.assertTrue(entry["compatibility"]["receipt"])
            self.assertTrue(entry["post_capture"]["recorded_only"])
            self.assertEqual(entry["delivery_acceptance"]["case_id"], entry["case_id"])

    def test_selected_runner_is_static_and_carla_lazy(self):
        result = subprocess.run([sys.executable, str(ROOT / "runner.py"), "--check"],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("static check passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
