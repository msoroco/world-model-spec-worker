import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('construct', Path(__file__).resolve().parents[1] / 'construct.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Actor:
    def __init__(self): self.destroyed = False
    def destroy(self): self.destroyed = True


class World:
    def __init__(self, fail_device=False):
        self.fail_device = fail_device; self.calls = []; self.actors = []
    def get_map(self): return type('Map', (), {'name': 'Town01'})()
    def get_blueprint_library(self): return self
    def find(self, name): return name
    def try_spawn_actor(self, blueprint, transform):
        self.calls.append((blueprint, transform))
        if self.fail_device and blueprint == 'static.prop.sign': return None
        actor = Actor(); self.actors.append(actor); return actor


class Tests(unittest.TestCase):
    def site(self):
        return {'map_name': 'Town01', 'ego_blueprint': 'vehicle.test', 'device_blueprint': 'static.prop.sign',
                'u_turn_route': ['approach', 'junction', 'opposite'], 'device': {'governed_approach': 'A'}}
    def test_construct_both_actors(self):
        world = World(); out = mod.construct(world, self.site(), ego_transform='ego', device_transform='sign')
        self.assertEqual(world.calls, [('vehicle.test', 'ego'), ('static.prop.sign', 'sign')])
        self.assertEqual(out['governed_approach'], 'A')
    def test_cleanup_on_device_failure(self):
        world = World(True)
        with self.assertRaisesRegex(mod.ConstructionError, 'device spawn failed'):
            mod.construct(world, self.site(), ego_transform='ego', device_transform='sign')
        self.assertTrue(world.actors[0].destroyed)
    def test_wrong_map_rejected(self):
        site = self.site(); site['map_name'] = 'Town02'
        with self.assertRaisesRegex(mod.ConstructionError, 'wrong live map'):
            mod.construct(World(), site, ego_transform='ego', device_transform='sign')
