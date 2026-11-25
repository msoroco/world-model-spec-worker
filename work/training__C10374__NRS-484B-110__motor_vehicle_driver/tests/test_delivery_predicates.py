"""CPU checks for original source rejection and comparison isolation."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


delivery = module("delivery_audit")
comparison = module("comparison_audit")


class DeliveryPredicates(unittest.TestCase):
    def test_original_result_rejection(self):
        case = "training__C10374__NRS-484B-110__motor_vehicle_driver__selected_c5852cfd__condition_a"
        sample = {"case_id": case, "provenance_kind": "original_native",
                  "diagnostic_fixture": False, "maneuver_completed": True,
                  "physical_checks": {"maneuver": {"status": "met"}, "setup": {"status": "unverified"}},
                  "realized_observables": {"progress_m": 20},
                  "recording_evidence": [{"name": "kin.speed"}, {"name": "zone_body"}]}
        delivery.check_result(sample, case)
        for key, bad in (("provenance_kind", "synthetic_fixture"),
                         ("maneuver_completed", False), ("recording_evidence", [])):
            changed = json.loads(json.dumps(sample))
            changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                delivery.check_result(changed, case)

    def test_comparison_changes_only_observed_overlap(self):
        a_case = "case_a"
        b_case = "case_b"
        fixed = {"cell_id": "C10374", "law_id": "NRS-484B-110",
                 "actor": "motor_vehicle_driver", "map_sha256": "map",
                 "camera_contract_sha256": "camera", "duration_s": 30,
                 "rate_hz": 20, "weather_profile": "ClearNoon"}

        def result(case, overlap):
            return {"case_id": case, "provenance_kind": "original_native",
                    "physical_checks": {"maneuver": {"status": "met"}, "setup": {"status": "unverified"}},
                    "comparison_fixed_conditions": fixed.copy(),
                    "measured_values": {"moving_body_rectangle_overlap_frames": overlap}}

        a, b = result(a_case, 60), result(b_case, 0)
        self.assertEqual(comparison.compare(a, b, a_case, b_case)["condition_b_overlap_frames"], 0)
        for key, bad in (("map_sha256", "other-map"), ("duration_s", 31)):
            changed = json.loads(json.dumps(b))
            changed["comparison_fixed_conditions"][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                comparison.compare(a, changed, a_case, b_case)


if __name__ == "__main__":
    unittest.main()
