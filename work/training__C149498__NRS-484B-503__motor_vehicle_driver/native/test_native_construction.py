"""CPU test of original curb/sign readback, actor creation and four cameras."""

import unittest

from native.loading_scene import CASES, request
from native.native_construction import checked_map, constructed_scene


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
        class Library:
            @staticmethod
            def find(name):
                return Blueprint(name)

            @staticmethod
            def filter(pattern):
                return [Blueprint("walker.pedestrian.0001")] if pattern == "walker.pedestrian.*" else []
        return Library()

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
    def test_six_exact_cases_construct_source_features_and_actors(self):
        for slug in CASES:
            with self.subTest(slug=slug):
                client = Client()
                with constructed_scene(client, Carla, request(slug)) as scene:
                    self.assertEqual(set(scene["cameras"]),
                                     {"overview", "approach", "reference_corner", "driver_reference"})
                    self.assertEqual(len(client.world.spawns), 6)
                    self.assertEqual(client.world.spawns[0][0], "vehicle.tesla.model3")
                    self.assertTrue(client.world.spawns[1][0].startswith("walker.pedestrian."))
                    self.assertFalse(scene["occupant_count_observed"])
                    self.assertFalse(scene["regulatory_authority_observed"])
                    self.assertEqual(checked_map(client.world, request(slug)), scene["map_opendrive"])
                self.assertTrue(all(actor.destroyed for actor in client.world.actors))
                self.assertFalse(client.world.settings.synchronous_mode)
                self.assertIsNone(client.world.settings.fixed_delta_seconds)

    def test_missing_original_curb_rejected(self):
        scene = request("condition_a")
        xml = scene["road_opendrive"].replace('type="curb"', 'type="unknown"')
        with self.assertRaisesRegex(ValueError, "marked passenger curb"):
            checked_map(World(xml), scene)

    def test_missing_original_sign_rejected(self):
        scene = request("condition_a")
        xml = scene["road_opendrive"].replace("08:00-18:00", "07:00-19:00")
        with self.assertRaisesRegex(ValueError, "sign schedule"):
            checked_map(World(xml), scene)


if __name__ == "__main__":
    unittest.main()
