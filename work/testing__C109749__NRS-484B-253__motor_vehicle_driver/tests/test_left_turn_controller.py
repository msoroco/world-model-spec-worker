import importlib.util
import pathlib
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "left_turn_controller.py"
SPEC = importlib.util.spec_from_file_location("left_turn_controller", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def call(policy, *, inside=True, cleared=False, later=False, connected=True):
    return policy.tick(ego_fully_inside=inside, initial_opponent_cleared=cleared,
                       later_opponent_present=later, left_route_connected=connected,
                       speed_mps=4)


class TurnController(unittest.TestCase):
    def test_initial_yield_and_release(self):
        policy = MODULE.TurnPolicy(True, True)
        self.assertEqual(call(policy)["target_speed_mps"], 0)
        released = call(policy, cleared=True)
        self.assertEqual(released["path_request"], "left_turn")
        self.assertIsNone(released["measured_behavior"])

    def test_requested_non_yield_is_distinct(self):
        policy = MODULE.TurnPolicy(False, True)
        self.assertEqual(call(policy)["path_request"], "left_turn")

    def test_signal_is_independent_of_yield(self):
        policy = MODULE.TurnPolicy(True, False)
        self.assertFalse(call(policy)["left_signal_requested"])
        self.assertEqual(policy.phase, "wait")

    def test_reciprocal_wait(self):
        policy = MODULE.TurnPolicy(True, True, True)
        call(policy, cleared=True, later=True)
        self.assertEqual(policy.phase, "later_wait")
        self.assertEqual(call(policy, cleared=True, later=False)["phase"], "turn")

    def test_missing_left_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "connected left-turn"):
            call(MODULE.TurnPolicy(True, True), connected=False)


if __name__ == "__main__":
    unittest.main()
