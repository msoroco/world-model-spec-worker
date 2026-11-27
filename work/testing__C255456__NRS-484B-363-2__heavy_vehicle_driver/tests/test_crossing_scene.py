"""Synthetic adapter tests of source seals and construction/readback protocol."""

import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crossing_scene import SOURCES, construct, load_case, validate_site
import native_capture
import native_output_bridge
from native_capture import validate_frame
from runner import check


class Adapter:
    def __init__(self):
        self.calls = []
        self.corrupt = None

    def build_school_crossing_zone(self, site, case):
        self.calls.append("build")
        result = {
            "map_sha256": site["map_sha256"],
            "zone_polygon_xy_m": site["zone_polygon_xy_m"],
            "route_xy_m": site["route_xy_m"],
            "crosswalk_polygon_xy_m": site["crosswalk_polygon_xy_m"],
            "pupil_route_xy_m": site["pupil_route_xy_m"],
            "vehicle_blueprint": site["heavy_blueprint"] if case["vehicle_request"] == "heavy_motor_vehicle" else site["car_blueprint"],
            "driver_id": site["driver_id"], "vehicle_id": 41,
            "children_xy_m": site["children_xy_m"] if case["children_request"] == "children" else [],
            "inside_designated_zone": case["zone_request"] == "inside",
            "school_in_session_today": site["school_in_session_today"],
            "time_window_label": site["time_window_label"],
            "beacon_or_sign_state": site["beacon_or_sign_state"],
            "beacon_yellow_lamp_count": site["beacon_yellow_lamp_count"],
            "beacon_alternating_capable": site["beacon_alternating_capable"],
        }
        if self.corrupt in result:
            result[self.corrupt] = None
        return result

    def configure_speed_controller(self, scene, speed, case):
        self.calls.append("controller")
        return {"vehicle_id": scene["vehicle_id"], "target_mps": speed}


class FakeWorld:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.frame = 99

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.frame / 20))


class FakeStream:
    def __init__(self, target):
        self.target = target
        self.data = bytearray()
        self.closed = False

    def write(self, data):
        self.data.extend(data)

    def close(self):
        self.target.write_bytes(self.data)
        self.closed = True


