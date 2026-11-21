import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location("inoperative_stop_measurements", Path(__file__).resolve().parents[1] / "inoperative_stop_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime" / "scenario_pipeline"))
import saved_finalizer
import comparison_audit
from worker_exchange.measurement_contract import verify_report


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class StopTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 6,
                   "native_signal_id": 13, "other_native_signal_id": 14,
                   "signal_head_video_source": "front-original",
                   "lane_governance_source": "native-affected-waypoints",
                   "stop_line_source": "native-map-and-front-video",
                   "other_stop_boundary": {"kind": "stop_line", "source": "other-approach-map-and-video"},
                   "installed_uncovered_vehicular_heads": True,
                   "stop_line_exists": True,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x = [-3, -3, -3, 1]
        other_x = [-3, -3, 1, 3]
        ego_speed = [2, 2, 0, 2]
        other_speed = [2, 0, 2, 2]
        rows = []
        for i in range(4):
            rows.append({"frame": 100 + i, "time_s": 1 + i * .05,
                         "native_signal_id": 13, "signal_state": "Off",
                         "other_native_signal_id": 14, "other_signal_state": "Off",
                         "ego": {"intersection_id": 6, "speed_mps": ego_speed[i],
                                 "front_to_stop_line_signed_m": 1 if i <= 2 else -1,
                                 "body_vertices_xy_m": body(ego_x[i])},
                         "other": {"intersection_id": 6, "speed_mps": other_speed[i],
                                   "front_to_stop_line_signed_m": 1 if i <= 1 else -1,
                                   "body_vertices_xy_m": body(other_x[i])}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_stop_order_and_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["ego_stopped_before_entry_observed"])
            self.assertTrue(report["other_completed_stop_before_ego_observed"])
            self.assertEqual(report["first_body_entry"]["other"]["frame"], 102)
            self.assertEqual(report["first_body_entry"]["ego"]["frame"], 103)
            self.assertTrue(report["other_body_inside_at_ego_entry_observed"])

    def test_other_halt_is_measured_at_its_own_crosswalk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            context_path = root / "junction_context.json"
            context = json.loads(context_path.read_text())
            context["other_stop_boundary"] = {"kind": "crosswalk", "source": "other-approach-map-and-video"}
            context_path.write_text(json.dumps(context))
            history_path = root / "vehicle_signal_history.jsonl"
            rows = [json.loads(line) for line in history_path.read_text().splitlines()]
            for row in rows:
                row["other"]["front_to_crosswalk_signed_m"] = row["other"].pop("front_to_stop_line_signed_m")
            rows[1]["other"]["front_to_crosswalk_signed_m"] = -0.5
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = measure.analyze(root)
            self.assertIsNone(report["first_full_halt_before_or_at_selected_boundary"]["other"])
            self.assertFalse(report["other_completed_stop_before_ego_observed"])

    def test_rejects_operating_signal_and_stale_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[2]["signal_state"] = "Red"
            (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Off state"):
                measure.analyze(root)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[2]["other_signal_state"] = "Green"
            (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "both identified signals"):
                measure.analyze(root)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[2]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_crosswalk_and_nearest_view_stop_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            context_path = root / "junction_context.json"
            history_path = root / "vehicle_signal_history.jsonl"
            context = json.loads(context_path.read_text())
            rows = [json.loads(line) for line in history_path.read_text().splitlines()]
            context["stop_line_exists"] = False
            context["crosswalk_exists"] = True
            context["crosswalk_source"] = "native-map-and-front-video-crosswalk"
            context["other_stop_boundary"] = {"kind": "crosswalk", "source": "other-approach-crosswalk"}
            for row in rows:
                for actor in ("ego", "other"):
                    row[actor]["front_to_crosswalk_signed_m"] = row[actor].pop("front_to_stop_line_signed_m")
            context_path.write_text(json.dumps(context))
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = measure.analyze(root)
            self.assertEqual(report["selected_stop_boundary"], "crosswalk")
            self.assertTrue(report["ego_stopped_before_entry_observed"])

            context["crosswalk_exists"] = False
            context["nearest_view_source"] = "native-map-and-original-view-review"
            context["other_stop_boundary"] = {"kind": "nearest_view", "source": "other-approach-view-review"}
            for row in rows:
                for actor in ("ego", "other"):
                    row[actor]["front_to_nearest_view_signed_m"] = row[actor].pop("front_to_crosswalk_signed_m")
            context_path.write_text(json.dumps(context))
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = measure.analyze(root)
            self.assertEqual(report["selected_stop_boundary"], "nearest_view")
            self.assertTrue(report["other_completed_stop_before_ego_observed"])

    def test_rejects_unsourced_boundary_hierarchy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            path = root / "junction_context.json"
            context = json.loads(path.read_text())
            context["stop_line_exists"] = False
            context["crosswalk_exists"] = False
            path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "nearest_view_source"):
                measure.analyze(root)

    def saved_fixture(self, root):
        attempt = root / "attempt"
        attempt.mkdir()
        self.fixture(attempt)
        (attempt / "capture").mkdir()
        (attempt / "capture" / "evidence.jsonl").write_text('{"frame":100}\n')
        for name in saved_finalizer.CAMERAS:
            (attempt / (name + ".mkv")).write_bytes(b"diagnostic-only")
        frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
        (attempt / "trace.jsonl").write_text("".join(json.dumps({"frame": f["carla_frame"],
            "time_s": f["time_s"], "position_m": [i, 0]}) + "\n" for i, f in enumerate(frames)))
        (attempt / "config.json").write_text(json.dumps({
            "cell_id": "C24757", "law_id": "NRS-484B-250-4",
            "selected_case_id": "testing__C24757__NRS-484B-250-4__motor_vehicle_driver__stop_line_other_prior",
            "recording_description": {"channels": ["ego_speed", "other_speed", "ego_stop_boundary_distance", "signal_state", "ego_position"]},
            "physical_completion": {"motion_source": "vehicle_signal_history.jsonl",
                                    "body_key": "ego.body_vertices_xy_m",
                                    "context_sources": ["junction_context.json"]}}))
        return attempt

    def test_saved_finalizer_derives_from_original_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt = self.saved_fixture(root)
            analysis = saved_finalizer.finalize_saved(attempt, root / "analysis.json")
            result = json.loads((attempt / "result.json").read_text())
            self.assertEqual(analysis["source_report"]["first_body_entry"]["ego"]["frame"], 103)
            channel = [json.loads(line) for line in (attempt / "channels/ego_speed.jsonl").read_text().splitlines()]
            self.assertEqual([row["value"] for row in channel], [2, 2, 0, 2])
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["measured_values"]["selected_stop_boundary"], "stop_line")
            contract = {"requirements": [
                {"output_key": "signal_states", "method": "measure_signal_states",
                 "value_type": "object", "inputs": list(analysis["source_report"]["sources"])},
                {"output_key": "post_stop_motion", "method": "measure_post_stop_motion",
                 "value_type": "object", "inputs": list(analysis["source_report"]["sources"])}]}
            checked = verify_report(contract, analysis, attempt)
            self.assertTrue(checked["signal_states"]["value"]["other_governing_off_all_frames"])
            self.assertEqual([s["speed_mps"] for s in
                              checked["post_stop_motion"]["value"]["post_halt_through_entry_samples"]], [2])
            self.assertEqual(analysis["format"], "worker-analysis-report")
            with self.assertRaisesRegex(ValueError, "Retain prior finalization"):
                saved_finalizer.finalize_saved(attempt, root / "another-analysis.json")

    def test_saved_finalizer_rejects_stale_trace_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt = self.saved_fixture(root)
            path = attempt / "trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]["frame"] = 999
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "trace/video frame join"):
                saved_finalizer.finalize_saved(attempt, root / "analysis.json")
            self.assertFalse((attempt / "channels").exists())
            self.assertFalse((attempt / "result.json").exists())

    def test_saved_finalizer_rejects_missing_case_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt = self.saved_fixture(root)
            (attempt / "junction_context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: junction_context.json"):
                saved_finalizer.finalize_saved(attempt, root / "analysis.json")
            self.assertFalse((attempt / "result.json").exists())
            self.assertFalse((attempt / "channels").exists())

    def test_independent_order_and_no_halt_comparisons(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            self.fixture(left)
            self.fixture(right)
            history = right / "vehicle_signal_history.jsonl"
            rows = [json.loads(line) for line in history.read_text().splitlines()]
            rows[1]["ego"]["speed_mps"] = 0
            rows[2]["ego"]["speed_mps"] = 2
            rows[1]["other"]["speed_mps"] = 2
            rows[2]["other"]["speed_mps"] = 0
            rows[2]["other"]["front_to_stop_line_signed_m"] = 1
            rows[2]["other"]["body_vertices_xy_m"] = body(-3)
            history.write_text("".join(json.dumps(row) + "\n" for row in rows))
            order = comparison_audit.audit_pair(left, right, "full_halt_order")
            self.assertTrue(order["observed_difference"])
            self.assertEqual((order["left"]["value"], order["right"]["value"]),
                             ("other_first", "ego_first"))
            self.assertFalse(order["legal_verdict_asserted"])
            with self.assertRaisesRegex(ValueError, "difference is absent"):
                comparison_audit.audit_pair(left, left, "full_halt_order")
            tied = [dict(row) for row in rows]
            tied[1] = json.loads(json.dumps(rows[1]))
            tied[1]["other"]["speed_mps"] = 0
            history.write_text("".join(json.dumps(row) + "\n" for row in tied))
            with self.assertRaisesRegex(ValueError, "Distinct observed full-halt times"):
                comparison_audit.audit_pair(left, right, "full_halt_order")
            rows[1]["ego"]["speed_mps"] = 2
            rows[2]["ego"]["speed_mps"] = 0.1
            history.write_text("".join(json.dumps(row) + "\n" for row in rows))
            halt = comparison_audit.audit_pair(left, right, "ego_full_halt")
            self.assertTrue(halt["left"]["value"])
            self.assertFalse(halt["right"]["value"])

    def test_boundary_comparison_holds_junction_fixed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            self.fixture(left)
            self.fixture(right)
            for attempt in (left, right):
                (attempt / "trace.jsonl").write_text('{"frame":1,"time_s":1.0}\n')
                (attempt / "capture").mkdir(exist_ok=True)
                (attempt / "capture/evidence.jsonl").write_text('{"frame":1,"time_s":1.0}\n')
            context_path = right / "junction_context.json"
            history_path = right / "vehicle_signal_history.jsonl"
            context = json.loads(context_path.read_text())
            context.update(stop_line_exists=False, crosswalk_exists=True,
                           crosswalk_source="native-map-and-front-video-crosswalk",
                           other_stop_boundary={"kind": "crosswalk", "source": "other-approach-crosswalk"})
            context_path.write_text(json.dumps(context))
            rows = [json.loads(line) for line in history_path.read_text().splitlines()]
            for row in rows:
                for who in ("ego", "other"):
                    row[who]["front_to_crosswalk_signed_m"] = row[who].pop("front_to_stop_line_signed_m")
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            audit = comparison_audit.audit_pair(left, right, "stopping_reference")
            self.assertEqual((audit["left"]["value"], audit["right"]["value"]),
                             ("stop_line", "crosswalk"))
            context["native_signal_id"] = 99
            context_path.write_text(json.dumps(context))
            for row in rows:
                row["native_signal_id"] = 99
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "Fixed Native junction"):
                comparison_audit.audit_pair(left, right, "stopping_reference")


