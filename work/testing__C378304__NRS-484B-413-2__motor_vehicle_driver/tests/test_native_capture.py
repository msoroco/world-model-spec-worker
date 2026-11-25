import hashlib
from io import BytesIO
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture, CAMERAS, DIMENSIONS
from test_native_site import SITE


class Session:
    diagnostic_test_only = True

    def __init__(self):
        self.frame = 100
        self.weather = "clear"
        self.requested = False
        self.bad_camera = False
        self.commands = []
        self.images = {}
        for name in CAMERAS:
            image = Image.new("RGB", DIMENSIONS[name], color=(2, 3, 4))
            stream = BytesIO()
            image.save(stream, format="PNG")
            self.images[name] = stream.getvalue()

    def read_map_name(self):
        return "ReviewedTown"

    def spawn_ego(self, blueprint_id, start):
        self.commands.append(("spawn", blueprint_id, start))
        return {"actor_id": 7}

    def read_ego_state(self):
        return {"actor_id": 7, "blueprint_id": "vehicle.reviewed.car",
                "x_m": -70 + (self.frame - 100) * 8, "y_m": 0,
                "heading_deg": 0 if self.frame < 102 else -20, "speed_m_s": 8}

    def set_weather(self, value):
        self.weather = value

    def read_weather(self):
        return self.weather

    def command_drive(self, target):
        self.commands.append(("drive", target))

    def request_right_signal(self, value):
        self.requested = value

    def read_right_signal(self):
        return self.requested

    def tick(self):
        self.frame += 1
        return {"frame": self.frame, "time_s": self.frame * .05}

    def read_camera(self, name, frame):
        return {"frame": frame + int(self.bad_camera and name == "approach"),
                "png_bytes": self.images[name]}


class NativeCaptureTests(unittest.TestCase):
    def test_four_camera_original_path_is_explicitly_diagnostic_in_fake(self):
        case = {"case_id": "a__short80", "target": {"weather_request": "clear",
                "signal_continuity_request": "continuous"}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = Session()
            result = capture(session, SITE, "f" * 64, case, root, frames=3)
            packet = json.loads((root / result["trace_path"]).read_text())
            self.assertEqual(result["frame_count"], 3)
            self.assertFalse(result["original_capture_claimed"])
            self.assertEqual(packet["source_kind"], "diagnostic_fixture")
            self.assertEqual(len(packet["samples"]), 3)
            self.assertEqual(set(packet["camera_archives"]), set(CAMERAS))
            self.assertTrue(packet["samples"][1]["course_change"])
            self.assertEqual(packet["site_sha256"], "f" * 64)
            self.assertEqual(hashlib.sha256((root / result["trace_path"]).read_bytes()).hexdigest(),
                             result["trace_sha256"])

    def test_bad_camera_aborts_all_archives(self):
        case = {"case_id": "a__rain", "target": {"weather_request": "rain",
                "signal_continuity_request": "continuous"}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = Session()
            session.bad_camera = True
            with self.assertRaisesRegex(ValueError, "camera frame mismatch"):
                capture(session, SITE, "f" * 64, case, root, frames=3)
            self.assertFalse(list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
