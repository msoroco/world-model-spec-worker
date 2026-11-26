"""Diagnostic-only fake adapter checks original capture calls and cleanup."""

from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from native_capture import capture
from native_capture_contract import CAMERAS, DIMENSIONS
from test_signal_construction import site


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
            stream = BytesIO()
            Image.new("RGB", DIMENSIONS[name], color=(2, 3, 4)).save(stream, "PNG")
            self.images[name] = stream.getvalue()

    def read_map_name(self):
        return "reviewed-map"

    def spawn_ego(self, blueprint_id, start):
        self.commands.append(("spawn", blueprint_id, start))
        return {"actor_id": 7}

    def read_ego_state(self):
        return {"actor_id": 7, "blueprint_id": "reviewed-vehicle",
                "x_m": -120 + (self.frame - 100) * 0.2, "y_m": 0,
                "heading_deg": 0 if self.frame < 102 else -20,
                "speed_m_s": 4.0}

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


class CaptureTest(unittest.TestCase):
    def test_four_camera_source_shape_and_commands(self):
        case = {"case_id": "a__business_sufficient",
                "target": {"weather_request": "clear",
                           "signal_continuity_request": "continuous"}}
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            root = Path(temporary)
            session = Session()
            result = capture(session, site(), "f" * 64, case, root, frames=3)
            packet = json.loads((root / result["trace_path"]).read_text())
            self.assertEqual(result["frame_count"], 3)
            self.assertFalse(result["original_capture_claimed"])
            self.assertEqual(packet["source_kind"], "diagnostic_fixture")
            self.assertEqual(set(packet["camera_archives"]), set(CAMERAS))
            self.assertEqual(len(packet["samples"]), 3)
            self.assertEqual(session.commands[0][0], "spawn")
            self.assertEqual(len([c for c in session.commands if c[0] == "drive"]), 3)

    def test_bad_camera_discards_incomplete_capture(self):
        case = {"case_id": "a__business_rain",
                "target": {"weather_request": "rain",
                           "signal_continuity_request": "continuous"}}
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            root = Path(temporary)
            session = Session()
            session.bad_camera = True
            with self.assertRaisesRegex(ValueError, "camera frame mismatch"):
                capture(session, site(), "f" * 64, case, root, frames=3)
            self.assertFalse(list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
