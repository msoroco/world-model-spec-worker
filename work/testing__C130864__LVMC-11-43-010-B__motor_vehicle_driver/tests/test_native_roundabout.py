import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_roundabout import TimedRoute, load_case, spawn
import test_roundabout_measurements as fixture_module


class NativeConstructionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.RoundaboutMeasurements("test_source_bound_entry_and_cli")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.packet = self.fixture.packet
        self.map_path = self.fixture.map_path
        self.case = self.fixture.case
        self.packet.update({"map_name": "reviewed-map", "route_source_sha256": "b" * 64,
            "ego_blueprint": "vehicle.ego", "opponent_blueprint": "vehicle.other",
            "ego_spawn": {"x": 0, "y": -5}, "opponent_spawn": {"x": 1, "y": 0},
            "ego_release_tick": 20, "opponent_release_tick": 0,
            "ego_route": [
                {"x": 0, "y": -5, "speed_mps": 3, "lane_id": "entry-1"},
                {"x": 0, "y": -3, "speed_mps": 3, "lane_id": "entry-1"},
                {"x": 0, "y": -1, "speed_mps": 3, "lane_id": "outer"}],
            "opponent_points": [
                {"x": 1, "y": 0, "speed_mps": 4, "lane_id": "outer"},
                {"x": 2, "y": 0, "speed_mps": 4, "lane_id": "outer"},
                {"x": 3, "y": 0, "speed_mps": 4, "lane_id": "outer"}]})
        self.fixture.write()

    def load(self):
        return load_case(self.map_path, hashlib.sha256(self.map_path.read_bytes()).hexdigest(), self.case)

    def test_source_bound_case_and_two_spawns(self):
        packet = self.load()
        class Actor:
            def __init__(self, actor_id):
                self.id = actor_id
                self.destroyed = False
            def destroy(self):
                self.destroyed = True
        class World:
            def __init__(self):
                self.calls = []
            def get_map(self):
                return type("Map", (), {"name": "reviewed-map"})()
            def get_blueprint_library(self):
                return type("Library", (), {"find": lambda self, name: name})()
            def try_spawn_actor(self, blueprint, transform):
                self.calls.append((blueprint, transform))
                return Actor(len(self.calls))
        world = World()
        ego, other = spawn(world, packet, lambda value: value)
        self.assertEqual((ego.id, other.id), (1, 2))
        self.assertEqual(world.calls[0][0], "vehicle.ego")
        self.assertEqual(world.calls[1][1], {"x": 1, "y": 0})

    def test_timed_control_holds_then_moves(self):
        packet = self.load()
        control = TimedRoute(packet["ego_route"], 20, lambda **values: values)
        class Actor:
            def __init__(self):
                self.controls = []
            def apply_control(self, value):
                self.controls.append(value)
            def get_transform(self):
                return type("Transform", (), {"location": type("Location", (), {"x": 0, "y": -5})(),
                       "rotation": type("Rotation", (), {"yaw": 90})()})()
        actor = Actor()
        control(actor, 19)
        control(actor, 20)
        self.assertEqual(actor.controls[0]["brake"], 1.0)
        self.assertGreater(actor.controls[1]["throttle"], 0)

    def test_rejects_wrong_connected_lane_and_stale_source(self):
        self.packet["ego_route"][-1]["lane_id"] = "inner"
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, "lane connection"):
            self.load()
        with self.assertRaisesRegex(ValueError, "source hash"):
            load_case(self.map_path, "0" * 64, self.case)

    def test_rejects_disconnected_route_and_tracking_loss(self):
        self.packet["ego_route"][1]["y"] = 100
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, "disconnected"):
            self.load()
        packet = self.packet
        packet["ego_route"][1]["y"] = -3
        control = TimedRoute(packet["ego_route"], 0, lambda **values: values)
        actor = type("Actor", (), {"get_transform": lambda self: type("Transform", (), {
            "location": type("Location", (), {"x": 100, "y": 100})(),
            "rotation": type("Rotation", (), {"yaw": 0})()})()})()
        with self.assertRaisesRegex(ValueError, "tracking lost"):
            control(actor, 0)


if __name__ == "__main__":
    unittest.main()
