import hashlib
import json
import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_right_turn_control import CASE_DISTANCES_M, RightTurnPolicy, source_row
from runner import CONFIG, check_construction, retain_site_packet


class Light:
    RightBlinker = 16


class Vehicle:
    def __init__(self, readback=True):
        self.lights = 4
        self.readback = readback
    def get_light_state(self):
        return self.lights
    def set_light_state(self, state):
        if self.readback:
            self.lights = state


class NativeRightTurnTests(unittest.TestCase):
    def test_runner_cpu_check_and_exact_site_packet(self):
        self.assertFalse(check_construction()["simulation_started"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = root / "source.txt"
            document.write_text("Independent freight zone and district review source\n")
            packet = root / "site.json"
            source = {"authored_map_sha256": CONFIG["map_sha256"],
                      "native_map_name": "Native C378304", "case_id": CONFIG["selected_case_id"],
                      "district_type": "other" if CONFIG["selected_case_id"].endswith(("__other_area_right_at_300ft", "__other_area_right_below_300ft", "__other_area_right_above_300ft")) else "business",
                      "independent_review": True,
                      "freight_loading_zone_review": True,
                      "source_document": str(document),
                      "source_document_sha256": hashlib.sha256(document.read_bytes()).hexdigest()}
            packet.write_text(json.dumps(source))
            out = root / "out"; out.mkdir()
            retained = retain_site_packet(packet, out, "Native C378304", CONFIG["selected_case_id"])
            self.assertEqual(retained["freight_loading_zone_source_sha256"], source["source_document_sha256"])
            self.assertEqual((out / "freight-zone-site-source.txt").read_bytes(), document.read_bytes())
            source["freight_loading_zone_review"] = False
            packet.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "independent district/zone"):
                retain_site_packet(packet, root / "rejected", "Native C378304", CONFIG["selected_case_id"])

    def test_exact_config_binds_map_camera_and_source_policy(self):
        folder = Path(__file__).resolve().parents[1]
        config = json.loads((folder / "config.json").read_text())
        self.assertEqual(config["map_sha256"], hashlib.sha256(
            (folder / config["map_path"]).read_bytes()).hexdigest())
        self.assertEqual(config["native_controller_module"], "native_right_turn_control.py")
        self.assertEqual((config["rate_hz"], config["duration_s"]), (20, 45))
        self.assertEqual([camera["name"] for camera in config["cameras"]],
                         ["overview", "approach", "reference_corner", "driver_reference"])
        self.assertEqual(len(config["supported_case_ids"]), len(CASE_DISTANCES_M))
        self.assertEqual(config["physical_completion"]["motion_source"], "drive_history.jsonl")

    def test_all_six_exact_indicator_starts(self):
        self.assertEqual(len(CASE_DISTANCES_M), 8)
        for name, distance in CASE_DISTANCES_M.items():
            with self.subTest(name=name):
                policy = RightTurnPolicy("testing__C378304__NRS-484B-413-2__motor_vehicle_driver__" + name)
                vehicle = Vehicle()
                self.assertFalse(policy.apply(vehicle, Light, 0)["readback_right_indicator"])
                self.assertFalse(policy.apply(vehicle, Light, 120 - distance - 0.1)["readback_right_indicator"])
                self.assertTrue(policy.apply(vehicle, Light, 120 - distance)["readback_right_indicator"])
                self.assertEqual(vehicle.lights & 4, 4)

    def test_interruption_and_failed_readback(self):
        policy = RightTurnPolicy("zone_right_interrupted")
        vehicle = Vehicle()
        self.assertTrue(policy.apply(vehicle, Light, 82)["readback_right_indicator"])
        self.assertFalse(policy.apply(vehicle, Light, 99)["readback_right_indicator"])
        self.assertTrue(policy.apply(vehicle, Light, 104)["readback_right_indicator"])
        self.assertTrue(policy.interruption_seen)
        with self.assertRaisesRegex(ValueError, "readback"):
            RightTurnPolicy("zone_right_at_100ft").apply(Vehicle(readback=False), Light, 90)
        with self.assertRaisesRegex(ValueError, "reversed"):
            policy.apply(vehicle, Light, 90)

    def test_source_row_uses_original_native_values(self):
        class Obj: pass
        snap = Obj();snap.frame = 42;snap.timestamp = Obj();snap.timestamp.elapsed_seconds = 2.1
        ego = Obj();ego.get_light_state = lambda: 20
        ego.get_transform = lambda: type("Transform", (), {"location": type("Point", (), {"x": -34.0, "y": -1.8})(), "rotation": type("Rotation", (), {"yaw": -12.0})()})()
        ego.get_velocity = lambda: type("Vector", (), {"x": 3.0, "y": 4.0, "z": 0.0})()
        ego.bounding_box = Obj()
        ego.bounding_box.get_world_vertices = lambda transform: [
            type("Point", (), {"x": x, "y": y})() for x, y in
            ((-35.0, -2.5), (-33.0, -2.5), (-35.0, -1.1), (-33.0, -1.1))]
        waypoint = Obj();waypoint.road_id = 378304;waypoint.lane_id = -1
        row = source_row(snap, ego, waypoint, Light)
        self.assertEqual((row["frame"], row["ego_speed_mps"], row["right_indicator"]), (42, 5.0, True))
        self.assertEqual((row["native_road_id"], row["native_lane_id"]), (378304, -1))
        self.assertEqual(len(row["ego_body_vertices_xy_m"]), 4)


if __name__ == "__main__":
    unittest.main()
