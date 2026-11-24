import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import FIXED, PREFIX, compare_exact


class ExactComparisonTests(unittest.TestCase):
    def record(self, suffix, event, siren, lamps):
        value = {field: "fixed-source-hash" for field in FIXED}
        value.update(cell_id="C109035", actor="emergency_vehicle_driver",
                     case_id=PREFIX + suffix, event_context=event,
                     requested_siren=siren, requested_warning_lamps=lamps)
        return value

    def test_exact_device_choice(self):
        records = [self.record("response_siren_pedestrian", "emergency_call", True, False),
                   self.record("response_lamps_only", "emergency_call", False, True),
                   self.record("response_silent", "emergency_call", False, False)]
        result = compare_exact(ROOT / "case-plan.json", "response_device_choice", records)
        self.assertEqual(len(result["case_plan_sha256"]), 64)
        self.assertEqual(result["physical_status"], "source_join_only")

    def test_substituted_case_rejected(self):
        records = [self.record("response_siren_pedestrian", "emergency_call", True, False),
                   self.record("unqualified_lamps_only", "none", False, True),
                   self.record("response_silent", "emergency_call", False, False)]
        with self.assertRaisesRegex(ValueError, "membership"):
            compare_exact(ROOT / "case-plan.json", "response_device_choice", records)

    def test_mislabeled_controls_rejected(self):
        records = [self.record("response_lamps_only", "emergency_call", True, True),
                   self.record("unqualified_lamps_only", "none", False, True)]
        with self.assertRaisesRegex(ValueError, "Authored controls"):
            compare_exact(ROOT / "case-plan.json", "lamps_without_siren", records)

    def test_changed_fixed_source_rejected(self):
        records = [self.record("response_lamps_only", "emergency_call", False, True),
                   self.record("unqualified_lamps_only", "none", False, True)]
        records[1]["site_sha256"] = "different-site"
        with self.assertRaisesRegex(ValueError, "Fixed condition"):
            compare_exact(ROOT / "case-plan.json", "lamps_without_siren", records)


if __name__ == "__main__":
    unittest.main()
