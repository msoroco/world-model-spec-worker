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
        samples = [{"distance_to_intersection_m": 15, "visible_through_vehicle_ids": [], "ray_source": "native-ray-1"},
                   {"distance_to_intersection_m": 8, "visible_through_vehicle_ids": [23], "ray_source": "native-ray-2"},
                   {"distance_to_intersection_m": 3, "visible_through_vehicle_ids": [23], "ray_source": "native-ray-3"}]
        (root / "visibility_samples.json").write_text(json.dumps(samples))
        rows = [{"frame": 100, "time_s": 1.0, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 4, "distance_to_intersection_m": 15},
                {"frame": 101, "time_s": 1.05, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 2, "distance_to_intersection_m": 8}]
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


if __name__ == "__main__":
    unittest.main()
