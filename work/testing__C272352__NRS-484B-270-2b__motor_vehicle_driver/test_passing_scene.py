import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from passing_controller import Sample, command
from passing_native_capture import capture
from passing_scene import construct, validate


AID = "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver"


class FakeAdapter:
    native_attested = False

    def __init__(self):
        self.actors = []
        self.destroyed = []
        self.bad_readback = False
        self.restored = False
        self.braked = False

    def map_name(self):
        return "CPU fixture map"

    def lane_at(self, xy):
        return (8, 1)

    def spawn(self, blueprint, xy, yaw):
        actor = (blueprint, tuple(xy), yaw)
        self.actors.append(actor)
        return actor

    def actor_blueprint(self, actor):
        return actor[0]

    def actor_lane(self, actor):
        return (8, 2) if self.bad_readback else (8, 1)

    def actor_id(self, actor):
        return self.actors.index(actor) + 1

    def destroy(self, actor):
        self.destroyed.append(actor)

    def observe_pass(self, scene):
        return Sample(0, 0, 4, 10, 12, 0, .5, 1.1, True,
                      "centerline", "zone", "traffic", "bodies")

    def apply_pass_control(self, ego, intent):
        self.intent = intent

    def tick(self, scene):
        return {"frame": 1, "time_s": .05}

    def read_pass_row(self, scene, frame):
        return {"origin": "native_world_snapshot", "frame": frame,
                "time_s": .05, "vehicle_box": [0, 4, 0, 2],
                "bicycle_box": [10, 12, 0, .5], "vehicle_speed_mps": 5,
                "bicycle_speed_mps": 2, "vehicle_source": "motion",
                "bicycle_source": "motion", "lane_source": "lane"}

    def read_cameras(self, scene, frame):
        return {}

    def brake(self):
        self.braked = True

    def restore(self):
        self.restored = True


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        refs = []
        for role, name in (("map", "map.json"), ("lane", "lanes.json"),
                           ("traffic", "traffic.json")):
            path = self.directory / name
            path.write_text('{"fixture":true}\n', encoding="utf-8")
            refs.append({"role": role, "path": name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.case = {"case_id": AID + "__bike_clearance_above", "control_kind": "bicycle",
                     "target_clearance_m": 1.1, "route_request": "within_right_half"}
        self.packet = {
            "case_id": self.case["case_id"], "cell_id": "C272352",
            "source_kind": "synthetic_cpu_fixture", "source_refs": refs,
            "public_highway_source": "map.json", "map_name": "CPU fixture map",
            "centerline_source": "lanes.json", "zone_source": "lanes.json",
            "centerline_y": 3.0, "right_side_y": 1.0,
            "opposing_traffic_source": "traffic.json",
            "exception_213_217_source": "map.json",
            "lanes": [{"direction": "forward", "native_road_id": 8,
                       "native_lane_id": 1, "source_ref": "lanes.json"},
                      {"direction": "reverse", "native_road_id": 8,
                       "native_lane_id": -1, "source_ref": "lanes.json"}],
            "ego_blueprint_id": "vehicle.test", "control_blueprint_id": "vehicle.bicycle",
            "control_kind": "bicycle", "ego_driver_source": "traffic.json",
            "control_rider_source": "traffic.json",
            "spawn_xy": {"ego": [0, 0], "control": [12, 0]},
            "road_forward": [1, 0], "spawn_yaw_deg": 0,
            "route_xy": [[0, 0], [12, 2], [25, 0]]}
        self.packet_path = self.directory / "survey.json"
        self.write_packet()

    def write_packet(self):
        self.packet_path.write_text(json.dumps(self.packet) + "\n", encoding="utf-8")

    def test_source_sealed_spawn_and_ownership(self):
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            validate(self.packet_path, self.case)
        adapter = FakeAdapter()
        result = construct(adapter, self.packet_path, self.case, synthetic=True)
        self.assertEqual(len(result["owned"]), 2)
        self.assertIsNone(result["legal_safety"])

    def test_fails_on_source_or_lane_change(self):
        (self.directory / "map.json").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale source"):
            validate(self.packet_path, self.case, synthetic=True)
        (self.directory / "map.json").write_text('{"fixture":true}\n', encoding="utf-8")
        self.packet["lanes"].append({"direction": "forward", "native_road_id": 8,
                                     "native_lane_id": 2, "source_ref": "lanes.json"})
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "one same-direction"):
            validate(self.packet_path, self.case, synthetic=True)

    def test_spawn_rollback_on_bad_readback(self):
        adapter = FakeAdapter()
        adapter.bad_readback = True
        with self.assertRaisesRegex(ValueError, "readback"):
            construct(adapter, self.packet_path, self.case, synthetic=True)
        self.assertEqual(len(adapter.destroyed), 1)

    def test_capture_rejects_missing_cameras_and_cleans_up(self):
        adapter = FakeAdapter()
        target = self.directory / "attempt"
        with self.assertRaisesRegex(ValueError, "four original cameras"):
            capture(adapter, self.packet_path, self.case, target,
                    synthetic=True, frame_count=1)
        self.assertFalse(target.exists())
        self.assertEqual(len(adapter.destroyed), 2)
        self.assertTrue(adapter.braked and adapter.restored)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.case = {"case_id": AID + "__bike_clearance_above", "control_kind": "bicycle",
                     "target_clearance_m": 1.1, "route_request": "within_right_half"}
        self.sample = Sample(21, 0, 4, 10, 12, 0, .5, 1.1, True,
                             "centerline", "zone", "traffic", "bodies")

    def test_clearance_and_return_are_readback_gated(self):
        self.assertEqual(command(self.case, self.sample)["mode"], "establish_left_clearance")
        left = replace(self.sample, ego_lateral_m=2)
        self.assertEqual(command(self.case, left)["mode"], "continue_left_pass")
        past = replace(left, ego_rear_m=13, ego_front_m=17)
        self.assertEqual(command(self.case, past)["mode"], "return_right")
        self.assertIsNone(command(self.case, past)["legal_safety"])

    def test_traffic_and_early_return_inhibit(self):
        self.assertEqual(command(self.case, replace(self.sample, opposing_path_clear=False))["mode"], "hold_back")
        early = {**self.case, "return_request": "early"}
        self.assertEqual(command(early, self.sample)["mode"], "return_right_early_requested")
        with self.assertRaisesRegex(ValueError, "missing original source"):
            command(self.case, replace(self.sample, traffic_source=""))


if __name__ == "__main__":
    unittest.main()
