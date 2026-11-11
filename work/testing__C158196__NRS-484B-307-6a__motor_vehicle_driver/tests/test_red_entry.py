import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("red_entry_measurements", Path(__file__).resolve().parents[1] / "red_entry_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class RedEntryTests(unittest.TestCase):
    def fixture(self, root, entry_index=2):
        context = {"native_map_id": "TownX", "intersection_id": 5,
                   "native_signal_id": 9, "governed_road_id": 4,
                   "governed_lane_id": -1, "signal_head_video_source": "front-original",
                   "lane_governance_source": "native-affected-waypoints",
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        states = ["Green", "Yellow", "Red", "Red"]
        rows = [{"frame": 100 + i, "time_s": 1 + i * .05,
                 "native_signal_id": 9, "road_id": 4, "lane_id": -1,
                 "signal_state": state, "ego_speed_mps": 4,
                 "ego_body_vertices_xy_m": body(1 if i >= entry_index else -1)}
                for i, state in enumerate(states)]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "signal_vehicle_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_before_at_after_red_onset(self):
        for index, expected in ((1, -0.05), (2, 0.0), (3, 0.05)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, entry_index=index)
                result = measure.analyze(root)
                self.assertAlmostEqual(result["entry_minus_red_onset_s"], expected)
                self.assertEqual(result["entry_with_red_exhibited_observed"], index >= 2)

    def test_rejects_missing_red_transition_and_stale_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "signal_vehicle_history.jsonl").read_text().splitlines()]
            for row in rows:
                row["signal_state"] = "Yellow"
            (root / "signal_vehicle_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Yellow-to-Red"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[2]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
