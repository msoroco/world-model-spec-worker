"""Synthetic packets test the measurement code, not physical observations."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("red_observations", ROOT / "red_observations.py")
red = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(red)


def rows(**override):
    base = {
        "source_kind": "native_observed", "signal_state": "red",
        "governing_signal_id": "head-307-8a", "ego_front_y_m": -3.0,
        "ego_speed_mps": 2.0, "nearest_crosswalk_y_m": 0.0,
        "indicated_sign_y_m": 0.0, "indicated_marking_y_m": None,
        "intersection_entry_y_m": 5.0, "ego_lane_side": "right",
        "ego_lane_extreme": True, "ego_maneuver": "straight",
        "approach_one_way": False, "downstream_direction": "two_directional",
        "pedestrian_priority_present": False, "traffic_priority_present": False,
        "pedestrian_yielded": False, "traffic_yielded": False,
    }
    base.update(override)
    points = [(-3.0, 2.0, "red"), (-2.0, 0.0, "red"), (-2.0, 0.0, "red"), (-1.0, 2.0, "green"), (0.1, 2.0, "green"), (5.1, 2.0, "green")]
    return [dict(base, frame=i, time_s=i / 20, ego_front_y_m=y,
                 ego_speed_mps=speed, signal_state=state) for i, (y, speed, state) in enumerate(points)]


class RedMeasurementTest(unittest.TestCase):
    def test_full_stop_and_green_release(self):
        result = red.analyze(rows(), expected_signal_id="head-307-8a")
        self.assertEqual(result["stop_reference_kind"], "nearest_crosswalk")
        self.assertEqual(result["first_full_stop_frame"], 1)
        self.assertEqual(result["first_reference_crossing_frame"], 4)
        self.assertEqual(result["first_green_frame"], 3)
        self.assertIsNone(result["red_departure_frame"])
        self.assertIsNone(result["legal_outcome"])

    def test_reference_contexts(self):
        contexts = [
            ({"nearest_crosswalk_y_m": None, "indicated_sign_y_m": 0.0}, "indicated_sign"),
            ({"nearest_crosswalk_y_m": None, "indicated_sign_y_m": None,
              "indicated_marking_y_m": 0.0}, "indicated_marking"),
            ({"nearest_crosswalk_y_m": None, "indicated_sign_y_m": None,
              "indicated_marking_y_m": None}, "intersection_entry"),
        ]
        for changes, expected in contexts:
            with self.subTest(expected=expected):
                self.assertEqual(red.analyze(rows(**changes), expected_signal_id="head-307-8a")["stop_reference_kind"], expected)

    def test_early_red_departure_is_measured(self):
        packet = rows()
        packet[2]["ego_speed_mps"] = 0.5
        self.assertEqual(red.analyze(packet, expected_signal_id="head-307-8a")["red_departure_frame"], 2)

    def test_turn_permissions_and_yield_are_separate_facts(self):
        right = red.analyze(rows(ego_maneuver="right", pedestrian_priority_present=True,
                                 pedestrian_yielded=True), expected_signal_id="head-307-8a")
        self.assertTrue(right["turn_permission_context"])
        self.assertTrue(right["yield_observation"]["pedestrian_yielded"])
        wrong = red.analyze(rows(ego_maneuver="right", downstream_direction="one_way_left"),
                            expected_signal_id="head-307-8a")
        self.assertFalse(wrong["turn_permission_context"])
        left = red.analyze(rows(ego_maneuver="left", approach_one_way=True,
                                ego_lane_side="left", downstream_direction="one_way_left"),
                           expected_signal_id="head-307-8a")
        self.assertTrue(left["turn_permission_context"])

    def test_source_and_governing_signal_rejections(self):
        for changed, message in [
            ({"source_kind": "authored_cpu_request"}, "not Native"),
            ({"governing_signal_id": "other-head"}, "does not govern"),
        ]:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, message):
                    red.analyze(rows(**changed), expected_signal_id="head-307-8a")
        incomplete = rows()
        del incomplete[0]["ego_speed_mps"]
        with self.assertRaisesRegex(ValueError, "Missing original Native source"):
            red.analyze(incomplete, expected_signal_id="head-307-8a")

    def test_conflicting_references_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting sign"):
            red.analyze(rows(indicated_marking_y_m=0.25), expected_signal_id="head-307-8a")
        with self.assertRaisesRegex(ValueError, "Crosswalk and stop indication positions conflict"):
            red.analyze(rows(indicated_sign_y_m=-0.5), expected_signal_id="head-307-8a")


if __name__ == "__main__":
    unittest.main()
