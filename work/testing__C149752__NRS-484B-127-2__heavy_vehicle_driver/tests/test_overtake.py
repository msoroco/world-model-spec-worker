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


class FollowingTests(unittest.TestCase):
    def fixture(self, root, gap_ft, lanes=1):
        context = {"native_map_id": "TownX", "highway_source": "diagnostic-highway",
                   "lane_count_source": "diagnostic-map-and-visual", "road_id": 7,
                   "same_direction_lane_count": lanes, "lane_forward_xy": [1, 0]}
        (root / "road_context.json").write_text(json.dumps(context))
        rows = []
        for i in range(3):
            ego = body(i, 0)
            lead = body(i + 4 + gap_ft * .3048, 0)
            ego["actor_id"], lead["actor_id"] = 11, 12
            rows.append({"frame": 200 + i, "time_s": 10 + i * .05,
                         "ego": ego, "lead": lead})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "following_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_exact_gap_branches_and_lane_context(self):
        for gap, expected in ((499, "below"), (500, "at_sampled_precision"), (501, "above")):
            with self.subTest(gap=gap), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, gap, lanes=2 if gap == 501 else 1)
                result = module.analyze_following(root)
                self.assertTrue(all(row["sample_relation"] == expected for row in result["samples"]))
                self.assertAlmostEqual(result["sampled_gap_min_m"], gap * .3048)
                self.assertEqual(result["two_lane_nonapplication_context"], gap == 501)
                self.assertEqual(result["all_samples_at_or_above_500_ft"], gap >= 500)
                self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_changed_lane_and_stale_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 500)
            rows = [json.loads(line) for line in (root / "following_history.jsonl").read_text().splitlines()]
            rows[1]["lead"]["lane_id"] = 2
            (root / "following_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "same sourced lane"):
                module.analyze_following(root)
            self.fixture(root, 500)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                module.analyze_following(root)

    def test_one_short_sample_breaks_continuous_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 500)
            rows = [json.loads(line) for line in (root / "following_history.jsonl").read_text().splitlines()]
            for vertex in rows[1]["lead"]["body_vertices_xy_m"]:
                vertex[0] -= .3048
            (root / "following_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = module.analyze_following(root)
            self.assertEqual([x["sample_relation"] for x in result["samples"]],
                             ["at_sampled_precision", "below", "at_sampled_precision"])
            self.assertFalse(result["all_samples_at_or_above_500_ft"])
            self.assertEqual(result["between_sample_gap"], "unresolved")


class WidthBoundaryTests(unittest.TestCase):
    def fixture(self, root, varied_role, width):
        context = {"native_map_id": "TownX", "highway_source": "diagnostic-highway",
                   "lane_count_source": "diagnostic-map-and-visual", "road_id": 7,
                   "lane_id": 1, "same_direction_lane_count": 1,
                   "lane_forward_xy": [1, 0]}
        (root / "road_context.json").write_text(json.dumps(context))
        rows = []
        for i in range(3):
            actors = {}
            for role, actor_id, x in (("ego", 11, i), ("lead", 12, i + 160)):
                measured = width if role == varied_role else 2.2
                actors[role] = {"actor_id": actor_id, "is_truck_or_combination": True,
                                "road_id": 7, "lane_id": 1, "overall_width_m": measured,
                                "body_vertices_xy_m": [[x + dx, dy * measured / 2]
                                                       for dx, dy in ((-2, -1), (-2, 1),
                                                                      (2, -1), (2, 1))]}
            rows.append({"frame": 300 + i, "time_s": 10 + .05 * i, **actors})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "truck_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_both_roles_below_at_above(self):
        for role in ("ego", "lead"):
            for width, relation in ((2.0, "below"), (2.032, "at"), (2.1, "above")):
                with self.subTest(role=role, relation=relation), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.fixture(root, role, width)
                    result = module.analyze_width_boundary(root, role, relation)
                    self.assertEqual(len(result["samples"]), 3)
                    self.assertTrue(all(row["sample_relation"] == relation for row in result["samples"]))
                    self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_mismatched_boundary_and_stale_sources_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, "ego", 2.0)
            with self.assertRaisesRegex(ValueError, "Width boundary relation differs"):
                module.analyze_width_boundary(root, "ego", "above")
            rows = [json.loads(line) for line in (root / "truck_history.jsonl").read_text().splitlines()]
            rows[1]["ego"]["overall_width_m"] = 2.2
            (root / "truck_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Body width and declared width disagree"):
                module.analyze_width_boundary(root, "ego", "below")
            self.fixture(root, "ego", 2.0)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "Original video frame join"):
                module.analyze_width_boundary(root, "ego", "below")


if __name__ == "__main__":
    unittest.main()
