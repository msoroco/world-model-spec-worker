import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Body:
    def get_world_vertices(self, transform):
        return [SimpleNamespace(x=x, y=y) for x, y in [(8, -1), (12, -1),
                                                         (8, 1), (12, 1)]]


class Actor:
    id = 12
    bounding_box = Body()
    def get_transform(self): return None
    def get_location(self): return SimpleNamespace(x=10, y=0, z=0)
    def get_velocity(self): return SimpleNamespace(x=3, y=4, z=0)


class Scene:
    carla = SimpleNamespace(Location=lambda **kwargs: SimpleNamespace(**kwargs))
    def __init__(self, hits):
        self.world = SimpleNamespace(cast_ray=lambda start, end: hits)


class NativeCaptureMathTest(unittest.TestCase):
    def test_original_body_projection(self):
        measured = module._state(Actor(), [1, 0], [0, 0])
        self.assertEqual(measured["rear_station_m"], 8)
        self.assertEqual(measured["front_station_m"], 12)
        self.assertEqual(measured["centerline_signed_body_edge_m"], 1)
        self.assertEqual(measured["speed_mps"], 5)

    def test_real_opaque_hit_and_censored_limit(self):
        actor = Actor()
        hit = SimpleNamespace(location=SimpleNamespace(x=30, y=0, z=1.4),
                              label="Buildings", actor_id=99)
        blocked = module._ray(Scene([hit]), actor, [1, 0])
        clear = module._ray(Scene([]), actor, [1, 0])
        self.assertEqual(blocked["hit_kind"], "opaque_obstacle")
        self.assertFalse(blocked["censored"])
        self.assertTrue(clear["censored"])
        self.assertEqual(clear["clear_distance_m"], 230)


if __name__ == "__main__": unittest.main()
