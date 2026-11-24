"""CPU mocks for the official-device contrast construction contract."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from device_branch import (entrance_devices, validate_device_pair,
                           check_entrance_device_expectation, build_presence_pair,
                           construct_device_pair)


class Actor:
    def __init__(self, native_id, kind, governs):
        self.id = native_id
        self.type_id = kind
        self.trigger_volume = SimpleNamespace(contains=lambda point, pose: governs)

    def get_transform(self):
        return object()


class World:
    def __init__(self, actors):
        self.actors = actors

    def get_actors(self):
        return self.actors

    def try_spawn_actor(self, blueprint, transform):
        actor = SimpleNamespace(destroy=lambda: self.destroyed.append((blueprint, transform)))
        self.spawned.append((blueprint, transform))
        return actor


def construction(presence):
    site = json.loads((ROOT / 'site.json').read_text())
    present, absent = build_presence_pair(site)
    return {'present': present, 'absent': absent}[presence]


class DeviceBranchTests(unittest.TestCase):
    def test_native_trigger_governance_and_missing_device_rejection(self):
        entrance = SimpleNamespace(transform=SimpleNamespace(location=object()))
        world = World([Actor(17, 'traffic.stop', True),
                       Actor(18, 'traffic.traffic_light', False),
                       Actor(19, 'vehicle.car', True)])
        observed = entrance_devices(world, entrance)
        self.assertEqual(observed, [{'native_id': 17, 'type_id': 'traffic.stop'}])
        self.assertEqual(check_entrance_device_expectation(observed, 'present')
                         ['observed_native_device_ids'], [17])
        with self.assertRaisesRegex(ValueError, 'differs'):
            check_entrance_device_expectation(observed, 'absent')
        self.assertEqual(entrance_devices(World([]), entrance), [])
        self.assertEqual(check_entrance_device_expectation([], 'absent')['presence'], 'absent')
        with self.assertRaisesRegex(ValueError, 'differs'):
            check_entrance_device_expectation([], 'present')

    def test_pair_isolates_presence_and_rejects_unreviewed_status_claim(self):
        present, absent = construction('present'), construction('absent')
        result = validate_device_pair(present, absent)
        self.assertEqual(result['measured_presence_values'], ['present', 'absent'])
        self.assertFalse(result['legal_acceptance_claimed'])
        bad = copy.deepcopy(absent)
        bad['other_release_frame'] = 48
        with self.assertRaisesRegex(ValueError, 'fixed condition'):
            validate_device_pair(present, bad)
        bad = copy.deepcopy(absent)
        bad['official_device_judgment'] = 'not_official'
        with self.assertRaisesRegex(ValueError, 'source review'):
            validate_device_pair(present, bad)
        bad = copy.deepcopy(absent)
        bad['expected_entrance_device'] = 'present'
        with self.assertRaisesRegex(ValueError, 'Present and absent'):
            validate_device_pair(present, bad)
        bad = copy.deepcopy(absent)
        bad['same_statutory_crossing'] = False
        with self.assertRaisesRegex(ValueError, 'fixed condition'):
            validate_device_pair(present, bad)

    def test_native_pair_construction_checks_presence_and_restores_actors(self):
        entrance = SimpleNamespace(transform=SimpleNamespace(location=object()))
        for presence, actors in [('present', [Actor(17, 'traffic.stop', True)]),
                                 ('absent', [])]:
            world = World(actors)
            world.spawned, world.destroyed = [], []
            with construct_device_pair(world, entrance, construction(presence),
                                       'ego-blueprint', 'other-blueprint',
                                       'ego-pose', 'other-pose') as (_, _, devices):
                self.assertEqual(bool(devices), presence == 'present')
                self.assertEqual(len(world.spawned), 2)
            self.assertEqual(world.destroyed,
                             [('other-blueprint', 'other-pose'),
                              ('ego-blueprint', 'ego-pose')])
            wrong = construction('absent' if presence == 'present' else 'present')
            with self.assertRaisesRegex(ValueError, 'differs'):
                with construct_device_pair(world, entrance, wrong,
                                           'ego-blueprint', 'other-blueprint',
                                           'ego-pose', 'other-pose'):
                    pass
            self.assertEqual(len(world.spawned), 2)
        class SecondSpawnFails(World):
            def try_spawn_actor(self, blueprint, transform):
                if blueprint == 'other-blueprint':
                    return None
                return super().try_spawn_actor(blueprint, transform)
        world = SecondSpawnFails([])
        world.spawned, world.destroyed = [], []
        with self.assertRaisesRegex(ValueError, 'other Native spawn failed'):
            with construct_device_pair(world, entrance, construction('absent'),
                                       'ego-blueprint', 'other-blueprint',
                                       'ego-pose', 'other-pose'):
                pass
        self.assertEqual(world.destroyed, [('ego-blueprint', 'ego-pose')])


if __name__ == '__main__':
    unittest.main()
