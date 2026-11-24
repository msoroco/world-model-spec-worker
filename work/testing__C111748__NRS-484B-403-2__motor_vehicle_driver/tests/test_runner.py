import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_runner_test", ROOT / "runner.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


class Actor:
    def __init__(self): self.commands = []; self.destroyed = False
    def apply_control(self, command): self.commands.append(command)
    def destroy(self): self.destroyed = True


class Map:
    name = "Town01"
    def __init__(self, source): self.source = source
    def to_opendrive(self): return self.source


class World:
    def __init__(self, source):
        self.map = Map(source); self.frame = 99; self.actors = []
    def get_map(self): return self.map
    def get_blueprint_library(self): return self
    def find(self, name): return name
    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(); self.actors.append(actor); return actor
    def tick(self): self.frame += 1; return self.frame
    def get_snapshot(self):
        return type("Snapshot", (), {"frame": self.frame,
                                     "timestamp": type("Timestamp", (), {"elapsed_seconds": (self.frame - 100) / 20})()})()


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "site.json"
        self.source = "<OpenDRIVE><road id='1'/></OpenDRIVE>"
        site = {"case_id": CASE, "map_name": "Town01",
                "map_sha256": hashlib.sha256(self.source.encode()).hexdigest(),
                "highway_status": {"source_sha256": "highway"},
                "ego_blueprint": "vehicle.test", "ego_spawn": [0, 0], "ego_id": 42,
                "device_blueprint": "static.prop.sign", "camera_plan_sha256": "cameras",
                "u_turn_route": [{"road_id": 1, "lane_id": 1, "x": 0, "y": 0},
                                 {"road_id": 1, "lane_id": 1, "x": 10, "y": 0},
                                 {"road_id": 1, "lane_id": -1, "x": 0, "y": 5}],
                "device": {"device_id": 77, "authority_source_sha256": "authority",
                           "legal_consistency_source_sha256": "legal",
                           "display_source_sha256": "display",
                           "governed_approach": "A", "position_xy_m": [1, 2],
                           "prohibits_u_turn": True}}
        raw = json.dumps(site).encode(); self.path.write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()
        self.restored = False

    def sample(self, world, actors, frame, site):
        i = frame - 100
        return {"ego": {"id": 42, "road_id": 1, "lane_id": -1 if i == 3 else 1,
                        "x": i, "y": 0, "yaw_deg": 180 if i == 3 else 0,
                        "approach_id": "A", "u_turn_in_progress": i == 2},
                "device_readback": {"device_id": 77, "prohibits_u_turn": True,
                                    "visible_to_ego": i >= 1},
                "cameras": {name: frame for name in mod.capture.CAMERAS}}

    def run_case(self, world, sample):
        return mod.run(world, self.path, self.sha, CASE, Path(self.tmp.name) / "native.json",
                       ego_transform="ego", device_transform="device",
                       camera_sample=sample, control_factory=lambda d: d,
                       snapshot_world=lambda w: "state",
                       restore_world=lambda w, state: setattr(self, "restored", state == "state"),
                       frames=4, diagnostic=True)

    def test_runner_controls_and_restores(self):
        world = World(self.source)
        result = self.run_case(world, self.sample)
        self.assertTrue(result["measurement"]["turn_observed"])
        self.assertFalse(result["map_binding"]["physical_turn_verified"])
        self.assertTrue(self.restored)
        self.assertTrue(all(a.destroyed for a in world.actors))
        self.assertTrue(any(c.get("phase") == "route_turn" for c in world.actors[0].commands))
        self.assertEqual(world.actors[0].commands[-1]["brake"], 1.0)

    def test_readback_failure_brakes_and_restores(self):
        world = World(self.source)
        def fail_sample(*args):
            raise RuntimeError("camera readback failed")
        with self.assertRaisesRegex(RuntimeError, "camera readback"):
            self.run_case(world, fail_sample)
        self.assertTrue(self.restored)
        self.assertTrue(all(a.destroyed for a in world.actors))
        self.assertEqual(world.actors[0].commands[-1]["brake"], 1.0)

    def test_map_drift_rejected_before_world_mutation(self):
        world = World(self.source + "changed")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            self.run_case(world, self.sample)
        self.assertEqual(world.actors, [])
