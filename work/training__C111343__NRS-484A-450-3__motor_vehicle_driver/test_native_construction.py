"""CPU test of selected geometry readback, both actors and four camera spawns."""

import unittest

from native_construction import checked_map, constructed_scene
from yield_crosswalk_scene import CASES, request


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Actor:
    def __init__(self, blueprint):
        self.blueprint = blueprint
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, xml):
        self.xml = xml
        self.settings = type("Settings", (), {"synchronous_mode": False,
                                               "fixed_delta_seconds": None})()
        self.actors = []
        self.spawns = []

    def get_map(self):
        return type("Map", (), {"to_opendrive": lambda unused: self.xml})()

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return type("Library", (), {"find": lambda unused, name: Blueprint(name)})()

    def try_spawn_actor(self, blueprint, pose):
        return self.spawn_actor(blueprint, pose)

    def spawn_actor(self, blueprint, pose, attach_to=None):
        actor = Actor(blueprint)
        self.actors.append(actor)
        self.spawns.append((blueprint.name, pose, attach_to))
        return actor


class Client:
    def __init__(self):
        self.world = None

    def generate_opendrive_world(self, xml):
        self.world = World(xml)
        return self.world


class Carla:
    @staticmethod
    def Location(**kwargs):
        return kwargs

    @staticmethod
    def Rotation(**kwargs):
        return kwargs

    @staticmethod
    def Transform(location, rotation):
        return location, rotation


class NativeConstructionTest(unittest.TestCase):
    def test_both_exact_cases_build_original_features_and_actors(self):
        for case in CASES:
            with self.subTest(case=case):
                client = Client()
                with constructed_scene(client, Carla, request(case)) as scene:
                    self.assertEqual(set(scene["cameras"]),
                                     {"overview", "approach", "reference_corner", "driver_reference"})
                    self.assertEqual(len(client.world.spawns), 6)
                    self.assertEqual([row[0] for row in client.world.spawns[:2]],
                                     ["vehicle.tesla.model3", "vehicle.tesla.model3"])
                    self.assertEqual(checked_map(client.world, request(case)), scene["map_opendrive"])
                self.assertTrue(all(actor.destroyed for actor in client.world.actors))
                self.assertFalse(client.world.settings.synchronous_mode)
                self.assertIsNone(client.world.settings.fixed_delta_seconds)

    def test_missing_original_crosswalk_rejected(self):
        xml = request("before_crosswalk")["road_opendrive"].replace(
            'type="crosswalk"', 'type="unknown"')
        with self.assertRaisesRegex(ValueError, "hierarchy differs"):
            checked_map(World(xml), request("before_crosswalk"))

    def test_wrong_governing_sign_rejected(self):
        xml = request("before_crosswalk")["road_opendrive"].replace(
            'name="YIELD"', 'name="STOP"')
        with self.assertRaisesRegex(ValueError, "YIELD sign differs"):
            checked_map(World(xml), request("before_crosswalk"))


if __name__ == "__main__":
    unittest.main()
