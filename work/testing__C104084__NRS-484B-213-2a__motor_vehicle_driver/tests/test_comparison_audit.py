import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'comparison_audit.py'
spec = importlib.util.spec_from_file_location('comparison_audit', MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
ASSIGNMENT = 'testing__C104084__NRS-484B-213-2a__motor_vehicle_driver'


def packet(suffix):
    return {'case_id': ASSIGNMENT + '__' + suffix, 'source_ref': 'sealed Native sample',
            'law_id': 'NRS-484B-213-2a', 'actor': 'motor_vehicle_driver',
            'map_source': 'map-A', 'camera_profile': 'four-camera', 'duration_frames': 600,
            'crest_grade_sha256': 'grade-A', 'ego_route_sha256': 'route-A',
            'other_route_sha256': 'other-A', 'other_timing_sha256': 'time-A',
            'lane_allocation': 'two_way', 'ego_left_side_observed': True,
            'sampled_grade_blocks_proxy_ray': True}


class ComparisonTests(unittest.TestCase):
    def test_left_side_pair_and_confounded_map(self):
        first = packet('right_crest_obstructed')
        first['ego_left_side_observed'] = False
        second = packet('left_crest_obstructed')
        self.assertTrue(audit_module.audit('left_side_motion', first, second, ASSIGNMENT)['passed'])
        second['map_source'] = 'map-B'
        with self.assertRaisesRegex(ValueError, 'confounded fixed condition'):
            audit_module.audit('left_side_motion', first, second, ASSIGNMENT)

    def test_obstruction_pair_and_missing_source(self):
        first = packet('left_crest_obstructed')
        second = packet('left_crest_clear')
        second['crest_grade_sha256'] = 'grade-B'
        second['sampled_grade_blocks_proxy_ray'] = False
        self.assertTrue(audit_module.audit('crest_view_obstruction', first, second, ASSIGNMENT)['passed'])
        second['source_ref'] = ''
        with self.assertRaisesRegex(ValueError, 'missing original source'):
            audit_module.audit('crest_view_obstruction', first, second, ASSIGNMENT)

    def test_one_way_exception_and_wrong_order(self):
        first = packet('left_crest_obstructed')
        second = packet('left_one_way_obstructed')
        second['lane_allocation'] = 'one_way'
        self.assertTrue(audit_module.audit('one_way_exception', first, second, ASSIGNMENT)['passed'])
        first['lane_allocation'] = 'one_way'
        with self.assertRaisesRegex(ValueError, 'missing deliberate difference'):
            audit_module.audit('one_way_exception', first, second, ASSIGNMENT)


if __name__ == '__main__':
    unittest.main()
