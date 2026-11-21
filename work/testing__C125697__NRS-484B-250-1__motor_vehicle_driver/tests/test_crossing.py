import importlib.util
import json
import tempfile
import unittest
import subprocess
import sys
import shutil
import hashlib
import types
from unittest import mock
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("crossing_measurements")
control = load("signal_control")
comparison = load("signal_comparison")


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
            self.assertEqual(report["occupancy_intervals"]["other"][0]["entry_frame"], 101)
            self.assertFalse(report["other_exit_observed"])
            self.assertEqual(len(report["ego_speed_samples_while_other_inside"]), 2)

    def test_operating_signal_comparison_and_saved_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            for row in rows:
                row["signal_state"] = "Green"
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not observed Off"):
                measure.analyze(root)
            report = measure.analyze(root, signal_mode="operating")
            self.assertEqual(report["observed_signal_states"], ["Green"] * 4)
            output = root / "processed" / "crossing.json"
            done = subprocess.run([sys.executable, str(ROOT / "crossing_measurements.py"),
                                   str(root), str(output), "--signal-mode", "operating"],
                                  text=True, capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(output.read_text())["sources"], report["sources"])
            rows[2]["signal_state"] = "Off"
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not observed operating"):
                measure.analyze(root, signal_mode="operating")

    def test_other_already_inside_is_left_censored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            rows[0]["other"]["body_vertices_xy_m"] = body(1)
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "No observed pre-entry"):
                measure.analyze(root)
            report = measure.analyze(root, allow_other_initially_inside=True)
            self.assertTrue(report["other_initially_inside_observed"])
            self.assertIsNone(report["first_body_entry"]["other"])
            self.assertIsNone(report["other_entered_before_ego_observed"])
            self.assertIsNone(report["occupancy_intervals"]["other"][0]["entry_time_s"])

    def test_signal_comparison_rejects_changed_trajectory(self):
        with tempfile.TemporaryDirectory() as temp:
            off, operating = Path(temp) / "off", Path(temp) / "operating"
            off.mkdir()
            self.fixture(off)
            shutil.copytree(off, operating)
            rows = [json.loads(line) for line in (operating / "crossing_history.jsonl").read_text().splitlines()]
            for row in rows:
                row["signal_state"] = "Green"
            (operating / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            report = comparison.audit(off, operating)
            self.assertTrue(report["fixed_trajectories_observed"])
            self.assertEqual(report["off_states"], ["Off"])
            rows[2]["ego"]["speed_mps"] = 17
            (operating / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "trajectory or source changed"):
                comparison.audit(off, operating)

    def test_entry_order_comparison_isolates_motion(self):
        with tempfile.TemporaryDirectory() as temp:
            other_first, ego_first = Path(temp) / "other", Path(temp) / "ego"
            other_first.mkdir()
            self.fixture(other_first)
            shutil.copytree(other_first, ego_first)
            rows = [json.loads(line) for line in (ego_first / "crossing_history.jsonl").read_text().splitlines()]
            for row, ego_x, other_x in zip(rows, (-20, 1, 3, 5), (-20, -18, -10, 1)):
                for who, x in (("ego", ego_x), ("other", other_x)):
                    row[who]["body_vertices_xy_m"] = body(x)
                    row[who]["distance_to_intersection_m"] = max(0, -x)
            (ego_first / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            report = comparison.audit_entry_order(other_first, ego_first)
            self.assertTrue(report["fixed_junction_frames_signal_and_actor_identity_observed"])
            self.assertEqual(report["right_of_way_judgment"], "unresolved")
            rows[1]["native_signal_id"] = 28
            (ego_first / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Identified signal source changed"):
                comparison.audit_entry_order(other_first, ego_first)

    def test_saved_finalizer_derives_original_channels_and_rejects_stale_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            (root / "trace.jsonl").write_text("".join(json.dumps({"frame": row["carla_frame"],
                "time_s": row["time_s"]})+"\n" for row in frames))
            (root / "config.json").write_text(json.dumps({
                "selected_case_id": "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__off_other_enters_first",
                "cell_id": "C125697", "law_id": "NRS-484B-250-1",
                "recording_description": {"channels": [{"name": "ego_speed"}]}}))
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text('{"frame":100}\n')
            for name in measure.CAMERAS:
                (root / (name + ".mkv")).write_bytes(b"synthetic-test-placeholder")
            original = hashlib.sha256((root / "crossing_history.jsonl").read_bytes()).hexdigest()
            def physical(_, result):
                result.update(physical_checks={"status": "unverified"}, realized_observables={},
                              provenance_kind="diagnostic_fixture", diagnostic_fixture=True)
                return result
            def write_result(attempt, result):
                (attempt / "result.json").write_text(json.dumps(result))
            native_output = types.ModuleType("worker_exchange.native_output")
            native_output.physical_result = physical
            native_output.write_result = write_result
            worker_exchange = types.ModuleType("worker_exchange")
            worker_exchange.native_output = native_output
            with mock.patch.dict(sys.modules, {"worker_exchange": worker_exchange,
                                                "worker_exchange.native_output": native_output}):
                trace_path = root / "trace.jsonl"
                original_trace = trace_path.read_text()
                stale = [json.loads(line) for line in original_trace.splitlines()]
                stale[1]["frame"] = 999
                trace_path.write_text("".join(json.dumps(row)+"\n" for row in stale))
                with self.assertRaisesRegex(ValueError, "trace/video frame join"):
                    measure.finalize_saved(root, root / "analysis.json")
                trace_path.write_text(original_trace)
                analysis = measure.finalize_saved(root, root / "analysis.json")
            self.assertEqual(analysis["source_hashes"]["crossing_history.jsonl"], original)
            self.assertEqual(hashlib.sha256((root / "crossing_history.jsonl").read_bytes()).hexdigest(), original)
            rows = [json.loads(line) for line in (root / "channels/other_body_inside.jsonl").read_text().splitlines()]
            self.assertEqual([row["value"] for row in rows], [False, True, True, True])
            self.assertTrue((root / "evidence/crossing_history.jsonl").is_file())
            with self.assertRaisesRegex(ValueError, "Fresh saved-processing version"):
                measure.finalize_saved(root, root / "second-analysis.json")

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

    def test_opposing_left_intent_requires_original_geometry_and_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            context = json.loads((root / "junction_context.json").read_text())
            context["other_highway_id"] = context["ego_highway_id"]
            context["ego_approach_direction_xy"] = [1, 0]
            context["other_approach_direction_xy"] = [-1, 0]
            context["other_left_turn_intent_source"] = "Native route and original body/heading rows"
            (root / "junction_context.json").write_text(json.dumps(context))
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            for row, x in zip(rows, (14, 9, 7, 5)):
                row["other"]["body_vertices_xy_m"] = body(x)
                row["other"]["distance_to_intersection_m"] = max(0, x - 10)
                row["other"]["turn_intent"] = "left"
                row["other"]["heading_deg"] = 180.0
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "different highways"):
                measure.analyze(root)
            report = measure.analyze(root, opposing_left_exception=True)
            observed = report["opposing_left_exception_observations"]
            self.assertEqual(observed["approach_direction_dot"], -1)
            self.assertEqual(len(observed["other_heading_samples_deg"]), 4)
            self.assertGreater(observed["original_body_motion"]["other"]["projection_on_approach_direction_m"], 0)
            self.assertEqual(observed["statutory_exception_judgment"], "unresolved")
            reversed_rows = [json.loads(json.dumps(row)) for row in rows]
            for row, x in zip(reversed_rows, (-14, -12, -9, 1)):
                row["other"]["body_vertices_xy_m"] = body(x)
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in reversed_rows))
            with self.assertRaisesRegex(ValueError, "motion contradicts"):
                measure.analyze(root, opposing_left_exception=True)
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            rows[2]["other"].pop("turn_intent")
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "left-turn intent missing"):
                measure.analyze(root, opposing_left_exception=True)
            rows[2]["other"]["turn_intent"] = "left"
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            context["other_approach_direction_xy"] = [0, 1]
            (root / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "not opposite"):
                measure.analyze(root, opposing_left_exception=True)


if __name__ == "__main__":
    unittest.main()
