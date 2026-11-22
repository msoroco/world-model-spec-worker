import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import spawn_walker


class NativeMapBindingTests(unittest.TestCase):
    def scene(self, band):
        return json.loads((ROOT / "cases" / (band+"_walk") / "scene.json").read_text())

    def world(self, scene, *, wrong_map=False, wrong_lane=False, missing=False):
        class Waypoint:
            def __init__(self, x, y):
                self.road_id = 1
                self.lane_id = {"roadway": -1, "shoulder": -2, "sidewalk": -3}[scene["route_band"]]
                if wrong_lane: self.lane_id = -5
                self.transform = type("Pose", (), {"location": type("Point", (), {"x": x, "y": y})()})()
        class Map:
            def to_opendrive(self):
                data = (ROOT / "candidate-corridor.xodr").read_text()
                return data + " " if wrong_map else data
            def get_waypoint(self, location, project_to_road=False, lane_type=None):
                if project_to_road or lane_type != "any": raise ValueError("wrong map lookup contract")
                if missing and location[0] == 15: return None
                return Waypoint(*location[:2])
        class Library:
            def filter(self, pattern):
                if pattern != "walker.pedestrian.*": raise ValueError("wrong actor type")
                return [object()]
        class Actor:
            pass
        class World:
            def __init__(self): self.spawned = []
            def get_map(self): return Map()
            def get_blueprint_library(self): return Library()
            def spawn_actor(self, blueprint, pose):
                actor = Actor(); self.spawned.append(actor); return actor
        return World()

    def test_all_three_cases_bind_then_spawn_exact_walker(self):
        class Carla:
            class LaneType:
                Any = "any"
            @staticmethod
            def Location(x, y, z): return x, y, z
        for band in ("roadway", "shoulder", "sidewalk"):
            with self.subTest(band=band):
                scene = self.scene(band)
                world = self.world(scene)
                self.assertIs(spawn_walker(world, scene, Carla), world.spawned[0])
                self.assertEqual(len(world.spawned), 1)
                for fault, message in (("wrong_map", "OpenDRIVE source"),
                                       ("wrong_lane", "wrong roadway or lane"),
                                       ("missing", "no Native waypoint")):
                    world = self.world(scene, **{fault: True})
                    with self.assertRaisesRegex(ValueError, message):
                        spawn_walker(world, scene, Carla)
                    self.assertEqual(world.spawned, [])


if __name__ == "__main__":
    unittest.main()
