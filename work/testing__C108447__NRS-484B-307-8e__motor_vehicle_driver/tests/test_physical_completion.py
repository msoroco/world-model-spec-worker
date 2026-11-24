import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for name in ('property_route', 'physical_completion'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
evaluate = sys.modules['physical_completion'].evaluate


class PhysicalCompletionTests(unittest.TestCase):
    def setUp(self):
        self.case = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__private_bypass'
        self.map = {'properties': [{'id': 'lot', 'status': 'private',
                                    'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
                    'connector_routes': {'lot': [[-3, 5], [5, 5], [13, 5]]},
                    'roadway_route': [[-3, -2], [5, -2], [13, -2]]}
        self.trace = {'destination_entry_frame': 102,
                      'ego': [{'frame': 100, 'x': -3, 'y': 5},
                              {'frame': 101, 'x': 5, 'y': 5},
                              {'frame': 102, 'x': 13, 'y': 5}]}

    def test_source_route_arrival_measured(self):
        result = evaluate(self.map, self.trace, self.case)
        self.assertEqual(result['status'], 'met')
        self.assertEqual(result['observed']['endpoint_error_m'], 0)

    def test_claimed_entry_without_endpoint_rejected(self):
        self.trace['ego'][-1]['x'] = 5
        self.assertEqual(evaluate(self.map, self.trace, self.case)['status'], 'not_met')

    def test_stationary_entry_rejected(self):
        for row in self.trace['ego']:
            row['x'] = 13
        self.assertEqual(evaluate(self.map, self.trace, self.case)['status'], 'not_met')

    def test_missing_entry_unverified(self):
        self.trace['destination_entry_frame'] = None
        self.assertEqual(evaluate(self.map, self.trace, self.case)['status'], 'unverified')

    def test_wrong_property_class_rejected(self):
        self.map['properties'][0]['status'] = 'public'
        self.assertEqual(evaluate(self.map, self.trace, self.case)['status'], 'not_met')

    def test_ordinary_roadway_uses_separate_source_route(self):
        for row in self.trace['ego']:
            row['y'] = -2
        case = self.case.replace('private_bypass', 'ordinary_crossing')
        self.assertEqual(evaluate(self.map, self.trace, case)['status'], 'met')


if __name__ == '__main__':
    unittest.main()
