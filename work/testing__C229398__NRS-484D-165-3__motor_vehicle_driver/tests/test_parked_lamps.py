import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / "parked_lamps.py"
SPEC = importlib.util.spec_from_file_location("parked_lamps", MODULE)
lamps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lamps)
sys.path.insert(0, str(MODULE.parent))
from finalize_original import finalize
HASH = "a" * 64


def site(case_key="dark_lamps_on"):
    return {
        "law_id": lamps.LAW, "cell_id": "C229398", "map_sha256": HASH,
        "site_source_sha256": "b" * 64, "map_name": "Town05", "curb_waypoint_xyz": [1.0, 2.0, 0.0],
        "road_id": 3, "lane_id": -1, "traffic_side": "left", "time_qualifies": case_key != "outside_referenced_time",
        "lighting_assessment": lamps.CASES[case_key]["lighting"], "lighting_assessment_source": "reviewed source",
        "revelation_station_m": 304.8, "front_lamp_station_m": 152.4, "rear_lamp_station_m": 152.4,
        "shoulder_spawn_transform": {"xyz": [1.0, 2.0, 0.0], "rpy": [0.0, 0.0, 0.0], "source": "survey"},
        "traveled_spawn_transform": {"xyz": [1.0, 4.0, 0.0], "rpy": [0.0, 0.0, 0.0], "source": "survey"},
        **{k: "reviewed local source" for k in ("highway_public_use_source", "shoulder_boundary_source",
            "traveled_boundary_source", "traffic_direction_source", "vehicle_class_source", "reference_time_source",
            "visibility_station_source", "lamp_installation_source")},
    }


def frames(case_key="dark_lamps_on"):
    spec = lamps.CASES[case_key]
    station = lambda n, color: {"station_m": 152.4, "source_camera": f"{n}_camera", "color_assessment": color,
                                 "visibility_assessment": "unknown"}
    one = {"map_sha256": HASH, "vehicle_alive": True, "vehicle_role": "motor_vehicle_driver",
           "placement": spec["placement"], "attendance": spec["attendance"], "curb_boundary_visible": None,
           "curb_boundary_source": "reviewed local source",
           "traffic_side": "left", "time_qualifies": case_key != "outside_referenced_time",
           "lighting_assessment": spec["lighting"], "parking_brake": True, "speed_mps": 0.0,
           "front_lamp_state": spec["lamps"], "rear_lamp_state": spec["lamps"],
           "front_lamp_observation": station("front", "unknown"),
           "rear_lamp_observation": station("rear", "unknown"),
           "revelation_observation": {"station_m": 304.8, "source_camera": "front_camera", "assessment": "unknown"},
           "installed_lamp_positions": [{"side": "left", "source": "reviewed installation record"}]}
    return [dict(copy.deepcopy(one), frame_index=i, time_s=i / 20) for i in range(900)]


