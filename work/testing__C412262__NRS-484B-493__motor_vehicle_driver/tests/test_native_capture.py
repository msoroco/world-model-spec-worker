"""Synthetic Native doubles exercise frame protocol and restoration only."""

import io
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture as nc
import native_output_bridge as bridge
from street_scene_construction import load_case

CASE = load_case(nc.ASSIGNMENT + "__park_left_notice")
MAP_BYTES = b"<OpenDRIVE synthetic-unit-fixture='true'/>"
MAP_SHA = hashlib.sha256(MAP_BYTES).hexdigest()


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 40

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        stamp = type("Stamp", (), {"elapsed_seconds": (self.frame - 41) / 20})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": stamp})()


class Adapter:
    def __init__(self, missing=False):
        self.missing = missing

    def read_original_context(self, site, case):
        out = {"case_id": case["case_id"], "one_way_status": "one_way",
               "notice_state": "erected_applicable",
               "map_sha256": MAP_SHA,
               "permitted_direction_centerline_xy_m": [[0, 0], [20, 0]]}
        out.update({key: case[key] for key in ("street_direction_request",
                                              "vehicle_side_request", "activity_request",
                                              "notice_request")})
        out.update({key: "synthetic-unit-fixture:" + key for key in nc.CONTEXT_SOURCES})
        return out

    def control_frame(self, case, index):
        pass

    def read_original_frame(self, case, index, frame):
        return {"native_frame": frame, "frame": index, "time_s": index / 20,
                "vehicle_speed_mps": 0, "vehicle_center_xy_m": [10, 3],
                "actor_id": 7, "vehicle_blueprint": "vehicle.synthetic-unit-fixture",
                "position_m": [10, 3, 0], "heading_xy": [1, 0],
                "body_vertices_m": [[9, 2, 0], [11, 2, 0], [11, 4, 0], [9, 4, 0]],
                "vehicle_body_polygon_xy_m": [[9, 2], [11, 2], [11, 4], [9, 4]]}

    def camera_rgb24(self, view, frame):
        return b"" if self.missing and view == "overview" else b"\x00\x00\x00"


class Encoder:
    def __init__(self, path):
        self.path = path
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()
        self.done = False

    def poll(self):
        return 0 if self.done else None

    def wait(self, timeout):
        self.path.write_bytes(b"synthetic-video-fixture")
        self.done = True
        return 0

    def terminate(self):
        self.done = True


class CaptureTests(unittest.TestCase):
    def test_original_frame_seal_and_restoration(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            world = World()
            root = Path(directory) / "attempt"
            def encoder(output, view):
                return Encoder(output / (view + ".mkv"))
            with patch.object(nc, "FRAMES", 2), patch.dict(nc.SIZES, {v: (1, 1) for v in nc.VIEWS}), patch.object(nc, "_encoder", encoder):
                result = nc.capture(world, Adapter(), {"_source_sha256": "a" * 64,
                                                     "map_sha256": MAP_SHA,
                                                     "lane_route_xy_m": [[0, 0], [20, 0]]},
                                    CASE["case_id"], root, "a" * 64)
            self.assertEqual(len((root / "original-trace.jsonl").read_text().splitlines()), 2)
            self.assertEqual(json.loads(Path(result["receipt"]).read_text())["frame_count"], 2)
            self.assertFalse(world.get_settings().synchronous_mode)

    def test_missing_original_camera_frame_restores_settings(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            world = World()
            root = Path(directory) / "attempt"
            with patch.object(nc, "FRAMES", 2), patch.dict(nc.SIZES, {v: (1, 1) for v in nc.VIEWS}), patch.object(nc, "_encoder", lambda output, view: Encoder(output / (view + ".mkv"))):
                with self.assertRaisesRegex(ValueError, "original synchronized RGB frame missing"):
                    nc.capture(world, Adapter(missing=True), {"_source_sha256": "a" * 64,
                                                              "map_sha256": MAP_SHA,
                                                              "lane_route_xy_m": [[0, 0], [20, 0]]},
                               CASE["case_id"], root, "a" * 64)
            self.assertFalse(world.get_settings().synchronous_mode)

    def test_bridge_rejects_changed_original_trace(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory) / "attempt"
            with patch.object(nc, "FRAMES", 2), patch.dict(nc.SIZES, {v: (1, 1) for v in nc.VIEWS}), patch.object(nc, "_encoder", lambda output, view: Encoder(output / (view + ".mkv"))):
                nc.capture(World(), Adapter(), {"_source_sha256": "a" * 64,
                                               "map_sha256": MAP_SHA,
                                               "lane_route_xy_m": [[0, 0], [20, 0]]},
                           CASE["case_id"], root, "a" * 64)
            with (root / "original-trace.jsonl").open("a") as stream:
                stream.write("{}\n")
            with patch.object(bridge, "FRAMES", 2):
                with self.assertRaisesRegex(ValueError, "sealed Native packet changed"):
                    bridge.publish(root, map_bytes=MAP_BYTES, restored=True)


if __name__ == "__main__":
    unittest.main()
