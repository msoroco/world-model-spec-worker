"""CPU checks that live motion, direction and brake requests drive the controller."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_control import step


class Actor:
    def __init__(self, x, speed):
        self.x, self.speed, self.controls = x, speed, []
        self.bounding_box = type("Box", (), {
            "extent": type("Extent", (), {"x": 2.})()})()

    def get_transform(self):
        return type("Transform", (), {"location": type("Point", (), {"x": self.x})()})()

    def get_velocity(self):
        return type("Velocity", (), {"x": self.speed, "y": 0., "z": 0.})()

    def apply_control(self, control):
        self.controls.append(control)


class ControlTests(unittest.TestCase):
    def test_both_directions_brake_at_stop_line_and_drive_on_approach(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                ego = Actor(-20 * direction, 1.)
                companion = Actor(-20 * direction, 1.)
                scene = type("Scene", (), {"ego": ego, "companion": companion,
                                            "packet": {"approach_direction": direction,
                                                       "stop_line_x_m": 0.}})()
                factory = lambda **kwargs: kwargs
                approach = step(scene, factory)
                self.assertGreater(approach["ego"]["throttle"], 0)
                self.assertEqual(len(ego.controls), 1)
                self.assertEqual(len(companion.controls), 1)
                ego.x = companion.x = -1 * direction
                stop = step(scene, factory)
                self.assertEqual(stop["ego"]["brake"], 1.)
                self.assertEqual(stop["companion"]["brake"], 1.)
                self.assertFalse(stop["ego"]["observed_stop_confirmed"])
                self.assertLess(stop["ego"]["remaining_to_authored_stop_m"], 0)

    def test_front_bumper_margin_changes_with_original_vehicle_length(self):
        ego = Actor(-3., 0.)
        ego.bounding_box.extent.x = 2.8
        scene = type("Scene", (), {"ego": ego, "companion": None,
                                    "packet": {"approach_direction": 1,
                                               "stop_line_x_m": 0.}})()
        result = step(scene, lambda **kwargs: kwargs)["ego"]
        self.assertEqual(result["brake"], 1.)
        self.assertAlmostEqual(result["remaining_to_authored_stop_m"], -.3)

    def test_nonfinite_live_velocity_rejected(self):
        ego = Actor(-10., float("nan"))
        scene = type("Scene", (), {"ego": ego, "companion": None,
                                    "packet": {"approach_direction": 1,
                                               "stop_line_x_m": 0.}})()
        with self.assertRaisesRegex(ValueError, "invalid Native motion sample"):
            step(scene, lambda **kwargs: kwargs)


if __name__ == "__main__":
    unittest.main()
