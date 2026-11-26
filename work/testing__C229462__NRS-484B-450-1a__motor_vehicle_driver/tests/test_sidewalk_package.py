"""Exact source/measurement and original-only comparison boundaries."""
import unittest

from comparison_audit import AID, PAIRS, audit_pair
from diagnostic_author import site
from sidewalk_case import CASES, measure_original


class SidewalkPackageTests(unittest.TestCase):
    def test_900_frame_source_bound_measurement_and_missing_source(self):
        item = CASES[0]
        packet = site(item)
        body = packet['target_footprints']['overlap']['polygon_xy']
        rows = []
        for i in range(900):
            rows.append({'original_frame': 100 + i, 'time_s': i / 20,
                         'source_sha256': 'test-source',
                         'body_geometry_source_sha256': 'test-body',
                         'activity_source_sha256': 'test-activity',
                         'sidewalk_source_sha256': packet['sidewalk_polygon_source_sha256'],
                         'exception_source_sha256': packet['exception_context_source_sha256'],
                         'ego_id': 'test-ego', 'vehicle_type': 'motor_vehicle',
                         'vehicle_body_polygon_xy': body, 'ego_speed_mps': 0,
                         'observed_activity': 'park',
                         'exception_context': packet['exception_context']})
        measured = measure_original(rows, packet, item)
        self.assertGreater(measured['terminal_mean_sidewalk_body_overlap_m2'], 0)
        self.assertIsNone(measured['legal_judgment'])
        rows[-1]['sidewalk_source_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'geometry source changed'):
            measure_original(rows, packet, item)

    def test_comparison_accepts_only_original_900_frame_reports(self):
        measured = {'frame_count': 900, 'terminal_mean_sidewalk_body_overlap_m2': 8,
                    'terminal_boundary_distance_m': .5,
                    'exception_context': {'traffic_conflict_necessity': 'absent'}}
        fixed = {'map': 'source'}
        def report(suffix, relation, overlap, distance, traffic='absent'):
            return {'format': 'worker-delivery-audit', 'passed': True,
                    'protocol_fixture_checked': False, 'case_id': AID + '__' + suffix,
                    'frame_count': 900, 'physical_acceptance_claimed': True,
                    'comparison_record': {'source_kind': 'original_native_capture',
                                          'fixed_source_sha256': fixed,
                                          'camera_plan': ['four'], 'duration_s': 45,
                                          'requested_relation': relation,
                                          'traffic_context': traffic,
                                          'measurement': dict(measured,
                                                              terminal_mean_sidewalk_body_overlap_m2=overlap,
                                                              terminal_boundary_distance_m=distance,
                                                              exception_context={'traffic_conflict_necessity': traffic})}}
        reports = {
            AID + '__park_on_sidewalk': report('park_on_sidewalk', 'overlap', 8, .5),
            AID + '__park_edge_touch': report('park_edge_touch', 'touch', 0, 0),
            AID + '__park_off_sidewalk': report('park_off_sidewalk', 'separate', 0, 1),
            AID + '__on_sidewalk_traffic_necessity': report('on_sidewalk_traffic_necessity', 'overlap', 8, .5, 'unresolved')}
        for name in PAIRS:
            self.assertTrue(audit_pair(name, reports)['physical_comparison_passed'])
        reports[AID + '__park_on_sidewalk']['protocol_fixture_checked'] = True
        with self.assertRaisesRegex(ValueError, 'original accepted report required'):
            audit_pair('footprint_overlap', reports)


if __name__ == '__main__':
    unittest.main()
