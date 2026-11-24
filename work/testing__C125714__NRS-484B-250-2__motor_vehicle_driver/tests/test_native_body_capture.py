"""CPU fake Native actor tests; these do not verify a physical intersection."""
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125714_capture", ROOT / "native_body_capture.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeBox:
    def get_world_vertices(self, transform):
        x, y = transform
        return [SimpleNamespace(x=x+dx, y=y+dy, z=z) for z in (0, 2)
                for dx, dy in ((-1,-.5), (1,-.5), (1,.5), (-1,.5))]


class FakeActor:
    def __init__(self, actor_id, x, y):
        self.id, self.x, self.y, self.is_alive = actor_id, x, y, True
        self.bounding_box = FakeBox()

    def get_transform(self):
        return self.x, self.y


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = SimpleNamespace(frame=100, timestamp=SimpleNamespace(elapsed_seconds=5.0))
        self.actors = {"ego": FakeActor(11, -4, 0), "other": FakeActor(22, 0, -4)}

    def test_two_original_footprints_same_snapshot(self):
        sample = module.capture_pair(self.snapshot, self.actors)
        self.assertEqual(sample["ego"]["frame"], sample["other"]["frame"])
        self.assertEqual(sample["ego"]["time_s"], 5.0)
        self.assertEqual(sample["ego"]["body_vertices_xy_m"],
                         [[-5.0,-.5],[-3.0,-.5],[-3.0,.5],[-5.0,.5]])
        streams = {"ego": io.StringIO(), "other": io.StringIO()}
        module.append_pair(streams, sample)
        self.assertIn('"actor_id": 11', streams["ego"].getvalue())

    def test_identity_death_and_join_rejected(self):
        self.actors["other"].id = 11
        with self.assertRaisesRegex(ValueError, "distinct"):
            module.capture_pair(self.snapshot, self.actors)
        self.actors["other"].id = 22
        self.actors["other"].is_alive = False
        with self.assertRaisesRegex(ValueError, "not alive"):
            module.capture_pair(self.snapshot, self.actors)
        sample = {"ego": {"frame": 1, "time_s": 0},
                  "other": {"frame": 2, "time_s": 0}}
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            module.append_pair({"ego": io.StringIO(), "other": io.StringIO()}, sample)


if __name__ == "__main__":
    unittest.main()
