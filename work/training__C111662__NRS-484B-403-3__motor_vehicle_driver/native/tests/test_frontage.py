import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frontage', HERE/'frontage.py')
frontage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontage)


class Blueprint:
    id = 'static.prop.shop_frontage'


class Bounds:
    def __init__(self, width): self.width = width
    def get_world_vertices(self, transform):
        x = transform.location.x
        return [SimpleNamespace(x=x-self.width/2), SimpleNamespace(x=x+self.width/2)]


class Actor:
    def __init__(self, ident, transform, width):
        self.id = ident
        self.transform = transform
        self.bounding_box = Bounds(width)
    def get_transform(self): return self.transform


class Library:
    def filter(self, pattern): return [Blueprint()]


class World:
    def __init__(self, width=5):
        self.width = width
        self.calls = []
    def get_blueprint_library(self): return Library()
    def try_spawn_actor(self, bp, transform):
        self.calls.append((bp.id, transform.location.x, transform.location.y))
        return Actor(len(self.calls), transform, self.width)


class Carla:
    class Location:
        def __init__(self, **kw): self.__dict__.update(kw)
    class Rotation:
        def __init__(self, **kw): self.__dict__.update(kw)
    class Transform:
        def __init__(self, location, rotation):
            self.location = location
            self.rotation = rotation


class FrontageConstruction(unittest.TestCase):
    def test_authored_window_and_crossing_gap(self):
        plan = frontage.authored_plan()
        self.assertAlmostEqual(plan['authored_frontage_ft'], 328.0839895, places=5)
        self.assertAlmostEqual(plan['window_x_m'][1]-plan['window_x_m'][0], frontage.WINDOW_M)
        self.assertTrue(all(-75 <= x <= -25 or 25 <= x <= 75 for x in plan['station_x_m']))
        self.assertEqual(len(plan['station_x_m']), 20)
        self.assertFalse(plan['district_designation_verified'])

    def test_statutory_boundary_and_overlap(self):
        at = frontage.MIN_FRONTAGE_M
        self.assertAlmostEqual(frontage.clipped_frontage([(-at/2, at/2)]), at)
        self.assertLess(frontage.clipped_frontage([(-at/2, at/2-.001)]), at)
        self.assertAlmostEqual(frontage.clipped_frontage([(-50, 10), (-10, 50)]), 100)
        with self.assertRaisesRegex(ValueError, '600 feet'):
            frontage.clipped_frontage([(0, 100)], (-100, 100))

    def test_native_spawn_calls_and_measured_extent(self):
        world = World(width=5)
        owned = []
        result = frontage.spawn_and_measure(world, Carla, frontage.authored_plan(), owned)
        self.assertEqual(len(world.calls), 20)
        self.assertEqual(len(owned), 20)
        self.assertEqual({row[2] for row in world.calls}, {22.0})
        self.assertAlmostEqual(result['native_frontage_m'], 100.0)
        self.assertFalse(result['building_use_legally_verified'])

    def test_native_shortfall_and_missing_asset_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'below 300 feet'):
            frontage.spawn_and_measure(World(width=3), Carla, frontage.authored_plan(), [])
        class NoAsset(World):
            def get_blueprint_library(self): return SimpleNamespace(filter=lambda _: [])
        with self.assertRaisesRegex(RuntimeError, 'No building'):
            frontage.spawn_and_measure(NoAsset(), Carla, frontage.authored_plan(), [])


if __name__ == '__main__': unittest.main()