if __name__ == "__main__":
    unittest.main()


# Native source-row fixtures kept with the saved stop measurements.
import importlib.util
import types
import unittest
import json
import tempfile
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_stop_sources", Path(__file__).resolve().parents[1] / "native_stop_sources.py")
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)
measurement_spec = importlib.util.spec_from_file_location(
    "inoperative_stop_measurements", Path(__file__).resolve().parents[1] / "inoperative_stop_measurements.py")
measure = importlib.util.module_from_spec(measurement_spec)
measurement_spec.loader.exec_module(measure)


class Actor:
    def __init__(self, x, speed):
        self.x, self.speed = x, speed
        self.bounding_box = types.SimpleNamespace(get_world_vertices=self.vertices)

    def get_transform(self):
        return None

    def vertices(self, transform):
        return [types.SimpleNamespace(x=self.x + dx, y=dy)
                for dx, dy in [(0, -1), (0, 1), (-2, -1), (-2, 1)]]

    def get_velocity(self):
        return types.SimpleNamespace(x=self.speed, y=0, z=0)


class SourceTests(unittest.TestCase):
    def site(self, kind):
        return {"intersection_id": 6, "native_signal_id": 13, "other_native_signal_id": 14,
                "stop_boundary": {"kind": kind, "source": "reviewed-map-and-original-video",
                                  "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]},
                "other_stop_boundary": {"kind": kind, "source": "other-approach-map-and-video",
                                        "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]}}

    def other_signal(self, state="Off"):
        return types.SimpleNamespace(id=14, get_state=lambda: state)

    def test_body_front_signed_distance_and_original_off_readback(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        for kind, field in [("stop_line", "front_to_stop_line_signed_m"),
                            ("crosswalk", "front_to_crosswalk_signed_m"),
                            ("nearest_view", "front_to_nearest_view_signed_m")]:
            row = sources.source_row(100, 1.0, signal, Actor(-3, 0), Actor(-5, 2), self.site(kind), self.other_signal())
            self.assertEqual(row["ego"][field], 3)
            self.assertEqual(row["other"][field], 5)
            self.assertEqual(row["signal_state"], "Off")
            self.assertEqual(len(row["ego"]["body_vertices_xy_m"]), 4)

    def test_other_approach_uses_its_own_boundary_geometry(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        site = self.site("stop_line")
        site["other_stop_boundary"]["point_xy_m"] = [0, -5]
        site["other_stop_boundary"]["upstream_normal_xy"] = [0, 1]
        row = sources.source_row(100, 1.0, signal, Actor(-3, 0), Actor(-5, 0), site, self.other_signal())
        self.assertEqual(row["ego"]["front_to_stop_line_signed_m"], 3)
        self.assertEqual(row["other"]["front_to_stop_line_signed_m"], 4)

    def test_rejects_unreviewed_geometry_and_operating_head(self):
        site = self.site("stop_line")
        site["stop_boundary"]["source"] = ""
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        with self.assertRaisesRegex(ValueError, "Sourced statutory stop boundary"):
            sources.source_row(100, 1, signal, Actor(-3, 0), Actor(-5, 2), site, self.other_signal())
        site = self.site("stop_line")
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Green")
        with self.assertRaisesRegex(ValueError, "Off readback"):
            sources.source_row(100, 1, signal, Actor(-3, 0), Actor(-5, 2), site, self.other_signal())
        site = self.site("stop_line")
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        with self.assertRaisesRegex(ValueError, "Off readback"):
            sources.source_row(100, 1, signal, Actor(-3, 0), Actor(-5, 2), site, self.other_signal("Green"))

    def test_native_source_rows_feed_saved_measurement(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        site = self.site("stop_line")
        context = {"native_map_id": "TownX", "intersection_id": 6,
                   "native_signal_id": 13, "other_native_signal_id": 14,
                   "signal_head_video_source": "front-original",
                   "lane_governance_source": "native-affected-waypoints",
                   "stop_line_source": "reviewed-map-and-original-video",
                   "other_stop_boundary": {"kind": "stop_line", "source": "other-approach-map-and-video"},
                   "installed_uncovered_vehicular_heads": True,
                   "stop_line_exists": True,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        ego = [Actor(-3, 2), Actor(-3, 2), Actor(-3, 0), Actor(1, 2)]
        other = [Actor(-3, 2), Actor(-3, 0), Actor(1, 2), Actor(3, 2)]
        rows = [sources.source_row(100 + i, 1 + i * .05, signal, ego[i], other[i], site, self.other_signal())
                for i in range(4)]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "junction_context.json").write_text(json.dumps(context))
            (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            report = measure.analyze(root)
        self.assertTrue(report["other_completed_stop_before_ego_observed"])
        self.assertTrue(report["other_body_inside_at_ego_entry_observed"])


if __name__ == "__main__":
    unittest.main()


# Consolidated from test_native_inoperative_control.py to stay within the return file cap.
import importlib.util
import types
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_inoperative_control", Path(__file__).resolve().parents[1] / "native_inoperative_control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Light:
    def __init__(self, ident, lane, state="Green", ignores_off=False, frozen=False):
        self.id, self.lane, self.state, self.frozen, self.ignores_off = ident, lane, state, frozen, ignores_off

    def get_affected_lane_waypoints(self):
        return [types.SimpleNamespace(road_id=self.lane[0], lane_id=self.lane[1])]

    def get_state(self):
        return self.state

    def set_state(self, state):
        if state != "Off" or not self.ignores_off:
            self.state = state

    def freeze(self, value):
        self.frozen = value

    def is_frozen(self):
        return self.frozen


class World:
    def __init__(self, lights):
        self.lights, self.ticks = lights, 0

    def get_actors(self):
        return types.SimpleNamespace(filter=lambda pattern: self.lights)

    def tick(self):
        self.ticks += 1


class ControlActor:
    def __init__(self, speed):
        self.speed, self.commands = speed, []

    def get_velocity(self):
        return types.SimpleNamespace(x=self.speed, y=0, z=0)

    def apply_control(self, command):
        self.commands.append(command)


class NativeControlTests(unittest.TestCase):
    def test_rolling_comparison_preserves_observed_motion(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = ControlActor(2.0)
        planner = control.RollingController(target_speed_mps=3.0, minimum_speed_mps=1.0)
        row = planner.step(carla, actor, 21, -0.1)
        self.assertTrue(row["rolling_comparison"])
        self.assertEqual(row["speed_mps"], 2.0)
        self.assertGreater(row["throttle"], 0)
        self.assertEqual(row["brake"], 0)
        actor.speed = 0.0
        self.assertEqual(planner.step(carla, actor, 22, -0.2)["speed_mps"], 0.0)
        with self.assertRaisesRegex(ValueError, "Bounded rolling"):
            control.RollingController(target_speed_mps=3.0, minimum_speed_mps=4.0)

    def test_all_governed_heads_off_and_restored_after_capture(self):
        lights = [Light(10, (1, -1)), Light(20, (2, -1), "Red", frozen=True)]
        world = World(lights)
        selected = control.governing_lights(world, [[1, -1], [2, -1]])
        with control.all_heads_off(world, selected, types.SimpleNamespace(Off="Off")):
            self.assertEqual([light.state for light in lights], ["Off", "Off"])
            self.assertTrue(all(light.frozen for light in lights))
        self.assertEqual([light.state for light in lights], ["Green", "Red"])
        self.assertEqual([light.frozen for light in lights], [False, True])
        self.assertEqual(world.ticks, 2)

    def test_rejects_duplicate_governance_and_failed_off_readback(self):
        world = World([Light(10, (1, -1)), Light(20, (2, -1), ignores_off=True)])
        with self.assertRaisesRegex(ValueError, "governing Native light"):
            control.governing_lights(world, [[1, -1], [3, -1]])
        lights = control.governing_lights(world, [[1, -1], [2, -1]])
        with self.assertRaisesRegex(ValueError, "Off readback"):
            with control.all_heads_off(world, lights, types.SimpleNamespace(Off="Off")):
                pass
        self.assertEqual([light.state for light in lights], ["Green", "Green"])

    def test_measured_halt_and_order_gate_release(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = ControlActor(3)
        planner = control.StopController(release_frame=102, target_speed_mps=5)
        pre = planner.step(carla, actor, 100, 3)
        self.assertFalse(pre["held"])
        hold = planner.step(carla, actor, 101, 0.2)
        self.assertTrue(hold["held"])
        self.assertEqual(hold["brake"], 1)
        actor.speed = 0
        stopped = planner.step(carla, actor, 102, 0.2, release_condition=False)
        self.assertEqual(stopped["full_halt_frame"], 102)
        self.assertTrue(stopped["held"])
        released = planner.step(carla, actor, 103, 0.2, release_condition=True)
        self.assertFalse(released["held"])
        self.assertGreater(released["throttle"], 0)

    def test_rejects_crossing_without_measured_halt(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        planner = control.StopController(release_frame=0, target_speed_mps=5)
        with self.assertRaisesRegex(ValueError, "without measured full halt"):
            planner.step(carla, ControlActor(2), 1, -0.1)

    def test_brakes_before_boundary_and_requires_observed_zero(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = ControlActor(6)
        planner = control.StopController(release_frame=10, target_speed_mps=6)
        far = planner.step(carla, actor, 0, 12)
        near = planner.step(carla, actor, 1, 1.0)
        self.assertEqual(far["brake"], 0)
        self.assertGreater(near["brake"], 0)
        self.assertEqual(near["throttle"], 0)
        actor.speed = 0.005
        crawl = planner.step(carla, actor, 11, 0.2)
        self.assertIsNone(crawl["full_halt_frame"])
        self.assertTrue(crawl["held"])
        actor.speed = 0
        stopped = planner.step(carla, actor, 12, 0.2)
        self.assertEqual(stopped["full_halt_frame"], 12)
        released = planner.step(carla, actor, 13, 0.2)
        self.assertFalse(released["held"])

    def test_rejects_unbounded_approach_deceleration(self):
        with self.assertRaisesRegex(ValueError, "approach deceleration"):
            control.StopController(10, 5, approach_deceleration_mps2=0)


if __name__ == "__main__":
    unittest.main()


# Consolidated from test_native_site_contract.py to stay within the return file cap.
import hashlib
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


spec = importlib.util.spec_from_file_location(
    "native_site_contract", Path(__file__).resolve().parents[1] / "native_site_contract.py")
site_contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_contract)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_runner


def write_bound(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class SiteTests(unittest.TestCase):
    def test_primary_packet_is_authored_and_cpu_validated(self):
        base = Path(__file__).resolve().parents[1]
        config = json.loads((base / "config.json").read_text())
        receipt = native_runner.validate_capture_plan(config, base)
        self.assertEqual(receipt["selected_boundary"], "stop_line")
        self.assertFalse(receipt["native_site_verified"])
        self.assertFalse(receipt["physical_head_visibility_verified"])
        self.assertEqual(config["site"]["native_signal_id"], None)
        self.assertEqual(config["site"]["map_signal_id"], 2475701)
        pipeline_root = Path(__file__).resolve().parents[3] / "runtime" / "scenario_pipeline"
        sys.path.insert(0, str(pipeline_root))
        from worker_exchange.measurement_contract import validate
        contract = json.loads((base / "measurement-contract.json").read_text())
        plan = json.loads((base / "case-plan.json").read_text())
        rows = validate(contract, plan["requirement_dispositions"],
                        (base / "saved_finalizer.py").read_text(), config["selected_case_id"])
        self.assertEqual(len(rows), 6)

    def test_every_planned_case_binds_a_distinct_branch_construction(self):
        base = Path(__file__).resolve().parents[1]
        plan = json.loads((base / "case-plan.json").read_text())
        self.assertEqual(len(plan["cases"]), 6)
        for case in plan["cases"]:
            candidate = case["construction_candidate"]
            path = base / candidate["map_path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             candidate["map_sha256"])
            self.assertEqual(candidate["ordered_approach_lanes"],
                             [[158190, -1], [158194, -1]])
            self.assertEqual(candidate["map_signal_ids"], [2475701, 2475702])
            suffix = case["case_id"].rsplit("__", 1)[-1]
            if suffix == "stop_line_no_halt":
                self.assertEqual(candidate["ego_control"], "rolling_comparison")
            else:
                self.assertEqual(candidate["ego_control"], "full_halt")
            if suffix.startswith("crosswalk"):
                self.assertEqual(candidate["ego_stop_reference"], "crosswalk")
            elif suffix.startswith("nearest_view"):
                self.assertEqual(candidate["ego_stop_reference"], "nearest_view")
            else:
                self.assertEqual(candidate["ego_stop_reference"], "stop_line")
        self.assertEqual(plan["cases"][1]["construction_candidate"]["other_release_rule"],
                         "after_other_clear")
        self.assertEqual(plan["cases"][2]["construction_candidate"]["ego_release_rule"],
                         "after_partner_entry")

    def test_authored_two_head_map_has_distinct_governed_junction_approaches(self):
        path = Path(__file__).resolve().parents[1] / "inoperative-two-head.xodr"
        root = ET.parse(path).getroot()
        roads = {int(road.get("id")): road for road in root.findall("road")}
        self.assertEqual(len(roads), 6)
        expected = {158190: "2475701", 158194: "2475702"}
        for road_id, signal_id in expected.items():
            road = roads[road_id]
            self.assertEqual(road.find("link/successor").get("elementType"), "junction")
            self.assertEqual(road.find("link/successor").get("elementId"), "158191")
            signals = road.findall("signals/signal")
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0].get("id"), signal_id)
            self.assertEqual(signals[0].get("dynamic"), "yes")
            self.assertEqual((signals[0].find("validity").get("fromLane"),
                              signals[0].find("validity").get("toLane")), ("-1", "-1"))
            self.assertGreater(float(signals[0].get("s")), 0)
            self.assertLess(float(signals[0].get("s")), float(road.get("length")))
        controls = {c.get("signalId") for c in root.findall("controller/control")}
        self.assertEqual(controls, set(expected.values()))
        junction = root.find("junction")
        self.assertEqual(junction.get("id"), "158191")
        connections = {(int(c.get("incomingRoad")), int(c.get("connectingRoad"))):
                       (c.find("laneLink").get("from"), c.find("laneLink").get("to"))
                       for c in junction.findall("connection")}
        self.assertEqual(connections[(158190, 158192)], ("-1", "-1"))
        self.assertEqual(connections[(158194, 158195)], ("-1", "-1"))
        pipeline_root = Path(__file__).resolve().parents[3] / "runtime" / "scenario_pipeline"
        sys.path.insert(0, str(pipeline_root))
        from traffic_spec_adapter.geometry import static_map
        observations, shapes, lane_keys = static_map(path, junctions=True)
        self.assertEqual(len(observations), len(shapes))
        self.assertIn((158190, 0, -1), lane_keys)
        self.assertIn((158194, 0, -1), lane_keys)
        self.assertNotEqual(lane_keys[(158190, 0, -1)], lane_keys[(158194, 0, -1)])

    def test_reviewed_authored_map_binding_and_governance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            map_bytes = (Path(__file__).resolve().parents[1] / "inoperative-stop-line.xodr").read_bytes()
            (root / "site.xodr").write_bytes(map_bytes)
            config = self.fixture(root)
            site = config["site"]
            site.update(native_map_name="C24757 two-head stop-line construction candidate",
                        native_map_xodr={"path": "site.xodr", "sha256": hashlib.sha256(map_bytes).hexdigest()},
                        intersection_id=158191, native_signal_id=2475701,
                        other_native_signal_id=2475702,
                        entrance_road_lanes=[[158190, -1], [158194, -1]])
            docs = {}
            for role, fields in site_contract.SOURCE_CLAIMS.items():
                claims = {field: site[field] for field in fields}
                if role == "map_geometry":
                    claims["native_map_xodr"] = site["native_map_xodr"]
                docs[role] = write_bound(root, role + ".json", {
                    "format": "worker-inoperative-junction-source", "source_role": role,
                    "review_basis": "synthetic CPU fixture only", "reviewed_site_fields": claims})
            config["site_review"] = write_bound(root, "review.json", {
                "format": "worker-inoperative-junction-review", "review_status": "reviewed_candidate",
                "site": site, "source_documents": docs})
            self.assertFalse(site_contract.validate_site(config, root)["native_site_verified"])
            site.update(native_signal_id=None, other_native_signal_id=None,
                        map_signal_id=2475701, other_map_signal_id=2475702)
            claims = {field: site[field] for field in site_contract.SOURCE_CLAIMS["signal_governance"]}
            claims.update(map_signal_id=2475701, other_map_signal_id=2475702)
            docs["signal_governance"] = write_bound(root, "signal_governance.json", {
                "format": "worker-inoperative-junction-source",
                "source_role": "signal_governance", "review_basis": "synthetic CPU fixture only",
                "reviewed_site_fields": claims})
            config["site_review"] = write_bound(root, "review.json", {
                "format": "worker-inoperative-junction-review", "review_status": "reviewed_candidate",
                "site": site, "source_documents": docs})
            self.assertFalse(site_contract.validate_site(config, root)["native_site_verified"])
            (root / "site.xodr").write_bytes(map_bytes + b"\n")
            with self.assertRaisesRegex(ValueError, "Native OpenDRIVE source missing or changed"):
                site_contract.validate_site(config, root)

    def test_stopping_reference_variants_have_separate_native_geometry(self):
        pipeline_root = Path(__file__).resolve().parents[3] / "runtime" / "scenario_pipeline"
        sys.path.insert(0, str(pipeline_root))
        from traffic_spec_adapter.geometry import painted_map_objects, static_map
        base = Path(__file__).resolve().parents[1]
        for variant, kind in (("stop-line", "stop_line"),
                              ("crosswalk", "crosswalk"), ("nearest-view", None)):
            path = base / ("inoperative-two-head.xodr" if variant == "nearest-view" else
                           "inoperative-" + variant + ".xodr")
            observations = painted_map_objects(path)
            self.assertEqual([row["region"]["kind"] for row in observations],
                             [] if kind is None else [kind, kind])
            if observations:
                self.assertEqual([row["source"]["road_id"] for row in observations],
                                 [158190, 158194])
                self.assertTrue(all(row["shape"].area > 0 for row in observations))
                self.assertTrue(all(row["shape"].bounds[2] < -8 or
                                    row["shape"].bounds[3] < -8 for row in observations))
            _, _, lane_keys = static_map(path, junctions=True)
            self.assertIn((158190, 0, -1), lane_keys)
            self.assertIn((158194, 0, -1), lane_keys)

    def fixture(self, root, kind="stop_line"):
        site = {"native_map_name": "DiagnosticTown", "intersection_id": 6,
                "native_signal_id": 13, "other_native_signal_id": 14,
                "installed_uncovered_vehicular_heads": True,
                "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]],
                "entrance_road_lanes": [[1, -1], [2, -1]],
                "stop_line_exists": kind == "stop_line",
                "crosswalk_exists": kind == "crosswalk",
                "stop_boundary": {"kind": kind, "source": "map-and-original-front-view",
                                  "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]},
                "other_stop_line_exists": True, "other_crosswalk_exists": False,
                "other_stop_boundary": {"kind": "stop_line", "source": "other-approach-map-and-view",
                                        "point_xy_m": [0, 0], "upstream_normal_xy": [0, -1]},
                "approach_visibility_source": "native-map-and-front-view"}
        docs = {}
        for role, fields in site_contract.SOURCE_CLAIMS.items():
            document = {"format": "worker-inoperative-junction-source", "source_role": role,
                        "review_basis": "synthetic CPU fixture only",
                        "reviewed_site_fields": {field: site[field] for field in fields}}
            docs[role] = write_bound(root, role + ".json", document)
        review = {"format": "worker-inoperative-junction-review",
                  "review_status": "reviewed_candidate", "site": site, "source_documents": docs}
        config = {"site": site, "site_review": write_bound(root, "review.json", review)}
        return config

    def test_three_stopping_reference_branches(self):
        for kind in ("stop_line", "crosswalk", "nearest_view"):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = self.fixture(root, kind)
                receipt = site_contract.validate_site(config, root)
                self.assertEqual(receipt["selected_boundary"], kind)
                self.assertFalse(receipt["native_site_verified"])

    def test_rejects_tampered_source_and_unsourced_boundary_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            document = root / "signal_heads.json"
            document.write_text(document.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site"]["stop_line_exists"] = False
            with self.assertRaisesRegex(ValueError, "differs from bound review packet"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site_review"]["path"] = "../review.json"
            with self.assertRaisesRegex(ValueError, "escapes packet root"):
                site_contract.validate_site(config, root)

    def test_other_approach_boundary_must_be_sourced_and_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            self.assertEqual(config["site"]["other_stop_boundary"]["upstream_normal_xy"], [0, -1])
            config["site"]["other_stop_boundary"]["upstream_normal_xy"] = [-1, 0]
            with self.assertRaisesRegex(ValueError, "differs from bound review packet"):
                site_contract.validate_site(config, root)

    def test_two_actor_four_camera_capture_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            config.update(cell_id="C24757", law_id="NRS-484B-250-4",
                selected_case_id="testing__C24757__NRS-484B-250-4__motor_vehicle_driver__stop_line_other_prior",
                required_atoms=[], rate_hz=20, duration_s=40,
                physical_completion={"motion_source": "vehicle_signal_history.jsonl",
                                     "body_key": "ego.body_vertices_xy_m",
                                     "context_sources": ["junction_context.json"]},
                actor_routes={"ego": {"spawn": [1, -1, 10.0], "target_xy_m": [[-15, 0], [15, 0]],
                                       "release_frame": 50, "release_rule": "after_other_clear",
                                       "target_speed_mps": 4.0},
                              "other": {"spawn": [2, -1, 10.0], "target_xy_m": [[0, -15], [0, 15]],
                                        "release_frame": 30, "release_rule": "scheduled",
                                        "target_speed_mps": 4.0}},
                cameras=[{"name": name, "width": size[0], "height": size[1],
                          "fov_deg": 90, "pose": {"x": 0, "y": 0, "z": 10,
                                                 "yaw": 0, "pitch": -20}}
                         for name, size in native_runner.SIZES.items()])
            receipt = native_runner.validate_capture_plan(config, root)
            self.assertFalse(receipt["native_site_verified"])
            config["cameras"][2]["width"] = 640
            with self.assertRaisesRegex(ValueError, "dimensions"):
                native_runner.validate_capture_plan(config, root)
            config["cameras"][2]["width"] = 1280
            config["actor_routes"]["other"]["spawn"] = [1, -1, 10.0]
            with self.assertRaisesRegex(ValueError, "distinct Native approaches"):
                native_runner.validate_capture_plan(config, root)
            config["actor_routes"]["other"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["ego"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["other"]["spawn"] = [1, -1, 10.0]
            with self.assertRaisesRegex(ValueError, "ordered signal-governed"):
                native_runner.validate_capture_plan(config, root)
            config["actor_routes"]["ego"]["spawn"] = [1, -1, 10.0]
            config["actor_routes"]["other"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["other"]["release_rule"] = "after_other_clear"
            with self.assertRaisesRegex(ValueError, "Circular Native release"):
                native_runner.validate_capture_plan(config, root)
            config["actor_routes"]["ego"]["release_rule"] = "scheduled"
            self.assertFalse(native_runner.validate_capture_plan(config, root)["native_site_verified"])
            config["actor_routes"]["ego"]["release_rule"] = "after_partner_entry"
            config["actor_routes"]["other"]["release_rule"] = "scheduled"
            self.assertFalse(native_runner.validate_capture_plan(config, root)["native_site_verified"])
            config["actor_routes"]["ego"]["stop_policy"] = "rolling"
            with self.assertRaisesRegex(ValueError, "Rolling policy limited"):
                native_runner.validate_capture_plan(config, root)
            config["selected_case_id"] = config["selected_case_id"].replace(
                "__stop_line_other_prior", "__stop_line_no_halt")
            self.assertFalse(native_runner.validate_capture_plan(config, root)["native_site_verified"])


if __name__ == "__main__":
    unittest.main()
