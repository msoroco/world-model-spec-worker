import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "heavy_lane_source.py"
spec = importlib.util.spec_from_file_location("heavy_lane_source", MODULE)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
sys.path.insert(0, str(MODULE.parent))
import runner
import heavy_lane_finalizer as finalizer
import heavy_physical_outcome as physical
import heavy_lifecycle_fixture as lifecycle


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Box:
    def __init__(self, x):
        self.x = x

    def get_world_vertices(self, transform):
        return [Point(self.x + dx, dy, z) for z in (0, 2)
                for dx, dy in ((-2, -1), (2, -1), (2, 1), (-2, 1))]


class Actor:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.bounding_box = Box(x)

    def get_transform(self):
        return object()

    def get_velocity(self):
        return Point(4, 0)


class Transform:
    location = Point(0, 0)

    def get_forward_vector(self):
        return Point(1, 0)


class Marking:
    type = "Solid"


class Waypoint:
    road_id, lane_id, lane_width = 8, -2, 3.5
    left_lane_marking = right_lane_marking = Marking()
    transform = Transform()

    lane_type = "Driving"

    def get_left_lane(self):
        return getattr(self, "left", None)

    def get_right_lane(self):
        return getattr(self, "right", None)


class HeavyLaneSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.survey = self.root / "survey.json"
        self.survey.write_text(json.dumps({"lanes": [
            {"road_id": 8, "lane_id": i, "direction": "east",
             "left_marking": "Solid", "right_marking": "Solid"}
            for i in (-1, -2, -3)]}))
        self.sha = hashlib.sha256(self.survey.read_bytes()).hexdigest()

    def recorder(self, components=None, overtaken=None):
        return source.HeavyLaneSourceRecorder(
            self.root, components or [Actor(1, 0), Actor(2, -5)],
            survey_path=self.survey, survey_sha256=self.sha, overtaken=overtaken)

    def test_two_component_original_tick_and_participant(self):
        with self.recorder(overtaken=Actor(3, 10)) as recorder:
            row = recorder.append(20, 1.0, Waypoint())
            recorder.append(21, 1.05, Waypoint())
        self.assertEqual(len(row["heavy_vehicle_components"]), 2)
        self.assertEqual(row["overtaken"]["actor_id"], 3)
        self.assertEqual(row["lane"]["lane_id"], -2)
        self.assertEqual(len(self.root.joinpath("heavy_lane_sources.jsonl").read_text().splitlines()), 2)

    def test_component_corner_clearance_and_crossing(self):
        with self.recorder() as recorder:
            row = recorder.append(20, 1.0, Waypoint())
        measured = source.measure_footprint(row)
        self.assertEqual(measured["frame"], 20)
        self.assertAlmostEqual(measured["minimum_clearance_m"], 0.75)
        row["heavy_vehicle_components"][1]["corners_xy_m"][0][1] = 2.25
        crossing = source.measure_footprint(row)
        self.assertAlmostEqual(crossing["minimum_clearance_m"], -0.5)
        self.assertLess(crossing["component_clearances"][1]["left_clearance_m"], 0)

    def test_missing_original_component_rejected(self):
        with self.recorder() as recorder:
            row = recorder.append(20, 1.0, Waypoint())
        row["heavy_vehicle_components"] = []
        with self.assertRaisesRegex(ValueError, "Missing original heavy body"):
            source.measure_footprint(row)

    def test_three_lane_site_source_and_two_lane_negative(self):
        lane_a, lane_b, lane_c = (Waypoint(), Waypoint(), Waypoint())
        for index, lane in enumerate((lane_a, lane_b, lane_c), start=1):
            lane.lane_id = -index
            lane.s = 5.0
        lane_a.right = lane_b
        lane_b.left, lane_b.right = lane_a, lane_c
        lane_c.left = lane_b

        class Map:
            name = "NativeThreeLane"

            def generate_waypoints(self, spacing):
                return [lane_a]

        origin, survey = source.select_three_lane_site(Map())
        self.assertIs(origin, lane_a)
        self.assertEqual(len(survey["lanes"]), 3)
        sha = source.save_three_lane_survey(self.root / "native-survey.json", survey)
        self.assertEqual(source._survey(self.root / "native-survey.json", sha), survey)
        lane_b.right = None
        with self.assertRaisesRegex(ValueError, "three-driving-lane"):
            source.select_three_lane_site(Map())

    def test_native_runner_check_route_and_control(self):
        config = json.loads(MODULE.with_name("config.json").read_text())
        runner.check_config(config)
        changed = json.loads(json.dumps(config))
        changed["engineering"]["heavy_blueprint"] = "vehicle.tesla.model3"
        with self.assertRaisesRegex(ValueError, "heavy truck blueprint"):
            runner.check_config(changed)

        class RoutePoint(Waypoint):
            def __init__(self, step):
                self.step = step
                self.lane_id = -2
                self.s = step
                self.transform = type("T", (), {"location": Point(step * 2, 0)})()

            def next(self, spacing):
                return [RoutePoint(self.step + 1)]

        route = runner.route_from_site(RoutePoint(0), step_m=2, count=4)
        self.assertEqual([wp.s for wp in route], [0, 1, 2, 3])

        class Vehicle(Actor):
            def get_transform(self):
                return type("T", (), {"location": Point(0, 0),
                                      "get_forward_vector": lambda self: Point(1, 0)})()

        command = runner.control_step(Vehicle(1, 0), route[1], 4)
        self.assertEqual(command["steer"], 0)
        self.assertEqual(command["throttle"], 0)
        self.assertEqual(command["brake"], 0)

    def test_saved_original_join_and_missing_camera_negative(self):
        (self.root / "config.json").write_bytes(MODULE.with_name("config.json").read_bytes())
        with self.recorder() as recorder:
            first = recorder.append(20, 0.0, Waypoint())
        survey = self.root / "native_three_lane_survey.json"
        survey.write_bytes(self.survey.read_bytes())
        rows = []
        for index in range(160):
            row = json.loads(json.dumps(first))
            row["frame"], row["time_s"] = 20 + index, index / 20
            rows.append(row)
        (self.root / "heavy_lane_sources.jsonl").write_text("".join(
            json.dumps(row) + "\n" for row in rows))
        (self.root / "trace.jsonl").write_text("".join(
            json.dumps({"frame": 20 + index, "time_s": index / 20}) + "\n"
            for index in range(160)))
        (self.root / "video_frames.jsonl").write_text("".join(
            json.dumps({"video_frame": index, "carla_frame": 20 + index,
                        "time_s": index / 20}) + "\n" for index in range(160)))
        for name in finalizer.CAMERA_FILES:
            (self.root / name).write_bytes(b"source-shaped CPU test bytes")
        report = finalizer.analyze(self.root)
        result = finalizer.build_result(self.root, report)
        self.assertEqual(len(report["measurements"]["heavy_lane_footprint"]["value"]["frames"]), 160)
        self.assertEqual(len(result["recording_evidence"]), 6)
        self.assertEqual(result["realized_observables"]["heavy_lane_minimum_clearance_m"]
                         ["sample_window_s"], [0.0, 159 / 20])
        self.assertFalse(result["physical_acceptance_claimed"])
        (self.root / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: overview"):
            finalizer.analyze(self.root, write_channels=False)
        (self.root / "overview.mkv").write_bytes(b"source-shaped CPU test bytes")
        rows[0]["survey_sha256"] = "0" * 64
        (self.root / "heavy_lane_sources.jsonl").write_text("".join(
            json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "survey source hash differs"):
            finalizer.analyze(self.root, write_channels=False)

    def test_stale_survey_rejected(self):
        self.survey.write_text(self.survey.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            self.recorder()

    def test_missing_lane_allocation_rejected(self):
        self.survey.write_text(json.dumps({"lanes": [{"road_id": 8, "lane_id": -2}]}))
        self.sha = hashlib.sha256(self.survey.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "three governed lanes"):
            self.recorder()

    def test_outside_survey_and_missing_frame_rejected(self):
        with self.recorder() as recorder:
            recorder.append(20, 1.0, Waypoint())
            with self.assertRaisesRegex(ValueError, "Missing or unordered"):
                recorder.append(22, 1.1, Waypoint())
            other = Waypoint()
            other.lane_id = -4
            with self.assertRaisesRegex(ValueError, "outside source-surveyed"):
                recorder.append(21, 1.05, other)

    def test_body_and_marking_errors_rejected(self):
        with self.recorder() as recorder:
            actor = recorder.ego_components[0]
            actor.bounding_box.get_world_vertices = lambda transform: [Point(0, 0)]
            with self.assertRaisesRegex(ValueError, "eight finite"):
                recorder.append(20, 1.0, Waypoint())
            waypoint = Waypoint()
            waypoint.left_lane_marking = None
            with self.assertRaisesRegex(ValueError, "Missing Native lane marking"):
                recorder.append(20, 1.0, waypoint)

    def test_physical_case_events_and_missing_pixel_review(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        frames = [{"frame": 1, "time_s": 0.0, "minimum_clearance_m": 0.5,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": 0.5,
                                             "right_clearance_m": 0.5}]},
                  {"frame": 2, "time_s": 0.05, "minimum_clearance_m": -0.2,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": -0.2,
                                             "right_clearance_m": 1.2}]}]
        trace = [{"frame": 1, "time_s": 0.0, "position": {"x": 0.0, "y": 0.0}},
                 {"frame": 2, "time_s": 0.05, "position": {"x": 1.0, "y": 0.0}}]
        sources = {name: name for name in ("native_three_lane_survey.json",
                    "heavy_lane_sources.jsonl", "trace.jsonl", "video_frames.jsonl")}
        sources.update({name + ".mkv": name for name in physical.CAMERAS})
        decoded = {name: {"sha256": name, "decoded_frames": 2} for name in physical.CAMERAS}
        review = {"cameras": {name: {"source_sha256": name, "reviewed_frames": 2,
                     "required_markings_visible": True, "required_bodies_visible": True}
                     for name in physical.CAMERAS}}

        def evaluate(suffix, *, passing=None, turn=None, rows=frames, pixels=review):
            case = prefix + suffix
            measurements = {"heavy_lane_footprint": {"value": {"frames": rows},
                            "sources": sources}}
            if passing is not None:
                measurements["passing_context"] = {"value": passing}
            if turn is not None:
                measurements["turn_preparation_context"] = {"value": turn}
            return physical.evaluate({"case_id": case, "measurements": measurements},
                    {"case_id": case, "source_join_verified": True, "frames": 2,
                     "four_camera_decode": decoded},
                    dict(pixels, case_id=case), trace)

        self.assertEqual(evaluate("unexcused_boundary_crossing")
                         ["physical_checks"]["maneuver"]["status"], "met")
        self.assertEqual(evaluate("within_marked_lane")
                         ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": False})
            ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": True})
            ["physical_checks"]["maneuver"]["status"], "met")
        turn = {"source_frame_count": 2, "turn_plan": {"requested_movement": "turn",
                                                "direction": "right"}}
        self.assertEqual(evaluate("lawful_turn_preparation_boundary_crossing", turn=turn)
                         ["physical_checks"]["maneuver"]["status"], "met")
        missing_review = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        missing_review["cameras"]["approach"]["required_markings_visible"] = False
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=missing_review)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        bad = [dict(row) for row in frames]
        bad[1]["component_clearances"] = []
        with self.assertRaisesRegex(ValueError, "full heavy-body clearances"):
            evaluate("unexcused_boundary_crossing", rows=bad)

    def test_lifecycle_order_and_early_processing_for_all_selected_cases(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        for suffix in ("within_marked_lane", "unexcused_boundary_crossing",
                       "passing_boundary_crossing",
                       "lawful_turn_preparation_boundary_crossing"):
            case = prefix + suffix
            with self.subTest(case=case, order="early"):
                rejected = lifecycle.run(case, out_of_order=True)
                self.assertEqual(rejected["status"], "rejected")
                self.assertIn("native-exit.json", rejected["reason"])
            with self.subTest(case=case, order="complete"):
                accepted = lifecycle.run(case)
                self.assertEqual(accepted["status"], "passed")
                self.assertEqual(accepted["events"], lifecycle.EVENTS)


if __name__ == "__main__":
    unittest.main()
