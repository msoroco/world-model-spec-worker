import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c111125_audit", ROOT / "comparison_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def row(suffix, **changes):
    base = {"case_suffix": suffix, "map_sha256": "a", "device_sha256": "b",
            "detector_sha256": "c", "blueprint_sha256": "d", "source_sha256": {k: k for k in ("native_trace_ref", "device_trace_ref", "detector_trace_ref", "geometry_ref")},
            "straight_route_observed": True, "entry_frame": 3, "duration_frames": 5,
            "prior_stop_observed": True, "red_held_to_entry": True,
            "detector_occupancy_observed": True, "detector_failure_observed": True,
            "complete_device_cycles_before_entry": 2, "conflict_at_entry": False}
    base.update(changes)
    return base


class AuditTests(unittest.TestCase):
    def test_all_controlled_pairs(self):
        self.assertEqual(audit.audit_pair("two_vs_one_complete_cycles", row("two_cycles_failed_detection"), row("one_cycle", complete_device_cycles_before_entry=1))["fixed_sources_checked"], 4)
        self.assertEqual(audit.audit_pair("failed_detection_vs_signal_change", row("two_cycles_failed_detection"), row("signal_changes", detector_failure_observed=False, red_held_to_entry=False))["fixed_sources_checked"], 4)
        self.assertEqual(audit.audit_pair("stop_antecedent", row("two_cycles_failed_detection"), row("no_prior_stop", prior_stop_observed=False))["fixed_sources_checked"], 4)
        self.assertEqual(audit.audit_pair("yield_to_directed_participant", row("two_cycles_failed_detection"), row("fails_to_yield", conflict_at_entry=True))["fixed_sources_checked"], 4)

    def test_reject_missing_and_uncontrolled_evidence(self):
        left = row("two_cycles_failed_detection")
        right = row("one_cycle", complete_device_cycles_before_entry=1)
        right["source_sha256"] = {}
        with self.assertRaisesRegex(audit.ComparisonError, "source bindings"):
            audit.audit_pair("two_vs_one_complete_cycles", left, right)
        right = row("one_cycle", complete_device_cycles_before_entry=1, map_sha256="other")
        with self.assertRaisesRegex(audit.ComparisonError, "fixed source"):
            audit.audit_pair("two_vs_one_complete_cycles", left, right)
        right = row("one_cycle", complete_device_cycles_before_entry=1, prior_stop_observed=False)
        with self.assertRaisesRegex(audit.ComparisonError, "undeclared"):
            audit.audit_pair("two_vs_one_complete_cycles", left, right)
        right = row("one_cycle", complete_device_cycles_before_entry=2)
        with self.assertRaisesRegex(audit.ComparisonError, "cycles not measured"):
            audit.audit_pair("two_vs_one_complete_cycles", left, right)


if __name__ == "__main__":
    unittest.main()
