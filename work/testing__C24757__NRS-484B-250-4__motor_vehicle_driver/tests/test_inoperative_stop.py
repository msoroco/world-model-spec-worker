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
