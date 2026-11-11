import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("truck_measurements", Path(__file__).resolve().parents[1] / "truck_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def body(front, back, half_width=1.02):
    return [[front, half_width], [front, -half_width], [back, half_width], [back, -half_width]]


class MeasurementTests(unittest.TestCase):
    def fixture(self, root, gap_m=152.4, lanes=1):
        context = {"native_map_id": "TownX", "road_id": 4, "lane_id": -1,
                   "same_direction_lane_count": lanes, "lane_forward_xy": [1, 0],
                   "lane_count_source": "native-map-topology"}
        (root / "road_context.json").write_text(json.dumps(context))
        rows = []
        for i in range(2):
            x = i * 2
            rows.append({"frame": 100 + i, "time_s": 5 + i * .05,
                         "ego": {"road_id": 4, "lane_id": -1, "overall_width_m": 2.032,
                                 "is_truck_or_combination": True, "body_vertices_xy_m": body(x, x - 10)},
                         "lead": {"road_id": 4, "lane_id": -1, "overall_width_m": 2.1,
                                  "is_truck_or_combination": True,
                                  "body_vertices_xy_m": body(x + gap_m + 10, x + gap_m)}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "truck_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_exact_boundaries_and_lane_exception_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, gap_m=152.4, lanes=1)
            result = measure.analyze(root)
            self.assertAlmostEqual(result["minimum_qualifying_width_m"], 2.032)
            self.assertAlmostEqual(result["statutory_space_m"], 152.4)
            self.assertAlmostEqual(result["samples"][0]["longitudinal_body_gap_m"], 152.4)
            self.assertFalse(result["same_direction_two_lane_exemption_observed"])
            self.fixture(root, gap_m=152.4, lanes=2)
            self.assertTrue(measure.analyze(root)["same_direction_two_lane_exemption_observed"])

    def test_reject_wrong_lane_and_stale_video_join(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "truck_history.jsonl").read_text().splitlines()]
            rows[1]["lead"]["lane_id"] = -2
            (root / "truck_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "following lane"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
