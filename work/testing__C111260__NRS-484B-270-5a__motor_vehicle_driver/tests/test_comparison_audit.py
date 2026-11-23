import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comparison_audit", ROOT / "comparison_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pair():
    base = {"map_sha256": "a" * 64, "rider_kind": "bicycle",
            "rider_blueprint_id": "vehicle.bicycle", "ego_route_sha256": "b" * 64,
            "rider_route_sha256": "c" * 64, "camera_plan_sha256": "d" * 64,
            "duration_frames": 900, "hz": 20, "initial_ego_speed_mps": 8.0,
            "initial_rider_speed_mps": 3.0}
    return ({**base, "case_id": "brake", "response": "brake", "observed_brake_peak": 0.7,
             "original_history_sha256": "e" * 64},
            {**base, "case_id": "maintain", "response": "maintain", "observed_brake_peak": 0.0,
             "original_history_sha256": "f" * 64})


class ComparisonTests(unittest.TestCase):
    def test_valid_pair_keeps_judgment_open(self):
        self.assertEqual(MODULE.audit_pair(*pair())["legal_judgment"], "undetermined")

    def test_missing_source_rejected(self):
        a, b = pair()
        del a["original_history_sha256"]
        with self.assertRaisesRegex(ValueError, "missing"):
            MODULE.audit_pair(a, b)

    def test_fixed_map_rejected(self):
        a, b = pair()
        b["map_sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "fixed"):
            MODULE.audit_pair(a, b)

    def test_response_readback_rejected(self):
        a, b = pair()
        a["observed_brake_peak"] = 0.0
        with self.assertRaisesRegex(ValueError, "not observed"):
            MODULE.audit_pair(a, b)

    def test_initial_speed_rejected(self):
        a, b = pair()
        b["initial_rider_speed_mps"] = 7.0
        with self.assertRaisesRegex(ValueError, "initial speed"):
            MODULE.audit_pair(a, b)


if __name__ == "__main__":
    unittest.main()
