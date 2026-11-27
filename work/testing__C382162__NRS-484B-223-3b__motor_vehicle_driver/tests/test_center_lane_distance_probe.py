"""Source and geometry checks for the 200-foot center-lane distance probe."""

import importlib.util
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "center_lane_distance_probe.py"
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location("center_lane_distance_probe_3b", path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def fixture(distance_m=60):
    site = {
        "highway_road_id": "road-highway",
        "center_lane_id": "center-turn",
        "site_source_sha256": "a" * 64,
        "ego_id": "ego-1",
        "one_shared_center_lane": True,
        "turns_only_both_directions": True,
    }
    frames = []
    for index in range(63):
        occupied = 1 <= index <= 61
        frames.append({
            "original_frame": 100 + index,
            "time_s": index / 20,
            "driver_id": "ego-1",
            "road_id": "road-turn" if index == 62 else "road-highway",
            "lane_id": "center-turn" if occupied else "other-lane",
            "x_m": max(0, min(index - 1, 60)) * distance_m / 60,
            "y_m": 0.0,
            "body_overlaps_center_lane": occupied,
            "body_within_center_lane": 2 <= index <= 60,
            "maneuver": "left_turn" if index == 62 else "travel",
            "source_sha256": "b" * 64,
        })
    return site, frames


class CenterLaneDistanceProbeTests(unittest.TestCase):
    def test_below_at_above_are_observations_without_legal_verdict(self):
        for feet, relation in [(190, "below"), (200, "at"), (210, "above")]:
            with self.subTest(feet=feet):
                site, frames = fixture(feet / probe.FEET_PER_METER)
                result = probe.measure(site, frames)
                self.assertAlmostEqual(result["observed_center_lane_path_ft"], feet)
                if feet == 200:
                    self.assertAlmostEqual(result["observed_center_lane_path_ft"], 200)
                else:
                    self.assertEqual(result["boundary_relation_observed"], relation)
                self.assertIsNone(result["legal_judgment"])
                self.assertEqual(result["entry_exit_interpolation"], "unresolved")

    def test_rejects_interrupted_occupancy(self):
        site, frames = fixture()
        frames[20]["body_overlaps_center_lane"] = False
        frames[20]["body_within_center_lane"] = False
        with self.assertRaisesRegex(ValueError, "interrupted"):
            probe.measure(site, frames)

    def test_rejects_wrong_turn_or_missing_site_design(self):
        site, frames = fixture()
        frames[-1]["maneuver"] = "right_turn"
        with self.assertRaisesRegex(ValueError, "left-turn departure"):
            probe.measure(site, frames)
        site, frames = fixture()
        site["turns_only_both_directions"] = False
        with self.assertRaisesRegex(ValueError, "single bidirectional"):
            probe.measure(site, frames)

    def test_rejects_source_and_time_discontinuity(self):
        site, frames = fixture()
        frames[9]["source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "source changed"):
            probe.measure(site, frames)
        site, frames = fixture()
        site["site_source_sha256"] = "unhashed"
        with self.assertRaisesRegex(ValueError, "source-bound"):
            probe.measure(site, frames)
        site, frames = fixture()
        frames[9]["time_s"] += 0.05
        with self.assertRaisesRegex(ValueError, "time join"):
            probe.measure(site, frames)

    def test_rejects_body_geometry_and_road_mismatch(self):
        site, frames = fixture()
        frames[10]["body_within_center_lane"] = True
        frames[10]["body_overlaps_center_lane"] = False
        with self.assertRaisesRegex(ValueError, "contradicts"):
            probe.measure(site, frames)
        site, frames = fixture()
        frames[10]["road_id"] = "wrong-road"
        with self.assertRaisesRegex(ValueError, "left highway"):
            probe.measure(site, frames)

    def test_exact_reviewed_site_join_and_onto_contrast(self):
        from test_center_lane_site import packet

        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c382162-2233b-tests"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            live = "reviewed OpenDRIVE"
            (root / "map.json").write_text(json.dumps({
                "opendrive_sha256": hashlib.sha256(live.encode()).hexdigest()}) + "\n")
            (root / "review.json").write_text(json.dumps({
                "public_highway_confirmed": True,
                "single_bidirectional_turn_only_center_lane": True,
                "highway_road_id": "H"}) + "\n")
            site = packet("short_travel")
            site["ego_id"] = "ego-1"
            for name, key in (("map.json", "native_map_source"),
                              ("review.json", "highway_review_source")):
                site[key] = {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
            _, frames = fixture()
            for row in frames:
                row["road_id"] = "S" if row["road_id"] == "road-turn" else "H"
                row["lane_id"] = "C" if row["lane_id"] == "center-turn" else "E"
            result = probe.measure_exact(root, site, "short_travel", live, frames)
            self.assertTrue(result["distance_restriction_applicable"])
            site["route"]["relationship"] = "onto_highway"
            site["route"]["approach_road_id"] = "S"
            site["route"]["departure_road_id"] = "H"
            contrast = [dict(frames[i]) for i in (0, 1, 2)]
            contrast[0]["road_id"] = "S"
            contrast[1]["road_id"] = "S"
            contrast[2]["road_id"] = "H"
            contrast[2]["maneuver"] = "left_turn"
            result = probe.measure_exact(root, site, "onto_highway_contrast", live, contrast)
            self.assertFalse(result["distance_restriction_applicable"])
            self.assertNotIn("observed_center_lane_path_ft", result)

    def test_original_eight_vertex_body_controls_occupancy(self):
        site = {
            "highway_road_id": "H", "center_lane_id": "C",
            "site_source_sha256": "a" * 64, "ego_id": "ego-1",
            "one_shared_center_lane": True, "turns_only_both_directions": True,
            "center_lane_polygon_xy_m": [(0, -1), (3, -1), (3, 1), (0, 1)],
        }
        frames = []
        for index, x in enumerate((-2, 0, 1, 2, 4)):
            vertices = [(x + dx, dy, z) for z in (0, 1) for dx, dy in
                        ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))]
            frames.append({
                "original_frame": 50 + index, "time_s": index / 20,
                "driver_id": "ego-1", "road_id": "S" if index == 4 else "H",
                "lane_id": "C" if 1 <= index <= 3 else "other",
                "x_m": x, "y_m": 0, "body_vertices_m": vertices,
                "maneuver": "left_turn" if index == 4 else "travel",
                "source_sha256": "b" * 64,
            })
        result = probe.measure_with_original_body(site, frames)
        self.assertAlmostEqual(result["observed_center_lane_path_m"], 2)
        self.assertIn("eight-vertex", result["body_occupancy_source"])
        frames[2]["body_within_center_lane"] = False
        with self.assertRaisesRegex(ValueError, "readback differs"):
            probe.measure_with_original_body(site, frames)


if __name__ == "__main__":
    unittest.main()
