"""Check source-bound participant construction and exact variant geometry."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import KINDS
from native_setup import create, validate_plan
from tests.test_source_bound_scene import fixture


def planned(root, suffix):
    packet = fixture(root)
    packet['signal']['native_actor_id'] = '9'
    if suffix == 'stopped_leftmost_two_way_receive':
        packet['receiving']['one_way_to_left'] = False
    lane = 'east' if suffix == 'stopped_inner_lane_clear' else 'west'
    x = 1.75 if lane == 'east' else -1.75
    def participant(blueprint, x):
        return {'blueprint_id': blueprint, 'location_xyz_m': [x, 0, 0],
                'rotation_rpy_deg': [0, 0, 0], 'source_citation': 'synthetic CPU source',
                'reviewer': 'CPU test', 'route_source_citation': 'synthetic CPU route',
                'route_points_xyz_m': [[x, 0, 0], [x, 2, 0]]}
    packet['spawn_plan'] = {
        'ego': {'blueprint_id': 'vehicle.protocol', 'location_xyz_m': [x, -8, 0],
                'rotation_rpy_deg': [0, 0, 90], 'approach_lane_id': lane,
                'source_citation': 'synthetic CPU source', 'reviewer': 'CPU test'},
        'pedestrians': [participant('walker.protocol', 3)],
        'other_traffic': [participant('vehicle.other', 5)]}
    path = root / 'site.json'
    path.write_text(json.dumps(packet))
    return path


class Actor:
    def __init__(self, ident):
        self.id = ident
        self.destroyed = False
    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_at=None):
        self.signal = Actor(9)
        self.spawned = []
        self.fail_at = fail_at
    def get_actors(self):
        return [self.signal]
    def get_blueprint_library(self):
        return NS(find=lambda name: name)
    def try_spawn_actor(self, blueprint, transform):
        if self.fail_at == len(self.spawned):
            return None
        actor = Actor(len(self.spawned) + 10)
        self.spawned.append((actor, blueprint, transform))
        return actor


class NativeSetupTests(unittest.TestCase):
    def test_all_exact_variant_spawns(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix in KINDS:
                site = planned(root, suffix)
                world = World()
                actors = create(world, site, suffix, lambda loc, rot: (loc, rot))
                self.assertEqual(len(world.spawned), 3)
                self.assertEqual(actors.signal.id, 9)
                self.assertEqual(actors.ego.id, 10)
                self.assertEqual(len(actors.pedestrians), 1)
                self.assertEqual(len(actors.traffic), 1)
                actors.close()
                self.assertTrue(all(actor.destroyed for actor, _, _ in world.spawned))

    def test_wrong_lane_heading_route_signal_and_failed_spawn(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = planned(root, 'stopped_leftmost_clear')
            packet = json.loads(site.read_text())
            packet['spawn_plan']['ego']['approach_lane_id'] = 'east'
            site.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'spawn lane differs'):
                validate_plan(site, 'stopped_leftmost_clear')
            packet['spawn_plan']['ego']['approach_lane_id'] = 'west'
            packet['spawn_plan']['ego']['rotation_rpy_deg'][2] = 0
            site.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'upstream, aligned'):
                validate_plan(site, 'stopped_leftmost_clear')
            packet['spawn_plan']['ego']['rotation_rpy_deg'][2] = 90
            packet['spawn_plan']['pedestrians'][0].pop('route_source_citation')
            site.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'route source missing'):
                validate_plan(site, 'stopped_leftmost_clear')
            site = planned(root, 'stopped_leftmost_pedestrian_yield')
            packet = json.loads(site.read_text())
            packet['spawn_plan']['pedestrians'] = []
            site.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'pedestrian case lacks'):
                validate_plan(site, 'stopped_leftmost_pedestrian_yield')
            site = planned(root, 'stopped_leftmost_clear')
            world = World(fail_at=1)
            with self.assertRaisesRegex(ValueError, 'spawn failed'):
                create(world, site, 'stopped_leftmost_clear', lambda loc, rot: (loc, rot))
            self.assertTrue(world.spawned[0][0].destroyed)
            missing = World()
            missing.signal.id = 8
            with self.assertRaisesRegex(ValueError, 'signal actor absent'):
                create(missing, site, 'stopped_leftmost_clear', lambda loc, rot: (loc, rot))


if __name__ == '__main__':
    unittest.main()
