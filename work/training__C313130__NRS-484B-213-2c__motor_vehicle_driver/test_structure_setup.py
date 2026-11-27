"""Exercise Native structure setup calls with a deterministic fake world."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from structure_setup import install
from structure_variant import request


class FakeCarla:
    Location = lambda **kw: SimpleNamespace(**kw)
    Transform = lambda location: SimpleNamespace(location=location)
    LaneType = SimpleNamespace(Driving="driving")


class FakeMap:
    def __init__(self, bad_deck=False):
        self.bad_deck = bad_deck
        self.calls = []

    def get_waypoint(self, location, project_to_road, lane_type):
        self.calls.append((location.x, project_to_road, lane_type))
        z = location.z + (2 if self.bad_deck else 0)
        return SimpleNamespace(road_id=313130, lane_id=-1,
                               transform=SimpleNamespace(location=SimpleNamespace(z=z)))


class FakeActor:
    def __init__(self, identifier, short=False):
        self.id = identifier
        self.type_id = "static.prop.structural_support"
        self.destroyed = False
        height = 1 if short else 4
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda _: [
            SimpleNamespace(z=z) for z in (0, height) for _ in range(4)])

    def get_transform(self):
        return None

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, short=False):
        self.short = short
        self.actors = []
        self.spawns = []

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: name)

    def try_spawn_actor(self, blueprint, transform):
        self.spawns.append((blueprint, transform.location.x,
                            transform.location.y, transform.location.z))
        actor = FakeActor(len(self.actors) + 1, self.short)
        self.actors.append(actor)
        return actor


class StructureSetupTest(unittest.TestCase):
    def test_bridge_and_viaduct_native_calls(self):
        for kind, expected_supports in (("bridge", 4), ("viaduct", 10)):
            world, mapping = FakeWorld(), FakeMap()
            source, owned = install(world, mapping, FakeCarla,
                                    request(kind, "right"),
                                    "static.prop.structural_support")
            self.assertEqual(len(owned), expected_supports)
            self.assertEqual(len(source["native_supports"]), expected_supports)
            self.assertEqual(len(mapping.calls), 5)
            self.assertTrue(all(not projected and lane == "driving"
                                for _, projected, lane in mapping.calls))
            self.assertFalse(source["physical_structure_verified"])

    def test_bad_deck_fails_before_spawning(self):
        world = FakeWorld()
        with self.assertRaisesRegex(RuntimeError, "deck elevation"):
            install(world, FakeMap(bad_deck=True), FakeCarla,
                    request("bridge", "left"), "static.prop.structural_support")
        self.assertEqual(world.spawns, [])

    def test_short_support_fails_and_releases_owner(self):
        world = FakeWorld(short=True)
        with self.assertRaisesRegex(RuntimeError, "deck-height"):
            install(world, FakeMap(), FakeCarla,
                    request("viaduct", "left"), "static.prop.structural_support")
        self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == "__main__":
    unittest.main()
