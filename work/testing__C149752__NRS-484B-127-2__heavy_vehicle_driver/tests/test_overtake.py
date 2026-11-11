import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("overtake_measurements", ROOT / "overtake_measurements.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def body(center_x, center_y):
    return {"road_id": 7, "lane_id": 1, "truck_or_combination": True,
            "overall_width_m": 2.5,
            "body_vertices_xy_m": [[center_x + dx, center_y + dy]
                                   for dx, dy in ((-2,-1.25),(-2,1.25),(2,-1.25),(2,1.25))]}


class PassingTests(unittest.TestCase):
    def fixture(self, root, lateral=4.0):
        context = {"native_map_id": "TownX", "highway_source": "reviewed-highway",
                   "lane_count_source": "native-map-and-visual", "road_id": 7,
                   "same_direction_lane_count": 1, "lane_forward_xy": [1,0]}
        (root / "road_context.json").write_text(json.dumps(context))
        rows = []
        for i, (x, y) in enumerate(((0,0),(6,lateral),(20,0))):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "ego": body(x,y), "lead": body(10,0)})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "passing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_original_frame_lateral_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = module.analyze(root)
            self.assertEqual((result["first_behind_frame"], result["first_ahead_frame"]), (100,102))
            self.assertFalse(result["two_lane_exemption_observed"])
            self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_no_lateral_pass_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, lateral=0)
            with self.assertRaisesRegex(ValueError, "No sourced lateral pass"):
                module.analyze(root)
            self.fixture(root)
            frames = [json.loads(row) for row in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                module.analyze(root)


if __name__ == "__main__":
    unittest.main()
