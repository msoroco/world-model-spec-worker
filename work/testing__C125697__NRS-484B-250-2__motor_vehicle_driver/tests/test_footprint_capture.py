import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE = Path(__file__).resolve().parents[1] / "footprint_capture.py"
spec = importlib.util.spec_from_file_location("footprint_capture", MODULE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class Box:
    def __init__(self, x):
        self.x = x

    def get_world_vertices(self, transform):
        x = self.x + transform.x
        return [SimpleNamespace(x=a, y=b) for a, b in ((x-1, 0), (x+1, 0), (x+1, 2), (x-1, 2), (x-1, 0))]


class Actor:
    def __init__(self, ident, x):
        self.id = ident
        self.bounding_box = Box(x)
        self.is_alive = True

    def get_transform(self):
        return SimpleNamespace(x=0)


class CaptureTests(unittest.TestCase):
    def test_geometry_and_live_readback(self):
        region = [(0, 0), (2, 0), (2, 2), (0, 2)]
        ego, other = Actor(3, -2), Actor(4, 4)
        snapshot = SimpleNamespace(frame=42, timestamp=SimpleNamespace(elapsed_seconds=2.1))
        first = capture.capture_frame(snapshot, {"ego": ego, "other": other}, region)
        self.assertFalse(first["actors"]["ego"]["footprint_intersects_intersection"])
        self.assertFalse(first["actors"]["other"]["footprint_intersects_intersection"])
        ego.bounding_box.x = 0
        snapshot.frame = 43
        snapshot.timestamp.elapsed_seconds = 2.15
        second = capture.capture_frame(snapshot, {"ego": ego, "other": other}, region)
        self.assertTrue(second["actors"]["ego"]["footprint_intersects_intersection"])
        self.assertEqual(second["actors"]["ego"]["actor_id"], 3)

    def test_rejects_stale_or_invalid_native_geometry(self):
        region = [(0, 0), (2, 0), (2, 2), (0, 2)]
        ego, other = Actor(3, -2), Actor(4, 4)
        snapshot = SimpleNamespace(frame=42, timestamp=SimpleNamespace(elapsed_seconds=2.1))
        other.is_alive = False
        with self.assertRaisesRegex(ValueError, "no longer alive"):
            capture.capture_frame(snapshot, {"ego": ego, "other": other}, region)
        other.is_alive = True
        other.id = ego.id
        with self.assertRaisesRegex(ValueError, "distinct"):
            capture.capture_frame(snapshot, {"ego": ego, "other": other}, region)
        with self.assertRaisesRegex(ValueError, "degenerate"):
            capture.intersects_convex(region, [(0, 0), (1, 1), (2, 2)])


if __name__ == "__main__":
    unittest.main()
