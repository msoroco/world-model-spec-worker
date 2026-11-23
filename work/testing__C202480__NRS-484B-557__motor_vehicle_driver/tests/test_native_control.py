import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[1] / "native_control.py"
SPEC = importlib.util.spec_from_file_location("native_control", MODULE)
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


class Ego:
    def __init__(self, x, vx):
        self.x, self.vx, self.commands = x, vx, []

    def get_location(self):
        return SimpleNamespace(x=self.x, y=0)

    def get_velocity(self):
        return SimpleNamespace(x=self.vx, y=0)

    def apply_control(self, command):
        self.commands.append(command)


def controller(ego, rolling=False):
    return CONTROL.RailApproachController(ego, [0, 0], [1, 0], 2.0, 30.0,
                                          lambda **kwargs: kwargs, rolling=rolling)


class NativeControlTest(unittest.TestCase):
    def test_approach_and_braking_commands(self):
        ego = Ego(-30, 2)
        unit = controller(ego)
        self.assertEqual(unit.step(False)["phase"], "approach_requested")
        ego.x = -11.5
        self.assertEqual(unit.step(False)["phase"], "braking_requested")
        self.assertGreater(ego.commands[-1]["brake"], 0)

    def test_stop_hold_then_clear_departure(self):
        ego = Ego(-(2 + 30 / CONTROL.FEET_PER_METRE), 0)
        unit = controller(ego)
        self.assertEqual(unit.step(False)["phase"], "stop_hold_requested")
        self.assertEqual(unit.step(True)["phase"], "departure_requested")
        self.assertEqual(unit.step(False)["phase"], "departure_requested")

    def test_rolling_probe_never_requests_complete_stop(self):
        ego = Ego(-(2 + 30 / CONTROL.FEET_PER_METRE), 1)
        unit = controller(ego, rolling=True)
        self.assertEqual(unit.step(False)["phase"], "rolling_requested")
        self.assertEqual(ego.commands[-1]["brake"], 0)

    def test_reverse_approach_direction(self):
        ego = Ego(30, -2)
        unit = CONTROL.RailApproachController(ego, [0, 0], [-1, 0], 2, 30,
                                               lambda **kwargs: kwargs)
        self.assertEqual(unit.step(False)["phase"], "approach_requested")

    def test_nonfinite_live_speed_rejected(self):
        ego = Ego(-20, float("nan"))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            controller(ego).step(False)


if __name__ == "__main__":
    unittest.main()
