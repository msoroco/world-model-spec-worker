import importlib.util
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[1] / "native_capture.py"
sys.path.insert(0, str(MODULE.parent))
SPEC = importlib.util.spec_from_file_location("native_capture", MODULE)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class NativeCaptureTest(unittest.TestCase):
    def test_original_world_bounding_box_corners(self):
        points = [SimpleNamespace(x=x, y=y, z=z)
                  for x in (-2.0, 2.0) for y in (-1.0, 1.0) for z in (0.0, 1.5)]
        ego = SimpleNamespace(bounding_box=SimpleNamespace(
            get_world_vertices=lambda transform: points),
            get_transform=lambda: object())
        self.assertEqual(CAPTURE._footprint(ego),
                         [[-2.0, -1.0], [-2.0, 1.0], [2.0, -1.0], [2.0, 1.0]])

    def test_reject_degenerate_or_nonfinite_world_body(self):
        for x in (0.0, math.nan):
            points = [SimpleNamespace(x=x, y=float(i % 2), z=float(i // 4))
                      for i in range(8)]
            ego = SimpleNamespace(bounding_box=SimpleNamespace(
                get_world_vertices=lambda transform: points),
                get_transform=lambda: object())
            with self.assertRaisesRegex(ValueError, "footprint"):
                CAPTURE._footprint(ego)

    def test_camera_contract_requires_four_views_and_900_frames(self):
        self.assertEqual(CAPTURE.FRAMES, 900)
        self.assertEqual(tuple(name for name, _, _ in CAPTURE.VIEWS),
                         ("overview", "approach", "reference_corner", "driver_reference"))
        self.assertEqual(tuple((width, height) for _, width, height in CAPTURE.VIEWS),
                         ((1920, 1080), (1280, 720), (1280, 720), (1280, 720)))


if __name__ == "__main__":
    unittest.main()
