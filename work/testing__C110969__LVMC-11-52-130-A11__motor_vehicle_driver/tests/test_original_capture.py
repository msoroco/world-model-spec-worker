import json
import pathlib
import sys
import tempfile
import types
import unittest


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from intersection_geometry import Box
from original_capture import capture_pose


class FakeWorld:
    def __init__(self, gap_at=None):
        self.frame = 200
        self.gap_at = gap_at

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.frame += 2 if self.frame == self.gap_at else 1
        return self.frame


class FakeControl:
    def __init__(self, throttle=0.0, brake=0.0):
        self.throttle = throttle
        self.brake = brake


class FakeEgo:
    id = 17

    def __init__(self):
        self.calls = []

    def get_transform(self):
        return types.SimpleNamespace(x=14.5172, y=0.0, heading=180.0)

    def get_velocity(self):
        return types.SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def get_control(self):
        return FakeControl()

    def apply_control(self, control):
        self.calls.append(control)


class NativeSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = pathlib.Path(self.temp.name) / "original.jsonl"
        self.ego = FakeEgo()
        self.args = dict(boundary=Box(-8, -8, 8, 8), approach="east",
                         target_gap_m=14 * 0.3048, vehicle_length_m=4.5,
                         world_to_local=lambda t: (t.x, t.y, t.heading))

    def test_writes_original_pose_and_brakes(self):
        receipt = capture_pose(FakeWorld(), self.ego, self.output, **self.args)
        rows = [json.loads(line) for line in self.output.read_text().splitlines()]
        self.assertEqual(len(rows), 900)
        self.assertEqual(rows[-1]["world_frame"], 1100)
        self.assertEqual(rows[0]["actor_id"], "17")
        self.assertFalse(receipt["physical_acceptance_claimed"])
        self.assertEqual(self.ego.calls[-1].brake, 1)

    def test_world_gap_rejected_with_cleanup_brake(self):
        with self.assertRaisesRegex(ValueError, "frame gap"):
            capture_pose(FakeWorld(gap_at=201), self.ego, self.output, **self.args)
        self.assertEqual(self.ego.calls[-1].brake, 1)

    def test_existing_source_never_overwritten(self):
        self.output.write_text("protected\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            capture_pose(FakeWorld(), self.ego, self.output, **self.args)
        self.assertEqual(self.output.read_text(), "protected\n")


if __name__ == "__main__":
    unittest.main()
