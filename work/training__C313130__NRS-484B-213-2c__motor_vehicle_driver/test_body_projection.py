"""Test original vehicle body projection without importing CARLA."""

import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_capture import body as tunnel_body
from one_way_capture import body as one_way_body


class FakeBox:
    def __init__(self, vertices):
        self.vertices = vertices

    def get_world_vertices(self, transform):
        return self.vertices


def actor(pitched):
    vertices = []
    for x in (-2.0, 2.0):
        for y in (-1.0, 1.0):
            for z in (-0.5, 0.5):
                vertices.append(SimpleNamespace(x=x + pitched * z,
                                                y=y + pitched * z / 2))
    return SimpleNamespace(get_transform=lambda: None,
                           bounding_box=FakeBox(vertices))


class BodyProjectionTest(unittest.TestCase):
    def test_pitched_body_encloses_all_eight_vertices(self):
        original = actor(0.6)
        for project in (tunnel_body, one_way_body):
            corners = project(original)
            self.assertEqual(len(corners), 4)
            xs = [point[0] for point in corners]
            ys = [point[1] for point in corners]
            for vertex in original.bounding_box.vertices:
                self.assertLessEqual(min(xs), vertex.x)
                self.assertGreaterEqual(max(xs), vertex.x)
                self.assertLessEqual(min(ys), vertex.y)
                self.assertGreaterEqual(max(ys), vertex.y)

    def test_flat_body_is_four_corner_envelope(self):
        for project in (tunnel_body, one_way_body):
            self.assertEqual(project(actor(0)),
                             [[-2.0, -1.0], [-2.0, 1.0],
                              [2.0, -1.0], [2.0, 1.0]])

    def test_missing_or_nonfinite_vertex_rejected(self):
        for project in (tunnel_body, one_way_body):
            short = actor(0)
            short.bounding_box.vertices.pop()
            with self.assertRaisesRegex(ValueError, "eight-vertex"):
                project(short)
            invalid = actor(0)
            invalid.bounding_box.vertices[0].x = math.nan
            with self.assertRaisesRegex(ValueError, "eight-vertex"):
                project(invalid)


if __name__ == "__main__":
    unittest.main()
