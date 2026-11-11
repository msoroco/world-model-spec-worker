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
control = load("signal_control")


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class FakeLight:
    def __init__(self, road, lane):
        self.road, self.lane, self.state, self.calls = road, lane, "Red", []

    def get_affected_lane_waypoints(self):
        return [NS(road_id=self.road, lane_id=self.lane)]

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.calls.append(("set", state))
        self.state = state

    def freeze(self, value):
        self.calls.append(("freeze", value))


class FakeActors(list):
    def filter(self, pattern):
        assert pattern == "traffic.traffic_light*"
        return self


class FakeWorld:
    def __init__(self, actors):
        self.actors, self.ticks = FakeActors(actors), 0

    def get_actors(self):
        return self.actors

    def tick(self):
        self.ticks += 1


class CrossingTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 9,
                   "ego_highway_id": "highway-a", "other_highway_id": "highway-b",
                   "ego_road_id": 3, "other_road_id": 4,
                   "native_signal_id": 27, "signal_governance_source": "native-affected-waypoints",
                   "signal_head_video_source": "front-original", "intersection_polygon_source": "native-map-junction",
                   "installed_uncovered_vehicular_heads": True,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x = [-20, -18, -10, 1]
        other_x = [-4, 1, 3, 5]
        rows = []
        for i in range(4):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "native_signal_id": 27, "signal_state": "Off",
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

    def test_other_first_and_ego_approach(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["other_entered_before_ego_observed"])
            self.assertTrue(report["ego_approaching_at_other_entry_observed"])
            self.assertEqual(report["minimum_ego_speed_while_other_inside_mps"], 0)

    def test_off_signal_native_selection_and_restoration(self):
        wrong, selected = FakeLight(99, -1), FakeLight(3, -1)
        world = FakeWorld([wrong, selected])
        light = control.find_governing_signal(world, 3, -1)
        self.assertIs(light, selected)
        with control.SignalControl(world, light, NS(Red="Red", Green="Green", Off="Off"), "Off"):
            self.assertEqual(light.get_state(), "Off")
        self.assertEqual(light.get_state(), "Red")
        self.assertEqual(world.ticks, 2)

    def test_rejects_same_highway_and_stale_join(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            context = json.loads((root / "junction_context.json").read_text())
            context["other_highway_id"] = context["ego_highway_id"]
            (root / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "different highways"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
