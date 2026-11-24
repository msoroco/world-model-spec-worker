import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_backing import ASSIGNMENT, process


def point(x, y):
    return {"x_m": x, "y_m": y, "source_ref": "map:waypoint", "junction_id": 11}


def write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(root, case=ASSIGNMENT + "__pedestrian_yield"):
    packet = {"map_sha256": "a" * 64, "map_name": "OriginalTown", "junction_id": 11,
              "vehicle_blueprint_id": "vehicle.audi.a2", "pedestrian_blueprint_id": "walker.pedestrian.0001",
              "vehicle_reverse_route": [point(5, 0), point(0, 0)],
              "pedestrian_route": [point(2, -3), point(2, 3)],
              "vehicle_half_width_m": 1.0, "pedestrian_radius_m": .3,
              "control_source": "original:intersection-control"}
    frames = [{"frame": i, "time_s": round(i*.05, 3), "vehicle_actor_id": 7,
               "pedestrian_actor_id": 8, "vehicle_xy": [5-i*.001, 0],
               "pedestrian_xy": [2, -.5+i*.001], "vehicle_velocity_xy": [-.2, 0],
               "vehicle_forward_xy": [1, 0], "pedestrian_velocity_xy": [0, .2],
               "brake": 1.0, "reverse_gear": True, "pedestrian_in_corridor": True}
              for i in range(900)]
    maps = [{"frame": i, "cameras": {name: i for name in ("front", "rear", "left", "right")}}
            for i in range(900)]
    media = {name: write(root, name + ".txt", {"fixture": name}) for name in ("front", "rear", "left", "right")}
    receipt = {"assignment_id": ASSIGNMENT, "case_id": case, "source_kind": "native_original",
               "diagnostic": False, "source_id": "original:attempt-1", "vehicle_actor_id": 7,
               "pedestrian_actor_id": 8, "map_packet": write(root, "map.json", packet),
               "telemetry": write(root, "telemetry.json", frames),
               "frame_map": write(root, "frame-map.json", maps), "media": media}
    write(root, "acquisition.json", receipt)
    return receipt


class SavedBackingTests(unittest.TestCase):
    def test_sealed_original_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            output = process(root, ASSIGNMENT + "__pedestrian_yield")
            self.assertEqual(output["frame_count"], 900)
            self.assertEqual(len(output["measurement"]["frames"]), 900)
            self.assertFalse(output["physical_completion"])

    def test_rejects_tampered_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "telemetry.json").write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                process(root, ASSIGNMENT + "__pedestrian_yield")

    def test_rejects_camera_frame_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = fixture(root)
            maps = json.loads((root / "frame-map.json").read_text())
            maps[50]["cameras"]["rear"] = 49
            receipt["frame_map"] = write(root, "frame-map.json", maps)
            write(root, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "camera frame identity"):
                process(root, ASSIGNMENT + "__pedestrian_yield")

    def test_rejects_missing_media_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = fixture(root)
            receipt["media"].pop("rear")
            write(root, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "four sealed media"):
                process(root, ASSIGNMENT + "__pedestrian_yield")
            receipt["diagnostic"] = True
            write(root, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "original Native"):
                process(root, ASSIGNMENT + "__pedestrian_yield")

    def test_rejects_case_and_outside_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = fixture(root)
            with self.assertRaisesRegex(ValueError, "exact-case identity"):
                process(root, ASSIGNMENT + "__pedestrian_continue")
            receipt["map_packet"]["path"] = "../outside.json"
            write(root, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "inside attempt"):
                process(root, ASSIGNMENT + "__pedestrian_yield")

    def test_rejects_time_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = fixture(root)
            frames = json.loads((root / "telemetry.json").read_text())
            frames[50]["time_s"] = frames[49]["time_s"] + .1
            receipt["telemetry"] = write(root, "telemetry.json", frames)
            write(root, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "20 Hz"):
                process(root, ASSIGNMENT + "__pedestrian_yield")
