import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'property_route.py'
spec = importlib.util.spec_from_file_location('property_route', MODULE)
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


def fixtures():
    packet = {
        'source': {'kind': 'original_native_map_and_property_authority', 'path': '/source', 'sha256': 'a' * 64},
        'coordinate_frame': 'native-xy', 'intersecting_street_id': 'cross',
        'properties': [{'id': 'lot', 'status': 'private', 'authority': 'deed/map', 'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
    }
    trace = {
        'coordinate_frame': 'native-xy', 'actor_class': 'vehicle', 'actor_source': 'Native blueprint and registry',
        'ego': [{'frame': 1, 'x': -2, 'y': 5}, {'frame': 2, 'x': 12, 'y': 5}, {'frame': 3, 'x': 14, 'y': 5}],
        'approach_signal': {'device_id': 'a', 'source': 'Native light state', 'facing_ego': True, 'state': 'red_alone', 'frame': 1},
        'destination_signal': {'device_id': 'b', 'source': 'Native light state', 'facing_ego': False, 'state': 'yellow', 'frame': 3},
        'destination_street_id': 'cross', 'destination_entry_frame': 3,
        'purpose': {'source': 'authored purpose declaration', 'value': 'avoid_red'},
    }
    return packet, trace, {'case_id': 'test'}


class PropertyRouteTests(unittest.TestCase):
    def test_segment_crosses_property_without_interior_sample(self):
        packet, trace, case = fixtures()
        result = route.analyze(packet, trace, case)
        self.assertEqual(result['traversed_property_ids'], ['lot'])
        self.assertTrue(result['all_observation_conditions_present'])
        self.assertIsNone(result['legal_judgment'])

    def test_public_property_same_geometry(self):
        packet, trace, case = fixtures()
        packet['properties'][0]['status'] = 'public'
        self.assertEqual(route.analyze(packet, trace, case)['traversed_property_statuses'], ['public'])

    def test_ordinary_intersection_route_does_not_traverse_property(self):
        packet, trace, case = fixtures()
        for sample in trace['ego']:
            sample['y'] = -2
        self.assertFalse(route.analyze(packet, trace, case)['all_observation_conditions_present'])

    def test_purpose_not_inferred_from_short_route(self):
        packet, trace, case = fixtures()
        trace['purpose']['value'] = 'unknown'
        self.assertFalse(route.analyze(packet, trace, case)['all_observation_conditions_present'])

    def test_destination_red_rejects_bypass_condition(self):
        packet, trace, case = fixtures()
        trace['destination_signal']['state'] = 'red_alone'
        self.assertFalse(route.analyze(packet, trace, case)['all_observation_conditions_present'])

    def test_approach_red_combined_rejects(self):
        packet, trace, case = fixtures()
        trace['approach_signal']['state'] = 'red_combined'
        self.assertFalse(route.analyze(packet, trace, case)['all_observation_conditions_present'])

    def test_missing_property_authority_rejects(self):
        packet, trace, case = fixtures()
        del packet['properties'][0]['authority']
        with self.assertRaisesRegex(ValueError, 'property status and authority'):
            route.analyze(packet, trace, case)

    def test_missing_signal_source_rejects(self):
        packet, trace, case = fixtures()
        del trace['approach_signal']['source']
        with self.assertRaisesRegex(ValueError, 'approach_signal'):
            route.analyze(packet, trace, case)

    def test_missing_destination_frame_join_rejects(self):
        packet, trace, case = fixtures()
        trace['destination_entry_frame'] = 4
        with self.assertRaisesRegex(ValueError, 'destination entry frame'):
            route.analyze(packet, trace, case)


if __name__ == '__main__':
    unittest.main()
