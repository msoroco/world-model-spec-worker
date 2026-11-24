import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from construction import ASSIGNMENT_ID, CAMERAS, POLICIES, build
from test_native_acquisition import waypoint


def packet():
    return {"map_sha256": "a" * 64, "source_ref": "diagnostic-map",
            "junction_id": 9,
            "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
            "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
            "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
            "later_opposing_route": [waypoint(0, 14, None), waypoint(0, 0, 9), waypoint(0, -14, None)],
            "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}


class Construction(unittest.TestCase):
    def test_all_eight_exact_cases_have_source_route_and_capture(self):
        for suffix in POLICIES:
            request = build(ASSIGNMENT_ID + "__" + suffix, packet())
            self.assertEqual(request["case_id"], ASSIGNMENT_ID + "__" + suffix)
            self.assertEqual(request["capture"]["frame_count"], 900)
            self.assertEqual(request["capture"]["cameras"], list(CAMERAS))
            self.assertEqual(request["legal_outcome"], "unresolved")

    def test_initial_yield_pair_changes_only_wait_policy(self):
        a = build(ASSIGNMENT_ID + "__inside_yield", packet())
        b = build(ASSIGNMENT_ID + "__inside_no_yield", packet())
        for key in a:
            if key not in ("case_id", "controller"):
                self.assertEqual(a[key], b[key])
        self.assertEqual(a["controller"]["signal_left"], b["controller"]["signal_left"])
        self.assertNotEqual(a["controller"]["wait_for_initial_opponent"],
                            b["controller"]["wait_for_initial_opponent"])

    def test_approach_spawn_is_outside_junction(self):
        a = build(ASSIGNMENT_ID + "__inside_yield", packet())
        b = build(ASSIGNMENT_ID + "__approaching_yield", packet())
        self.assertEqual(a["initial_opponent_spawn_waypoint"]["junction_id"], 9)
        self.assertIsNone(b["initial_opponent_spawn_waypoint"]["junction_id"])

    def test_reciprocal_needs_distinct_later_route(self):
        source = packet()
        source.pop("later_opposing_route")
        with self.assertRaisesRegex(ValueError, "distinct later opposing route"):
            build(ASSIGNMENT_ID + "__reciprocal_yield", source)

    def test_wrong_case_and_wrong_turn_rejected(self):
        with self.assertRaisesRegex(ValueError, "unplanned"):
            build(ASSIGNMENT_ID + "__unknown", packet())
        source = packet()
        source["ego_route"][-1] = waypoint(10, 0, None)
        with self.assertRaisesRegex(ValueError, "turn left"):
            build(ASSIGNMENT_ID + "__inside_yield", source)


if __name__ == "__main__":
    unittest.main()
