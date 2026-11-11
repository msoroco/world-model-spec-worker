import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("inoperative_stop_measurements", Path(__file__).resolve().parents[1] / "inoperative_stop_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class StopTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 6,
                   "native_signal_id": 13, "signal_head_video_source": "front-original",
                   "lane_governance_source": "native-affected-waypoints",
                   "stop_line_source": "native-map-and-front-video",
                   "installed_uncovered_vehicular_heads": True,
                   "stop_line_exists": True,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x = [-3, -3, -3, 1]
        other_x = [-3, -3, 1, 3]
        ego_speed = [2, 2, 0, 2]
        other_speed = [2, 0, 2, 2]
        rows = []
        for i in range(4):
            rows.append({"frame": 100 + i, "time_s": 1 + i * .05,
                         "native_signal_id": 13, "signal_state": "Off",
                         "ego": {"intersection_id": 6, "speed_mps": ego_speed[i],
                                 "front_to_stop_line_signed_m": 1 if i <= 2 else -1,
                                 "body_vertices_xy_m": body(ego_x[i])},
                         "other": {"intersection_id": 6, "speed_mps": other_speed[i],
                                   "front_to_stop_line_signed_m": 1 if i <= 1 else -1,
                                   "body_vertices_xy_m": body(other_x[i])}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_stop_order_and_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["ego_stopped_before_entry_observed"])
            self.assertTrue(report["other_completed_stop_before_ego_observed"])
            self.assertEqual(report["first_body_entry"]["other"]["frame"], 102)
            self.assertEqual(report["first_body_entry"]["ego"]["frame"], 103)

    def test_rejects_operating_signal_and_stale_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[2]["signal_state"] = "Red"
            (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Off state"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[2]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
