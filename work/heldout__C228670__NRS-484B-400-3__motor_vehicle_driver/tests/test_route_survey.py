import hashlib
import importlib.util
from io import BytesIO
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_position_finalizer import analyze_attempt, build_native_result, finalize
from turn_native_plan import OFFSETS_M, control_step, prepare, seal_route_source
from turn_source_recorder import SourceRecorder
from turn_native_capture import CAMERAS, FourCameraCapture


MODULE = Path(__file__).resolve().parents[1] / "route_survey.py"
spec = importlib.util.spec_from_file_location("c228670_route_survey", MODULE)
survey_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey_module)


def source():
    return {
        "provenance_kind": "native_xodr_survey",
        "map_name": "fixture-map",
        "intersection_kind": "public_highway_non_alley",
        "approach_directions": 2,
        "destination_directions": 1,
        "waypoints": [
            {"road_id": 1, "lane_id": -1, "s": 1, "xy_m": [0, -8]},
            {"road_id": 1, "lane_id": -1, "s": 8, "xy_m": [0, -1]},
            {"road_id": 2, "lane_id": -1, "s": 2, "xy_m": [-6, 0]},
        ],
        "approach_centerline_xy_m": [[0, -10], [0, 0]],
        "destination_left_curb_xy_m": [[0, -3], [-10, -3]],
        "approach_right_half_width_m": 3.5,
        "destination_one_way_width_m": 3.5,
        "intersection_entry_xy_m": [0, 0],
    }


class Map:
    name = "fixture-map"

    def __init__(self, junction=True, shift=0, opposing_approach=True, opposing_exit=False):
        self.junction, self.shift = junction, shift
        self.opposing_approach, self.opposing_exit = opposing_approach, opposing_exit

    def _waypoint(self, road_id, x, y, yaw, junction=False):
        return SimpleNamespace(road_id=road_id, lane_id=-1, lane_type="Driving",
            is_junction=junction,
            transform=SimpleNamespace(location=SimpleNamespace(x=x, y=y),
                                      rotation=SimpleNamespace(yaw=yaw)))

    def get_waypoint_xodr(self, road_id, lane_id, s):
        positions = {(1, 1): (0, -8), (1, 8): (0, -1), (2, 2): (-6, 0)}
        x, y = positions[(road_id, s)]
        return self._waypoint(road_id, x + self.shift, y,
                              90 if road_id == 1 else 180,
                              self.junction and s == 8)

    def generate_waypoints(self, spacing):
        assert spacing == 2.0
        lanes = [self._waypoint(1, 0, -8, 90), self._waypoint(2, -6, 0, 180)]
        if self.opposing_approach:
            lanes.append(self._waypoint(1, 2, -8, 270))
        if self.opposing_exit:
            lanes.append(self._waypoint(2, -6, 2, 0))
        return lanes


