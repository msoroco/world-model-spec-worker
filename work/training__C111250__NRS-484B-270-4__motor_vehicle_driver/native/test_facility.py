import copy
import unittest
from facility import CYCLE_LANE, INTERSECTION, body_overlap, check
from runner import check as check_runner


class FacilityProof(unittest.TestCase):
    def test_continuity_and_controlled_overlap(self):
        self.assertTrue(check()['passed'])
        outside = check_runner('outside_cycle_lane', 'primary')['example_saved_body']
        within = check_runner('within_cycle_lane', 'primary')['example_saved_body']
        self.assertEqual(outside['cycle_intersection_body_overlap_m2'], 0)
        self.assertGreater(within['cycle_intersection_body_overlap_m2'], 0)
        self.assertEqual((CYCLE_LANE, INTERSECTION), ((3.5, 5.5), (-7.0, 7.0)))

    def test_changed_source_rejects(self):
        row = {'body_xy_m': [[3.6, -1], [5.4, -1], [5.4, 1], [3.6, 1]],
               'speed_mps': 4.0}
        self.assertGreater(body_overlap(row)['cycle_intersection_body_overlap_m2'], 0)
        short = copy.deepcopy(row)
        short['body_xy_m'].pop()
        with self.assertRaisesRegex(ValueError, 'corners'):
            body_overlap(short)
        with self.assertRaisesRegex(ValueError, 'case'):
            check_runner('unknown', 'primary')


if __name__ == '__main__':
    unittest.main()
