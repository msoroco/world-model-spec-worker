import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from activity_controller import apply, command


class FakeControl:
    def __init__(self, **kwargs):
        self.values = kwargs


class FakeVehicle:
    def __init__(self):
        self.calls = []

    def apply_control(self, control):
        self.calls.append(control.values)


class ActivityControllerTest(unittest.TestCase):
    def test_all_three_requests_drive_distinct_calls(self):
        expected = {"stop": ("halt", "departure"),
                    "stand": ("standing_request", "standing_request"),
                    "park": ("parking_request", "parking_request")}
        for name, phases in expected.items():
            with self.subTest(name=name):
                vehicle = FakeVehicle()
                self.assertEqual(apply(vehicle, FakeControl, name, 80)["phase"], phases[0])
                self.assertEqual(apply(vehicle, FakeControl, name, 200)["phase"], phases[1])
                self.assertEqual(len(vehicle.calls), 2)
                self.assertEqual(vehicle.calls[0]["hand_brake"], name == "park")
        self.assertEqual(command("stop", 59)["phase"], "approach")
        self.assertEqual(command("stand", 440)["phase"], "departure")

    def test_out_of_range_rejected(self):
        for name, frame in (("unknown", 1), ("stop", -1), ("park", 600)):
            with self.subTest(name=name, frame=frame), self.assertRaises(ValueError):
                command(name, frame)


if __name__ == "__main__":
    unittest.main()
