import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("yield_control", Path(__file__).resolve().parents[1] / "yield_control.py")
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def observation(**changes):
    value = {"ego_speed_mps": 3.0, "distance_to_view_point_m": 5.0,
             "through_vehicle_in_conflict_interval": True,
             "yield_sign_governs_approach": True, "viewpoint_source_verified": True}
    value.update(changes)
    return value


class YieldControlTests(unittest.TestCase):
    def test_response_holds_on_observed_conflict(self):
        result = controller.control("nearest_view_response", observation())
        self.assertGreater(result["brake"], 0)
        self.assertEqual(result["throttle"], 0)

    def test_comparison_changes_only_conflict_response(self):
        uninterrupted = controller.control("nearest_view_uninterrupted", observation())
        self.assertEqual(uninterrupted["brake"], 0)
        self.assertGreater(uninterrupted["throttle"], 0)
        before_view = observation(distance_to_view_point_m=12)
        self.assertEqual(controller.control("nearest_view_response", before_view),
                         controller.control("nearest_view_uninterrupted", before_view))
        clear = observation(through_vehicle_in_conflict_interval=False)
        self.assertEqual(controller.control("nearest_view_response", clear),
                         controller.control("nearest_view_uninterrupted", clear))

    def test_rejects_unsourced_viewpoint(self):
        with self.assertRaisesRegex(ValueError, "source-verified viewpoint"):
            controller.control("nearest_view_response", observation(viewpoint_source_verified=False))

    def test_rejects_missing_traffic_observation(self):
        value = observation()
        del value["through_vehicle_in_conflict_interval"]
        with self.assertRaisesRegex(ValueError, "conflict observation"):
            controller.control("nearest_view_response", value)


if __name__ == "__main__":
    unittest.main()
