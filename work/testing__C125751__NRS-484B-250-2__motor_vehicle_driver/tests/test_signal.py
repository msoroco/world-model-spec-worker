import importlib.util
import hashlib
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

    def test_two_approach_signals_set_and_restored_together(self):
        ego, other = Light(8, 11, -1), Light(9, 22, -1)
        world = World([ego, other])
        class States:
            Red, Green, Off = "Red", "Green", "Off"
        with control.SignalPairControl(world, ego, other, States, "Green", "Red"):
            self.assertEqual((ego.get_state(), other.get_state()), ("Green", "Red"))
            self.assertEqual(world.ticks, 1)
        self.assertEqual((ego.get_state(), other.get_state()), ("Red", "Red"))
        self.assertEqual(world.ticks, 2)
        with control.SignalPairControl(world, ego, other, States, "Off", "Off"):
            self.assertEqual((ego.get_state(), other.get_state()), ("Off", "Off"))
        self.assertEqual((ego.get_state(), other.get_state()), ("Red", "Red"))
        with self.assertRaisesRegex(ValueError, "distinct"):
            control.SignalPairControl(world, ego, ego, States, "Off", "Off")

    def fixture(self, root):
        context = {"intersection_id": 25, "native_signal_id": 8,
                   "native_map_id": "TownX", "governed_road_id": 11,
                   "governed_lane_id": -1, "other_native_signal_id": 9,
                   "other_governed_road_id": 22, "other_governed_lane_id": -1}
        (root / "signal_context.json").write_text(json.dumps(context))
        (root / "approach.mkv").write_bytes(b"synthetic source-camera placeholder")
        review = {"native_signal_id": 8, "camera": "approach", "video_frame": 1,
                  "carla_frame": 102, "source_video_sha256": hashlib.sha256((root / "approach.mkv").read_bytes()).hexdigest(),
                  "head_region_px": [10, 10, 50, 50], "installed": True, "uncovered": True,
                  "review_basis": "synthetic diagnostic only; physical pixels unverified"}
        (root / "head_visibility_review.json").write_text(json.dumps(review))
        (root / "other_head_visibility_review.json").write_text(json.dumps({**review, "native_signal_id": 9}))
        rows = [{"frame": 101, "time_s": 1.0, "native_signal_id": 8, "state": "Red",
                 "other_native_signal_id": 9, "other_state": "Green"},
                {"frame": 102, "time_s": 1.1, "native_signal_id": 8, "state": "Off",
                 "other_native_signal_id": 9, "other_state": "Green"}]
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
            self.assertEqual(result["at_body_entry"]["other"]["native_state"], "Green")
            self.assertIn("unresolved", result["inoperative_judgment"])

    def test_reject_stale_frame_and_uncovered_assertion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = self.fixture(root)
            (root / "video_frames.jsonl").write_text((root / "video_frames.jsonl").read_text().replace('"carla_frame": 102', '"carla_frame": 999'))
            with self.assertRaisesRegex(ValueError, "join"):
                measure.analyze(root, entry)
            self.fixture(root)
            review = json.loads((root / "head_visibility_review.json").read_text())
            review["uncovered"] = False
            (root / "head_visibility_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "uncovered"):
                measure.analyze(root, entry)

    def test_distinct_other_light_and_its_review_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = self.fixture(root)
            context = json.loads((root / "signal_context.json").read_text())
            context["other_native_signal_id"] = context["native_signal_id"]
            (root / "signal_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "Distinct governing signals"):
                measure.analyze(root, entry)
            self.fixture(root)
            (root / "other_head_visibility_review.json").unlink()
            with self.assertRaisesRegex(ValueError, "other_head_visibility_review"):
                measure.analyze(root, entry)

    def test_other_entry_uses_other_native_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = self.fixture(root)
            report = measure.analyze(root, entry)
            self.assertEqual(report["at_body_entry"]["other"]["native_signal_id"], 9)
            self.assertEqual(report["at_body_entry"]["other"]["native_state"], "Green")
            self.assertNotEqual(report["at_body_entry"]["other"]["native_state"],
                                report["at_body_entry"]["ego"]["native_state"])


if __name__ == "__main__":
    unittest.main()
