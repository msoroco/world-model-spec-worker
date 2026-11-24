import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "staged-turn-cells"
SPEC = importlib.util.spec_from_file_location("c104538_staged_geometry", ROOT / "geometry.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StagedTurnCellsTest(unittest.TestCase):
    def test_right_and_left_have_distinct_real_turn_paths(self):
        for direction, expected_sign in (("left", -1), ("right", 1)):
            with self.subTest(direction=direction):
                self.assertTrue(MODULE.check(direction)["passed"])
                straight = MODULE.sampled_source(direction, "obey")
                turning = MODULE.sampled_source(direction, "turn")
                self.assertEqual(600, len(straight))
                self.assertEqual(straight[220]["body_center_xy_m"],
                                 turning[220]["body_center_xy_m"])
                self.assertEqual(0, straight[-1]["body_center_xy_m"][0])
                self.assertGreater(turning[-1]["body_center_xy_m"][0] * expected_sign, 8)
                self.assertEqual(0, turning[-1]["body_center_xy_m"][1])
                self.assertEqual([0, -8], turning[220]["body_center_xy_m"])

    def test_source_rejects_wrong_direction_and_behavior(self):
        with self.assertRaises(ValueError):
            MODULE.sampled_source("u_turn", "turn")
        with self.assertRaises(ValueError):
            MODULE.sampled_source("left", "dismount")
