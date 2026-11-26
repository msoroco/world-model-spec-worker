"""Exercise Native construction, settings, frame and camera joins without CARLA."""

import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
import sys
sys.path.insert(0, str(ROOT))
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
SITE = sys.modules["crosswalk_site"] if "crosswalk_site" in sys.modules else None
if SITE is None:
    import crosswalk_site as SITE


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 99

    def get_settings(self):
        return self.settings

    def apply_settings(self, value):
        self.settings = value

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        timestamp = type("Timestamp", (), {"elapsed_seconds": (self.frame - 100) / 20})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": timestamp})()


class Vertex:
    def __init__(self, x, y):
        self.x, self.y, self.z = x, y, 0.0


class Box:
    def get_world_vertices(self, transform):
        return [Vertex(x, y) for x, y in
                ((8, -1), (10, -1), (10, 1), (8, 1),
                 (8, -1), (10, -1), (10, 1), (8, 1))]


class Vehicle:
    id = 17
    type_id = "vehicle.test"
    is_alive = True
    bounding_box = Box()

    def get_transform(self):
        return type("Transform", (), {
            "location": Vertex(9, 0),
            "rotation": type("Rotation", (), {"yaw": 0.0})()})()

    def get_velocity(self):
        return type("Velocity", (), {"x": 0.0, "y": 0.0, "z": 0.0,
                                     "length": lambda self: 0.0})()

    def destroy(self):
        self.is_alive = False


class Operator:
    diagnostic_test_only = True

    def __init__(self, png):
        self.png = png
        self.vehicle = Vehicle()
        self.calls = []

    def map_bytes(self, world):
        return b"reviewed map"

    def site_readback(self, world, site):
        return site

    def spawn_vehicle(self, point):
        self.calls.append("spawn")
        return self.vehicle

    def set_crosswalk(self, polygon, marked):
        self.calls.append(("crosswalk", marked))

    def set_vehicle_route(self, vehicle, route, clearance):
        self.calls.append(("route", clearance))

    def set_activity(self, vehicle, activity):
        self.calls.append(("activity", activity))

    def set_exception_context(self, exception, site):
        self.calls.append(("exception", exception))

    def control(self, vehicle, site, case):
        self.calls.append("control")

    def observe(self, world, vehicle, frame, site):
        return {"source_frame_id": frame, "actor_id": vehicle.id,
                "ego_alive": True, "road_id": 1, "lane_id": -1,
                "crosswalk_marked": site["crosswalk_marked"],
                "crossing_polygon_xy_m": site["crossing_polygon_xy_m"],
                "activity": site["requested_activity"],
                "exception_context": site["requested_exception"]}

    def cameras(self, world, vehicle, views, camera_offset_m=0.0):
        self.calls.append(("camera_offset", camera_offset_m))
        return {name: lambda frame: self.png for name in views}, []

    def start_pipeline_capture(self, output, case):
        self.calls.append("start")

    def capture_pipeline_tick(self, frame, time):
        self.calls.append("tick")

    def close_pipeline_capture(self, confirmed):
        self.calls.append(("close", confirmed))

    def destroy(self, vehicle):
        vehicle.destroy()


class CaptureTests(unittest.TestCase):
    def test_full_body_hull(self):
        points = [[0, 0], [2, 0], [2, 2], [0, 2],
                  [0, 0], [2, 0], [2, 2], [0, 2]]
        self.assertEqual(len(CAPTURE.convex_hull(points)), 4)

    def test_diagnostic_capture_controls_and_restoration(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            image = BytesIO()
            Image.new("RGB", (2, 2), "white").save(image, format="PNG")
            operator = Operator(image.getvalue())
            world = World()
            site = {"map_sha256": CAPTURE.digest(b"reviewed map"),
                    "crosswalk_marked": True,
                    "crossing_polygon_xy_m": [[0, -2], [2, -2], [2, 2], [0, 2]],
                    "road_id": 1, "lane_id": -1, "jurisdiction_id": "reviewed",
                    "vehicle_route_xy_m": [[-10, 0], [15, 0]],
                    "requested_activity": "destination_stop", "requested_exception": "none",
                    "requested_body_clearance_m": 5.9}
            case = SITE.ASSIGNMENT_ID + "__destination_inside_20ft"
            with patch.dict(CAPTURE.VIEWS, {name: (2, 2) for name in CAPTURE.VIEWS}):
                receipt = CAPTURE.capture(world, operator, site, case,
                                          Path(temporary) / "attempt",
                                          requested_clearance_m=5.9, diagnostic_frames=2)
            self.assertEqual(receipt["source_kind"], "diagnostic_fixture")
            self.assertEqual(world.get_settings().synchronous_mode, False)
            self.assertIn(("crosswalk", True), operator.calls)
            self.assertIn(("route", 5.9), operator.calls)
            packet = json.loads((Path(temporary) / "attempt" /
                                 "original-crosswalk-history.json").read_text())
            self.assertEqual(packet["frame_count"], 2)
            self.assertEqual(len(packet["samples"][0]["ego_body_polygon_xy_m"]), 4)
            self.assertTrue(packet["diagnostic_fixture"])


if __name__ == "__main__":
    unittest.main()
