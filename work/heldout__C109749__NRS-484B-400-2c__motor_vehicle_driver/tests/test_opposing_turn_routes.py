import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('opposing_turn_routes', ROOT / 'opposing_turn_routes.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def pair():
    east = {'path': ['east-entry', 'junction', 'north-exit'],
            'junction_id': 7, 'approach_axis': 'east-west',
            'approach_heading_xy': [1, 0], 'exit_heading_xy': [0, 1],
            'approach_road_id': 10, 'exit_road_id': 20}
    west = {'path': ['west-entry', 'junction', 'south-exit'],
            'junction_id': 7, 'approach_axis': 'east-west',
            'approach_heading_xy': [-1, 0], 'exit_heading_xy': [0, -1],
            'approach_road_id': 10, 'exit_road_id': 20}
    return [east, west], {10: [-2, 3], 20: [-1, 1]}


class RouteSelectionTests(unittest.TestCase):
    def test_both_opposing_left_paths_selected(self):
        routes, lanes = pair()
        selected = module.select_opposing_left_pair(routes, lanes)
        self.assertIs(selected['subject'], routes[0])
        self.assertIs(selected['opposing'], routes[1])
        self.assertEqual(selected['legal_front_of_each_other'], 'unreviewed')

    def test_one_way_or_wrong_turn_rejected(self):
        routes, lanes = pair()
        lanes[20] = [1, 2]
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            module.select_opposing_left_pair(routes, lanes)
        lanes[20] = [-1, 1]
        routes[1]['exit_heading_xy'] = [0, 1]
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            module.select_opposing_left_pair(routes, lanes)

    def test_unconnected_and_device_filter_rejected(self):
        routes, lanes = pair()
        routes[0]['path'] = []
        with self.assertRaisesRegex(ValueError, 'connected Native'):
            module.select_opposing_left_pair(routes, lanes)
        routes, lanes = pair()
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            module.select_opposing_left_pair(routes, lanes, route_accept=lambda a, b: False)


if __name__ == '__main__':
    unittest.main()
