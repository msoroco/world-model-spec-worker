import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_speed_controller import NativeSpeedController, SpeedControlError


class Ego:
    def __init__(self, speed):
        self.speed = speed
        self.applied = []

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0.0, z=0.0)

    def apply_control(self, control):
        self.applied.append(control)


class SpeedControllerTests(unittest.TestCase):
    def test_uses_original_velocity_and_applies_throttle_or_brake(self):
        maker = lambda **fields: fields
        control = NativeSpeedController(15 * .44704, maker)
        slow = Ego(2.0)
        receipt = control.apply(slow)
        self.assertGreater(slow.applied[-1]["throttle"], 0)
        self.assertEqual(slow.applied[-1]["brake"], 0)
        self.assertEqual(receipt["original_speed_mps"], 2.0)
        fast = Ego(12.0)
        control.apply(fast)
        self.assertGreater(fast.applied[-1]["brake"], 0)
        self.assertEqual(fast.applied[-1]["throttle"], 0)

    def test_invalid_original_speed_rejected_before_control(self):
        maker = lambda **fields: fields
        control = NativeSpeedController(6.7, maker)
        bad = Ego(float("nan"))
        with self.assertRaisesRegex(SpeedControlError, "velocity unavailable"):
            control.apply(bad)
        self.assertEqual(bad.applied, [])

    def test_bounded_fallback_reduces_positive_throttle_only(self):
        maker = lambda **fields: fields
        primary = NativeSpeedController(6.7, maker, 1.0)
        fallback = NativeSpeedController(6.7, maker, 0.75)
        slow = Ego(5.7)
        primary.apply(slow)
        primary_throttle = slow.applied[-1]["throttle"]
        fallback_receipt = fallback.apply(slow)
        self.assertLess(slow.applied[-1]["throttle"], primary_throttle)
        self.assertEqual(fallback_receipt["target_mps"], 6.7)
        self.assertEqual(fallback_receipt["controller_gain"], 0.75)
        with self.assertRaisesRegex(SpeedControlError, "bounded controller gain"):
            NativeSpeedController(6.7, maker, 2.0)


if __name__ == "__main__":
    unittest.main()
