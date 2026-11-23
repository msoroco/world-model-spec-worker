"""CPU checks for the selected red-left-turn motion request sequence."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from red_left_turn_controller import Observation, RedLeftTurnController, controller_for_case


def sample(t, distance, speed, *, signal="steady_red_alone", pedestrian=False,
           traffic=False, exited=False):
    return Observation(t, distance, speed, signal, pedestrian, traffic, exited)


class ControllerTests(unittest.TestCase):
    def test_stops_before_boundary_and_yields_to_both_conflict_types(self):
        control = RedLeftTurnController()
        self.assertEqual(control.step(sample(0, 5, 3))["phase"], "approach")
        self.assertEqual(control.step(sample(1, 1, 1))["phase"], "stopping")
        self.assertEqual(control.step(sample(2, 0.5, 0))["phase"], "stopping")
        self.assertEqual(control.step(sample(2.5, 0.5, 0, pedestrian=True))["phase"], "yielding")
        self.assertEqual(control.step(sample(2.6, 0.5, 0, traffic=True))["phase"], "yielding")
        self.assertEqual(control.step(sample(2.7, 0.5, 0))["phase"], "turning")
        self.assertEqual(control.step(sample(4, -5, 2, exited=True))["phase"], "done")
        self.assertTrue(all(row["engineering_only"] for row in control.history))

    def test_rolling_or_beyond_boundary_never_unlocks_turn(self):
        control = RedLeftTurnController()
        control.step(sample(0, 1, 2))
        self.assertEqual(control.step(sample(1, -0.2, 0))["phase"], "stopping")
        self.assertEqual(control.step(sample(2, -0.2, 0))["phase"], "stopping")
        self.assertIsNone(control.stop_start_s)

    def test_signal_and_time_guards(self):
        control = RedLeftTurnController()
        control.step(sample(0, 1, 0))
        control.step(sample(0.5, 1, 0, signal="unknown"))
        self.assertEqual(control.phase, "yielding")
        self.assertEqual(control.step(sample(0.6, 1, 0, signal="other"))["phase"], "yielding")
        with self.assertRaises(ValueError):
            control.step(sample(0.6, 1, 0))
        with self.assertRaises(ValueError):
            RedLeftTurnController(stop_dwell_s=0)

    def test_exact_requested_rolling_and_conflict_advance_probes(self):
        rolling = controller_for_case("rolling_leftmost_clear")
        row = rolling.step(sample(0, 1, 2))
        self.assertEqual(row["phase"], "turning")
        self.assertEqual(row["stop_request"], "rolling")
        pedestrian = controller_for_case("stopped_leftmost_pedestrian_advance")
        pedestrian.step(sample(0, 1, 0, pedestrian=True))
        row = pedestrian.step(sample(0.5, 1, 0, pedestrian=True))
        self.assertEqual(row["phase"], "turning")
        self.assertTrue(row["pedestrian_conflict"])
        self.assertEqual(row["conflict_response_request"], "advance")
        traffic = controller_for_case("stopped_leftmost_traffic_yield")
        traffic.step(sample(0, 1, 0, traffic=True))
        self.assertEqual(traffic.step(sample(0.5, 1, 0, traffic=True))["phase"], "yielding")
        with self.assertRaises(ValueError):
            controller_for_case("not_a_frozen_case")


if __name__ == "__main__":
    unittest.main()
