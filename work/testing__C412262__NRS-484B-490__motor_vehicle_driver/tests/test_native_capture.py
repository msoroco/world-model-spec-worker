"""CPU exercise of source copy, synchronized frames, cameras and settings restore."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

import native_capture
from highway_scene_construction import ASSIGNMENT, validate_site
from test_highway_construction import site_packet

CASE = ASSIGNMENT + "__park_narrow_device"


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 100

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        timestamp = type("Timestamp", (), {"elapsed_seconds": (self.frame - 101) / 20})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": timestamp})()


class Adapter:
    def read_original_context(self, site, case):
        context = {key: site[key] for key in native_capture.SOURCE_FIELDS}
        context.update({"assignment_id": ASSIGNMENT, "case_id": CASE,
                        "source_kind": "original_reviewed_highway_site",
                        "highway_boundary_xy_m": site["highway_boundary_xy_m"],
                        "full_highway_width_profile_m": site["full_highway_width_profile_m"]})
        context.update({key: case[key] for key in
                       ("highway_width_request", "device_request", "activity_request", "parking_location_request")})
        context.update({key: "reviewed-source" for key in native_capture.CONTEXT_SOURCES})
        return context

    def control_frame(self, case, index):
        self.index = index

    def read_original_frame(self, case, index, frame):
        return {"native_frame": frame, "frame": index, "time_s": index / 20,
                "vehicle_center_xy_m": [10, 0],
                "vehicle_body_polygon_xy_m": [[9, -1], [11, -1], [11, 1], [9, 1]],
                "vehicle_speed_mps": 0.0, "actor_id": 11,
                "vehicle_blueprint": "vehicle.test.car", "position_m": [10, 0, 0],
                "heading_xy": [1, 0],
                "body_vertices_m": [[9, -1, 0], [11, -1, 0], [11, 1, 0], [9, 1, 0]]}

    def camera_rgb24(self, view, frame):
        width, height = native_capture.SIZES[view]
        return bytes(width * height * 3)


class Encoder:
    def __init__(self, output, view):
        (output / (view + ".mkv")).write_bytes(b"diagnostic encoder bytes")
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class CaptureTests(unittest.TestCase):
    def test_original_source_and_frame_protocol(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            root = Path(name)
            site_path = site_packet(root)
            site = validate_site(site_path, CASE)
            world = World()
            output = root / "capture-output"
            with patch.object(native_capture, "FRAMES", 9), patch.object(native_capture, "SIZES",
                     {view: (2, 2) for view in native_capture.VIEWS}), patch.object(native_capture,
                     "_encoder", side_effect=lambda destination, view: Encoder(destination, view)):
                result = native_capture.capture(world, Adapter(), site, CASE, output, site["_source_sha256"])
            self.assertEqual(result["receipt"], str(output / "receipt.json"))
            self.assertEqual(json.loads((output / "receipt.json").read_text())["frame_count"], 9)
            self.assertEqual(len((output / "original-trace.jsonl").read_text().splitlines()), 9)
            self.assertEqual((output / "reviewed-source/reviewed-site.json").read_bytes(), site_path.read_bytes())
            self.assertFalse(world.settings.synchronous_mode)
            self.assertIsNone(world.settings.fixed_delta_seconds)


if __name__ == "__main__":
    unittest.main()
