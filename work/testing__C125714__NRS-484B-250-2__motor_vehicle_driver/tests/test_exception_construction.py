"""CPU creation and rejection tests for distinct exception geometry."""
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from exception_construction import BASE, construct


class Actor:
    def __init__(self, identity):
        self.id = identity
        self.is_alive = True


class Adapter:
    def __init__(self):
        self.calls = []
        self.device_ok = True
        self.turn_ok = True
        self.readback_ok = True

    def map_opendrive_bytes(self):
        return b'CPU candidate map'

    def route_enters_crossing(self, route, crossing, highway):
        self.calls.append(('crossing', crossing, highway))
        return crossing == 'X'

    def device_controls_intersection(self, device, crossing):
        self.calls.append(('device', device, crossing))
        return self.device_ok

    def route_makes_left_turn(self, route, crossing):
        self.calls.append(('left_turn', crossing))
        return self.turn_ok

    def spawn_vehicle(self, point, blueprint_sha256):
        actor = Actor(1 + sum(c[0] == 'spawn' for c in self.calls))
        self.calls.append(('spawn', point, blueprint_sha256))
        return actor

    def set_vehicle_route(self, actor, route):
        self.calls.append(('route', actor.id))

    def vehicle_route_readback(self, actor, route):
        return self.readback_ok

    def destroy(self, actor):
        self.calls.append(('destroy', actor.id))


class ExceptionConstructionTests(unittest.TestCase):
    def packet(self, kind):
        case_id = BASE + kind
        site = {'assignment_id': BASE[:-2], 'cell_id': 'C125714',
                'case_id': case_id,
                'map_sha256': hashlib.sha256(b'CPU candidate map').hexdigest(),
                'reviewer': 'CPU fixture', 'map_source_citation': 'fixture',
                'highway_source_citation': 'fixture',
                'device_source_citation': 'fixture',
                'turn_source_citation': 'fixture', 'crossing_id': 'X',
                'roadway_id': 'R', 'ego_blueprint_sha256': 'ego-hash',
                'other_blueprint_sha256': 'other-hash',
                'subsection_4_context_reviewed': True,
                'official_device_controls_intersection': kind == 'official_device_controlled',
                'official_device_id': 'signal-1',
                'approach_relation': 'crossing' if kind == 'official_device_controlled' else 'opposite',
                'ego_highway': 'A',
                'other_highway': 'B' if kind == 'official_device_controlled' else 'A',
                'ego_side': 'left', 'other_side': 'right',
                'other_left_turn_intent': kind != 'official_device_controlled',
                'other_left_turn_making': kind == 'opposite_makes_left',
                'ego_route_xyz_m': [[-20, -4, 0], [0, -4, 0], [20, -4, 0]],
                'other_route_xyz_m': [[20, 4, 0], [0, 4, 0], [-20, 4, 0]]}
        if kind == 'official_device_controlled':
            site['other_route_xyz_m'] = [[-1, -20, 0], [-1, 0, 0], [-1, 20, 0]]
        if kind == 'opposite_makes_left':
            site['other_route_xyz_m'] = [[20, 4, 0], [0, 4, 0], [0, -20, 0]]
        return site, {'case_id': case_id}

    def test_distinct_device_and_turn_construction_calls(self):
        for kind, expected in [('official_device_controlled', 'device'),
                               ('opposite_intends_left', None),
                               ('opposite_makes_left', 'left_turn')]:
            with self.subTest(kind=kind):
                adapter = Adapter()
                site, case = self.packet(kind)
                result = construct(adapter, site, case)
                self.assertEqual(result['exception_fact_pattern'], kind)
                self.assertEqual(result['legal_exception_applies'], 'unresolved')
                self.assertEqual(sum(c[0] == 'spawn' for c in adapter.calls), 2)
                self.assertEqual(sum(c[0] == 'route' for c in adapter.calls), 2)
                self.assertEqual(expected in [c[0] for c in adapter.calls], expected is not None)

    def test_missing_control_and_unrealized_left_turn_rejected_before_spawn(self):
        adapter = Adapter()
        site, case = self.packet('official_device_controlled')
        adapter.device_ok = False
        with self.assertRaisesRegex(ValueError, 'does not control'):
            construct(adapter, site, case)
        self.assertFalse(any(c[0] == 'spawn' for c in adapter.calls))
        adapter = Adapter()
        site, case = self.packet('opposite_makes_left')
        adapter.turn_ok = False
        with self.assertRaisesRegex(ValueError, 'left-turn route missing'):
            construct(adapter, site, case)
        self.assertFalse(any(c[0] == 'spawn' for c in adapter.calls))

    def test_stale_map_wrong_relation_and_route_readback_rejected(self):
        adapter = Adapter()
        site, case = self.packet('official_device_controlled')
        site['map_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'live map differs'):
            construct(adapter, site, case)
        site, case = self.packet('opposite_intends_left')
        site['approach_relation'] = 'crossing'
        with self.assertRaisesRegex(ValueError, 'opposite ungoverned'):
            construct(adapter, site, case)
        site, case = self.packet('opposite_intends_left')
        site['other_route_xyz_m'] = [[-20, 4, 0], [0, 4, 0], [20, 4, 0]]
        with self.assertRaisesRegex(ValueError, 'routes are not opposite'):
            construct(adapter, site, case)
        site, case = self.packet('opposite_intends_left')
        adapter.readback_ok = False
        with self.assertRaisesRegex(ValueError, 'readback differs'):
            construct(adapter, site, case)
        self.assertEqual(sum(c[0] == 'destroy' for c in adapter.calls), 2)
