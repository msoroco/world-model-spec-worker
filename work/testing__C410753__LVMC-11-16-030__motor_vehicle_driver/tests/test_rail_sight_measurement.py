"""Source, exact-distance, speed and exception probes for rail grade crossing."""
import hashlib
import json
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from rail_sight_measurement import measure
from rail_native_capture import CAMERAS, _write_source, capture
from rail_camera_adapter import CameraAdapter
from rail_saved_measurement import verify_camera_row, verify_saved
from rail_route_reader import ReviewedRailRouteReader
from rail_ray_reader import ReviewedRailRayReader
from rail_exception_reader import ReviewedRailExceptionReader
from rail_construction import spawn_occluder, validate_occluder_source
from rail_native_runner import RailRouteController, run_case
from rail_comparison_audit import audit_comparison


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RailSightTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work/rail-sight-measurement-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.road = "<OpenDRIVE><road name=\"original-grade-crossing\"/></OpenDRIVE>"
        (self.root / "road.xodr").write_text(self.road)
        review = {"road_sha256": sha(self.root / "road.xodr"),
                  "grade_crossing": True, "railway_kind": "electric",
                  "track_extent_each_direction_ft": 400,
                  "approach_extent_ft": 100, "municipal_jurisdiction": True}
        (self.root / "review.json").write_text(json.dumps(review) + "\n")
        self.packet = {"assignment_id": HERE.name,
                       "road_sha256": review["road_sha256"],
                       "original_map_source": {"path": "road.xodr", "sha256": sha(self.root / "road.xodr")},
                       "railway_review_source": {"path": "review.json", "sha256": sha(self.root / "review.json")}}
        self.frames = []
        for index in range(8):
            sight = self.root / ("ray-" + str(index) + ".json")
            sight.write_text(json.dumps({"frame": 100 + index, "crossing": True,
                                         "rail_minus_400ft": index != 2,
                                         "rail_plus_400ft": True}) + "\n")
            self.frames.append({"original_frame": 100 + index,
                                "time_s": index * .05,
                                "route_station_m": index * 6.096,
                                "speed_mps": 14 / 2.2369362920544,
                                "position_xy_m": [index * 6.096, 0.0],
                                "body_on_crossing": index >= 6,
                                "sight_crossing_clear": True,
                                "sight_rail_negative_400ft_clear": index != 2,
                                "sight_rail_positive_400ft_clear": True,
                                "sight_source_path": sight.name,
                                "sight_source_sha256": sha(sight),
                                "flagman_on_duty": False,
                                "signal_installed": False,
                                "signal_clearly_visible": False,
                                "signal_immediate_train_approach": False})
        self.seal_frames()

    def seal_frames(self):
        observed = ("original_frame", "time_s", "route_station_m", "speed_mps", "position_xy_m",
                    "body_on_crossing", "flagman_on_duty", "signal_installed",
                    "signal_clearly_visible", "signal_immediate_train_approach")
        for index, row in enumerate(self.frames):
            exception = self.root / ("exception-" + str(index) + ".json")
            exception.write_text(json.dumps({
                "frame": row["original_frame"],
                **{key: row[key] for key in observed[6:]}}) + "\n")
            trace = {"path": exception.name, "sha256": sha(exception)}
            source = self.root / ("frame-" + str(index) + ".json")
            source.write_text(json.dumps({**{key: row[key] for key in observed},
                                          "exception_source_trace": trace}) + "\n")
            row["frame_source_path"] = source.name
            row["frame_source_sha256"] = sha(source)

    def test_source_bound_obstructed_approach_and_traversal_speed(self):
        result = measure(self.root, self.packet, self.road, self.frames)
        self.assertEqual(result["crossing_original_frames"], [106, 107])
        self.assertEqual(result["speed_boundary_relation_observed"], "below")
        self.assertTrue(result["any_required_sight_ray_obstructed"])
        self.assertIsNone(result["legal_speed_verdict"])

    def test_original_sight_ray_changed_rejects(self):
        (self.root / "ray-2.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "sight ray source"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_row_cannot_relabel_original_sight_result(self):
        self.frames[2]["sight_rail_negative_400ft_clear"] = True
        with self.assertRaisesRegex(ValueError, "sight ray readback"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_exception_is_separate_from_speed_and_view(self):
        for row in self.frames[6:]:
            row["signal_installed"] = True
            row["signal_clearly_visible"] = True
        self.seal_frames()
        result = measure(self.root, self.packet, self.road, self.frames)
        self.assertTrue(result["exceptions"]["clearly_visible_nonwarning_signal_observed"])
        self.assertTrue(result["any_required_sight_ray_obstructed"])

    def test_warning_signal_is_measured_separately_from_exception(self):
        for row in self.frames[6:]:
            row["signal_installed"] = True
            row["signal_clearly_visible"] = True
            row["signal_immediate_train_approach"] = True
        self.seal_frames()
        result = measure(self.root, self.packet, self.road, self.frames)
        self.assertTrue(result["exceptions"]["clearly_visible_warning_signal_observed"])
        self.assertFalse(result["exceptions"]["clearly_visible_nonwarning_signal_observed"])

    def test_independent_comparison_requires_realized_original_contrast(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        cases = {item["case_id"]: item for item in plan["cases"]}
        saved = {}
        for key, relation, obstructed, flagman, nonwarning, warning in (
                ("obscured_14mph", "below", True, False, False, False),
                ("obscured_15mph", "at", True, False, False, False),
                ("obscured_16mph", "above", True, False, False, False),
                ("clear_view_16mph", "above", False, False, False, False),
                ("flagman_16mph", "above", True, True, False, False),
                ("signal_nonwarning_16mph", "above", True, False, True, False),
                ("signal_warning_16mph", "above", True, False, False, True)):
            case_id = plan["assignment_id"] + "__" + key
            self.assertIn(case_id, cases)
            saved[case_id] = {
                "case_id": case_id, "source_complete": True,
                "original_frame_count": 900, "camera_views": list(CAMERAS),
                "legal_conclusion": None,
                "observation": {
                    "review_source_sha256": "a" * 64,
                    "speed_boundary_relation_observed": relation,
                    "any_required_sight_ray_obstructed": obstructed,
                    "legal_speed_verdict": None,
                    "exceptions": {
                        "on_duty_flagman_observed": flagman,
                        "clearly_visible_nonwarning_signal_observed": nonwarning,
                        "clearly_visible_warning_signal_observed": warning}}}
        for comparison in plan["comparisons"]:
            selected = {case_id: saved[case_id] for case_id in comparison["case_ids"]}
            audited = audit_comparison(plan, comparison["comparison_id"], selected)
            self.assertTrue(audited["planned_contrast_observed"])
            self.assertIsNone(audited["legal_conclusion"])
        speed = plan["comparisons"][0]
        selected = {case_id: saved[case_id] for case_id in speed["case_ids"]}
        selected[speed["case_ids"][1]]["observation"]["speed_boundary_relation_observed"] = "above"
        with self.assertRaisesRegex(ValueError, "contrast not observed"):
            audit_comparison(plan, speed["comparison_id"], selected)
        selected[speed["case_ids"][1]]["observation"]["speed_boundary_relation_observed"] = "at"
        selected[speed["case_ids"][1]]["source_complete"] = False
        with self.assertRaisesRegex(ValueError, "source admission"):
            audit_comparison(plan, speed["comparison_id"], selected)

    def test_row_cannot_relabel_original_body_or_signal(self):
        self.frames[6]["body_on_crossing"] = False
        with self.assertRaisesRegex(ValueError, "frame readback"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_row_cannot_relabel_original_ego_position(self):
        self.frames[6]["position_xy_m"] = [999.0, 0.0]
        with self.assertRaisesRegex(ValueError, "frame readback"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_changed_original_frame_source_rejects(self):
        (self.root / "frame-6.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "frame source"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_changed_original_exception_source_rejects(self):
        (self.root / "exception-6.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "exception source"):
            measure(self.root, self.packet, self.road, self.frames)

    def test_original_capture_source_cannot_be_overwritten(self):
        _write_source(self.root, "original-frames/00000100.json", {"frame": 100})
        original = (self.root / "original-frames/00000100.json").read_bytes()
        with self.assertRaises(FileExistsError):
            _write_source(self.root, "original-frames/00000100.json", {"frame": 999})
        self.assertEqual((self.root / "original-frames/00000100.json").read_bytes(), original)

    def test_four_camera_adapter_joins_original_frame_and_timestamp(self):
        class Sensor:
            def listen(self, callback):
                self.callback = callback

            def stop(self):
                self.stopped = True

        sensors = {name: Sensor() for name in CAMERAS}
        adapter = CameraAdapter(sensors)
        adapter.start()
        for name, (width, height) in CAMERAS.items():
            sensors[name].callback(SimpleNamespace(
                frame=100, timestamp=2.5, width=width, height=height,
                raw_data=bytes((0, 0, 0, 255)) * (width * height)))
        snapshot = SimpleNamespace(timestamp=SimpleNamespace(elapsed_seconds=2.5))
        images = adapter.read(100, snapshot)
        self.assertEqual(set(images), set(CAMERAS))
        self.assertTrue(all(item[0] == 100 and item[1].startswith(b"\x89PNG")
                            for item in images.values()))
        adapter.stop()
        self.assertTrue(all(sensor.stopped for sensor in sensors.values()))

    def test_four_camera_adapter_stops_attached_sensors_on_start_failure(self):
        class Sensor:
            def __init__(self, fail=False):
                self.fail = fail
                self.stopped = False

            def listen(self, callback):
                if self.fail:
                    raise RuntimeError("sensor attachment failed")

            def stop(self):
                self.stopped = True

        sensors = {name: Sensor(fail=(index == 2))
                   for index, name in enumerate(CAMERAS)}
        with self.assertRaisesRegex(RuntimeError, "attachment failed"):
            CameraAdapter(sensors).start()
        self.assertTrue(sensors["overview"].stopped)
        self.assertTrue(sensors["approach"].stopped)

    def test_saved_camera_row_requires_original_hashed_four_views(self):
        from PIL import Image
        row = {"original_frame": 100, "sources": {}}
        for name, dimensions in CAMERAS.items():
            source = self.root / f"original-cameras/{name}/00000100.png"
            source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", dimensions).save(source, "PNG")
            row["sources"][name] = {
                "path": str(source.relative_to(self.root)), "sha256": sha(source)}
        self.assertEqual(set(verify_camera_row(self.root, row, 100)), set(CAMERAS))
        row["sources"]["track_left"]["path"] = row["sources"]["track_left"]["path"].replace("00000100", "00000101")
        with self.assertRaisesRegex(ValueError, "frame path differs"):
            verify_camera_row(self.root, row, 100)
        row["sources"]["track_left"]["path"] = "original-cameras/track_left/00000100.png"
        row["sources"]["track_left"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source missing or changed"):
            verify_camera_row(self.root, row, 100)

    def test_saved_measurement_rejects_missing_original_receipt(self):
        with self.assertRaisesRegex(ValueError, "receipt missing"):
            verify_saved(self.root, self.packet, HERE.name + "__obscured_14mph")

    def test_selected_analysis_rejects_missing_original_frame_source(self):
        from analysis import analyze
        case_id = HERE.name + "__obscured_14mph"
        packet = _write_source(self.root, "reviewed-rail-packet.json", self.packet)
        (self.root / "native-rail-receipt.json").write_text(json.dumps({
            "case_id": case_id, "packet": packet}) + "\n")
        contract = HERE / "cases" / "obscured_14mph" / "measurement-contract.json"
        with self.assertRaisesRegex(ValueError,
                                    "Missing required source: native-rail-frames.json"):
            analyze(self.root, contract, case_id)

    def test_saved_measurement_recomputes_full_original_900_frame_attempt(self):
        from PIL import Image
        templates = {}
        for name, size in CAMERAS.items():
            template = self.root / ("template-" + name + ".png")
            Image.new("RGB", size, (40, 30, 20)).save(template, "PNG")
            templates[name] = template
        frames, camera_map = [], []
        for index in range(900):
            original_frame = 100 + index
            frame = {
                "original_frame": original_frame, "time_s": index * .05,
                "route_station_m": index * 6.096,
                "speed_mps": 14 / 2.2369362920544,
                "position_xy_m": [index * 6.096, 0.0],
                "body_on_crossing": index >= 6,
                "flagman_on_duty": False, "signal_installed": False,
                "signal_clearly_visible": False,
                "signal_immediate_train_approach": False}
            exception_ref = _write_source(
                self.root, f"original-exceptions/{original_frame:08d}.json",
                {"frame": original_frame, **{key: frame[key] for key in
                 ("flagman_on_duty", "signal_installed", "signal_clearly_visible",
                  "signal_immediate_train_approach")}})
            frame_ref = _write_source(
                self.root, f"original-frames/{original_frame:08d}.json",
                {**frame, "exception_source_trace": exception_ref})
            rays = {"frame": original_frame, "crossing": True,
                    "rail_minus_400ft": index != 2,
                    "rail_plus_400ft": True}
            ray_ref = _write_source(
                self.root, f"original-rays/{original_frame:08d}.json", rays)
            frames.append({**frame,
                           "sight_crossing_clear": rays["crossing"],
                           "sight_rail_negative_400ft_clear": rays["rail_minus_400ft"],
                           "sight_rail_positive_400ft_clear": rays["rail_plus_400ft"],
                           "frame_source_path": frame_ref["path"],
                           "frame_source_sha256": frame_ref["sha256"],
                           "sight_source_path": ray_ref["path"],
                           "sight_source_sha256": ray_ref["sha256"]})
            camera_row = {"original_frame": original_frame, "sources": {}}
            for name in CAMERAS:
                relative = f"original-cameras/{name}/{original_frame:08d}.png"
                destination = self.root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.link(templates[name], destination)
                camera_row["sources"][name] = {
                    "path": relative, "sha256": sha(destination)}
            camera_map.append(camera_row)
        measurement = measure(self.root, self.packet, self.road, frames)
        frame_ref = _write_source(self.root, "native-rail-frames.json", frames)
        camera_ref = _write_source(self.root, "native-rail-camera-map.json", camera_map)
        packet_ref = _write_source(self.root, "reviewed-rail-packet.json", self.packet)
        case_id = HERE.name + "__obscured_14mph"
        _write_source(self.root, "native-rail-receipt.json", {
            "case_id": case_id, "capture_kind": "original_native", "fps": 20,
            "duration_s": 45, "frame_count": 900, "frames": frame_ref,
            "camera_map": camera_ref, "packet": packet_ref,
            "measurement": measurement,
            "legal_conclusion": None})
        saved = verify_saved(self.root, self.packet, case_id)
        self.assertTrue(saved["source_complete"])
        self.assertEqual(saved["original_frame_count"], 900)
        self.assertEqual(saved["observation"], measurement)
        from analysis import analyze
        contract = HERE / "cases" / "obscured_14mph" / "measurement-contract.json"
        report = analyze(self.root, contract, case_id)
        self.assertEqual(report["measurements"]["traversal_speed_and_sight"]["value"]
                         ["speed_boundary_relation_observed"], "below")
        self.assertFalse(report["physical_completion_confirmed"])
        self.assertIsNone(report["legal_conclusion"])
        self.packet["road_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "packet differs"):
            verify_saved(self.root, self.packet, case_id)

    def test_original_capture_writes_frame_ray_and_four_camera_sources(self):
        from PIL import Image
        encoded = {}
        for name, size in CAMERAS.items():
            buffer = BytesIO()
            Image.new("RGB", size, (40, 30, 20)).save(buffer, "PNG")
            encoded[name] = buffer.getvalue()

        class World:
            def __init__(self, road):
                self.road = road
                self.frame = 99

            def get_map(self):
                return SimpleNamespace(to_opendrive=lambda: self.road)

            def tick(self):
                self.frame += 1
                return self.frame

            def get_snapshot(self):
                return SimpleNamespace(frame=self.frame,
                    timestamp=SimpleNamespace(elapsed_seconds=(self.frame - 100) * .05))

        world = World(self.road)
        ego = SimpleNamespace(
            get_velocity=lambda: SimpleNamespace(x=6.0, y=0.0, z=0.0),
            get_transform=lambda: SimpleNamespace(location=SimpleNamespace(x=0.0, y=0.0)))
        brake_calls = []
        receipt = capture(
            case_id=HERE.name + "__obscured_14mph", packet=self.packet,
            world=world, ego=ego, attempt_root=self.root, frame_count=8,
            route_reader=lambda frame, snapshot, actor: ((frame - 100) * 6.096, frame >= 106),
            ray_reader=lambda frame, snapshot, actor: {
                "crossing": True, "rail_minus_400ft": frame != 102,
                "rail_plus_400ft": True},
            exception_reader=lambda frame, snapshot, actor: {
                "flagman_on_duty": False, "signal_installed": False,
                "signal_clearly_visible": False,
                "signal_immediate_train_approach": False},
            camera_reader=lambda frame, snapshot: {
                name: (frame, raw) for name, raw in encoded.items()},
            brake=lambda actor: brake_calls.append(actor))
        self.assertEqual(receipt["camera_count"], 8)
        self.assertEqual(brake_calls, [ego])
        self.assertTrue((self.root / "original-frames/00000100.json").is_file())
        self.assertTrue((self.root / "original-rays/00000102.json").is_file())
        self.assertTrue((self.root / "original-cameras/track_left/00000107.png").is_file())

    def test_reviewed_rail_route_measures_body_occupancy(self):
        source = {"source_kind": "rail_crossing_route", "reviewer": "test-reviewer",
                  "source_citation": "test-original-map", "road_sha256": self.packet["road_sha256"],
                  "route_xy": [[0, 0], [100, 0], [200, 0]],
                  "crossing_entry_xy": [100, 0], "crossing_exit_xy": [110, 0]}
        route = self.root / "route.json"
        route.write_text(json.dumps(source) + "\n")
        site = {"route_source_sha256": sha(route), "road_sha256": self.packet["road_sha256"]}
        reader = ReviewedRailRouteReader(site, route)
        transform = SimpleNamespace(location=SimpleNamespace(x=99.0, y=0.0))
        vertices = [SimpleNamespace(x=99.0 + offset, y=0.0)
                    for offset in (-2, -2, -2, -2, 2, 2, 2, 2)]
        ego = SimpleNamespace(get_transform=lambda: transform,
            bounding_box=SimpleNamespace(get_world_vertices=lambda current: vertices))
        station, occupancy = reader(100, SimpleNamespace(frame=100), ego)
        self.assertEqual(station, 99.0)
        self.assertTrue(occupancy)
        transform.location.x = 90.0
        vertices = [SimpleNamespace(x=90.0 + offset, y=0.0)
                    for offset in (-2, -2, -2, -2, 2, 2, 2, 2)]
        _, occupancy = reader(101, SimpleNamespace(frame=101), ego)
        self.assertFalse(occupancy)

    def test_reviewed_bidirectional_rail_rays_use_original_hits(self):
        stations = [i * 5.0 for i in range(25)] + [121.92]
        source = {
            "source_kind": "railway_sight_geometry", "reviewer": "test-reviewer",
            "source_citation": "test-original-map",
            "road_sha256": self.packet["road_sha256"],
            "crossing_xyz": [10, 0, 0],
            "rail_minus_400ft": [
                {"station_m": d, "xyz": [-10 - d, 0, 0]} for d in stations],
            "rail_plus_400ft": [
                {"station_m": d, "xyz": [10 + d, 0, 0]} for d in stations],
        }
        path = self.root / "ray-geometry.json"
        path.write_text(json.dumps(source) + "\n")
        site = {"rail_ray_geometry_source_sha256": sha(path),
                "road_sha256": self.packet["road_sha256"]}

        def point(x, y, z):
            return SimpleNamespace(x=x, y=y, z=z)

        class World:
            def cast_ray(self, start, end):
                return ([SimpleNamespace(location=point(-5, 0, 1), label="wall")]
                        if end.x < 0 else [])

        reader = ReviewedRailRayReader(site, path, World(), point)
        ego = SimpleNamespace(get_transform=lambda: SimpleNamespace(location=point(0, 0, 0)))
        result = reader(100, SimpleNamespace(frame=100), ego)
        self.assertTrue(result["crossing"])
        self.assertFalse(result["rail_minus_400ft"])
        self.assertTrue(result["rail_plus_400ft"])
        self.assertEqual(result["source_trace"]["original_frame"], 100)
        path.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            ReviewedRailRayReader(site, path, World(), point)

    def test_exception_reader_requires_authority_and_original_frame(self):
        review = {"source_kind": "railway_exception_review",
                  "reviewer": "test-reviewer", "source_citation": "test-original-map",
                  "road_sha256": self.packet["road_sha256"],
                  "flagman_duty_authority_source": "test-duty-record",
                  "signal_installation_source": "test-installation-record",
                  "signal_kind": "electrical"}
        review_path = self.root / "exception-review.json"
        review_path.write_text(json.dumps(review) + "\n")
        state = {"frame": 100, "flagman_on_duty": False,
                 "signal_installed": True, "signal_clearly_visible": True,
                 "signal_immediate_train_approach": False}
        original_path = self.root / "exception-100.json"
        original_path.write_text(json.dumps(state) + "\n")
        site = {"road_sha256": self.packet["road_sha256"],
                "rail_exception_review_sha256": sha(review_path)}
        original_digest = sha(original_path)
        read = lambda frame, snapshot, ego: {
            **{key: value for key, value in state.items() if key != "frame"},
            "original_source": {"path": original_path.name,
                                "sha256": original_digest}}
        reader = ReviewedRailExceptionReader(site, review_path, self.root, read)
        result = reader(100, SimpleNamespace(frame=100), None)
        self.assertTrue(result["signal_clearly_visible"])
        original_path.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source missing or changed"):
            ReviewedRailExceptionReader(site, review_path, self.root, read)(
                100, SimpleNamespace(frame=100), None)

    def test_occluder_requires_reviewed_site_and_spawn_readback(self):
        review = {"source_kind": "railway_occluder_site",
                  "reviewer": "test-reviewer", "source_citation": "test-original-map",
                  "road_sha256": self.packet["road_sha256"],
                  "target_ray": "rail_minus_400ft",
                  "blueprint_id": "static.prop.wall",
                  "transform": {"x": 4.0, "y": 5.0, "z": 0.0, "yaw": 90.0}}
        path = self.root / "occluder-review.json"
        path.write_text(json.dumps(review) + "\n")
        packet = {"reviewed_occluder_source": {"path": path.name,
                                                "sha256": sha(path)}}
        self.assertIsNone(validate_occluder_source(
            self.root, packet, self.packet["road_sha256"], "clear_view_16mph"))
        calls = []
        actor = SimpleNamespace(is_alive=True,
            get_transform=lambda: SimpleNamespace(
                location=SimpleNamespace(x=4.0, y=5.0, z=0.0)))

        class World:
            def get_blueprint_library(self):
                return SimpleNamespace(find=lambda name: calls.append(name) or name)

            def try_spawn_actor(self, blueprint, transform):
                calls.append((blueprint, transform))
                return actor

        observed = spawn_occluder(
            World(), lambda **fields: fields, self.root, packet,
            self.packet["road_sha256"], "obscured_14mph")
        self.assertIs(observed, actor)
        self.assertEqual(calls[0], "static.prop.wall")
        path.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source missing or changed"):
            validate_occluder_source(
                self.root, packet, self.packet["road_sha256"], "obscured_14mph")

    def test_route_controller_uses_reviewed_path_and_original_speed(self):
        route = SimpleNamespace(points=[(0.0, 0.0), (10.0, 0.0), (10.0, 20.0)])
        applied = []
        ego = SimpleNamespace(
            get_transform=lambda: SimpleNamespace(
                location=SimpleNamespace(x=9.0, y=0.0),
                rotation=SimpleNamespace(yaw=0.0)),
            get_velocity=lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0),
            apply_control=lambda command: applied.append(command))
        controller = RailRouteController(route, 15, lambda **fields: fields)
        result = controller.apply(ego)
        self.assertGreater(result["steer"], 0)
        self.assertGreater(result["throttle"], 0)
        self.assertEqual(len(applied), 1)

    def test_runner_refuses_missing_reviewed_route_before_native_start(self):
        world = SimpleNamespace(get_map=lambda: SimpleNamespace(
            to_opendrive=lambda: self.road))
        with self.assertRaisesRegex(ValueError, "reviewed rail source reference missing"):
            run_case(
                case_key="clear_view_16mph", packet=self.packet,
                attempt_root=self.root, world=world, ego=None,
                location_factory=None, transform_factory=None,
                original_exception_reader=None, camera_adapter=None,
                control_factory=None, brake=None, frame_count=8)


if __name__ == "__main__":
    unittest.main()
