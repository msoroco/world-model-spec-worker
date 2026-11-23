import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import FIXED, compare


def packet(profile, capture, speed):
    value = {field: 'same-source' for field in FIXED}
    value['initial_speed_mps'] = 12
    value.update(profile=profile, capture_id=capture, approach_start_m=0,
                 waypoints=[{'s_m': s, 'z_m': z, 'source_ref': f'map:{s}'} for s,z in
                            ((0,0),(10,2),(20,6),(30,3),(40,0))],
                 frames=[{'frame_id':i,'time_s':i/20,'ego_s_m':s,
                          'ego_speed_mps':v,'other_s_m':40-s,
                          'body_clearance_m':40-2*s,'source_ref':f'native:{capture}:{i}'}
                         for i,(s,v) in enumerate(zip((0,5,10,15),speed))])
    return value


class ComparisonTests(unittest.TestCase):
    def test_early_vs_steady(self):
        out=compare(packet('early_decrease','a',(12,11,9,8)),
                    packet('steady_approach','b',(12,12,12,12)),
                    expected_profiles=('early_decrease','steady_approach'))
        self.assertEqual(out['capture_ids'], ['a','b'])

    def test_rejects_changed_fixed_condition(self):
        other=packet('steady_approach','b',(12,12,12,12))
        other['other_motion_source_sha256']='different'
        with self.assertRaisesRegex(ValueError, 'fixed condition'):
            compare(packet('early_decrease','a',(12,11,9,8)),other,
                    expected_profiles=('early_decrease','steady_approach'))

    def test_rejects_missing_source(self):
        other=packet('steady_approach','b',(12,12,12,12))
        del other['frames'][2]['source_ref']
        with self.assertRaisesRegex(ValueError, 'source'):
            compare(packet('early_decrease','a',(12,11,9,8)),other,
                    expected_profiles=('early_decrease','steady_approach'))

    def test_rejects_unrealized_difference(self):
        with self.assertRaisesRegex(ValueError, 'not measured'):
            compare(packet('early_decrease','a',(12,12,12,12)),
                    packet('steady_approach','b',(12,12,12,12)),
                    expected_profiles=('early_decrease','steady_approach'))


if __name__ == '__main__':
    unittest.main()