class FakeEncoder:
    def __init__(self, target):
        self.stdin = FakeStream(target)
        self.stderr = SimpleNamespace(read=lambda: b"")

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class SceneTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def packet(self, case_id):
        case = load_case(case_id)
        records = {}
        for name in SOURCES:
            p = self.root / (name + ".txt")
            p.write_text("Synthetic protocol test for " + name + "\n")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            records[name] = {"path": p.name, "sha256": digest}
        device = case["beacon_or_sign_request"]
        packet = {
            "case_id": case_id, "source_kind": "reviewed_original_school_crossing_zone_site",
            "map_sha256": "a" * 64, "source_records": records,
            "zone_polygon_xy_m": [[0, 0], [100, 0], [100, 20], [0, 20]],
            "route_xy_m": [[-20, 10], [120, 10]], "children_xy_m": [[40, 16]],
            "heavy_blueprint": "vehicle.school_bus", "car_blueprint": "vehicle.sedan",
            "driver_id": "test_driver", "heavy_route_id": "test_route",
            "school_property_id": "test_property", "street_nonadjacent_to_school_property": True,
            "crosswalk_id": "test_crosswalk", "designated_pupil_route_id": "test_pupil_route",
            "crosswalk_polygon_xy_m": [[38, 0], [42, 0], [42, 20], [38, 20]],
            "pupil_route_xy_m": [[40, -10], [40, 30]],
            "school_in_session_today": case["session_request"] == "session",
            "operational_beacon_designation": device.startswith("operational_") or device in
                ("one_yellow_light", "nonalternating_yellow"),
            "time_window_label": case["time_request"], "beacon_or_sign_state": device,
            "beacon_yellow_lamp_count": 1 if device == "one_yellow_light" else 2,
            "beacon_alternating_capable": device != "nonalternating_yellow",
        }
        when = "2026-11-26T12:00:00-08:00"
        if case["time_request"] == "after_half_hour":
            when = "2026-11-26T16:31:00-08:00"
        if case["time_request"] == "before_half_hour":
            when = "2026-11-27T07:29:00-08:00"
        lamp_count = packet["beacon_yellow_lamp_count"]
        if device == "operational_not_flashing":
            history = [[False] * lamp_count for _ in range(4)]
        elif device == "one_yellow_light":
            history = [[True], [False], [True], [False]]
        elif device == "nonalternating_yellow":
            history = [[True, False] for _ in range(4)]
        else:
            history = [[True, False], [False, True], [True, False], [False, True]]
        packet["timing_packet"] = {
            "source_kind": "original_school_clock_and_device",
            "local_datetime": when,
            "operation_end_local": "2026-11-26T16:00:00-08:00",
            "next_operation_start_local": "2026-11-27T08:00:00-08:00",
            "class_start_local": "2026-11-26T08:00:00-08:00",
            "class_end_local": "2026-11-26T16:00:00-08:00",
            "school_in_session_today": packet["school_in_session_today"],
            "operational_beacon_designation": packet["operational_beacon_designation"],
            "sign_limit_active": device == "nonbeacon_sign_on",
            "beacon_yellow_lamp_count": lamp_count,
            "beacon_alternating_capable": packet["beacon_alternating_capable"],
            "beacon_lamp_history": history,
        }
        hash_fields = {
            "calendar_source_sha256": "school_calendar",
            "operation_source_sha256": "operation_hours",
            "class_source_sha256": "class_hours",
            "clock_source_sha256": "civil_date_time",
            "beacon_designation_source_sha256": "beacon_designation",
            "beacon_configuration_source_sha256": "beacon_lamp_configuration",
            "beacon_history_source_sha256": "beacon_lamp_history",
            "sign_source_sha256": "sign_active_period",
        }
        for field, name in hash_fields.items():
            packet["timing_packet"][field] = records[name]["sha256"]
        for name, record in records.items():
            packet[name + "_source_sha256"] = record["sha256"]
        path = self.root / "site.json"
        path.write_text(json.dumps(packet) + "\n")
        return path

    def test_all_exact_cases_build_and_bind_speed(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual(len(plan["cases"]), 14)
        for case in plan["cases"]:
            with self.subTest(case=case["case_id"]):
                path = self.packet(case["case_id"])
                adapter = Adapter()
                result = construct(adapter, path, case["case_id"])
                self.assertEqual(adapter.calls, ["build", "controller"])
                self.assertAlmostEqual(result["target_speed_mph"], case["speed_target_mph"])
                self.assertEqual(check(case["case_id"])["case_id"], case["case_id"])

    def test_source_change_rejected(self):
        case = load_case(json.loads((ROOT / "case-plan.json").read_text())["cases"][0]["case_id"])
        path = self.packet(case["case_id"])
        (self.root / "school_calendar.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            validate_site(path, case["case_id"])

    def test_crossing_zone_geometry_and_nonadjacency_required(self):
        case_id = json.loads((ROOT / "case-plan.json").read_text())["cases"][0]["case_id"]
        path = self.packet(case_id)
        packet = json.loads(path.read_text())
        packet["crosswalk_polygon_xy_m"] = [[138, 0], [142, 0], [142, 20], [138, 20]]
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "outside designated crossing-zone"):
            validate_site(path, case_id)
        packet["crosswalk_polygon_xy_m"] = [[38, 0], [42, 0], [42, 20], [38, 20]]
        packet["street_nonadjacent_to_school_property"] = False
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "nonadjacency"):
            validate_site(path, case_id)

    def test_readback_change_rejected(self):
        case_id = json.loads((ROOT / "case-plan.json").read_text())["cases"][0]["case_id"]
        path = self.packet(case_id)
        adapter = Adapter()
        adapter.corrupt = "inside_designated_zone"
        with self.assertRaisesRegex(ValueError, "intervention readback"):
            construct(adapter, path, case_id)

    def test_unproved_time_label_rejected(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        case_id = next(case["case_id"] for case in plan["cases"]
                       if case["time_request"] == "after_half_hour")
        path = self.packet(case_id)
        packet = json.loads(path.read_text())
        packet["timing_packet"]["local_datetime"] = "2026-11-26T12:00:00-08:00"
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "clock proof"):
            validate_site(path, case_id)

    def test_beacon_uses_lamp_history_not_label(self):
        case_id = json.loads((ROOT / "case-plan.json").read_text())["cases"][0]["case_id"]
        path = self.packet(case_id)
        packet = json.loads(path.read_text())
        packet["timing_packet"]["beacon_lamp_history"] = [[False, False]] * 4
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "alternating yellow flash"):
            validate_site(path, case_id)

    def test_original_frame_protocol_rejects_missing_device_readback(self):
        case = json.loads((ROOT / "case-plan.json").read_text())["cases"][0]
        site = validate_site(self.packet(case["case_id"]), case["case_id"])
        site["vehicle_id"] = 41
        row = {"native_frame": 100, "frame": 0, "time_s": 0.0,
               "map_sha256": site["map_sha256"], "driver_id": site["driver_id"],
               "vehicle_id": 41, "vehicle_blueprint": site["heavy_blueprint"],
               "heavy_speed_mps": case["speed_target_mph"] / 2.2369362921,
               "inside_designated_zone": True, "sign_limit_active": True,
               "beacon_yellow_lights_lit": [True, False],
               "children_actor_ids": ["51"],
               "children_actor_readback": [{"actor_id": 51, "blueprint": "walker.pedestrian.0001",
                                             "position_m": [40, 16, 0],
                                             "body_vertices_m": [[40, 16, 0]] * 4}],
               "actor_id": 41, "position_m": [0, 10, 0],
               "heading_xy": [1, 0], "body_vertices_m": [[0, 10, 0]] * 4,
               "school_in_session_today": True,
               "beacon_or_sign_state": case["beacon_or_sign_request"],
               "time_window_label": case["time_request"]}
        for name in SOURCES:
            row[name + "_source_sha256"] = site[name + "_source_sha256"]
        validate_frame(row, 0, 100, case, site)
        row.pop("beacon_yellow_lights_lit")
        with self.assertRaisesRegex(ValueError, "per-yellow-lamp"):
            validate_frame(row, 0, 100, case, site)

    def test_two_tick_capture_protocol_and_world_restore(self):
        case = json.loads((ROOT / "case-plan.json").read_text())["cases"][0]
        site = validate_site(self.packet(case["case_id"]), case["case_id"])
        site["vehicle_id"] = 41
        map_bytes = b"original test OpenDRIVE"
        site["map_sha256"] = hashlib.sha256(map_bytes).hexdigest()

        class CaptureAdapter:
            def read_original_context(self, current_site, current_case):
                result = {"case_id": current_case["case_id"],
                          "map_sha256": current_site["map_sha256"],
                          "vehicle_id": current_site["vehicle_id"],
                          "driver_id": current_site["driver_id"],
                          "heavy_blueprint": current_site["heavy_blueprint"],
                          "vehicle_blueprint": current_site["heavy_blueprint"],
                          "zone_polygon_xy_m": current_site["zone_polygon_xy_m"],
                          "route_xy_m": current_site["route_xy_m"],
                          "crosswalk_polygon_xy_m": current_site["crosswalk_polygon_xy_m"],
                          "pupil_route_xy_m": current_site["pupil_route_xy_m"],
                          "street_nonadjacent_to_school_property": True,
                          "school_in_session_today": current_site["school_in_session_today"],
                          "operational_beacon_designation": current_site["operational_beacon_designation"]}
                for name in SOURCES:
                    result[name + "_source_sha256"] = current_site[name + "_source_sha256"]
                    result[name + "_source"] = current_site["source_records"][name]["path"]
                for field in ("local_datetime", "operation_end_local", "next_operation_start_local",
                              "class_start_local", "class_end_local"):
                    result[field] = current_site["timing_packet"][field]
                return result

            def control_frame(self, current_case, index):
                pass

            def read_original_frame(self, current_case, index, number):
                result = {"native_frame": number, "frame": index,
                          "time_s": index / 20, "map_sha256": site["map_sha256"],
                          "driver_id": site["driver_id"], "vehicle_id": 41,
                          "vehicle_blueprint": site["heavy_blueprint"],
                          "heavy_speed_mps": case["speed_target_mph"] / 2.2369362921,
                          "inside_designated_zone": True, "sign_limit_active": True,
                          "beacon_yellow_lights_lit": [index == 0, index == 1],
                          "children_actor_ids": ["51"],
                          "children_actor_readback": [{"actor_id": 51, "blueprint": "walker.pedestrian.0001",
                                                        "position_m": [40, 16, 0],
                                                        "body_vertices_m": [[40, 16, 0]] * 4}],
                          "actor_id": 41, "position_m": [0, 10, 0],
                          "heading_xy": [1, 0], "body_vertices_m": [[0, 10, 0]] * 4,
                          "school_in_session_today": True,
                          "beacon_or_sign_state": case["beacon_or_sign_request"],
                          "time_window_label": case["time_request"]}
                for name in SOURCES:
                    result[name + "_source_sha256"] = site[name + "_source_sha256"]
                return result

            def camera_rgb24(self, view, number):
                return bytes([number % 256] * 12)

        world = FakeWorld()
        output = self.root / "capture"
        def encoder(folder, view):
            return FakeEncoder(folder / (view + ".mkv"))
        with patch.object(native_capture, "FRAMES", 2), patch.object(
                native_capture, "SIZES", {view: (2, 2) for view in native_capture.VIEWS}), patch.object(
                native_capture, "_encoder", side_effect=encoder):
            produced = native_capture.capture(world, CaptureAdapter(), site,
                                              case["case_id"], output, site["_source_sha256"])
        self.assertFalse(world.get_settings().synchronous_mode)
        self.assertIsNone(world.get_settings().fixed_delta_seconds)
        receipt = json.loads(Path(produced["receipt"]).read_text())
        self.assertEqual(receipt["frame_count"], 2)
        self.assertEqual(len(Path(produced["trace"]).read_text().splitlines()), 2)
        self.assertEqual(set(json.loads(Path(produced["camera_manifest"]).read_text())["streams"]),
                         set(native_capture.VIEWS))
        camera_bytes = (output / "overview.mkv").read_bytes()
        with patch.object(native_output_bridge, "FRAMES", 2):
            with self.assertRaisesRegex(ValueError, "loaded map differs"):
                native_output_bridge.publish(output, map_bytes=b"wrong map", restored=True)
            (output / "overview.mkv").write_bytes(b"changed camera")
            with self.assertRaisesRegex(ValueError, "original synchronized camera stream differs"):
                native_output_bridge.publish(output, map_bytes=map_bytes, restored=True)
            (output / "overview.mkv").write_bytes(camera_bytes)
            adapter_package = types.ModuleType("traffic_spec_adapter")
            adapter_module = types.ModuleType("traffic_spec_adapter.adapter")
            adapter_module.write_adapter_graph = lambda graph, path: Path(path).write_text(
                json.dumps(graph.graph) + "\n")
            worker_package = types.ModuleType("worker_exchange")
            native_module = types.ModuleType("worker_exchange.native_output")
            native_module.seal_capture = lambda root, **kwargs: {"frames": kwargs["frames"]}
            with patch.dict(sys.modules, {"traffic_spec_adapter": adapter_package,
                                          "traffic_spec_adapter.adapter": adapter_module,
                                          "worker_exchange": worker_package,
                                          "worker_exchange.native_output": native_module}):
                receipt = native_output_bridge.publish(output, map_bytes=map_bytes,
                                                       restored=True)
            self.assertEqual(receipt["frames"], 2)
            self.assertEqual(len((output / "trace.jsonl").read_text().splitlines()), 2)
            self.assertEqual(len((output / "video_frames.jsonl").read_text().splitlines()), 2)
            self.assertEqual(len((output / "capture/native/frames.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
