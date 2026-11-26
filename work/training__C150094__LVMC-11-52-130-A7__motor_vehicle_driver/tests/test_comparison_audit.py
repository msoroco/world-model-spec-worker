import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import AID, compare


def case(probe, gap, authority, driveway_kind='private'):
    return {'case_id': AID + '__probe_' + probe,
            'config': {'cell_id': 'C150094', 'law_id': 'LVMC-11-52-130-A7',
                       'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                       'duration_s': 30, 'frames': 600,
                       'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                       'recording_description': {'source': 'same'}},
            'context': {'case_id': AID + '__probe_' + probe,
                        'driveway_kind': driveway_kind,
                        'owner_controller_family_invitee': authority,
                        'private_driveway_authority_role': 'owner' if authority else 'none',
                        'usps_vehicle': False, 'usps_official_business': False,
                        'driveway_curb_interval_m': [50, 53]},
            'value': {'minimum_footprint_gap_m_at_rest': gap, 'rest_frame_count': 600,
                      'strict_front_overlap_frame_count': 600 if gap == 0 else 0,
                      'maximum_front_overlap_m': 0.5 if gap == 0 else 0.0},
            'report_sha256': 'a' * 64,
            'source_hashes': {name: 'b' * 64 for name in
                              ('road.xodr', 'overview.mkv', 'approach.mkv',
                               'reference_corner.mkv', 'driver_reference.mkv')}}


class ComparisonAuditTests(unittest.TestCase):
    def test_distance_and_authority_contrasts(self):
        far, near, invited = case('01', 2.0, False), case('02', 1.2, False), case('03', 1.2, True)
        equal = case('04', 1.524, False)
        self.assertTrue(compare(far, near, 'distance_boundary')['passed'])
        self.assertTrue(compare(near, invited, 'private_authority')['passed'])
        self.assertTrue(compare(near, equal, 'five_foot_equality_below')['passed'])
        self.assertTrue(compare(equal, far, 'five_foot_equality_above')['passed'])
        self.assertTrue(compare(case('05', 0.0, False), near, 'front_overlap')['passed'])
        self.assertTrue(compare(near, case('06', 1.2, False, 'public'),
                                'public_private_driveway')['passed'])
        controller = case('07', 1.2, True)
        controller['context']['private_driveway_authority_role'] = 'controller'
        self.assertTrue(compare(near, controller, 'private_controller')['passed'])
        for probe, role, comparison in [('08', 'family_member', 'private_family'),
                                        ('09', 'invitee', 'private_invitee')]:
            alternate = case(probe, 1.2, True)
            alternate['context']['private_driveway_authority_role'] = role
            self.assertTrue(compare(near, alternate, comparison)['passed'])
        postal = case('10', 1.2, False)
        postal['context']['usps_vehicle'] = True
        postal['context']['usps_official_business'] = True
        self.assertTrue(compare(near, postal, 'usps_official_business')['passed'])

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
        equal = case('04', 1.6, False)
        with self.assertRaisesRegex(ValueError, 'misses five feet'):
            compare(near, equal, 'five_foot_equality_below')
        invited['context']['driveway_curb_interval_m'] = [50, 53]
        invited['context']['private_driveway_authority_role'] = 'invitee'
        with self.assertRaisesRegex(ValueError, 'private owner status'):
            compare(near, invited, 'private_authority')
        touching = case('05', 0.0, False)
        touching['value']['strict_front_overlap_frame_count'] = 0
        with self.assertRaisesRegex(ValueError, 'positive interior body overlap'):
            compare(touching, near, 'front_overlap')
        false_public = case('06', 1.2, False, 'private')
        with self.assertRaisesRegex(ValueError, 'isolate driveway kind'):
            compare(near, false_public, 'public_private_driveway')
        false_controller = case('07', 1.2, True)
        with self.assertRaisesRegex(ValueError, 'specific private authority'):
            compare(near, false_controller, 'private_controller')
        for probe, comparison in [('08', 'private_family'), ('09', 'private_invitee')]:
            false_role = case(probe, 1.2, True)
            with self.assertRaisesRegex(ValueError, 'specific authority'):
                compare(near, false_role, comparison)
        false_postal = case('10', 1.2, False)
        false_postal['context']['usps_vehicle'] = True
        with self.assertRaisesRegex(ValueError, 'official-business vehicle facts'):
            compare(near, false_postal, 'usps_official_business')


if __name__ == '__main__':
    unittest.main()
