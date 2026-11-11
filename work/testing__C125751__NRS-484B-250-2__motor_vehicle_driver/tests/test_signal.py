import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


control = load("signal_control")
measure = load("signal_measurements")


class Waypoint:
    def __init__(self, road, lane):
        self.road_id, self.lane_id = road, lane


class Light:
    def __init__(self, ident, road, lane):
        self.id, self.waypoints, self.state, self.calls = ident, [Waypoint(road, lane)], "Red", []

    def get_affected_lane_waypoints(self):
        return self.waypoints

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.calls.append(("set", state))
        self.state = state

    def freeze(self, value):
        self.calls.append(("freeze", value))


class Actors(list):
    def filter(self, pattern):
        assert pattern == "traffic.traffic_light*"
        return self


class World:
    def __init__(self, lights):
        self.lights, self.ticks = Actors(lights), 0

    def get_actors(self):
        return self.lights

    def tick(self):
        self.ticks += 1


class SignalTests(unittest.TestCase):
    def test_governing_lane_and_reversible_off_state(self):
        wrong, right = Light(1, 10, -1), Light(2, 11, -1)
        world = World([wrong, right])
        selected = control.find_governing_signal(world, 11, -1)
        self.assertIs(selected, right)
        class States:
            Red, Green, Off = "Red", "Green", "Off"
        with control.SignalControl(world, selected, States, "Off"):
            self.assertEqual(right.get_state(), "Off")
        self.assertEqual(right.get_state(), "Red")
        self.assertEqual(right.calls, [("freeze", True), ("set", "Off"),
                                       ("set", "Red"), ("freeze", False)])
        self.assertEqual(world.ticks, 2)

    def test_missing_or_ambiguous_governance_rejected(self):
        with self.assertRaises(ValueError):
            control.find_governing_signal(World([]), 11, -1)
        with self.assertRaises(ValueError):
            control.find_governing_signal(World([Light(1, 11, -1), Light(2, 11, -1)]), 11, -1)

    def fixture(self, root):
        context = {"intersection_id": 25, "native_signal_id": 8,
                   "native_map_id": "TownX", "governed_road_id": 11,
                   "governed_lane_id": -1, "vehicular_heads_installed": True,
                   "vehicular_heads_uncovered": True,
                   "head_visibility_source": "source-camera/front"}
        (root / "signal_context.json").write_text(json.dumps(context))
        rows = [{"frame": 101, "time_s": 1.0, "native_signal_id": 8, "state": "Red"},
                {"frame": 102, "time_s": 1.1, "native_signal_id": 8, "state": "Off"}]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "signal_history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in frames))
        entry = {"intersection_id": 25, "first_body_entry": {
            "ego": {"frame": 102, "time_s": 1.1},
            "other": {"frame": 101, "time_s": 1.0}}}
        return entry

    def test_entry_state_join(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = self.fixture(root)
            result = measure.analyze(root, entry)
            self.assertEqual(result["at_body_entry"]["ego"]["native_state"], "Off")
            self.assertEqual(result["at_body_entry"]["other"]["native_state"], "Red")
            self.assertIn("unresolved", result["inoperative_judgment"])

    def test_reject_stale_frame_and_uncovered_assertion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = self.fixture(root)
            (root / "video_frames.jsonl").write_text((root / "video_frames.jsonl").read_text().replace('"carla_frame": 102', '"carla_frame": 999'))
            with self.assertRaisesRegex(ValueError, "join"):
                measure.analyze(root, entry)
            self.fixture(root)
            context = json.loads((root / "signal_context.json").read_text())
            context["vehicular_heads_uncovered"] = False
            (root / "signal_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "uncovered"):
                measure.analyze(root, entry)


if __name__ == "__main__":
    unittest.main()
