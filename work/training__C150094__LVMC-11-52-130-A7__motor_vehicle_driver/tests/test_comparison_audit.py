import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import AID, compare


def case(probe, gap, authority):
    return {'case_id': AID + '__probe_' + probe,
            'config': {'cell_id': 'C150094', 'law_id': 'LVMC-11-52-130-A7',
                       'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                       'duration_s': 30, 'frames': 600,
                       'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                       'recording_description': {'source': 'same'}},
            'context': {'case_id': AID + '__probe_' + probe,
                        'driveway_kind': 'private',
                        'owner_controller_family_invitee': authority,
                        'driveway_curb_interval_m': [50, 53]},
            'value': {'minimum_footprint_gap_m_at_rest': gap, 'rest_frame_count': 600},
            'report_sha256': 'a' * 64,
            'source_hashes': {name: 'b' * 64 for name in
                              ('road.xodr', 'overview.mkv', 'approach.mkv',
                               'reference_corner.mkv', 'driver_reference.mkv')}}


class ComparisonAuditTests(unittest.TestCase):
    def test_distance_and_authority_contrasts(self):
        far, near, invited = case('01', 2.0, False), case('02', 1.2, False), case('03', 1.2, True)
        self.assertTrue(compare(far, near, 'distance_boundary')['passed'])
        self.assertTrue(compare(near, invited, 'private_authority')['passed'])

    def test_rejects_uncontrolled_source_change(self):
        far, near = case('01', 2.0, False), case('02', 1.2, False)
        near['source_hashes']['road.xodr'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'Fixed road source differs'):
            compare(far, near, 'distance_boundary')

    def test_rejects_false_boundary_or_authority_isolation(self):
        far, near, invited = case('01', 2.0, False), case('02', 1.2, False), case('03', 1.2, True)
        wrong = copy.deepcopy(far)
        wrong['value']['minimum_footprint_gap_m_at_rest'] = 1.4
        with self.assertRaisesRegex(ValueError, 'five-foot boundary'):
            compare(wrong, near, 'distance_boundary')
        invited['context']['driveway_curb_interval_m'] = [51, 53]
        with self.assertRaisesRegex(ValueError, 'Uncontrolled driveway context'):
            compare(near, invited, 'private_authority')


if __name__ == '__main__':
    unittest.main()
