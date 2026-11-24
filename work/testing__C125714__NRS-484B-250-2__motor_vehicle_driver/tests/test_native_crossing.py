"""Construction protocol checks; original physical motion remains unproven."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c125714_construct', ROOT / 'native_crossing.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'


class Actor:
    def __init__(self, actor_id):
        self.id = actor_id
        self.is_alive = True


class Adapter:
    def __init__(self):
        self.calls = []
        self.destroyed = []
        self.fail = None

    def map_opendrive_bytes(self):
        return b'<OpenDRIVE fixture="true"/>'

    def route_enters_crossing(self, route, crossing, highway):
        self.calls.append(('crossing', crossing, highway))
        return highway != self.fail

    def spawn_vehicle(self, start, blueprint_sha256):
        self.calls.append(('spawn', start, blueprint_sha256))
        return Actor(len([c for c in self.calls if c[0] == 'spawn']))

    def set_vehicle_route(self, actor, route):
        self.calls.append(('route', actor.id, route))

    def vehicle_route_readback(self, actor, route):
        return self.fail != 'readback'

    def apply_vehicle_control(self, actor, **kwargs):
        self.calls.append(('control', actor.id, kwargs))

    def destroy(self, actor):
        self.destroyed.append(actor.id)


def site():
    road = b'<OpenDRIVE fixture="true"/>'
    return {'assignment_id': BASE, 'cell_id': 'C125714',
            'case_id': BASE + '__timing_inside_training',
            'map_sha256': hashlib.sha256(road).hexdigest(),
            'map_source_citation': 'fixture map',
            'highway_source_citation': 'fixture highway',
            'device_source_citation': 'fixture device',
            'crossing_id': 'crossing A', 'roadway_id': 'roadway A',
            'ego_blueprint_sha256': 'ego blueprint',
            'other_blueprint_sha256': 'other blueprint',
            'approach_relation': 'crossing',
            'ego_highway': 'A', 'other_highway': 'B',
            'ego_side': 'left', 'other_side': 'right',
            'official_device_controls_intersection': False,
            'other_left_turn_intent': False,
            'subsection_4_context_reviewed': True,
            'ego_route_xyz_m': [[-12, 0, 0], [12, 0, 0]],
            'other_route_xyz_m': [[0, -12, 0], [0, 12, 0]]}


def case(offset=-.025):
    return {'case_id': BASE + '__timing_inside_training',
            'requested_entry_offset_s': offset}


class ConstructionTest(unittest.TestCase):
    def test_two_distinct_crossing_approaches_and_controls(self):
        adapter = Adapter()
        built = m.construct(adapter, site(), case())
        self.assertEqual(len(built['owned']), 2)
        self.assertEqual([c[2] for c in adapter.calls if c[0] == 'crossing'], ['A', 'B'])
        m.apply_timing(adapter, built['actors'], 1.0, case(),
                       {'ego_release_s': .975, 'other_release_s': 1.0})
        controls = [c[2] for c in adapter.calls if c[0] == 'control']
        self.assertEqual(controls, [{'throttle': .35, 'brake': 0.0}] * 2)

    def test_map_governance_and_route_fails_closed(self):
        adapter = Adapter(); data = site(); data['map_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'live map differs'):
            m.construct(adapter, data, case())
        data = site(); data['official_device_controls_intersection'] = True
        with self.assertRaisesRegex(ValueError, 'exception context'):
            m.construct(adapter, data, case())
        data = site(); adapter.fail = 'B'
        with self.assertRaisesRegex(ValueError, 'same reviewed crossing'):
            m.construct(adapter, data, case())
        self.assertEqual(adapter.destroyed, [])

    def test_partial_spawn_rolls_back_and_schedule_is_only_request(self):
        adapter = Adapter(); adapter.fail = 'readback'
        with self.assertRaisesRegex(ValueError, 'readback differs'):
            m.construct(adapter, site(), case())
        self.assertEqual(adapter.destroyed, [2, 1])
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, 'release schedule differs'):
            m.apply_timing(adapter, {'ego': Actor(1), 'other': Actor(2)},
                           .5, case(), {'ego_release_s': 1.5, 'other_release_s': 1.0})
        self.assertFalse(any(c[0] == 'control' for c in adapter.calls))


if __name__ == '__main__':
    unittest.main()
