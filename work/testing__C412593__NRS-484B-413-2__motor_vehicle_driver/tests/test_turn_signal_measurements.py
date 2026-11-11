import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("turn_signal_measurements", Path(__file__).resolve().parents[1] / "turn_signal_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class TurnSignalTests(unittest.TestCase):
    def fixture(self, root, distance, district="business", interrupted=False):
        context = {"native_map_id": "TownX", "approach_road_id": 1,
                   "approach_lane_id": -1, "outgoing_road_id": 2,
                   "outgoing_lane_id": -1, "native_route_source": "native-lane-links",
                   "district_source": "source-reviewed-map-context",
                   "district_type": district, "turn_onset_frame": 104}
        (root / "route_context.json").write_text(json.dumps(context))
        x = [-1, 0, distance / 2, distance * .75, distance]
        indicators = [False, True, not interrupted, True, True]
        rows = [{"frame": 100+i, "time_s": 1+i*.05,
                 "ego_position_xy_m": [point, 0], "ego_speed_mps": 5,
                 "right_indicator": indicators[i]}
                for i, point in enumerate(x)]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "drive_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_100_foot_below_at_above_and_300_foot_area(self):
        for distance, expected in ((30.47, False), (30.48, True), (30.49, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, distance)
                result = measure.analyze(root)
                self.assertAlmostEqual(result["turn_onset"]["continuous_right_signal_distance_m"], distance)
                self.assertEqual(result["observed_continuous_distance_meets_boundary"], expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, district="other")
            self.assertAlmostEqual(measure.analyze(root)["required_distance_m"], 91.44)
        for distance, expected in ((91.43, False), (91.44, True), (91.45, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, distance, district="other")
                result = measure.analyze(root)
                self.assertEqual(result["observed_continuous_distance_meets_boundary"], expected)

    def test_interruption_resets_distance_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, interrupted=True)
            result = measure.analyze(root)
            self.assertLess(result["turn_onset"]["continuous_right_signal_distance_m"], 30.48)
            self.fixture(root, 30.48)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[3]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
