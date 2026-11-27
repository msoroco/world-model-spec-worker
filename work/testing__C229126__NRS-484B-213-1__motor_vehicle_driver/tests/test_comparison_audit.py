import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("comparison_audit", ROOT / "comparison_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def report(case_id, value):
    return {"format": "nrs-484b-213-1-comparison-input", "case_id": case_id,
            "native_result_sha256": "native-source", "measurement_sha256": "measured-source",
            "physical_completion_reviewed": True, "full_video_decode_reviewed": True,
            "actual_pixels_reviewed": True,
            "fixed_conditions": {"road": "same-reviewed-source", "ego_policy": "same-controller"},
            "measured_differences": {"left_ray_any_occluded": value}}


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.item = next(c for c in PLAN["comparisons"] if c["comparison_id"] == "visibility_clear_vs_occluded")
        self.left = report(self.item["case_ids"][0], False)
        self.right = report(self.item["case_ids"][1], True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lp = Path(self.temp.name) / "left.json"
        self.rp = Path(self.temp.name) / "right.json"

    def check(self):
        self.lp.write_text(json.dumps(self.left))
        self.rp.write_text(json.dumps(self.right))
        return module.audit(PLAN, self.left, self.right, self.lp, self.rp,
                            "visibility_clear_vs_occluded")

    def test_positive_source_bound_isolation(self):
        receipt = self.check()
        self.assertEqual(receipt["checked_differences"], ["left_ray_any_occluded"])
        self.assertEqual(receipt["judgment"], "unresolved")

    def test_changed_fixed_condition_rejected(self):
        self.right["fixed_conditions"]["road"] = "different-road"
        with self.assertRaisesRegex(ValueError, "fixed conditions differ"):
            self.check()

    def test_missing_physical_review_rejected(self):
        self.right["actual_pixels_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "actual pixels"):
            self.check()

    def test_unchanged_declared_factor_rejected(self):
        self.right["measured_differences"]["left_ray_any_occluded"] = False
        with self.assertRaisesRegex(ValueError, "not measured"):
            self.check()


if __name__ == "__main__":
    unittest.main()
