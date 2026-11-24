import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sight_measurement import ASSIGNMENT, DIRECTIONS, STATIONS_M, measure


CASE = ASSIGNMENT + "__curve_ahead_blocked"


class SightMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        frames = [{"frame": i + 10, "time_s": i / 20} for i in range(900)]
        motion = [dict(row, yaw_deg=(i - 100) * 180 / 19 if 100 <= i < 120
                       else (0 if i < 100 else 180), turn_active=100 <= i < 120)
                  for i, row in enumerate(frames)]
        rays = []
        for row in frames[100:120]:
            for direction in DIRECTIONS:
                for station in STATIONS_M:
                    blocked = direction == "ahead_opposing" and station == 100.0
                    rays.append({"frame": row["frame"], "time_s": row["time_s"],
                                 "direction": direction, "station_distance_m": station,
                                 "observer_height_m": 1.4,
                                 "observer_lane_source": "test original lane waypoint",
                                 "target_vehicle_id": "ego-1",
                                 "body_point_clear": [not blocked] * 9,
                                 "terrain_hit_id": "test-terrain-1" if blocked else None})
        self.data = {
            "frame_map": {"frames": frames},
            "ego_motion": {"case_id": CASE, "source_kind": "original_native",
                           "samples": motion},
            "sight_rays": {"case_id": CASE, "source_kind": "original_native",
                           "samples": rays},
            "road_geometry": {"source_kind": "original_native_geometry",
                              "highway_source": "test source map",
                              "location_kind": "curve", "ego_vehicle_id": "ego-1"},
        }
        self.inventory = self.seal()

    def seal(self):
        inventory = {"case_id": CASE, "source_kind": "original_native", "sources": {}}
        for name, data in self.data.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(data))
            inventory["sources"][name] = {"path": path.name,
                                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        return inventory

    def test_900_frames_both_directions_and_numeric_500_feet(self):
        result = measure(self.root, self.inventory, CASE)
        self.assertEqual(result["original_frames"], 900)
        self.assertEqual(result["rays_checked"], 20 * 2 * 5)
        self.assertEqual(result["statutory_distance_m"], 152.4)
        self.assertEqual(result["blocked_ray_counts"]["ahead_opposing"], 20)
        self.assertEqual(result["driver_visibility_judgment"], "unresolved")

    def test_missing_opposing_direction_rejected(self):
        self.data["sight_rays"]["samples"] = [r for r in self.data["sight_rays"]["samples"]
                                              if r["direction"] != "behind_same_direction"]
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "both approach directions"):
            measure(self.root, inventory, CASE)

    def test_blocked_ray_requires_terrain_hit(self):
        self.data["sight_rays"]["samples"][2]["terrain_hit_id"] = None
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "terrain occluder"):
            measure(self.root, inventory, CASE)

    def test_rejects_stale_source_and_nonreversal(self):
        (self.root / "ego_motion.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            measure(self.root, self.inventory, CASE)
        for row in self.data["ego_motion"]["samples"]:
            row["yaw_deg"] = 0
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "did not reverse"):
            measure(self.root, inventory, CASE)

    def test_missing_500_foot_endpoint_rejected(self):
        self.data["sight_rays"]["samples"] = [r for r in self.data["sight_rays"]["samples"]
                                              if r["station_distance_m"] != 152.4]
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "500-foot sight coverage"):
            measure(self.root, inventory, CASE)

    def test_rejects_rebound_ray_clock_and_missing_body_corner(self):
        self.data["sight_rays"]["samples"][0]["time_s"] += .05
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            measure(self.root, inventory, CASE)
        self.data["sight_rays"]["samples"][0]["time_s"] -= .05
        self.data["sight_rays"]["samples"][0]["body_point_clear"].pop()
        inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "nine-point"):
            measure(self.root, inventory, CASE)


if __name__ == "__main__":
    unittest.main()
