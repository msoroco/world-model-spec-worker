import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "comparison_audit.py"
SPEC = importlib.util.spec_from_file_location("comparison_audit", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def row(case_id, gap):
    return {"case_id": case_id, "source_kind": "original_native_saved", "measurement_status": "measured",
            "capture_fps": 20, "source_sha256": "a" * 64, "crossing_map_sha256": "b" * 64,
            "crossing_authority_sha256": "c" * 64, "sign_landmark_id": "s", "nearest_rail_id": "r",
            "ego_blueprint_id": "vehicle.test", "approach_direction": 1, "camera_plan_sha256": "d" * 64,
            "first_stop_body_to_nearest_rail_min_ft": gap}


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.left, self.right = row("left", 14.9), row("right", 15.1)
        self.comparison = {"comparison_id": "lower", "case_ids": ["left", "right"], "variable": "stop_position_ft"}

    def test_measured_contrast(self):
        self.assertEqual(AUDIT.audit_pair(self.left, self.right, self.comparison)["status"], "measured_contrast")

    def test_missing_original_source_rejected(self):
        self.right["source_kind"] = "synthetic"
        with self.assertRaisesRegex(ValueError, "original saved"):
            AUDIT.audit_pair(self.left, self.right, self.comparison)

    def test_fixed_authority_change_rejected(self):
        self.right["crossing_authority_sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "fixed comparison field"):
            AUDIT.audit_pair(self.left, self.right, self.comparison)

    def test_missing_measurement_rejected(self):
        del self.right["first_stop_body_to_nearest_rail_min_ft"]
        with self.assertRaisesRegex(ValueError, "measurement missing"):
            AUDIT.audit_pair(self.left, self.right, self.comparison)

    def test_no_measured_contrast_rejected(self):
        self.right["first_stop_body_to_nearest_rail_min_ft"] = 14.9
        with self.assertRaisesRegex(ValueError, "lacks measured contrast"):
            AUDIT.audit_pair(self.left, self.right, self.comparison)

    def test_wrong_identity_rejected(self):
        self.right["case_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity differs"):
            AUDIT.audit_pair(self.left, self.right, self.comparison)


if __name__ == "__main__":
    unittest.main()
