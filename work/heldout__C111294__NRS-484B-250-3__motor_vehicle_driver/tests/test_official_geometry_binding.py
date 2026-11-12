import copy
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_geometry_binding import bind_geometry, require_expected_geometry
from official_geometry_preflight import select_binding
from test_categorical_highway_points import native_map


class Point:
    def __init__(self, x, y, road, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, -1, junction
        self.transform = NS(location=NS(x=x, y=y))

    def get_junction(self):
        return NS(id=42) if self.is_junction else None


def sources():
    world = NS(name='SyntheticJunction', to_opendrive=lambda: '<OpenDRIVE/>')
    routes = {'junction_id': '42',
              'subject': [Point(-8, 0, 1), Point(0, 0, 5, True), Point(6, 0, 3)],
              'other': [Point(0, -8, 2), Point(0, 0, 6, True), Point(0, 8, 2)]}
    device = (NS(id=10), 'signal-7', routes['subject'][0])
    return world, routes, device


class OfficialGeometryBindingTests(unittest.TestCase):
    def test_preflight_selects_governed_connected_native_pair(self):
        world_map, ending, through = native_map(subject_continues=False)
        world_map.to_opendrive = lambda: '<OpenDRIVE/>'
        light = NS(id=10, get_opendrive_id=lambda: 'signal-7',
                   get_affected_lane_waypoints=lambda: [ending[0]])
        world = NS(get_map=lambda: world_map,
                   get_actors=lambda: NS(filter=lambda pattern: [light]))
        binding = select_binding(world)
        self.assertEqual(binding['routes']['subject'][0]['road_id'], 1)
        self.assertEqual(binding['routes']['other'][0]['road_id'], 2)
        self.assertEqual(binding['governing_device']['opendrive_signal_id'], 'signal-7')

    def test_red_green_same_sources_and_changed_waypoint(self):
        world, routes, device = sources()
        red = bind_geometry(world, routes, device)
        green = bind_geometry(world, routes, device)
        self.assertEqual(red, require_expected_geometry(green, red))
        self.assertFalse(red['legal_official_status_claimed'])
        routes['other'][1].transform.location.x += 2
        with self.assertRaisesRegex(ValueError, 'differs'):
            require_expected_geometry(bind_geometry(world, routes, device), red)

    def test_changed_map_signal_lane_and_stale_hash_rejected(self):
        world, routes, device = sources()
        expected = bind_geometry(world, routes, device)
        world.to_opendrive = lambda: '<OpenDRIVE changed="1"/>'
        with self.assertRaisesRegex(ValueError, 'differs'):
            require_expected_geometry(bind_geometry(world, routes, device), expected)
        world.to_opendrive = lambda: '<OpenDRIVE/>'
        with self.assertRaisesRegex(ValueError, 'differs'):
            require_expected_geometry(bind_geometry(world, routes, (device[0], 'signal-8', device[2])), expected)
        bad = copy.deepcopy(expected)
        bad['routes']['subject'][0]['lane_id'] = -2
        with self.assertRaisesRegex(ValueError, 'stale'):
            require_expected_geometry(expected, bad)
        with self.assertRaisesRegex(ValueError, 'govern'):
            bind_geometry(world, routes, (device[0], 'signal-7', routes['other'][0]))
