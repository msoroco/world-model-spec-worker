"""Original Native body rotation must survive the saved footprint projection."""
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import _footprint


def actor(points):
    vertices = [SimpleNamespace(x=x, y=y, z=z)
                for z in (0, 2) for x, y in points]
    box = SimpleNamespace(get_world_vertices=lambda transform: vertices)
    return SimpleNamespace(bounding_box=box, get_transform=lambda: object())


class NativeFootprintTests(unittest.TestCase):
    def test_rotated_body_keeps_original_four_corners(self):
        diamond = [(-3, 0), (0, -1.2), (3, 0), (0, 1.2)]
        footprint = _footprint(actor(diamond))
        self.assertEqual({tuple(point) for point in footprint}, set(diamond))
        self.assertNotIn((-3.0, -1.2), {tuple(point) for point in footprint})

    def test_nonfinite_and_degenerate_original_body_rejected(self):
        for points in ([(-3, 0), (0, -1), (3, 0), (math.nan, 1)],
                       [(-3, 0), (-1, 0), (1, 0), (3, 0)]):
            with self.subTest(points=points):
                with self.assertRaisesRegex(ValueError, 'original Native bus body'):
                    _footprint(actor(points))


if __name__ == '__main__':
    unittest.main()
