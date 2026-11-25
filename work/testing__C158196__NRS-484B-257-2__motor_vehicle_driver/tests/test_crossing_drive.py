import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crossing_drive", ROOT / "crossing_drive.py")
drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drive)


class Actor:
    def __init__(self):
        self.controls = []

    def apply_control(self, command):
        self.controls.append(command)


class DriveTests(unittest.TestCase):
    def test_hold_then_proceed_with_other_traffic(self):
        ego, other = Actor(), Actor()
        make = lambda **kwargs: kwargs
        for tick in range(4):
            drive.apply_tick(ego, other, make, tick, hold_ticks=2)
        self.assertEqual([c["brake"] for c in ego.controls], [1, 1, 0, 0])
        self.assertEqual([c["throttle"] for c in ego.controls], [0, 0, 0.3, 0.3])
        self.assertEqual([c["throttle"] for c in other.controls], [0.2]*4)

    def test_invalid_phase_and_actor_identity_rejected(self):
        ego, other = Actor(), Actor()
        make = lambda **kwargs: kwargs
        with self.assertRaisesRegex(ValueError, "hold phase"):
            drive.apply_tick(ego, other, make, 0, hold_ticks=0)
        with self.assertRaisesRegex(ValueError, "distinct actors"):
            drive.apply_tick(ego, ego, make, 0, hold_ticks=2)
        with self.assertRaisesRegex(ValueError, "throttle"):
            drive.apply_tick(ego, other, make, 0, hold_ticks=2, other_throttle=1.5)


if __name__ == "__main__":
    unittest.main()
