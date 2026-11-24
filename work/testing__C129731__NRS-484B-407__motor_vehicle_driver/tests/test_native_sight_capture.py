import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import capture
from distance_probe_audit import audit as audit_distance
from sight_measurement import ASSIGNMENT, measure


CASE = ASSIGNMENT + "__curve_ahead_blocked"
DIGEST = hashlib.sha256(b"reviewed native mountain map").hexdigest()


class NativeAdapter:
    def __init__(self):
        self.i = 0
        self.loaded_map = DIGEST
        self.drop_endpoint = False
        self.clock_gap = False
        self.wrong_vehicle = False
        self.blocked_direction = "ahead_opposing"

    def geometry(self):
        return {"source_kind": "original_native_geometry", "highway_source": "Native map waypoint",
                "location_kind": "curve", "ego_vehicle_id": "ego-1",
                "map_source_sha256": DIGEST, "loaded_map_sha256": self.loaded_map}

    def tick(self):
        i = self.i
        self.i += 1
        return {"source_kind": "original_native", "frame": i + 10,
                "time_s": i / 20 + (.1 if self.clock_gap and i == 200 else 0)}

    def ego(self, frame):
        i = frame["frame"] - 10
        return {"source_kind": "original_native", "vehicle_id": "other" if self.wrong_vehicle else "ego-1",
                "yaw_deg": 0 if i <= 400 else 179, "turn_active": i in (400, 401)}

    def ray(self, frame, direction, station):
        blocked = direction == self.blocked_direction and station == 100.0
        return {"source_kind": "original_native", "frame": frame["frame"],
                "time_s": frame["time_s"], "direction": direction,
                "station_distance_m": 150.0 if self.drop_endpoint and station == 152.4 else station,
                "observer_height_m": 1.4, "observer_lane_source": "Native lane waypoint",
                "target_vehicle_id": "ego-1", "body_point_clear": [not blocked] * 9,
                "terrain_hit_id": "Native terrain actor" if blocked else None}


class DistanceProbeAdapter(NativeAdapter):
    def __init__(self, distance_ft=500):
        super().__init__()
        self.distance_ft = distance_ft
        self.wrong_approach = False

    def geometry(self):
        return dict(super().geometry(), approach_vehicle_id="approach-1")

    def approach(self, frame):
        return {"source_kind": "original_native", "frame": frame["frame"],
                "time_s": frame["time_s"],
                "vehicle_id": "wrong" if self.wrong_approach else "approach-1",
                "ego_position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "approach_position": {"x": self.distance_ft * 0.3048,
                                      "y": 0.0, "z": 0.0}}


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "attempt"

    def test_capture_round_trip_and_hash_binding(self):
        measured = capture(NativeAdapter(), CASE, self.out)
        inventory = json.loads((self.out / "inventory.json").read_text())
        self.assertEqual(measured, measure(self.out, inventory, CASE))
        self.assertEqual(measured["original_frames"], 900)
        self.assertEqual(measured["rays_checked"], 20)
        self.assertEqual(measured["blocked_ray_counts"]["ahead_opposing"], 2)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            capture(NativeAdapter(), CASE, self.out)

    def test_four_original_views_are_frame_joined_and_sealed(self):
        class Cameras:
            def __init__(self, root):
                self.root = root
                self.frames = []

            def append(self, frame):
                self.frames.append(frame)

            def close(self):
                pass

            def files(self):
                if len(self.frames) != 900 or self.frames != list(range(10, 910)):
                    raise ValueError("camera frames not joined")
                files = {}
                for name in ("overview", "approach", "reference_corner", "driver_reference"):
                    path = self.root / (name + ".mkv")
                    path.write_bytes((name + " original frames").encode())
                    files[name] = path
                return files

        cameras = Cameras(Path(self.tmp.name))
        capture(NativeAdapter(), CASE, self.out, camera_recorder=cameras)
        inventory = json.loads((self.out / "inventory.json").read_text())
        self.assertEqual(set(inventory["camera_sources"]),
                         {"overview", "approach", "reference_corner", "driver_reference"})
        for entry in inventory["camera_sources"].values():
            source = self.out / entry["path"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), entry["sha256"])

    def test_changed_map_rejected_before_ticks(self):
        adapter = NativeAdapter()
        adapter.loaded_map = "0" * 64
        with self.assertRaisesRegex(ValueError, "loaded map"):
            capture(adapter, CASE, self.out)
        self.assertEqual(adapter.i, 0)

    def test_clock_gap_rejected_without_attempt(self):
        adapter = NativeAdapter()
        adapter.clock_gap = True
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            capture(adapter, CASE, self.out)
        self.assertFalse(self.out.exists())

    def test_missing_endpoint_rejected_without_attempt(self):
        adapter = NativeAdapter()
        adapter.drop_endpoint = True
        with self.assertRaisesRegex(ValueError, "station mismatch"):
            capture(adapter, CASE, self.out)
        self.assertFalse(self.out.exists())

    def test_subject_swap_rejected(self):
        adapter = NativeAdapter()
        adapter.wrong_vehicle = True
        with self.assertRaisesRegex(ValueError, "identity changed"):
            capture(adapter, CASE, self.out)
        self.assertFalse(self.out.exists())

    def test_source_measured_500_foot_probe_and_sealed_packet(self):
        case = ASSIGNMENT + "__distance_at_500ft"
        result = capture(DistanceProbeAdapter(), case, self.out)
        self.assertEqual(result["approach_distance_probe"]["target_ft"], 500)
        inventory = json.loads((self.out / "inventory.json").read_text())
        self.assertEqual(inventory["approach_probe"]["path"], "approach_motion.json")
        packet = json.loads((self.out / "approach_motion.json").read_text())
        self.assertEqual(packet["probe_target_ft"], 500)
        self.assertAlmostEqual(packet["first_turn_distance_m"], 152.4)
        self.assertEqual(packet["legal_visibility_judgment"], "unresolved")
        saved = audit_distance(self.out, case)
        self.assertEqual(saved["target_ft"], 500)
        self.assertEqual(saved["original_turn_samples"], 2)
        cli_output = self.out.parent / "probe-cli.json"
        script = Path(__file__).resolve().parents[1] / "distance_probe_audit.py"
        subprocess.run([sys.executable, str(script), "--attempt", str(self.out),
                        "--case", case, "--output", str(cli_output)],
                       check=True, capture_output=True)
        self.assertEqual(json.loads(cli_output.read_text())["target_ft"], 500)
        packet["samples"][0]["approach_position"]["x"] = 100.0
        (self.out / "approach_motion.json").write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            audit_distance(self.out, case)
        inventory["approach_probe"]["sha256"] = hashlib.sha256(
            (self.out / "approach_motion.json").read_bytes()).hexdigest()
        (self.out / "inventory.json").write_text(json.dumps(inventory) + "\n")
        with self.assertRaisesRegex(ValueError, "saved measurement changed"):
            audit_distance(self.out, case)

    def test_distance_miss_and_identity_swap_rejected_without_attempt(self):
        case = ASSIGNMENT + "__distance_below_500ft"
        with self.assertRaisesRegex(ValueError, "distance misses probe target"):
            capture(DistanceProbeAdapter(500), case, self.out)
        self.assertFalse(self.out.exists())
        adapter = DistanceProbeAdapter(499)
        adapter.wrong_approach = True
        with self.assertRaisesRegex(ValueError, "frame or identity mismatch"):
            capture(adapter, case, self.out)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
