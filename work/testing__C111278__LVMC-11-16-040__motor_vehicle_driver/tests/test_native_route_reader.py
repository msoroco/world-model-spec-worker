import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_route_reader import ReviewedRouteReader, RouteReadError


class Ego:
    def __init__(self, y):
        self.y = y
        self.bounding_box = self

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=0.0, y=self.y))

    def get_world_vertices(self, transform):
        return [SimpleNamespace(x=x, y=self.y + dy)
                for x in (-0.5, 0.5) for dy in (-1.0, -0.3, 0.3, 1.0)]


class NativeRouteReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reviewed-route.json"
        self.source = {"source_kind": "ego_route_geometry", "reviewer": "fixture reviewer",
                       "source_citation": "synthetic route only",
                       "route_xy": [[0, -40], [0, 0], [0, 15]],
                       "intersection_boundary_xy": [0, 0], "traversal_exit_xy": [0, 10]}
        self.site = {"ego_route_xy": self.source["route_xy"],
                     "intersection_boundary_xy": [0, 0]}
        self.write_source()

    def write_source(self):
        raw = json.dumps(self.source, sort_keys=True).encode()
        self.path.write_bytes(raw)
        self.site["ego_route_xy_source_sha256"] = hashlib.sha256(raw).hexdigest()

    @staticmethod
    def snapshot(frame):
        return SimpleNamespace(frame=frame)

    def test_original_body_projection_and_traversal(self):
        reader = ReviewedRouteReader(self.site, self.path)
        distance, traversing = reader(11, self.snapshot(11), Ego(-30))
        self.assertAlmostEqual(distance, 30)
        self.assertFalse(traversing)
        distance, traversing = reader(12, self.snapshot(12), Ego(-0.5))
        self.assertAlmostEqual(distance, 0.5)
        self.assertTrue(traversing)
        distance, traversing = reader(13, self.snapshot(13), Ego(5))
        self.assertAlmostEqual(distance, -5)
        self.assertTrue(traversing)
        _, traversing = reader(14, self.snapshot(14), Ego(12))
        self.assertFalse(traversing)

    def test_tampered_route_and_unreviewed_exit_rejected(self):
        self.path.write_text("{}")
        with self.assertRaisesRegex(RouteReadError, "hash differs"):
            ReviewedRouteReader(self.site, self.path)
        self.source["traversal_exit_xy"] = [0, -10]
        self.write_source()
        with self.assertRaisesRegex(RouteReadError, "cannot cover"):
            ReviewedRouteReader(self.site, self.path)

    def test_frame_and_corridor_rejected(self):
        reader = ReviewedRouteReader(self.site, self.path)
        with self.assertRaisesRegex(RouteReadError, "frame differs"):
            reader(1, self.snapshot(2), Ego(-30))
        with self.assertRaisesRegex(RouteReadError, "corridor"):
            reader(1, self.snapshot(1), Ego(20))
        reader(1, self.snapshot(1), Ego(-30))
        with self.assertRaisesRegex(RouteReadError, "frame gap"):
            reader(3, self.snapshot(3), Ego(-29))


if __name__ == "__main__":
    unittest.main()
