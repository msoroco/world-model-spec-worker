import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import capture
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


if __name__ == "__main__":
    unittest.main()
