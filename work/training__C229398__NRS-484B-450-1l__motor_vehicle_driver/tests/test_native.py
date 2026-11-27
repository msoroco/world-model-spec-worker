"""CPU tests for the authored two-vehicle geometry and common controller."""
import unittest

from controller import TARGET_X_M, check as controller_check, command
from geometry import check as geometry_check
from runner import check as runner_check


class NativeConstructionTest(unittest.TestCase):
    def test_curbside_lanes_and_overlap_station(self):
        road = geometry_check()
        self.assertEqual(road['ego_lane_id'], -1)
        self.assertEqual(road['curbside_lane_id'], -2)
        self.assertEqual(road['road_interior_normal_sign'], 1)
        self.assertLess(TARGET_X_M['park'], TARGET_X_M['clear'])

    def test_all_cases_one_policy(self):
        controller_check()
        for case in TARGET_X_M:
            self.assertEqual(command(case, 0, TARGET_X_M[case], 0)['phase'], 'hold')
            self.assertEqual(command(case, 0, -80, 0)['phase'], 'approach')

    def test_four_view_native_check(self):
        names = ('overview', 'approach', 'reference_corner', 'driver_reference')
        for case in TARGET_X_M:
            cfg = {'cell_id': 'C229398', 'law_id': 'NRS-484B-450-1l',
                   'actor': 'motor_vehicle_driver', 'case_id': 'A__' + case,
                   'rate_hz': 20, 'duration_s': 30,
                   'cameras': [{'name': name} for name in names]}
            self.assertEqual(runner_check(cfg)['frames'], 600)


if __name__ == '__main__':
    unittest.main()
