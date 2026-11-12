import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("yield_measurements", Path(__file__).resolve().parents[1] / "yield_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class YieldTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 42,
                   "approach_road_id": 9, "approach_lane_id": -1,
                   "through_highway_id": 3, "native_yield_sign_id": 12,
                   "sign_governance_source": "native-trigger", "marking_inventory_source": "map-and-front-video",
                   "no_stop_line": True, "no_near_crosswalk": True,
                   "police_control": False, "traffic_signal_control": False}
        (root / "road_context.json").write_text(json.dumps(context))
        samples = [{"frame": 100, "distance_to_intersection_m": 15, "through_highway_visible": False, "visible_through_vehicle_ids": [], "ray_source": "visibility_rays.jsonl"},
                   {"frame": 101, "distance_to_intersection_m": 3, "through_highway_visible": True, "visible_through_vehicle_ids": [23], "ray_source": "visibility_rays.jsonl"}]
        (root / "visibility_samples.json").write_text(json.dumps(samples))
        rays = [{"frame": row["frame"], "distance_to_intersection_m": row["distance_to_intersection_m"],
                 "observer_m": [0, 0, 1.5], "target_m": [1.8, 0, 1.5],
                 "blockers": [] if row["through_highway_visible"] else [{"label": "wall", "location_m": [1, 0, 1]}],
                 "clear": row["through_highway_visible"],
                 "visible_through_vehicle_ids": row["visible_through_vehicle_ids"]} for row in samples]
        (root / "visibility_rays.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rays))
        rows = [{"frame": 100, "time_s": 1.0, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 4, "distance_to_intersection_m": 15},
                {"frame": 101, "time_s": 1.05, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 2, "distance_to_intersection_m": 3}]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "approach_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_nearest_sourced_view_and_speed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertEqual(report["closest_sourced_visible_sample"]["distance_to_intersection_m"], 3)
            self.assertEqual(report["minimum_observed_approach_speed_mps"], 2)
            self.assertIn("unresolved", report["yield_judgment"])

    def test_full_video_extends_beyond_approach_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with (root / "video_frames.jsonl").open('a') as handle:
                handle.write(json.dumps({'video_frame': 2, 'carla_frame': 102,
                                         'time_s': 1.1}) + '\n')
            self.assertEqual(measure.analyze(root)['minimum_observed_approach_speed_mps'], 2)

    def test_rejects_marking_and_control_exceptions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            context = json.loads((root / "road_context.json").read_text())
            context["no_near_crosswalk"] = False
            (root / "road_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "crosswalk"):
                measure.analyze(root)
            context["no_near_crosswalk"] = True
            context["traffic_signal_control"] = True
            (root / "road_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "exception"):
                measure.analyze(root)

    def test_rejects_unsourced_view_and_stale_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            samples = json.loads((root / "visibility_samples.json").read_text())
            samples[1]["ray_source"] = ""
            (root / "visibility_samples.json").write_text(json.dumps(samples))
            with self.assertRaisesRegex(ValueError, "ray evidence"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_clear_through_highway_uses_road_view_without_actor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            samples = json.loads((root / "visibility_samples.json").read_text())
            for sample in samples:
                sample["visible_through_vehicle_ids"] = []
            (root / "visibility_samples.json").write_text(json.dumps(samples))
            rays = [json.loads(line) for line in (root / "visibility_rays.jsonl").read_text().splitlines()]
            for row in rays:
                row["visible_through_vehicle_ids"] = []
            (root / "visibility_rays.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rays))
            report = measure.analyze(root)
            self.assertEqual(report["closest_sourced_visible_sample"]["distance_to_intersection_m"], 3)
            self.assertEqual(report["closest_sourced_visible_sample"]["visible_through_vehicle_ids"], [])

    def test_rejects_ray_result_relabeling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            samples = json.loads((root / "visibility_samples.json").read_text())
            samples[1]["through_highway_visible"] = False
            (root / "visibility_samples.json").write_text(json.dumps(samples))
            with self.assertRaisesRegex(ValueError, "differs from original ray"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