class RouteSurveyTests(unittest.TestCase):
    def load(self, value):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            raw = json.dumps(value).encode()
            path.write_bytes(raw)
            return survey_module.load_survey(path, hashlib.sha256(raw).hexdigest())

    def test_source_and_native_junction_join(self):
        survey = self.load(source())
        self.assertEqual(len(survey_module.verify_native_route(Map(), survey, "Driving")), 3)
        with self.assertRaisesRegex(ValueError, "no interior Native junction"):
            survey_module.verify_native_route(Map(junction=False), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "differs from source"):
            survey_module.verify_native_route(Map(shift=1), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "lacks opposing"):
            survey_module.verify_native_route(Map(opposing_approach=False), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "exit has opposing"):
            survey_module.verify_native_route(Map(opposing_exit=True), survey, "Driving")

    def test_rejects_unproved_layout_and_stale_source(self):
        value = source()
        value["provenance_kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(ValueError, "XODR provenance"):
            self.load(value)
        value = source()
        value["intersection_entry_xy_m"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "off the approach centerline"):
            self.load(value)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(source()))
            with self.assertRaisesRegex(ValueError, "hash differs"):
                survey_module.load_survey(path, "0" * 64)

    def test_finalizer_joins_all_original_phases_and_rejects_duplicate_frame(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            survey = root / "survey.json"
            raw = json.dumps(source()).encode()
            survey.write_bytes(raw)
            body = root / "body.jsonl"
            def row(frame, phase):
                return {"frame": frame, "phase": phase,
                        "body_corners_xy_m": [[1, -7], [2, -7], [2, -6], [1, -6]]}
            rows = [row(1, "approach"), row(2, "entry"), row(3, "departure")]
            body.write_text("\n".join(json.dumps(value) for value in rows) + "\n")
            report = finalize(survey, hashlib.sha256(raw).hexdigest(), body, root / "measured.json")
            self.assertEqual(report["frames"], 3)
            self.assertIsNone(report["legal_conclusion"])
            rows[2]["frame"] = 2
            body.write_text("\n".join(json.dumps(value) for value in rows) + "\n")
            with self.assertRaisesRegex(ValueError, "Duplicate original frame"):
                finalize(survey, hashlib.sha256(raw).hexdigest(), body, root / "measured.json")

    def test_saved_finalizer_uses_originals_and_rejects_missing_source(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(source()).encode()
            (root / "route_survey_original.json").write_bytes(raw)
            case_id = "heldout__C228670__NRS-484B-400-3__motor_vehicle_driver__centerline_approach_left_curb_departure"
            description = {"channels": [{"name": name, "unit": "structured"} for name in (
                "approach_body_to_centerline", "entry_body_right_of_centerline",
                "departure_body_to_left_curb", "highway_directions")]+
                [{"name": "measured_departure_left_curb_distance_m", "unit": "m"}]}
            config = {"selected_case_id": case_id, "law_id": "NRS-484B-400-3",
                      "cell_id": "C228670", "actor": "motor_vehicle_driver",
                      "case": {"recording_description": description}}
            (root / "config.json").write_text(json.dumps(config))
            (root / "route_survey_capture_receipt.json").write_text(json.dumps({
                "case_id": case_id, "source_path": "route_survey_original.json",
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "map_name": "fixture-map", "native_route_verified": True}))
            original = [{"frame": i + 1, "time_s": (i + 1) / 20,
                         "phase": phase,
                         "body_corners_xy_m": [[1, -7], [2, -7], [2, -6], [1, -6]]}
                        for i, phase in enumerate(("approach", "entry", "departure"))]
            (root / "body_corners_original.jsonl").write_text("".join(json.dumps(row) + "\n" for row in original))
            (root / "trace.jsonl").write_text("".join(json.dumps({"frame": row["frame"], "time_s": row["time_s"]}) + "\n" for row in original))
            (root / "video_frames.jsonl").write_text("".join(json.dumps({"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}) + "\n" for i, row in enumerate(original)))
            for name in ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
                (root / name).write_bytes(b"nonempty original camera placeholder")
            report = analyze_attempt(root)
            self.assertEqual(set(report["measurements"]), set(name["name"] for name in description["channels"]))
            result = build_native_result(root, report)
            self.assertFalse(result["legal_acceptance_claimed"])
            self.assertEqual(len(result["recording_evidence"]), 5)
            self.assertEqual(result["realized_observables"]["measured_departure_left_curb_distance_m"]["statistic"], "min")
            (root / "route_survey_original.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: route_survey_original.json"):
                analyze_attempt(root, write_channels=False)

    def test_exact_native_targets_isolate_approach_and_departure(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            raw = json.dumps(source()).encode()
            path.write_bytes(raw)
            prefix = "heldout__C228670__NRS-484B-400-3__motor_vehicle_driver__"
            plans = {suffix: prepare(prefix + suffix, path, hashlib.sha256(raw).hexdigest())
                     for suffix in OFFSETS_M}
            base = plans["centerline_approach_left_curb_departure"]["targets_xy_m"]
            approach = plans["farther_approach_left_curb_departure"]["targets_xy_m"]
            departure = plans["centerline_approach_farther_departure"]["targets_xy_m"]
            self.assertNotEqual(base[1], approach[1])
            self.assertEqual(base[2], approach[2])
            self.assertEqual(base[1], departure[1])
            self.assertNotEqual(base[2], departure[2])
            self.assertLessEqual(abs(control_step((0, -8), (0, 1), (0, 0), base[1])["steer"]), .5)
            bad = source()
            bad["approach_right_half_width_m"] = 2.5
            raw = json.dumps(bad).encode()
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "cannot fit surveyed roadway"):
                prepare(prefix + "farther_approach_left_curb_departure", path,
                        hashlib.sha256(raw).hexdigest())

    def test_sealed_route_source_requires_native_direction_inventory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site.json"
            raw = json.dumps(source()).encode()
            site.write_bytes(raw)
            case = "heldout__C228670__NRS-484B-400-3__motor_vehicle_driver__centerline_approach_left_curb_departure"
            plan = prepare(case, site, hashlib.sha256(raw).hexdigest())
            failed = root / "failed"
            failed.mkdir()
            with self.assertRaisesRegex(ValueError, "lacks opposing"):
                seal_route_source(Map(opposing_approach=False), plan, "Driving", failed)
            self.assertFalse((failed / "route_survey_capture_receipt.json").exists())
            output = root / "capture"
            output.mkdir()
            receipt = seal_route_source(Map(), plan, "Driving", output)
            self.assertTrue(receipt["native_route_verified"])
            self.assertFalse(receipt["public_access_verified"])
            self.assertEqual((output / "route_survey_original.json").read_bytes(), raw)

    def test_original_four_camera_recorder_joins_body_frames(self):
        class Encoder:
            def __init__(self):
                self.stdin = BytesIO()
            def poll(self):
                return None
            def wait(self, timeout):
                return 0
        with TemporaryDirectory() as directory, patch(
                "turn_source_recorder.subprocess.Popen", side_effect=lambda *a, **k: Encoder()):
            root = Path(directory)
            recorder = SourceRecorder(root, {name: (2, 2) for name in
                                           ("overview", "approach", "reference_corner", "driver_reference")})
            (root / "route_survey_capture_receipt.json").write_text("{}")
            for name in recorder.camera_frames:
                (root / (name + ".mkv")).write_bytes(b"fake encoded original")
            for frame, phase in enumerate(("approach", "entry", "departure"), start=1):
                for name in recorder.camera_frames:
                    recorder.on_frame(name, SimpleNamespace(width=2, height=2,
                        raw_data=b"\x00" * 16, frame=frame, timestamp=frame / 20))
                recorder.record_body({"frame": frame, "time_s": frame / 20,
                    "phase": phase, "actor_id": 7,
                    "body_corners_xy_m": [[1, -7], [2, -7], [2, -6], [1, -6]]})
            self.assertEqual(recorder.seal()["frames"], 3)
            self.assertEqual(len((root / "video_frames.jsonl").read_text().splitlines()), 3)

    def test_native_camera_setup_uses_four_named_profile_views(self):
        class Blueprint:
            def __init__(self):
                self.attributes = {}
            def set_attribute(self, key, value):
                self.attributes[key] = value
        class Sensor:
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                pass
            def destroy(self):
                pass
        class World:
            def __init__(self):
                self.blueprints = []
                self.sensors = []
            def get_blueprint_library(self):
                return self
            def find(self, name):
                self.asserted_name = name
                item = Blueprint()
                self.blueprints.append(item)
                return item
            def spawn_actor(self, blueprint, transform, attach_to):
                assert attach_to == "ego"
                self.transforms = getattr(self, "transforms", []) + [transform]
                sensor = Sensor()
                self.sensors.append(sensor)
                return sensor
        world = World()
        carla = SimpleNamespace(Transform=lambda *parts: parts,
                                Location=lambda *values: values,
                                Rotation=lambda *values: values)
        cameras = FourCameraCapture(world, carla, "ego", lambda name, image: None,
                                    overview_mount_z_m=9.)
        self.assertEqual(len(world.sensors), 4)
        self.assertEqual([(int(b.attributes["image_size_x"]), int(b.attributes["image_size_y"]))
                          for b in world.blueprints], [spec[2] for spec in CAMERAS.values()])
        self.assertTrue(all(b.attributes["sensor_tick"] == "0.05" for b in world.blueprints))
        self.assertEqual(world.transforms[0][0][2], 9.)
        cameras.close()


if __name__ == "__main__":
    unittest.main()
