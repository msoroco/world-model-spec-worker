import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path.cwd() / "runtime" / "scenario_pipeline"))
from native_session import LaneChangeSession
from test_camera_capture import Sensor
from test_native_construction import reviewed_packet


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = SimpleNamespace(cloudiness=10.0)
        self.actors = []
        self.spawned = 0

    def get_map(self):
        return SimpleNamespace(name="TownReviewed",
            to_opendrive=lambda: "<OpenDRIVE>reviewed</OpenDRIVE>")

    def get_settings(self):
        return copy.deepcopy(self.settings)

    def apply_settings(self, value):
        self.settings = copy.deepcopy(value)

    def get_weather(self):
        return copy.deepcopy(self.weather)

    def set_weather(self, value):
        self.weather = copy.deepcopy(value)

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: SimpleNamespace(set_attribute=lambda *a: None))

    def spawn_actor(self, blueprint, transform, attach_to=None):
        self.spawned += 1
        actor = Actor() if self.spawned <= 2 else Sensor()
        self.actors.append(actor)
        return actor


class Client:
    def __init__(self, world):
        self.world = world

    def get_world(self):
        return self.world

    def get_available_maps(self):
        return ["TownReviewed"]

    def load_world(self, name):
        if name != "TownReviewed":
            raise ValueError("unexpected map")


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.packet = reviewed_packet()
        self.map_path = Path(self.temp.name) / "reviewed-site.json"
        self.map_path.write_text(json.dumps(self.packet) + "\n")
        self.map_sha = hashlib.sha256(self.map_path.read_bytes()).hexdigest()
        self.input_path = Path(self.temp.name) / "driver-input.jsonl"
        self.input_path.write_text("")
        self.world = World()
        self.client = Client(self.world)
        self.carla = SimpleNamespace(
            Location=lambda **kw: kw, Rotation=lambda **kw: kw,
            Transform=lambda a, b: (a, b),
            VehicleLightState=SimpleNamespace(LeftBlinker=4, RightBlinker=8))
        self.case = "testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__both_observed"

    def session(self, digest=None):
        return LaneChangeSession(self.client, self.carla, self.map_path,
            digest or self.map_sha, self.case, self.input_path, "driver-source-1")

    def test_source_gate_before_world_mutation(self):
        session = self.session("0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            session.__enter__()
        self.assertEqual(self.world.spawned, 0)
        self.assertFalse(self.world.settings.synchronous_mode)

    def test_owned_actor_camera_lifecycle_and_world_readback(self):
        with self.session() as session:
            self.assertTrue(self.world.settings.synchronous_mode)
            self.assertEqual(self.world.settings.fixed_delta_seconds, .05)
            self.assertEqual(self.world.spawned, 6)
        self.assertTrue(all(actor.destroyed for actor in self.world.actors))
        self.assertFalse(self.world.settings.synchronous_mode)
        self.assertIsNone(self.world.settings.fixed_delta_seconds)
        self.assertTrue(session.restoration["restored"])


if __name__ == "__main__":
    unittest.main()
