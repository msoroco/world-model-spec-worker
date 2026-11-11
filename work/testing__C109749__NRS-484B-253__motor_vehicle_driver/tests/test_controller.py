import importlib.util
from pathlib import Path
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controller", PACKAGE / "controller.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def values(**overrides):
    row = dict(distance_to_hold_m=1.0, ego_speed_mps=0.0,
               oncoming_distance_to_conflict_m=12.0, oncoming_closing_speed_mps=5.0,
               oncoming_in_intersection=False, oncoming_cleared=False,
               turn_complete=False)
    row.update(overrides)
    return row


class LeftTurnControllerTest(unittest.TestCase):
    def test_waits_then_turns_after_opposing_clearance(self):
        controller = MODULE.LeftTurnController()
        waiting = controller.step(**values(oncoming_in_intersection=True))
        self.assertEqual((waiting["state"], waiting["brake"]), ("yield", 1.0))
        turning = controller.step(**values(oncoming_distance_to_conflict_m=-2,
                                          oncoming_cleared=True))
        self.assertEqual(turning["state"], "turn")
        self.assertTrue(turning["left_indicator"])
        self.assertLess(turning["steer"], 0)

    def test_does_not_release_only_from_ttc(self):
        controller = MODULE.LeftTurnController()
        controller.step(**values())
        result = controller.step(**values(oncoming_distance_to_conflict_m=50))
        self.assertEqual(result["state"], "yield")

    def test_complete_stops_and_clears_signal(self):
        controller = MODULE.LeftTurnController()
        result = controller.step(**values(turn_complete=True))
        self.assertEqual(result["state"], "complete")
        self.assertFalse(result["left_indicator"])


if __name__ == "__main__":
    unittest.main()
