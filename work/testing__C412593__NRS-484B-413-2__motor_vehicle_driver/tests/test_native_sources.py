"""CPU checks of original Native source capture boundaries."""

import importlib.util
import hashlib
import json
import os
import queue
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "native_sources.py"
SPEC = importlib.util.spec_from_file_location("c412593_native_sources", SOURCE)
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
sys.path.insert(0, str(SOURCE.parent))
from saved_finalizer import finalize
from distance_control import DistanceController, remaining_approach_m
import runner
from site_context import validate_site


def plan():
    return {"rate_hz": 20, "duration_s": 10,
            "cameras": [{"name": name, "width": size[0], "height": size[1],
                         "fov_deg": 90, "pose": {key: 1 for key in
                                                ("x", "y", "z", "yaw", "pitch")}}
                        for name, size in native.SIZES.items()]}


class NativeSourcesTests(unittest.TestCase):
    def test_materialized_runner_check_uses_pinned_exact_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "construction.json").write_text("{}\n")
            config = {"selected_case_id": runner.PREFIX + "right_other_at_300_ft",
                      "supported_case_ids": [runner.PREFIX + "right_other_at_300_ft"],
                      "cell_id": "C412593", "law_id": "NRS-484B-413-2",
                      "actor": "motor_vehicle_driver", "rate_hz": 20,
                      "duration_s": 45, "required_atoms": ["sig.turn_indicator"],
                      "requested_speed_mps": 4.0,
                      "case": {"case_id": runner.PREFIX + "right_other_at_300_ft",
                               "district_type": "other", "signal_target_ft": 300},
                      "cameras": plan()["cameras"]}
            (root / "config.json").write_text(json.dumps(config))
            self.assertTrue(runner.check_construction(root)["cpu_check_passed"])
            config["cameras"][0]["width"] = 640
            (root / "config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "camera dimensions"):
                runner.check_construction(root)

    def test_all_selected_case_bundles_bind_district_and_signal_target(self):
        template = json.loads((runner.ROOT / "construction.json").read_text())
        original = json.dumps(template, sort_keys=True)
        hashes = set()
        for name, target in runner.CASE_TARGET_FEET.items():
            case_id = runner.PREFIX + name
            bundle = runner.make_case_bundle(case_id, template)
            config = json.loads(next(row["content"] for row in bundle["files"]
                                     if row["path"] == "config.json"))
            self.assertEqual(bundle["case_id"], case_id)
            self.assertEqual(config["case"]["case_id"], case_id)
            self.assertEqual(config["case"]["district_type"], runner._district(name))
            self.assertEqual(config["case"]["signal_target_ft"], target)
            self.assertEqual(set(config["supported_case_ids"]),
                             {runner.PREFIX + item for item in runner.CASE_TARGET_FEET})
            hashes.add(hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest())
        self.assertEqual(len(hashes), len(runner.CASE_TARGET_FEET))
        self.assertEqual(json.dumps(template, sort_keys=True), original)
        with self.assertRaisesRegex(ValueError, "Unsupported exact"):
            runner.make_case_bundle(runner.PREFIX + "missing", template)

    def test_fallbacks_change_distinct_physical_knobs(self):
        template = json.loads((runner.ROOT / "construction.json").read_text())
        case = runner.PREFIX + "right_business_at_100_ft"
        configs = {}
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = runner.make_case_bundle(case, template, candidate)
            configs[candidate] = json.loads(next(row["content"] for row in bundle["files"]
                                                 if row["path"] == "config.json"))
        invariant = ("cell_id", "law_id", "actor", "selected_case_id",
                     "required_atoms", "source_packets", "rate_hz", "duration_s",
                     "cameras", "case")
        for candidate in ("fallback1", "fallback2", "fallback3"):
            self.assertTrue(all(configs[candidate][key] == configs["primary"][key]
                                for key in invariant))
        self.assertEqual(configs["fallback1"]["requested_speed_mps"], 3.0)
        self.assertEqual(configs["fallback2"]["blueprint_selection_index"], 1)
        self.assertEqual(configs["fallback3"]["approach_start_m"], 5.0)
        with self.assertRaisesRegex(ValueError, "Unsupported C412593 fallback"):
            runner.make_case_bundle(case, template, "fallback4")
        work = Path.cwd() / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as folder:
            output = Path(folder)
            route, _, _ = runner.materialize_draft_inputs(
                output, case, "cpu-native-map", requested_speed_mps=3.0,
                approach_start_m=5.0)
            self.assertEqual(route["requested_speed_mps"], 3.0)
            self.assertEqual(route["approach"][0][2], 5.0)
            self.assertGreaterEqual(route["approach"][-1][2] - route["approach"][0][2], 100)

    def test_draft_inputs_cover_three_distinct_district_variants(self):
        work = Path.cwd() / ".runtime-work"
        work.mkdir(exist_ok=True)
        hashes = []
        with tempfile.TemporaryDirectory(dir=work) as folder:
            for district, case_name in (("business", "right_business_at_100_ft"),
                                        ("residential", "right_residential_at_100_ft"),
                                        ("other", "right_other_at_300_ft")):
                output = Path(folder) / district
                output.mkdir()
                case = runner.PREFIX + case_name
                route, site, cameras = runner.materialize_draft_inputs(
                    output, case, "cpu-native-map")
                self.assertEqual(site["district"]["type"], district)
                self.assertEqual(runner.check_inputs(case, route, site, cameras,
                                                            source_root=output)["duration_s"], 45)
                xml = ET.fromstring((output / "map.xodr").read_text())
                names = [item.get("name") for item in xml.findall("./road/objects/object")]
                self.assertIn("freight_loading_zone_sign", names)
                self.assertIn("freight_loading_bay", names)
                self.assertEqual(sum("frontage" in name for name in names),
                                 0 if district == "other" else 6)
                realized = {"native_map_id": "cpu-native-map",
                            "approach_road_id": runner.APPROACH_ROAD,
                            "approach_points_xy_m": [[-120, -1.8], [0, -1.8]],
                            "outgoing_points_xy_m": [[3.2, -5], [3.2, -20]]}
                self.assertFalse(validate_site(site, realized, output)["physical_acceptance_claimed"])
                hashes.append(route["map_sha256"])
        self.assertEqual(len(set(hashes)), 3)

    def test_runner_binds_exact_case_map_site_and_four_cameras(self):
        from unittest.mock import patch
        case = runner.PREFIX + "right_other_at_300_ft"
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)):
            root = Path(folder)
            (root / "map.xodr").write_text("cpu-only source map\n")
            digest = hashlib.sha256((root / "map.xodr").read_bytes()).hexdigest()
            route = {"case_id": case, "map_path": "map.xodr", "map_sha256": digest,
                     "native_map_id": "reviewed-map", "requested_speed_mps": 5,
                     "approach": [[1, -1, s] for s in range(0, 101, 2)],
                     "connector": [[2, -1, s] for s in (0, 1)],
                     "outgoing": [[3, -1, s] for s in (0, 1)]}
            site = {"native_map_id": "reviewed-map", "district": {"type": "other"}}
            cameras = plan()
            cameras["map_sha256"] = digest
            self.assertFalse(runner.check_inputs(case, route, site, cameras)["simulation_started"])
            route["approach"][10][2] += 6
            with self.assertRaisesRegex(ValueError, "gap or reversal"):
                runner.check_inputs(case, route, site, cameras)
            route["approach"][10][2] -= 6
            site["district"]["type"] = "business"
            with self.assertRaisesRegex(ValueError, "district differs"):
                runner.check_inputs(case, route, site, cameras)
            site["district"]["type"] = "other"
            (root / "map.xodr").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "map hash differs"):
                runner.check_inputs(case, route, site, cameras)

    def test_runner_rejects_unmaterialized_capture_before_carla_import(self):
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(output_dir=folder, case_id=runner.PREFIX +
                                   "right_business_at_100_ft")
            with self.assertRaisesRegex(ValueError, "runtime.py"):
                runner.capture(args)

    def test_distance_controller_uses_route_progress_and_native_readback(self):
        points = [[float(index), 0.0] for index in range(101)]
        self.assertAlmostEqual(remaining_approach_m(points, (69.52, 0)), 30.48)
        with self.assertRaisesRegex(ValueError, "initial Off buffer"):
            remaining_approach_m(points[:96], (0, 0))
        state = [4]
        position = [0.0]
        actor = SimpleNamespace(get_location=lambda: SimpleNamespace(x=position[0], y=0),
                                get_light_state=lambda: state[0],
                                set_light_state=lambda value: state.__setitem__(0, value))
        light_type = SimpleNamespace(RightBlinker=2)
        control = DistanceController("right_business_at_100_ft", points)
        self.assertFalse(control.step(actor, light_type)["requested_right_indicator"])
        position[0] = 69.52
        self.assertTrue(control.step(actor, light_type)["readback_right_indicator"])
        self.assertEqual(state[0], 6)
        position[0] = 65
        with self.assertRaisesRegex(ValueError, "reversed"):
            control.step(actor, light_type)

    def test_interrupted_schedule_has_observed_off_gap(self):
        points = [[float(index), 0.0] for index in range(101)]
        state = [0]
        position = [0.0]
        actor = SimpleNamespace(get_location=lambda: SimpleNamespace(x=position[0], y=0),
                                get_light_state=lambda: state[0],
                                set_light_state=lambda value: state.__setitem__(0, value))
        control = DistanceController("right_interrupted", points)
        light_type = SimpleNamespace(RightBlinker=2)
        observed = []
        for x in (0, 70, 84, 87):
            position[0] = x
            observed.append(control.step(actor, light_type)["readback_right_indicator"])
        self.assertEqual(observed, [False, True, False, True])
        with self.assertRaisesRegex(ValueError, "departed"):
            remaining_approach_m(points, (50, 10))

    def test_plan_requires_all_four_correct_views(self):
        self.assertEqual(native.validate_plan(plan())["frames_planned"], 200)
        missing = plan()
        missing["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named"):
            native.validate_plan(missing)
        wrong = plan()
        wrong["cameras"][0]["width"] -= 1
        with self.assertRaisesRegex(ValueError, "dimensions"):
            native.validate_plan(wrong)

    def test_frame_join_rejects_skipped_source(self):
        frames = queue.Queue()
        frames.put(SimpleNamespace(frame=7, raw_data=b"abcd"))
        self.assertEqual(native.source_camera_frame(frames, 7), b"abcd")
        frames.put(SimpleNamespace(frame=9, raw_data=b"abcd"))
        with self.assertRaisesRegex(ValueError, "skipped"):
            native.source_camera_frame(frames, 8)

    def test_native_state_row_has_original_indicator_and_position(self):
        snapshot = SimpleNamespace(frame=10, timestamp=SimpleNamespace(elapsed_seconds=0.5))
        actor = SimpleNamespace(id=4, get_location=lambda: SimpleNamespace(x=2, y=3),
                                get_velocity=lambda: SimpleNamespace(x=3, y=4),
                                get_transform=lambda: SimpleNamespace(rotation=SimpleNamespace(yaw=0)),
                                get_light_state=lambda: 2)
        carla = SimpleNamespace(VehicleLightState=SimpleNamespace(RightBlinker=2))
        row = native.source_row(snapshot, actor, carla)
        self.assertEqual((row["ego_position_xy_m"], row["ego_speed_mps"], row["right_indicator"]),
                         ([2.0, 3.0], 5.0, True))

    def test_ffv1_encodes_original_bgra_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "original.mkv"
            with native.ffv1_writer(video, (2, 2)) as write:
                write(bytes([0, 0, 255, 255] * 4))
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                    "-show_entries", "stream=codec_name,width,height",
                                    "-of", "json", str(video)], check=True,
                                   capture_output=True, text=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream, {"codec_name": "ffv1", "width": 2, "height": 2})

    def test_saved_finalizer_requires_all_original_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = []
            frame_map = []
            for index, indicator in enumerate((False, True, True)):
                rows.append({"frame": index + 1, "time_s": (index + 1) / 20,
                             "ego_position_xy_m": [index, 0], "ego_speed_mps": 5,
                             "ego_heading_deg": (0, 0, -45)[index],
                             "ego_road_id": (1, 1, 2)[index],
                             "ego_lane_id": 1,
                             "right_indicator": indicator})
                frame_map.append({"video_frame": index, "carla_frame": index + 1,
                                  "time_s": (index + 1) / 20})
            (root / "drive_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frame_map))
            (root / "route_context.json").write_text(json.dumps({
                "native_map_id": "cpu-example", "approach_road_id": 1, "approach_lane_id": 1,
                "outgoing_road_id": 2, "outgoing_lane_id": 1,
                "native_route_source": "cpu-example", "district_source": "cpu-example",
                "district_type": "business", "turn_onset_frame": 3}))
            for name in native.CAMERAS:
                with native.ffv1_writer(root / (name + ".mkv"), (2, 2)) as write:
                    for _ in range(3):
                        write(bytes([0, 0, 255, 255] * 4))
            output = finalize(root)
            self.assertEqual(output["frames"], 3)
            self.assertEqual(set(output["original_cameras"]), set(native.CAMERAS))
            self.assertEqual(output["original_course"]["turn_onset_frame"], 3)
            changed = [dict(row) for row in rows]
            changed[-1]["ego_heading_deg"] = 45
            (root / "drive_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in changed))
            with self.assertRaisesRegex(ValueError, "No fully observed|Turn onset differs"):
                finalize(root)
            (root / "drive_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            (root / "approach.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original camera"):
                finalize(root)

    def test_saved_finalizer_measures_exact_business_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            positions = (-10.0, 0.0, 30.48, 32.0)
            rows = []
            frames = []
            for index, x in enumerate(positions):
                frame = index + 1
                rows.append({"frame": frame, "time_s": frame / 20,
                             "ego_position_xy_m": [x, 0.0], "ego_speed_mps": 5.0,
                             "ego_heading_deg": (0, 0, -10, -90)[index],
                             "ego_road_id": (1, 1, 1, 2)[index], "ego_lane_id": -1,
                             "right_indicator": index > 0})
                frames.append({"video_frame": index, "carla_frame": frame,
                               "time_s": frame / 20})
            (root / "video_frames.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in frames))
            (root / "route_context.json").write_text(json.dumps({
                "native_map_id": "cpu-example", "approach_road_id": 1,
                "approach_lane_id": -1, "outgoing_road_id": 2,
                "outgoing_lane_id": -1, "native_route_source": "cpu-example",
                "district_source": "cpu-example", "district_type": "business",
                "turn_onset_frame": 3}))
            for name in native.CAMERAS:
                with native.ffv1_writer(root / (name + ".mkv"), (2, 2)) as write:
                    for _ in rows:
                        write(bytes([0, 0, 255, 255] * 4))
            for onset_x, meets in ((30.479, False), (30.48, True),
                                   (30.481, True)):
                rows[2]["ego_position_xy_m"] = [onset_x, 0.0]
                (root / "drive_history.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows))
                result = finalize(root)
                self.assertEqual(result["measurement"]["observed_continuous_distance_meets_boundary"],
                                 meets)
                self.assertAlmostEqual(
                    result["measurement"]["turn_onset"]["continuous_right_signal_distance_m"],
                    onset_x)
                self.assertFalse(result["physical_acceptance_claimed"])
            rows[1]["right_indicator"] = False
            (root / "drive_history.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            interrupted = finalize(root)
            self.assertFalse(interrupted["measurement"]["observed_continuous_distance_meets_boundary"])
            self.assertEqual(interrupted["measurement"]["turn_onset"][
                "continuous_right_signal_distance_m"], 0.0)

    def test_saved_finalizer_full_duration_sources_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = []
            frames = []
            for index in range(900):
                frame = index + 1
                if index < 599:
                    x = (-120.0 + index * 89.52 / 446 if index < 446 else
                         -30.48 + (index - 446) * 30.48 / 153)
                    y, heading, road = 0.0, 0.0, 412593
                else:
                    x, y = 0.0, -(index - 599) * 0.2
                    heading = -10.0 if index == 599 else -90.0
                    road = 412594 if index == 599 else 412595
                rows.append({"frame": frame, "time_s": frame / 20,
                             "ego_position_xy_m": [x, y], "ego_speed_mps": 4.0,
                             "ego_heading_deg": heading, "ego_road_id": road,
                             "ego_lane_id": -1, "right_indicator": index >= 446})
                frames.append({"video_frame": index, "carla_frame": frame,
                               "time_s": frame / 20})
            (root / "drive_history.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            (root / "video_frames.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in frames))
            (root / "route_context.json").write_text(json.dumps({
                "native_map_id": "synthetic-C412593", "approach_road_id": 412593,
                "approach_lane_id": -1, "outgoing_road_id": 412595,
                "outgoing_lane_id": -1, "native_route_source": "synthetic geometry",
                "district_source": "synthetic district packet",
                "district_type": "business", "turn_onset_frame": 600}))
            for name in native.CAMERAS:
                with native.ffv1_writer(root / (name + ".mkv"), (2, 2)) as write:
                    for index in range(900):
                        write(bytes([(index // 9) % 256, 0, 255, 255] * 4))
            source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in root.iterdir()}
            result = finalize(root)
            self.assertEqual(result["frames"], 900)
            self.assertEqual(set(result["original_cameras"]), set(native.CAMERAS))
            self.assertAlmostEqual(result["measurement"]["turn_onset"][
                "continuous_right_signal_distance_m"], 30.48)
            self.assertTrue(result["measurement"]["observed_continuous_distance_meets_boundary"])
            self.assertFalse(result["physical_acceptance_claimed"])
            missing = root / "approach.mkv"
            held = root / "approach.mkv.held"
            missing.rename(held)
            try:
                with self.assertRaisesRegex(ValueError, "Missing original camera source: approach"):
                    finalize(root)
            finally:
                held.rename(missing)
            self.assertEqual(source_hashes,
                             {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in root.iterdir()})

    def test_recorder_retains_four_synchronized_native_sources(self):
        work = Path.cwd() / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as folder:
            root = Path(folder)
            (root / "construction.json").write_text("{}\n")
            actor = SimpleNamespace(id=11,
                                    get_location=lambda: SimpleNamespace(x=1, y=2),
                                    get_velocity=lambda: SimpleNamespace(x=3, y=4),
                                    get_transform=lambda: SimpleNamespace(rotation=SimpleNamespace(yaw=0)),
                                    get_light_state=lambda: 2)
            carla = SimpleNamespace(VehicleLightState=SimpleNamespace(RightBlinker=2))
            sizes = {name: (2, 2) for name in native.CAMERAS}
            prior_cwd = Path.cwd()
            os.chdir(root)
            try:
                with native.source_recorder(root, sizes) as append:
                    for index in range(3):
                        snapshot = SimpleNamespace(frame=index + 1,
                                                   timestamp=SimpleNamespace(elapsed_seconds=(index + 1) / 20))
                        queues = {name: queue.Queue() for name in native.CAMERAS}
                        for item in queues.values():
                            item.put(SimpleNamespace(frame=index + 1,
                                                     raw_data=bytes([0, 0, 255, 255] * 4)))
                        append(snapshot, actor, carla, queues)
            finally:
                os.chdir(prior_cwd)
            rows = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            self.assertEqual([row["carla_frame"] for row in rows], [1, 2, 3])
            for name in native.CAMERAS:
                self.assertEqual(int(subprocess.run(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
                     str(root / (name + ".mkv"))], check=True,
                    capture_output=True, text=True).stdout.strip()), 3)


if __name__ == "__main__":
    unittest.main()
