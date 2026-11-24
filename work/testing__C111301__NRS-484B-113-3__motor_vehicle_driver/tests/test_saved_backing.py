import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_backing import ASSIGNMENT, process
from saved_comparison import audit


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
    def _paired(self, root):
        left = root / "yield"
        right = root / "continue"
        left.mkdir()
        right.mkdir()
        fixture(left)
        receipt = fixture(right, ASSIGNMENT + "__pedestrian_continue")
        receipt["source_id"] = "original:attempt-2"
        frames = json.loads((right / "telemetry.json").read_text(encoding="utf-8"))
        for row in frames:
            row["brake"] = 0.0
            row["vehicle_velocity_xy"] = [-.5, 0]
        receipt["telemetry"] = write(right, "telemetry.json", frames)
        write(right, "acquisition.json", receipt)
        return left, right, receipt

    def test_saved_comparison_replays_both_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right, _ = self._paired(Path(directory))
            result = audit(left, right)
            self.assertEqual(result["frame_count"], 900)
            self.assertEqual(result["comparison_id"], "pedestrian_yield_response")
            self.assertFalse(result["physical_completion"])
            output = Path(directory) / "comparison.json"
            command = [sys.executable, str(ROOT / "saved_comparison.py"),
                       "--yield-attempt", str(left), "--continue-attempt", str(right),
                       "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["comparison_id"],
                             "pedestrian_yield_response")

    def test_saved_comparison_rejects_changed_context_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right, receipt = self._paired(Path(directory))
            packet = json.loads((right / "map.json").read_text(encoding="utf-8"))
            packet["pedestrian_route"][1]["y_m"] = 4
            receipt["map_packet"] = write(right, "map.json", packet)
            write(right, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "fixed original map"):
                audit(left, right)
            (right / "telemetry.json").write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                audit(left, right)

    def test_saved_comparison_rejects_exposure_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right, receipt = self._paired(Path(directory))
            frames = json.loads((right / "telemetry.json").read_text(encoding="utf-8"))
            frames[100]["pedestrian_xy"] = [9, 9]
            receipt["telemetry"] = write(right, "telemetry.json", frames)
            write(right, "acquisition.json", receipt)
            with self.assertRaisesRegex(ValueError, "exposure differs"):
                audit(left, right)

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
