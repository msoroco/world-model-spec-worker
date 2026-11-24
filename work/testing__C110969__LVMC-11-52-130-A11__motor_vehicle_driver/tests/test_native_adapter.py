"""Source packet and original camera callback checks without CARLA."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import types
import unittest

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from native_adapter import Session, VIEWS, _CameraFrames, validate_packet


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.packet = pathlib.Path(self.temp.name) / "reviewed.json"
        self.value = {
            "vehicle_blueprint_id": "vehicle.diagnostic", "reviewer": "diagnostic test only",
            "vehicle_spawn_world": {"location_xyz_m": [20, 0, 1],
                                    "rotation_rpy_deg": [0, 0, 180]},
            "local_transform": {"origin_xyz_m": [10, 5, 0], "yaw_deg": 90},
            "cameras": [{"name": name, "width": width, "height": height,
                         "attachment": "ego" if name == "driver_reference" else "world",
                         "pose_source_citation": "diagnostic test only",
                         "reviewer": "diagnostic test only",
                         "location_xyz_m": [1, 2, 3],
                         "rotation_rpy_deg": [0, 0, 0], "fov_deg": 90}
                        for name, width, height in VIEWS]}
        self.packet.write_text(json.dumps(self.value))

    def test_four_view_source_packet_and_transform(self):
        self.assertEqual(len(validate_packet(self.packet)["cameras"]), 4)
        session = Session.__new__(Session)
        session.packet = self.value
        pose = types.SimpleNamespace(location=types.SimpleNamespace(x=10, y=6),
                                     rotation=types.SimpleNamespace(yaw=180))
        x, y, heading = session.world_to_local(pose)
        self.assertAlmostEqual(x, 1)
        self.assertAlmostEqual(y, 0)
        self.assertAlmostEqual(heading, 90)

    def test_unreviewed_or_wrong_resolution_rejected(self):
        del self.value["reviewer"]
        self.packet.write_text(json.dumps(self.value))
        with self.assertRaisesRegex(ValueError, "actor selection"):
            validate_packet(self.packet)
        self.value["reviewer"] = "diagnostic test only"
        self.value["cameras"][0]["width"] = 2
        self.packet.write_text(json.dumps(self.value))
        with self.assertRaisesRegex(ValueError, "camera identity"):
            validate_packet(self.packet)

    def test_original_pixel_callback_decodes_exact_frame(self):
        frames = _CameraFrames()
        image = types.SimpleNamespace(frame=17, width=2, height=2,
                                      raw_data=bytes([0, 0, 255, 255] * 4))
        frames.receive("overview", 2, 2, image)
        frame, png = frames.read("overview", 17)
        self.assertEqual(frame, 17)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaisesRegex(ValueError, "missing"):
            frames.read("overview", 17, timeout_s=0)


if __name__ == "__main__":
    unittest.main()
