"""CPU checks for authored cross-traffic geometry and control."""
import unittest

from traffic_branch import decide
from traffic_geometry import check, open_drive


class TrafficBranchTests(unittest.TestCase):
    def test_geometry_has_separate_cross_traffic_signal(self):
        result = check()
        self.assertEqual(result["cross_traffic_signal_id"], "602")
        self.assertIn('name="west-approach-circular-green"', open_drive())
        self.assertFalse(result["native_signal_direction_verified"])

    def test_both_policies_preserve_common_red_stop(self):
        for policy in ("traffic_yield_wait", "traffic_conflict_entry"):
            outcome = decide(policy, red_stop_completed=False,
                             in_merge_approach=True, traffic_conflict_occupied=True,
                             previous_clear_frames=0, required_clear_frames=20)
            self.assertTrue(outcome.brake)

    def test_occupied_traffic_changes_only_post_stop_response(self):
        values = dict(red_stop_completed=True, in_merge_approach=True,
                      traffic_conflict_occupied=True, previous_clear_frames=0,
                      required_clear_frames=20)
        self.assertTrue(decide("traffic_yield_wait", **values).brake)
        self.assertFalse(decide("traffic_conflict_entry", **values).brake)

    def test_clearance_and_invalid_state(self):
        values = dict(red_stop_completed=True, in_merge_approach=True,
                      traffic_conflict_occupied=False, previous_clear_frames=3,
                      required_clear_frames=20)
        self.assertTrue(decide("traffic_yield_wait", **values).brake)
        with self.assertRaises(ValueError):
            decide("traffic_yield_wait", **dict(values, required_clear_frames=-1))


if __name__ == "__main__":
    unittest.main()
