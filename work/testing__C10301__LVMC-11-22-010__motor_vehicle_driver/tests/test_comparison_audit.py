import copy
import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "comparison_audit.py"
spec = importlib.util.spec_from_file_location("comparison_audit", MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def fixture():
    measurements = {}
    captures = {}
    for index, case_id in enumerate(audit_module.CASES):
        digest = str(index + 1) * 64
        measurements[case_id] = {
            "case_id": case_id, "source": {"path": "original/ego.jsonl", "sha256": digest},
            "frame_count": 900, "attention_state": "unobserved",
            "legal_judgment": "unresolved",
            "observed_exterior": {"max_abs_yaw_rate_rad_s": .01 + index * .02},
        }
        captures[case_id] = {
            "case_id": case_id, "operation_source_sha256": digest,
            "site_source_sha256": "a" * 64,
            "alley_route_source_sha256": "b" * 64,
            "access_aisle_source_sha256": "c" * 64,
            "parking_designation_source_sha256": "d" * 64,
            "municipal_jurisdiction_source_sha256": "e" * 64,
            "camera_ids": ["front", "rear", "left", "right"],
            "duration_frames": 900, "fps": 20, "nominal_speed_m_s": 2.0,
            "requested_lateral_profile": "steady" if index == 0 else "variation",
        }
    return measurements, captures


class ComparisonAuditTests(unittest.TestCase):
    def test_accepted_source_bound_comparison_keeps_judgment_open(self):
        measurements, captures = fixture()
        receipt = audit_module.audit(measurements, captures)
        self.assertEqual(receipt["legal_judgment"], "unresolved")
        self.assertEqual(receipt["physical_realization"], "requires_original_capture_review")

    def test_missing_source_and_fixed_condition_fail(self):
        measurements, captures = fixture()
        broken = copy.deepcopy(measurements)
        broken[audit_module.STEADY]["source"].pop("sha256")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            audit_module.audit(broken, captures)
        broken = copy.deepcopy(captures)
        broken[audit_module.VARIATION]["camera_ids"] = ["front"]
        with self.assertRaisesRegex(ValueError, "fixed-condition"):
            audit_module.audit(measurements, broken)

    def test_control_contrast_and_unsupported_claim_fail(self):
        measurements, captures = fixture()
        broken = copy.deepcopy(captures)
        broken[audit_module.VARIATION]["requested_lateral_profile"] = "steady"
        with self.assertRaisesRegex(ValueError, "control contrast"):
            audit_module.audit(measurements, broken)
        broken = copy.deepcopy(measurements)
        broken[audit_module.STEADY]["attention_state"] = "distracted"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            audit_module.audit(broken, captures)


if __name__ == "__main__":
    unittest.main()