class LampEvidenceTest(unittest.TestCase):
    def test_native_construction_shoulder_and_traveled(self):
        class State(int):
            NONE = 0
            Position = 1
            LowBeam = 2

        carla = types.SimpleNamespace(Location=lambda *xyz: xyz, Rotation=lambda *rpy: rpy,
                                      Transform=lambda xyz, rpy: (xyz, rpy), VehicleControl=lambda **k: k,
                                      VehicleLightState=State)

        class Actor:
            def __init__(self):
                self.light = State(0)

            def apply_control(self, value):
                self.control = value

            def set_light_state(self, value):
                self.light = value

            def get_light_state(self):
                return self.light

        class Map:
            name = "Town05"

            def get_waypoint(self, *_args, **_kwargs):
                return types.SimpleNamespace(road_id=3, lane_id=-1)

        class World:
            def __init__(self):
                self.spawns = []

            def get_map(self):
                return Map()

            def get_blueprint_library(self):
                return types.SimpleNamespace(find=lambda name: name)

            def try_spawn_actor(self, _blueprint, transform):
                self.spawns.append(transform)
                return Actor()

        with patch.dict(sys.modules, {"carla": carla}):
            world = World()
            shoulder = lamps.construct(world, site(), "dark_lamps_on", HASH)
            traveled = lamps.construct(world, site("dark_traveled"), "dark_traveled", HASH)
            self.assertEqual(world.spawns[0][0], (1.0, 2.0, 0.0))
            self.assertEqual(world.spawns[1][0], (1.0, 4.0, 0.0))
            self.assertEqual(shoulder["requested_lamp_mask"], 3)
            self.assertEqual(traveled["requested_lamp_mask"], 3)
            self.assertTrue(shoulder["actor"].control["hand_brake"])

    def test_all_six_exact_cases_and_20hz(self):
        for key in lamps.CASES:
            with self.subTest(key=key):
                result = lamps.measure(site(key), key, HASH, frames(key))
                self.assertEqual(result["original_frame_count"], 900)
                self.assertEqual(len(result["one_hz_original_samples"]), 45)

    def test_referenced_time_requires_source_status(self):
        s = site("outside_referenced_time")
        s["time_qualifies"] = True
        with self.assertRaisesRegex(ValueError, "reference-time"):
            lamps.validate_site(s, "outside_referenced_time", HASH)

    def test_missing_source_rejected(self):
        s = site()
        del s["highway_public_use_source"]
        with self.assertRaisesRegex(ValueError, "highway_public_use_source"):
            lamps.validate_site(s, "dark_lamps_on", HASH)

    def test_wrong_lamp_state_rejected(self):
        f = frames()
        f[130]["front_lamp_state"] = "off"
        with self.assertRaisesRegex(ValueError, "lamp state"):
            lamps.measure(site(), "dark_lamps_on", HASH, f)

    def test_missing_revelation_source_rejected(self):
        f = frames()
        del f[88]["revelation_observation"]["source_camera"]
        with self.assertRaisesRegex(ValueError, "revelation source"):
            lamps.measure(site(), "dark_lamps_on", HASH, f)

    def test_original_gap_rejected(self):
        f = frames()
        f[92]["frame_index"] = 93
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            lamps.measure(site(), "dark_lamps_on", HASH, f)

    def test_comparison_isolation_and_missing_member(self):
        keys = ["dark_lamps_on", "dark_lamps_off"]
        reports = [lamps.measure(site(k), k, HASH, frames(k)) for k in keys]
        self.assertEqual(len(lamps.audit_comparison(reports, keys, {"lamps"})["case_ids"]), 2)
        with self.assertRaisesRegex(ValueError, "member missing"):
            lamps.audit_comparison(reports[:1], keys, {"lamps"})
        with self.assertRaisesRegex(ValueError, "undeclared difference"):
            lamps.audit_comparison(reports, keys, set())

    def test_referenced_time_comparison(self):
        keys = ["sufficient_light", "outside_referenced_time"]
        reports = [lamps.measure(site(k), k, HASH, frames(k)) for k in keys]
        self.assertEqual(lamps.audit_comparison(reports, keys, {"time_qualifies"})["changed_fields"], ["time_qualifies"])

    def test_comparison_allows_changed_condition_source_but_rejects_changed_fixed_site(self):
        keys = ["dark_lamps_off", "sufficient_light"]
        first = lamps.measure(site(keys[0]), keys[0], HASH, frames(keys[0]))
        second_site = site(keys[1])
        second_site["site_source_sha256"] = "c" * 64
        second = lamps.measure(second_site, keys[1], HASH, frames(keys[1]))
        self.assertEqual(lamps.audit_comparison([first, second], keys, {"lighting"})["changed_fields"], ["lighting"])
        changed_site = site(keys[1])
        changed_site["traffic_side"] = "right"
        second["fixed_site_signature"] = lamps.fixed_site_signature(changed_site)
        with self.assertRaisesRegex(ValueError, "comparison fixed site changed"):
            lamps.audit_comparison([first, second], keys, {"lighting"})

    def test_saved_capture_source_seals_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            mapping = root / "original-map.json"
            mapping.write_text('{"frame_count":900}\n')
            cameras = {}
            for name in ("front", "rear", "left", "right"):
                source = root / f"{name}.txt"
                source.write_text(f"synthetic {name} receipt; no video\n")
                cameras[name] = {"path": source.name, "sha256": lamps.digest(source),
                                 "source_sensor": f"sensor-{name}", "fps": 20, "frames": 900}
            packet = {"case_id": f"{lamps.ASSIGNMENT}__dark_lamps_on", "map_sha256": HASH,
                      "site_source_sha256": "b" * 64, "source_type": "original_native_capture", "fps": 20,
                      "frame_count": 900, "cameras": cameras, "original_frame_map_path": mapping.name,
                      "original_frame_map_sha256": lamps.digest(mapping)}
            packet_path = root / "capture-packet.json"
            packet_path.write_text(json.dumps(packet))
            self.assertEqual(len(lamps.audit_saved_capture(root, "dark_lamps_on", HASH)["camera_names"]), 4)
            (root / "rear.txt").unlink()
            with self.assertRaisesRegex(ValueError, "rear camera source absent"):
                lamps.audit_saved_capture(root, "dark_lamps_on", HASH)

    def test_saved_finalizer_uses_sealed_original_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            s = site()
            site_path = root / "site.json"
            site_path.write_text(json.dumps(s))
            history = root / "original.jsonl"
            history.write_text("".join(json.dumps(row) + "\n" for row in frames()))
            mapping = root / "map.json"
            mapping.write_text('{"frame_count":900}\n')
            cameras = {}
            for name in ("front", "rear", "left", "right"):
                camera_path = root / f"{name}.txt"
                camera_path.write_text(f"synthetic {name} receipt\n")
                cameras[name] = {"path": camera_path.name, "sha256": lamps.digest(camera_path),
                                 "source_sensor": name, "fps": 20, "frames": 900}
            packet = {"case_id": lamps.ASSIGNMENT + "__dark_lamps_on", "map_sha256": HASH,
                      "site_source_sha256": "b" * 64, "site_packet_sha256": lamps.digest(site_path),
                      "source_type": "original_native_capture", "fps": 20, "frame_count": 900,
                      "cameras": cameras, "original_frame_map_path": mapping.name,
                      "original_frame_map_sha256": lamps.digest(mapping),
                      "original_history_path": history.name, "original_history_sha256": lamps.digest(history)}
            (root / "capture-packet.json").write_text(json.dumps(packet))
            self.assertEqual(finalize(root, "dark_lamps_on", site_path, HASH)["measurement"]["original_frame_count"], 900)
            history.write_text(history.read_text().replace('"front_lamp_state": "on"', '"front_lamp_state": "off"', 1))
            with self.assertRaisesRegex(ValueError, "original history seal mismatch"):
                finalize(root, "dark_lamps_on", site_path, HASH)


if __name__ == "__main__":
    unittest.main()
