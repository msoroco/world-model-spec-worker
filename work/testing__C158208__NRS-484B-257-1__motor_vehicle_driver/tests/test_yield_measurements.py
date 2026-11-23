import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


spec = importlib.util.spec_from_file_location("yield_measurements", Path(__file__).resolve().parents[1] / "yield_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)
sign_spec = importlib.util.spec_from_file_location("yield_sign_control", Path(__file__).resolve().parents[1] / "yield_sign_control.py")
sign_control = importlib.util.module_from_spec(sign_spec)
sign_spec.loader.exec_module(sign_control)


class YieldTests(unittest.TestCase):
    def test_native_yield_sign_trigger_governs_approach(self):
        class Actors(list):
            def filter(self, pattern):
                self.assert_pattern = pattern
                return self
        selected = NS(trigger_volume=NS(contains=lambda p,t: True), get_transform=lambda: "sign")
        wrong = NS(trigger_volume=NS(contains=lambda p,t: False), get_transform=lambda: "other")
        world = NS(get_actors=lambda: Actors([wrong, selected]))
        approach = NS(transform=NS(location="approach"))
        self.assertIs(sign_control.find_governing_yield_sign(world, approach), selected)
        with self.assertRaisesRegex(ValueError, "found 0"):
            sign_control.find_governing_yield_sign(NS(get_actors=lambda: Actors([wrong])), approach)

    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 42,
                   "approach_road_id": 9, "approach_lane_id": -1,
                   "through_highway_id": 3, "native_yield_sign_id": 12,
                   "sign_governance_source": "native-trigger", "marking_inventory_source": "map-and-front-video",
                   "no_stop_line": True, "no_near_crosswalk": True,
                   "police_control": False, "traffic_signal_control": False}
        (root / "road_context.json").write_text(json.dumps(context))
        samples = [{"frame": frame, "distance_to_intersection_m": distance,
                    "through_highway_visible": True,
                    "visible_through_vehicle_ids": ids, "ray_source": "visibility_rays.jsonl"}
                   for frame, distance, ids in ((100, 15, []), (101, 8, [23]),
                                                (102, 3, [23]))]
        (root / "visibility_samples.json").write_text(json.dumps(samples))
        rays = [{"frame": row["frame"], "distance_to_intersection_m": row["distance_to_intersection_m"],
                 "observer_m": [-20, 1.8, 1.5], "target_m": [1.8, 0, 1.5],
                 "blockers": [], "clear": True,
                 "visible_through_vehicle_ids": row["visible_through_vehicle_ids"]}
                for row in samples]
        (root / "visibility_rays.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rays))
        rows = [{"frame": 100, "time_s": 1.0, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 4, "distance_to_intersection_m": 15},
                {"frame": 101, "time_s": 1.05, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 2, "distance_to_intersection_m": 8},
                {"frame": 102, "time_s": 1.1, "road_id": 9, "lane_id": -1,
                 "ego_speed_mps": 1, "distance_to_intersection_m": 3}]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        frames.append({"video_frame": 3, "carla_frame": 103, "time_s": 1.15})
        (root / "approach_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_nearest_sourced_view_and_speed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertEqual(report["closest_sourced_visible_sample"]["distance_to_intersection_m"], 3)
            self.assertEqual(report["closest_sourced_visible_sample"]["frame"], 102)
            self.assertEqual(report["speed_at_closest_view_mps"], 1)
            self.assertEqual(report["minimum_observed_approach_speed_mps"], 1)
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
            with self.assertRaisesRegex(ValueError, "spatial ray evidence"):
                measure.analyze(root)
            self.fixture(root)
            samples = json.loads((root / "visibility_samples.json").read_text())
            samples[2]["frame"] = 999
            (root / "visibility_samples.json").write_text(json.dumps(samples))
            with self.assertRaisesRegex(ValueError, "complete original ray"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "camera frame map"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
