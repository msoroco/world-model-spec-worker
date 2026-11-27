"""Independent fixed-condition comparison tests for future branch captures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from branch_comparison import FIXED, audit


class BranchComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c135702-comparison-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        common = {key: (30 if key == "duration_s" else 20 if key == "frame_rate_hz" else
                        -1.1 if key == "park_y_m" else "fixed-" + key) for key in FIXED}
        self.a = dict(common, case_id="case-a", activity_request="park",
                      exception_request=None, source_gate_passed=True,
                      source_gate_sha256="a" * 64, physical_acceptance_claimed=False,
                      legal_acceptance_claimed=False)
        self.b = dict(self.a, case_id="case-b", activity_request="stand",
                      source_gate_sha256="b" * 64)

    def check(self, axis="activity_request"):
        a, b = self.root / "a.json", self.root / "b.json"
        a.write_text(json.dumps(self.a) + "\n")
        b.write_text(json.dumps(self.b) + "\n")
        return audit(a, b, axis)

    def test_activity_pair_keeps_physical_conditions(self):
        result = self.check()
        self.assertEqual(result["axis"], "activity_request")
        self.assertFalse(result["legal_acceptance_claimed"])

    def test_exception_pair_keeps_activity(self):
        self.b["activity_request"] = "park"
        self.b["exception_request"] = "police_direction"
        self.assertTrue(self.check("exception_request")["comparison_recorded"])

    def test_road_geometry_change_rejected(self):
        self.b["road_geometry_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "fixed physical"):
            self.check()

    def test_two_axis_change_rejected(self):
        self.b["exception_request"] = "police_direction"
        with self.assertRaisesRegex(ValueError, "two axes"):
            self.check()

    def test_missing_original_source_gate_rejected(self):
        self.b["source_gate_passed"] = False
        with self.assertRaisesRegex(ValueError, "source gate"):
            self.check()

    def test_unsupported_legal_claim_rejected(self):
        self.b["legal_acceptance_claimed"] = True
        with self.assertRaisesRegex(ValueError, "unsupported outcome"):
            self.check()


if __name__ == "__main__":
    unittest.main()
