import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from officer_native_capture import VIEWS, capture
from test_officer_scene import Adapter
import test_officer_site_packet


class CaptureAdapter(Adapter):
    def __init__(self, missing=None):
        super().__init__()
        self.index = 0
        self.missing = missing
        self.closed = False

    def attach_cameras(self, actors, cameras):
        self.calls.append(("attach_cameras", len(actors)))
        return dict.fromkeys(VIEWS, object())

    def request_officer_case_control(self, actors, case, index):
        self.calls.append(("control", case.suffix, index))

    def tick_and_read(self, actors, cameras):
        index = self.index
        self.index += 1
        views = {name: b"\x89PNG\r\n\x1a\n" + bytes([index]) for name in VIEWS}
        if self.missing and index == 1:
            del views[self.missing]
        return {"frame": 100 + index, "time_s": 4 + index / 20,
                "state": {"ego": {"id": "ego"}, "other": {"id": "other"},
                          "officer": {"id": "officer"}, "officer_directive": "stop"},
                "trace": {"frame": 100 + index, "time_s": 4 + index / 20},
                "video_frame": {"video_frame": index, "carla_frame": 100 + index,
                                "time_s": 4 + index / 20},
                "camera_png": views}

    def finalize_media(self, output, views, mapping):
        out = {}
        for name in (*views, "raw"):
            path = output / (name + ".mkv")
            path.write_bytes(b"fixture media")
            out[name] = path
        return out

    def close(self):
        self.closed = True
        return True


class OriginalCaptureTest(unittest.TestCase):
    def make_config(self):
        return {"assignment_id": "testing__C157964__NRS-484B-257-2__motor_vehicle_driver",
                "selected_case_id": "testing__C157964__NRS-484B-257-2__motor_vehicle_driver__occupied_stop",
                "frame_count": 3, "cameras": [{"name": name} for name in VIEWS]}

    def test_source_bound_frame_camera_and_officer_capture(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            root = Path(temp)
            packet = test_officer_site_packet.OfficerSitePacketTest().packet(root)
            adapter = CaptureAdapter()
            out = capture(adapter, self.make_config(), packet, root / "attempt")
            self.assertEqual(out["frame_count"], 3)
            self.assertTrue(adapter.closed)
            self.assertEqual(len(json.loads((root / "attempt/original-attempt/frame-map.json").read_text())), 3)
            self.assertEqual(len(json.loads((root / "attempt/original-attempt/history.json").read_text())), 3)
            self.assertEqual(len(json.loads((root / "attempt/capture-seal.json").read_text())["source_sha256"]), 24)

    def test_missing_camera_fails_and_restores_owned_actors(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            root = Path(temp)
            packet = test_officer_site_packet.OfficerSitePacketTest().packet(root)
            adapter = CaptureAdapter(missing="approach")
            with self.assertRaisesRegex(ValueError, "camera join"):
                capture(adapter, self.make_config(), packet, root / "attempt")
            self.assertTrue(adapter.closed)
            self.assertEqual(adapter.calls[-3:], [("destroy", "officer"),
                                                  ("destroy", "other"),
                                                  ("destroy", "ego")])


if __name__ == "__main__":
    unittest.main()
