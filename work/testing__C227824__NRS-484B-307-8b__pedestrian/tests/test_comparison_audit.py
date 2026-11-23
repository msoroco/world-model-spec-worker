import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "comparison_audit.py"
SPEC = importlib.util.spec_from_file_location("c227824_comparison_audit", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report(case, device="none", request="entry", entered=True):
    devices = [] if device == "none" else [{"official": True, "indication": device}]
    event = {"frame": 2, "facing_traffic_signal": {"official": True, "indication": "steady_red_alone"},
             "other_devices": devices} if entered else None
    return {"case_id": case, "map_sha256": "map", "highway_boundary_sha256": "boundary",
            "facing_signal_id": "red-1", "actor_blueprint": "walker.pedestrian.test",
            "route_id": "crossing-1", "camera_plan_sha256": "cameras",
            "entry_request": request, "planned_device_indication": device,
            "measurement": {"first_entry": event, "entry_observed": entered,
                            "measurement_only": True, "legal_permission_determined": False}}


class ComparisonAuditTests(unittest.TestCase):
    def test_accepts_bound_entry_wait_pair(self):
        result = MODULE.audit_pair(report("a"), report("b", request="wait", entered=False),
                                   comparison_id="entry_vs_wait", deliberate_difference="entry_request")
        self.assertTrue(result["diagnostic_audit_passed"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_accepts_separate_walk_device_pair(self):
        result = MODULE.audit_pair(report("a"), report("b", device="walk"),
                                   comparison_id="walk", deliberate_difference="other_device_indication")
        self.assertEqual(result["case_ids"], ["a", "b"])

    def test_rejects_changed_fixed_boundary_and_missing_device(self):
        changed = report("b", device="walk")
        changed["highway_boundary_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed comparison condition"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")
        changed = report("b", device="walk")
        changed["measurement"]["first_entry"]["other_devices"] = []
        with self.assertRaisesRegex(ValueError, "planned device disagrees"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")

    def test_rejects_missing_entry_source_and_red_state(self):
        changed = report("b", device="walk", entered=False)
        with self.assertRaisesRegex(ValueError, "lacks observed first entry"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")
        changed = report("b", device="walk")
        changed["measurement"]["first_entry"]["facing_traffic_signal"]["indication"] = "other"
        with self.assertRaisesRegex(ValueError, "steady red"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")


if __name__ == "__main__":
    unittest.main()
