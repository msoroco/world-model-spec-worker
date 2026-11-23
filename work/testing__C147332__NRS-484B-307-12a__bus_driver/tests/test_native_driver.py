"""CARLA-free tests of exact actor creation and controller calls."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import spawn_scene, control_request


def struct(**fields):
    return SimpleNamespace(**fields)


class FakeActor:
    def __init__(self, blueprint, transform):
        self.blueprint = blueprint
        self.transform = transform
        self.bounding_box = struct(extent=struct(x=3.0, y=1.2))
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self):
        self.calls = []

    def get_blueprint_library(self):
        return self

    def find(self, identifier):
        return identifier

    def spawn_actor(self, blueprint, transform):
        actor = FakeActor(blueprint, transform)
        self.calls.append(actor)
        return actor


class FakeCarla:
    @staticmethod
    def Location(**values):
        return struct(**values)

    @staticmethod
    def Rotation(**values):
        return struct(**values)

    @staticmethod
    def Transform(location, rotation):
        return struct(location=location, rotation=rotation)


class NativeDriverTests(unittest.TestCase):
    def test_both_overhead_heads_and_bus_spawn_at_exact_lane_centers(self):
        site = {"native_asset_blueprint_id": "fixture.green",
                "dark_asset_blueprint_id": "fixture.dark"}
        for kind in ("green_selected_drive", "adjacent_dark_drive",
                     "second_green_drive", "green_selected_stand"):
            with self.subTest(kind=kind):
                scene = json.loads((ROOT / "cases" / kind / "scene.json").read_text())
                world = FakeWorld()
                bus, heads = spawn_scene(world, scene, FakeCarla, site)
                self.assertEqual(len(heads), 2)
                self.assertEqual(len(world.calls), 3)
                self.assertEqual([head.transform.location.y for head in heads], [-1.8, -5.4])
                self.assertEqual([head.transform.location.z for head in heads], [6.0, 6.0])
                self.assertEqual(bus.transform.location.y,
                                 -5.4 if scene["bus_lane_id"] == "west" else -1.8)
                expected = ["fixture.green", "fixture.green" if kind == "second_green_drive"
                            else "fixture.dark", "vehicle.mitsubishi.fusorosa"]
                self.assertEqual([actor.blueprint for actor in world.calls], expected)
                x, y = scene["route_waypoint_centers_m"][0]
                request = control_request(scene, x_m=x, y_m=y, yaw_deg=0, speed_mps=0)
                self.assertEqual(request["target_lateral_m"], y)
                self.assertEqual(request["brake"], 1.0 if kind == "green_selected_stand" else 0.0)


if __name__ == "__main__":
    unittest.main()
