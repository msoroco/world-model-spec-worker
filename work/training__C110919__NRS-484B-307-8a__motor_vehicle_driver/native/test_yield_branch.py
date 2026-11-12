from __future__ import annotations

import unittest

from yield_branch import POLICIES, decide


class YieldBranchTest(unittest.TestCase):
    def test_identical_red_stop_obligation(self):
        for policy in POLICIES:
            decision = decide(policy, red_stop_completed=False, in_turn_approach=True,
                              conflict_occupied=True, previous_clearance_frames=0,
                              required_clearance_frames=20)
            self.assertTrue(decision.brake)
            self.assertEqual(decision.reason, "red_stop_not_completed")

    def test_pedestrian_occupancy_is_only_deliberate_difference(self):
        arguments = dict(red_stop_completed=True, in_turn_approach=True,
                         conflict_occupied=True, previous_clearance_frames=0,
                         required_clearance_frames=20)
        wait = decide("yield_wait", **arguments)
        entry = decide("yield_conflict_entry", **arguments)
        self.assertTrue(wait.brake)
        self.assertFalse(entry.brake)
        self.assertEqual(wait.clearance_frames, entry.clearance_frames)

    def test_clearance_margin_and_outside_approach(self):
        args = dict(red_stop_completed=True, in_turn_approach=True,
                    conflict_occupied=False, required_clearance_frames=20)
        self.assertTrue(decide("yield_wait", previous_clearance_frames=18, **args).brake)
        self.assertFalse(decide("yield_wait", previous_clearance_frames=19, **args).brake)
        for policy in POLICIES:
            self.assertFalse(decide(policy, red_stop_completed=True,
                                    in_turn_approach=False, conflict_occupied=True,
                                    previous_clearance_frames=0,
                                    required_clearance_frames=20).brake)

    def test_bad_states_rejected(self):
        with self.assertRaises(ValueError):
            decide("unknown", red_stop_completed=True, in_turn_approach=True,
                   conflict_occupied=True, previous_clearance_frames=0,
                   required_clearance_frames=20)
        with self.assertRaises(ValueError):
            decide("yield_wait", red_stop_completed=True, in_turn_approach=True,
                   conflict_occupied=True, previous_clearance_frames=-1,
                   required_clearance_frames=20)


if __name__ == "__main__":
    unittest.main()
