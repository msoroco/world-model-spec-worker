import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit, audit_saved_pair
from comparison_source_guard import audit_guarded_pair, check_record


AID = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def record(suffix, speed=3.0, visibility="clear", surface="dry", pedestrians="none"):
    return {"case_id": AID + "__" + suffix, "source_kind": "original_native",
            "legal_prudence": "unresolved", "samples": [{"time_s": 0.0, "speed_mps": speed}],
            "summary": {"mean_speed_mps": speed}, "condition_samples": [{"time_s": 0.0,
                "weather": "clear", "surface": surface, "visibility": visibility,
                "pedestrians": pedestrians, "curvature": "straight"}], "context": {
                "jurisdiction": "Las Vegas", "bicycle_classification": "human-powered",
                "alley_route": "same route", "rack_geometry": "same rack"}}


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.plan = {"comparisons": [
            {"comparison_id": "speed_under_clear_conditions", "case_ids": [AID + "__reference", AID + "__faster"]},
            {"comparison_id": "visibility_at_reference_speed", "case_ids": [AID + "__reference", AID + "__reduced_visibility"]},
            {"comparison_id": "pedestrian_at_reference_speed", "case_ids": [AID + "__reference", AID + "__pedestrian_near_rack"]},
            {"comparison_id": "surface_at_reference_speed", "case_ids": [AID + "__reference", AID + "__wet_surface"]},
        ]}

    def test_speed_change(self):
        self.assertTrue(audit(self.plan, "speed_under_clear_conditions", record("reference"), record("faster", 5.0))["passed"])

    def test_visibility_change(self):
        self.assertTrue(audit(self.plan, "visibility_at_reference_speed", record("reference"), record("reduced_visibility", visibility="reduced"))["passed"])

    def test_pedestrian_and_surface_change(self):
        self.assertTrue(audit(self.plan, "pedestrian_at_reference_speed", record("reference"),
                              record("pedestrian_near_rack", pedestrians="near_rack"))["passed"])
        self.assertTrue(audit(self.plan, "surface_at_reference_speed", record("reference"),
                              record("wet_surface", surface="wet"))["passed"])

    def test_independent_delivery_receipt_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = []
            receipts = []
            for suffix, speed in (("reference", 3.0), ("faster", 5.0)):
                path = base / (suffix + ".json")
                path.write_text(json.dumps(record(suffix, speed)))
                receipt_path = base / (suffix + "-delivery.json")
                receipt_path.write_text(json.dumps({
                    "format": "worker-delivery-audit", "passed": True,
                    "case_id": AID + "__" + suffix,
                    "native_result_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "checks": ["native_source", "all_participants", "time_join",
                               "full_video_decode", "actual_pixels", "physical_completion"]}))
                paths.append(path)
                receipts.append(receipt_path)
            result = audit_guarded_pair(self.plan, "speed_under_clear_conditions", *paths, *receipts)
            self.assertTrue(result["independent_delivery_audits"])
            tampered = json.loads(receipts[1].read_text())
            tampered["native_result_sha256"] = "0" * 64
            receipts[1].write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "source-bound"):
                audit_guarded_pair(self.plan, "speed_under_clear_conditions", *paths, *receipts)

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

    def test_reported_mean_must_match_original_speeds(self):
        right = record("faster", 5.0)
        right["summary"]["mean_speed_mps"] = 6.0
        with self.assertRaisesRegex(ValueError, "reported mean"):
            check_record(right)

    def test_condition_time_must_join_original_speed_time(self):
        right = record("faster", 5.0)
        right["condition_samples"][0]["time_s"] = 0.05
        with self.assertRaisesRegex(ValueError, "condition source time"):
            check_record(right)

    def test_invalid_original_speed_rejected(self):
        right = record("faster", 5.0)
        right["samples"][0]["speed_mps"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid original speed"):
            check_record(right)


if __name__ == "__main__":
    unittest.main()
