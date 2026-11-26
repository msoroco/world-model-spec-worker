"""Fake Native construction checks; synthetic packets are never production evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "pass_scene.py"
spec = importlib.util.spec_from_file_location("pass_scene", MODULE)
scene = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scene
spec.loader.exec_module(scene)
PLAN = json.loads((MODULE.parent / "case-plan.json").read_text())


class FakeAdapter:
    native_attested = False

    def __init__(self, packet):
        self.packet = packet
        self.destroyed = []
        self.spawned = []

    def map_name(self):
        return self.packet["map_name"]

    def lane_at(self, xy):
        return (1, -2) if xy[1] < 2 else (1, -1)

    def spawn(self, blueprint, xy, yaw):
        actor = (blueprint, tuple(xy), yaw)
        self.spawned.append(actor)
        return actor

    def actor_blueprint(self, actor):
        return actor[0]

    def actor_lane(self, actor):
        return self.lane_at(actor[1])

    def destroy(self, actor):
        self.destroyed.append(actor)


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = PLAN["cases"][0]

    def packet(self, case=None):
        case = case or self.case
        refs = []
        for name in ("map", "lanes", "actors"):
            data = (name + " synthetic source\n").encode()
            (self.root / (name + ".txt")).write_bytes(data)
            refs.append({"path": name + ".txt", "sha256": hashlib.sha256(data).hexdigest()})
        two = case["same_direction_lane_count_requested"] == 2
        occupied = case["left_lane_traffic_requested"] == "occupied"
        lanes = [{"lane_id": "right", "native_road_id": 1, "native_lane_id": -2,
                  "travel_direction": "forward", "immediate_left_lane_id": "left" if two else None,
                  "source_ref": "lanes.txt"}]
        if two:
            lanes.append({"lane_id": "left", "native_road_id": 1, "native_lane_id": -1,
                          "travel_direction": "forward", "source_ref": "lanes.txt"})
        packet = {"case_id": case["case_id"], "cell_id": "C228989",
                  "actor": "motor_vehicle_driver", "source_kind": "synthetic_cpu_fixture",
                  "source_refs": refs, "map_name": "TownSurvey", "control_kind": case["control_kind"],
                  "ego_blueprint_id": "vehicle.test.car", "control_blueprint_id": "vehicle.test.cycle",
                  "ego_driver_source": "actors.txt", "control_rider_source": "actors.txt",
                  "lanes": lanes, "ego_lane_id": "right",
                  "immediate_left_lane_id": "left" if two else None,
                  "road_forward": [1, 0], "spawn_yaw_deg": 0,
                  "spawn_xy": {"ego": [0, 0], "control": [20, 0]},
                  "lane_restrictions_source": "lanes.txt",
                  "lane_obstructions_source": "lanes.txt",
                  "surrounding_traffic_source": "actors.txt",
                  "occupant_lane_id": "left" if occupied else None}
        if occupied:
            packet["occupant_blueprint_id"] = "vehicle.test.other"
            packet["spawn_xy"]["occupant"] = [10, 4]
        path = self.root / "packet.json"
        path.write_text(json.dumps(packet) + "\n")
        return path, packet

    def test_all_fourteen_cases_spawn_in_surveyed_lanes(self):
        for case in PLAN["cases"]:
            with self.subTest(case=case["case_id"]):
                path, packet = self.packet(case)
                fake = FakeAdapter(packet)
                result = scene.construct(fake, path, case, allow_synthetic=True)
                expected = 3 if case["left_lane_traffic_requested"] == "occupied" else 2
                self.assertEqual(len(result["owned"]), expected)
                self.assertIsNone(result["legal_due_care"])

    def test_production_rejects_synthetic_packet(self):
        path, packet = self.packet()
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            scene.construct(FakeAdapter(packet), path, self.case)

    def test_lost_source_or_wrong_lane_readback_rejects(self):
        path, packet = self.packet()
        (self.root / "lanes.txt").write_text("altered\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            scene.validate(path, self.case, allow_synthetic=True)
        path, packet = self.packet()
        fake = FakeAdapter(packet)
        fake.lane_at = lambda xy: (1, -1)
        with self.assertRaisesRegex(ValueError, "waypoint lane readback"):
            scene.construct(fake, path, self.case, allow_synthetic=True)

    def test_spawn_failure_cleans_owned_ego(self):
        path, packet = self.packet()
        fake = FakeAdapter(packet)
        original = fake.spawn
        fake.spawn = lambda blueprint, xy, yaw: None if blueprint == packet["control_blueprint_id"] else original(blueprint, xy, yaw)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            scene.construct(fake, path, self.case, allow_synthetic=True)
        self.assertEqual(fake.destroyed, fake.spawned)


if __name__ == "__main__":
    unittest.main()
