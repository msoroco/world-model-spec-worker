import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_roundabout_readback import CameraFrames, body_vertices


class CarlaBridgeTests(unittest.TestCase):
    def test_exact_bgra_frame_and_body_bridge(self):
        bridge = CameraFrames({name: (2, 1) for name in
            ("overview", "approach", "entry_conflict", "driver_reference")})
        image = type("Image", (), {"frame": 42, "width": 2, "height": 1,
                  "raw_data": b"\x00\x00\xff\xff" * 2})()
        for name in bridge.readers():
            bridge.callback(name)(image)
            sample = bridge.reader(name)(42)
            self.assertEqual(sample["frame"], 42)
            self.assertTrue(sample["png_bytes"].startswith(b"\x89PNG"))
        points = [type("Point", (), {"x": i, "y": 0, "z": 1})()
                  for i in range(8)]
        box = type("Box", (), {"get_world_vertices": lambda self, transform: points})()
        actor = type("Actor", (), {"bounding_box": box,
                 "get_transform": lambda self: object()})()
        self.assertEqual(len(body_vertices(actor)), 8)

    def test_rejects_missing_and_wrong_camera_bytes(self):
        bridge = CameraFrames({name: (2, 1) for name in
            ("overview", "approach", "entry_conflict", "driver_reference")})
        with self.assertRaisesRegex(ValueError, "unavailable"):
            bridge.reader("overview")(7)
        bad = type("Image", (), {"frame": 7, "width": 2, "height": 1,
                   "raw_data": b"bad"})()
        with self.assertRaisesRegex(ValueError, "byte count"):
            bridge.callback("overview")(bad)


if __name__ == "__main__":
    unittest.main()
