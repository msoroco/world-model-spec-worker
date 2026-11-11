import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("crossing_measurements")
signs = load("yield_sign_control")


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class FakeSign:
    def __init__(self, valid):
        self.id, self.calls = 10, []
        def contains(point, transform):
            self.calls.append((point, transform))
            return valid
        self.trigger_volume = NS(contains=contains)

    def get_transform(self):
        return "native-sign-transform"


class FakeActors(list):
    def filter(self, pattern):
        assert pattern == "traffic.yield*"
        return self


class CrossingTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 9,
                   "ego_highway_id": "highway-a", "other_highway_id": "highway-b",
                   "ego_road_id": 3, "other_road_id": 4,
                   "native_yield_sign_id": 10, "sign_governance_source": "native-trigger",
                   "yield_sign_video_source": "front-original", "intersection_polygon_source": "native-map-junction",
                   "yield_sign_erected": True, "yield_sign_governed_road_id": 3,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x, other_x = [-20, -18, -10, 1], [-4, 1, 3, 5]
        rows = []
        for i in range(4):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "native_yield_sign_id": 10,
                         "ego": {"intersection_id": 9, "road_id": 3,
                                 "distance_to_intersection_m": max(0, -ego_x[i]),
                                 "speed_mps": 3 if i != 2 else 0,
                                 "body_vertices_xy_m": body(ego_x[i])},
                         "other": {"intersection_id": 9, "road_id": 4,
                                   "distance_to_intersection_m": max(0, -other_x[i]),
                                   "speed_mps": 3, "body_vertices_xy_m": body(other_x[i])}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_native_yield_trigger_selection(self):
        wrong, right = FakeSign(False), FakeSign(True)
        world = NS(get_actors=lambda: FakeActors([wrong, right]))
        waypoint = NS(transform=NS(location="ego-approach-point"))
        self.assertIs(signs.find_governing_yield_sign(world, waypoint), right)
        self.assertEqual(right.calls, [("ego-approach-point", "native-sign-transform")])
        with self.assertRaisesRegex(ValueError, "found 0"):
            signs.find_governing_yield_sign(NS(get_actors=lambda: FakeActors([wrong])), waypoint)

    def test_other_first_at_yield_sign_and_context_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["other_entered_before_ego_observed"])
            self.assertTrue(report["ego_approaching_at_other_entry_observed"])
            self.assertIn("unresolved", report["official_device_exclusion_judgment"])
            context = json.loads((root / "junction_context.json").read_text())
            context["yield_sign_governed_road_id"] = 4
            (root / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "governing yield sign"):
                measure.analyze(root)

    def test_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
