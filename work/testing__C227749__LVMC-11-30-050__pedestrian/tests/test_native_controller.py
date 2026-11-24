import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('native_controller', ROOT/'native_controller.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fallback_spec = importlib.util.spec_from_file_location('native_controller_fallback', ROOT/'native_controller_fallback.py')
fallback = importlib.util.module_from_spec(fallback_spec)
fallback_spec.loader.exec_module(fallback)


class Carla:
    class Location:
        def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    class Transform:
        def __init__(self, location): self.location = location
    class Vector3D:
        def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    class WalkerControl:
        def __init__(self, direction, speed, jump): self.direction, self.speed, self.jump = direction, speed, jump


class Actor:
    def __init__(self, x, y): self.location = Carla.Location(x, y, 0); self.control = None; self.destroyed = False
    def get_transform(self): return types.SimpleNamespace(location=self.location)
    def apply_control(self, value): self.control = value
    def destroy(self): self.destroyed = True


class World:
    def __init__(self, offset=0): self.offset = offset; self.actor = None
    def get_blueprint_library(self): return types.SimpleNamespace(find=lambda name: name)
    def try_spawn_actor(self, blueprint, transform):
        self.actor = Actor(transform.location.x+self.offset, transform.location.y)
        return self.actor


def scene(route):
    return {'actor':'pedestrian', 'route_xy_m':route,
            'starting_curb_xy_m':[[0,0],[10,0]], 'opposite_curb_xy_m':[[0,6],[10,6]],
            'crosswalk_boundaries_xy_m':[[[20,-1],[25,-1],[25,7],[20,7]]],
            'crosswalk_context':'outside', 'jurisdiction_source':'frozen source',
            'curb_source':'authored source', 'control_context':'none'}


class NativeControllerTests(unittest.TestCase):
    def test_spawn_and_waypoint_request(self):
        item = scene([[5,0],[5,3],[5,6]])
        actor = m.spawn_walker(World(), Carla, item)
        index = m.request_next_control(actor, Carla, item, 1)
        self.assertEqual(index, 1)
        self.assertAlmostEqual(actor.control.direction.y, 1)
        self.assertEqual(actor.control.speed, 1.2)
        actor.location.y = 3
        index = m.request_next_control(actor, Carla, item, index)
        self.assertEqual(index, 2)

    def test_spawn_readback_rejected(self):
        world = World(offset=1)
        with self.assertRaisesRegex(RuntimeError, 'readback'):
            m.spawn_walker(world, Carla, scene([[5,0],[5,6]]))
        self.assertTrue(world.actor.destroyed)

    def test_bad_target_rejected(self):
        item = scene([[5,0],[5,6]])
        actor = m.spawn_walker(World(), Carla, item)
        with self.assertRaisesRegex(ValueError, 'target index'):
            m.request_next_control(actor, Carla, item, 2)

    def test_fallback_keeps_route_and_reduces_requested_speed(self):
        item = scene([[5,0],[5,6]])
        primary_actor = m.spawn_walker(World(), Carla, item)
        alternate_actor = fallback.spawn_walker(World(), Carla, item)
        m.request_next_control(primary_actor, Carla, item, 1)
        fallback.request_next_control(alternate_actor, Carla, item, 1)
        self.assertEqual(primary_actor.control.direction.y, alternate_actor.control.direction.y)
        self.assertEqual(primary_actor.control.speed, 1.2)
        self.assertEqual(alternate_actor.control.speed, 0.8)


if __name__ == '__main__': unittest.main()
