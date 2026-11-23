import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit


AID = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def record(suffix, speed=3.0, visibility="clear"):
    return {"case_id": AID + "__" + suffix, "source_kind": "original_native",
            "legal_prudence": "unresolved", "samples": [{"time_s": 0.0, "speed_mps": speed}],
            "summary": {"mean_speed_mps": speed}, "condition_samples": [{"time_s": 0.0,
                "weather": "clear", "surface": "dry", "visibility": visibility,
                "pedestrians": "none", "curvature": "straight"}], "context": {
                "jurisdiction": "Las Vegas", "bicycle_classification": "human-powered",
                "alley_route": "same route", "rack_geometry": "same rack"}}


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.plan = {"comparisons": [
            {"comparison_id": "speed_under_clear_conditions", "case_ids": [AID + "__reference", AID + "__faster"]},
            {"comparison_id": "visibility_at_reference_speed", "case_ids": [AID + "__reference", AID + "__reduced_visibility"]},
        ]}

    def test_speed_change(self):
        self.assertTrue(audit(self.plan, "speed_under_clear_conditions", record("reference"), record("faster", 5.0))["passed"])

    def test_visibility_change(self):
        self.assertTrue(audit(self.plan, "visibility_at_reference_speed", record("reference"), record("reduced_visibility", visibility="reduced"))["passed"])

    def test_missing_measured_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, "measured speed"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), record("faster"))

    def test_fixed_condition_change_rejected(self):
        right = record("faster", 5.0)
        right["condition_samples"][0]["surface"] = "wet"
        with self.assertRaisesRegex(ValueError, "fixed condition changed"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), right)

    def test_case_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "case identity"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), record("reduced_visibility", 5.0))

    def test_nonoriginal_rejected(self):
        right = record("faster", 5.0)
        right["source_kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(ValueError, "original measurement"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), right)


if __name__ == "__main__":
    unittest.main()
