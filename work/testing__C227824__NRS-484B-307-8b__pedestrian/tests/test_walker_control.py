import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "walker_control.py"
SPEC = importlib.util.spec_from_file_location("c227824_walker_control", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeActor:
    def __init__(self, x=0, y=0):
        self.location = SimpleNamespace(x=x, y=y)
        self.applied = []

    def get_transform(self):
        return SimpleNamespace(location=self.location)

    def apply_control(self, value):
        self.applied.append(value)


class FakeCarla:
    @staticmethod
    def Vector3D(x, y, z):
        return SimpleNamespace(x=x, y=y, z=z)

    @staticmethod
    def WalkerControl(**kwargs):
        return SimpleNamespace(**kwargs)


class WalkerControlTests(unittest.TestCase):
    def test_entry_calls_walker_control_toward_target(self):
        actor = FakeActor(0, 0)
        receipt = MODULE.request(actor, FakeCarla, entry_request="entry", target_xy_m=[3, 4], speed_mps=1.2)
        self.assertEqual(len(actor.applied), 1)
        self.assertAlmostEqual(actor.applied[0].direction.x, 0.6)
        self.assertAlmostEqual(actor.applied[0].direction.y, 0.8)
        self.assertEqual(actor.applied[0].speed, 1.2)
        self.assertFalse(receipt["realized_motion_claimed"])

    def test_wait_issues_zero_speed(self):
        actor = FakeActor()
        MODULE.request(actor, FakeCarla, entry_request="wait", target_xy_m=[4, 0], speed_mps=1.2)
        self.assertEqual(actor.applied[0].speed, 0)
        self.assertEqual(actor.applied[0].direction.x, 0)

    def test_rejects_bad_requests_before_actor_call(self):
        actor = FakeActor()
        for kwargs in ({"entry_request": "unknown", "target_xy_m": [4, 0], "speed_mps": 1},
                       {"entry_request": "entry", "target_xy_m": [4, 0], "speed_mps": -1},
                       {"entry_request": "entry", "target_xy_m": [4], "speed_mps": 1}):
            with self.assertRaises(ValueError):
                MODULE.request(actor, FakeCarla, **kwargs)
        self.assertEqual(actor.applied, [])


if __name__ == "__main__":
    unittest.main()
