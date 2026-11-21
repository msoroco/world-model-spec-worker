import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ending_road_control_inventory import approach_landmarks, ungoverned_route_pair, original_ungoverned_inventory


class Waypoint:
    def __init__(self, road, lane, *, junction=False, signs=()):
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.signs = signs
        self.transform = NS(location=NS(x=0., y=0.))
        self.successors = []

    def get_landmarks(self, distance, stop_at_junction=False):
        assert distance == 3.0 and stop_at_junction
        return self.signs

    def next(self, distance):
        return self.successors

    def get_junction(self):
        return NS(id=42) if self.is_junction else None


class InventoryTests(unittest.TestCase):
    def routes(self):
        a = [Waypoint(1, -1), Waypoint(2, -1, junction=True)]
        b = [Waypoint(3, 1), Waypoint(2, 1, junction=True)]
        for path in (a, b):
            path[0].successors = [path[1]]
        return ({'path': a, 'junction_id': '42'},
                {'path': b, 'junction_id': '42'})

    def test_both_approaches_and_landmark_types(self):
        ending, through = self.routes()
        self.assertTrue(ungoverned_route_pair(ending, through, []))
        for route, kind in ((ending, '206'), (through, '205')):
            route['path'][0].signs = [NS(id='sign-1', type=kind)]
            self.assertFalse(ungoverned_route_pair(ending, through, []))
            self.assertEqual(approach_landmarks(route['path'])[0]['type'], kind)
            route['path'][0].signs = []

    def test_fails_closed_on_missing_landmark_api_or_identity(self):
        ending, through = self.routes()
        ending['path'][0].get_landmarks = None
        with self.assertRaisesRegex(ValueError, 'query unavailable'):
            ungoverned_route_pair(ending, through, [])
        ending, through = self.routes()
        ending['path'][0].signs = [NS(id='', type='206')]
        with self.assertRaisesRegex(ValueError, 'lacks OpenDRIVE'):
            ungoverned_route_pair(ending, through, [])

    def test_original_inventory_records_both_approaches_and_rejects_control(self):
        ending, through = self.routes()
        source = original_ungoverned_inventory(ending, through, [])
        self.assertEqual(source['format'], 'worker-ending-road-original-control-inventory')
        self.assertEqual(source['ending_approach_road_id'], 1)
        self.assertEqual(source['through_approach_road_id'], 3)
        self.assertEqual(source['ending_landmarks'], [])
        self.assertEqual(source['through_landmarks'], [])
        through['path'][0].signs = [NS(id='yield-1', type='205')]
        with self.assertRaisesRegex(ValueError, 'potential governing control'):
            original_ungoverned_inventory(ending, through, [])
